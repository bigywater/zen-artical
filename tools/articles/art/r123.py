import json
from lib import *
R = J('r123'); c = R['cnt']; tab = R['tab']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tl(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
users = ('ro', 'nodanger', 'appuser', 'empty')
def col(u): return [k for k, v in tab.items() if v[users.index(u)] == '允许']
steps = [
    step(f"Redis 8.10.2 一共 {R['total']} 条命令(COMMAND LIST,不含子命令),被分成 {len(c)} 个类别。@read {c['read']}、@write {c['write']}、@dangerous {c['dangerous']}、@admin {c['admin']}、@slow {c['slow']}、@fast {c['fast']}。一条命令可以同时属于多个类别。", b=bars([[f'@{k}', c[k], str(c[k])] for k in ('read', 'write', 'dangerous', 'admin', 'slow', 'fast', 'scripting', 'pubsub')], 320, done=[0, 1], mark=[2]), kv=KV([['命令总数', R['total']], ['类别数', len(c)]], ['命令总数'])),
    step(f"ro = -@all +@read:允许 {', '.join(col('ro'))};其余(包括 PING、INFO)都拒绝——@read 里没有 PING 和 INFO。", t=tl([f"{k:<20} {v[0]}" for k, v in tab.items()][:8], mark=[]), kv=KV([['ro 允许的命令', str(len(col('ro'))) + ' 条(样本 19 条里)']], ['ro 允许的命令'])),
    step(f"nodanger = +@all -@dangerous:KEYS、CONFIG、FLUSHALL、SHUTDOWN 等被拒;GET/SET/DEL/SCAN/PING/EVAL 都放行。样本 19 条里它允许 {len(col('nodanger'))} 条。INFO、CLIENT LIST 也被拒(它们在 @dangerous 里);SUBSCRIBE、PUBLISH 被拒是因为没给频道权限,不是分类的问题。", kv=KV([['nodanger 允许', ', '.join(x.split()[0] for x in col('nodanger'))]], ['nodanger 允许'])),
    step(f"顺序很重要:+@all -@dangerous 先开后关,FLUSHALL 被拒({R['o1'][:40]}…);-@dangerous +@all 先关后开,FLUSHALL → {R['o2']}。Redis 把规则按写入顺序依次应用。", n=fl([['+@all -@dangerous', 'FLUSHALL 拒绝'], ['-@dangerous +@all', 'FLUSHALL 允许']], mark=[0], done=[1]), kv=KV([['o1', '+@all -@dangerous → 拒绝'], ['o2', '-@dangerous +@all → ' + R['o2']]], ['o2'])),
    step(f"子命令粒度:+config|get 只允许 CONFIG GET;CONFIG SET → {R['sub_set'].replace('(error) ', '')[:80]}。", n=fl([['CONFIG GET maxmemory', '允许'], ['CONFIG SET / REWRITE', 'NOPERM']], done=[0], mark=[1]), kv=KV([['子命令规则', '+config|get']], ['子命令规则'])),
    step("选择器:(~reports:* +get) 让同一个用户在 reports:* 上只能 GET,在 cache:* 上能做除 @dangerous 外的一切。DRYRUN 结果:SET cache:1 OK、GET reports:1 OK、SET reports:1 拒绝、GET other:1 拒绝。", n=fl([['SET cache:1', '允许'], ['GET reports:1', '允许'], ['SET reports:1', '拒绝'], ['GET other:1', '拒绝']], done=[0, 1], mark=[2, 3]), kv=KV([['规则', '~cache:* +@all -@dangerous (~reports:* +get)']], ['规则'])),
]
A = dict(
    n=123, series='redis', tags='Redis,ACL,安全,真实验证,动画演示',
    desc=f'ACL Category 实测:8.10.2 共 {R["total"]} 条命令、{len(c)} 个类别(@dangerous {c["dangerous"]} 条);ro / nodanger / appuser 三种常见配置对 19 条命令的逐条判定表;规则顺序会改变结果;子命令和选择器的粒度。',
    lead='给每条命令写一遍 +get +set 太累,ACL 提供了命令分类:+@read、-@dangerous。这篇把每个分类里到底有多少命令、几种常见配置对常用命令的放行/拒绝表、规则顺序造成的差别都实测出来,用 ACL DRYRUN 让服务端自己回答,不用真连。',
    facts=[(f'{R["total"]} / {len(c)}', '命令总数 / 类别数(8.10.2,COMMAND LIST 与 ACL CAT)'), (f'@dangerous {c["dangerous"]}', '危险命令的数量,INFO、CLIENT LIST、MONITOR、DEBUG 都在里面'), ('顺序', '+@all -@dangerous 与 -@dangerous +@all 结果相反')],
    body=[
        sec('分类与数量', '', term('', blk('r123', 1)), '<p>分类不是互斥的:一条命令可以同时是 <code>@write</code>、<code>@slow</code>、<code>@dangerous</code>。上面的数字是 8.10.2 的,别的版本不同(本文没有验证)。</p>'),
        sec('几种常见配置的判定表', '', term('', blk('r123', 2)), '<p><code>ACL DRYRUN 用户 命令…</code> 让服务端按该用户的规则判定,不执行命令。看表要注意几件事:</p><ul><li><code>ro</code>(<code>-@all +@read</code>)不能 <code>PING</code>、<code>INFO</code>——它们不属于 <code>@read</code>,给只读账号别忘了单独放行 <code>+ping</code> 和需要的 <code>+info</code>。</li><li><code>nodanger</code>(<code>+@all -@dangerous</code>)能 <code>EVAL</code>(脚本可以做很多事,对它的边界见第 130 篇),但 <code>INFO</code>、<code>CLIENT LIST</code>、<code>MONITOR</code>、<code>DEBUG</code> 都在 <code>@dangerous</code> 里,被一并拦下——监控账号要单独给 <code>+info</code>。<code>SUBSCRIBE</code>、<code>PUBLISH</code> 被拒则是另一回事:没有频道权限(见第 124 篇),加上 <code>&amp;*</code> 就放行了(见第六节)。</li><li>新用户什么都不给(<code>empty</code>)就是全拒。</li></ul>'),
        sec('规则顺序', '', term('', blk('r123', 3)), '<p>两条规则同一组、顺序相反,FLUSHALL 一个被拒一个放行。ACL LIST 输出的规则也保留了顺序。写 ACL 时把「先给大范围、再收窄」作为习惯,并且写完用 <code>ACL DRYRUN</code> 验一遍。</p>'),
        sec('子命令与选择器', '', term('', blk('r123', 4)), term('', blk('r123', 5)), '<p><code>+config|get</code> 只放行 <code>CONFIG GET</code>。选择器 <code>(~reports:* +get)</code> 是一组独立的「key + 命令」权限,和根权限是「或」的关系:命中任一组就放行。</p>'),
        sec('两个容易误会的地方', '', term('', blk('r123', 6)), '<p>拦掉 INFO 的是 <code>@dangerous</code>,拦掉 SUBSCRIBE / PUBLISH 的是频道权限。搭配 <code>+@all -@dangerous</code> 时这两类都要考虑。</p>'),
        sec('分步演示:同一批命令,不同配置', '', demo('ACL Category', [('b', 'bars', '每类命令数'), ('t', 'term', '判定表'), ('n', 'flow', '规则效果'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。判定全部来自 ACL DRYRUN', '没有验证:其它版本的分类内容、自定义模块命令的分类、+@all 之后新增命令的行为、ACL DRYRUN 与真实连接执行结果的逐条一致性(这里只用 DRYRUN;第 122 篇里有少量真实连接的对照)'],
)
