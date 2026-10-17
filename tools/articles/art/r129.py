import json
from lib import *
R = J('r129'); rows = R['rows']; L = R['labels']; d = R['defaults']; il = R['info_leak']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def tl(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
A_, B_, C_, D_, E_ = (rows[l] for l in L)
def col(r, keys): return [f"{k:<34} {r[k]}" for k in keys]
K = ['PING', 'INFO server', 'GET session:1', 'CONFIG GET dir', 'CONFIG SET dir(改到我自己的临时目录)', 'KEYS *']
steps = [
    step(f"配置 A:全默认、bind 0.0.0.0、protected-mode no、没有密码。站在局域网上一个没有任何凭据的客户端:PING → PONG,INFO server 能读,GET session:1 读到数据,CONFIG GET dir 能读,KEYS * 能列出全部 key。", t=tl(col(A_, K), mark=[0, 1, 2, 3, 5]), kv=KV([['结论', '没有密码 = 任何能连上的人都能读全部数据']], ['结论'])),
    step(f"但 CONFIG SET dir 被拒:{R['setdir_err']['A'].replace('ERR ', '')}。出厂 enable-protected-configs = {d['enable-protected-configs']}。DEBUG 也被拒(enable-debug-command = {d['enable-debug-command']},MODULE 命令同理 = {d['enable-module-command']})。这三个开关的默认值都是收紧的。", t=tl([f"CONFIG SET dir → {A_['CONFIG SET dir(改到我自己的临时目录)']}", f"DEBUG SLEEP 0 → {A_['DEBUG SLEEP 0']}", f"enable-protected-configs = {d['enable-protected-configs']}", f"enable-debug-command = {d['enable-debug-command']}", f"enable-module-command = {d['enable-module-command']}"], cur=[2, 3, 4]), kv=KV([['默认', '受保护配置 / DEBUG / MODULE 都关']], ['默认'])),
    step(f"配置 B:把 enable-protected-configs 改成 yes——陌生客户端的 CONFIG SET dir → {B_['CONFIG SET dir(改到我自己的临时目录)']},dir 真的被改了({B_['  dir 真的被改了吗']})。(这里改到的是我自己的临时目录,随后已改回。)这个开关是放大器:数据目录、文件名一类的配置一旦能被远程改,就把「读数据」升级成了「往磁盘写东西」。", t=tl(col(B_, ['CONFIG SET dir(改到我自己的临时目录)', '  dir 真的被改了吗'])), n=fl([['enable-protected-configs yes', '远程可改 dir']], mark=[0]), kv=KV([['B', '不要设成 yes']], ['B'])),
    step(f"配置 C:enable-protected-configs = local——来自局域网的 CONFIG SET dir → {C_['CONFIG SET dir(改到我自己的临时目录)']}(被拒),只有本地连接才能改。远程管理员用别的办法,而不是打开这个开关。", t=tl(col(C_, ['CONFIG SET dir(改到我自己的临时目录)', '  dir 真的被改了吗'])), kv=KV([['C', 'local:远程被拒']], ['C'])),
    step(f"配置 D:default 用户 -@dangerous。陌生客户端:INFO、CONFIG GET、KEYS、MODULE LIST 都是 {D_['INFO server']};但 PING → {D_['PING']},GET session:1 → {D_['GET session:1']}——ACL 收紧了命令,没有收紧数据:命令没被拦的读操作照样能读。要保护数据得限制 key 模式(~pattern)或者直接要求密码。", t=tl(col(D_, K), mark=[1, 3, 5], cur=[0, 2]), kv=KV([['D', '命令被限制,GET 仍能读数据']], ['D'])),
    step(f"配置 E:requirepass。同一批检查,PING / INFO / GET / CONFIG / KEYS 全部 {E_['PING']}。这是最简单、也最有效的一层。", t=tl(col(E_, K), mark=list(range(6))), kv=KV([['E', '全部 NOAUTH']], ['E'])),
    step(f"被审计的一方能看到什么:管理员的 CLIENT LIST 里有 {R['client_list_example'][:30]}…(陌生客户端保持着连接时);INFO server 对未登录客户端泄露:版本 {il['redis_version']}、操作系统 {il['os']}、进程号、run_id、可执行文件路径、配置文件路径。", n=fl([['CLIENT LIST', 'addr = 来源地址'], ['INFO server', '版本 / OS / 路径']], done=[0], mark=[1]), kv=KV([['泄露字段', 'redis_version os process_id run_id executable config_file']], ['泄露字段'])),
]
A = dict(
    n=129, series='redis', tags='Redis,安全,未授权访问,自查,真实验证,动画演示',
    desc='站在局域网上的一个陌生客户端的位置,对自己的 Redis 做自查:裸奔时能读全部数据、INFO 泄露版本与路径;enable-protected-configs 默认拒绝远程改 dir,设成 yes 就被改动;default -@dangerous 拦命令不拦数据;requirepass 一层全拦。全部在本机实例上,只改到自己的临时目录。',
    lead='「Redis 未授权访问」这个词被说了很多年。这篇不讲怎么打,只讲怎么自查:站在局域网上一个没有任何凭据的客户端的位置,对自己的实例问一组固定的问题,看每种配置下能得到什么。五种配置,每一种都是本机的临时实例,没有碰任何别人的东西。',
    facts=[('全默认', f'没密码时:陌生客户端能读全部数据、INFO 泄露版本和文件路径;但 CONFIG SET dir 与 DEBUG 默认被拒'), ('yes', '把 enable-protected-configs 设成 yes,陌生客户端就能远程改 dir(本次改到自己的临时目录后已恢复)'), ('-@dangerous ≠ 保护数据', 'default 用户 -@dangerous 后 INFO / KEYS 被拒,但 GET 读数据照样可以')],
    body=[
        sec('自查:五种配置对同一批问题的回答', '', term('', blk('r129', 1)), '<p>方法:另起一条来自局域网地址(不是回环)的连接,不带任何凭据,依次问:能 PING 吗?能读 INFO 吗?能读数据吗?能读 / 改 <code>dir</code> 吗?能 <code>DEBUG</code> 吗?再让管理员用 <code>ACL DRYRUN default</code> 判定 default 用户对几条危险命令的权限。改 <code>dir</code> 时改到的是我自己的临时目录,随后立刻改回。</p>'),
        sec('几个开关的默认值与泄露', '', term('', blk('r129', 2)), '<p>三个「危险开关」出厂都是关的:<code>enable-protected-configs no</code>、<code>enable-debug-command no</code>、<code>enable-module-command no</code>。所以没配 <code>requirepass</code> 的实例,陌生人默认也改不了 <code>dir</code>、跑不了 <code>DEBUG</code>——但依然能读走全部数据。<code>INFO server</code> 还会告诉对方版本、操作系统和文件路径,方便对方选择手段。</p>'),
        sec('该怎么办(每一条都对应上面的一个观察)', '', '<ul><li><b>先要求密码</b>(配置 E):一层挡住上面所有问题,见第 126、128 篇。</li><li><b>别把 protected-configs 设成 yes</b>(配置 B);要远程管理,用 <code>local</code>(配置 C)加别的方式。</li><li><b>ACL 限命令时想清楚数据</b>(配置 D):<code>-@dangerous</code> 挡不住 GET;需要限制 key 模式(第 122、123 篇)。</li><li><b>只 bind 需要的地址,并用防火墙</b>:本文没有测网络层防护。</li><li><b>关注连接来源</b>:<code>CLIENT LIST</code> 里的 <code>addr</code> 能看到陌生来源(第 125 篇的 ACL LOG 只记录被 ACL 拒绝的操作,不记录成功的读取)。</li></ul>'),
        sec('分步演示:五种配置', '', demo('未授权访问自查', [('t', 'term', '陌生客户端得到的回答'), ('n', 'flow', '要点'), ('kv', 'kv', '结论')], steps, '本步的对象')),
    ],
    refs=[ENV_R + f'。「陌生客户端」是本机对自己的局域网地址 {J("r128")["lan"]} 发起的连接', '没有验证:真实的另一台机器、云环境安全组、容器网络、Unix socket 场景、CONFIG SET dir 之后的其它后续操作(本文刻意没有做)、Redis 8 以前版本的默认值、MODULE LIST 返回 1 项具体是什么'],
)
