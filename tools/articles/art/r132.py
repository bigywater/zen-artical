import json
from lib import *
R = J('r132'); A_ = R['A']; B_ = R['B']; ks = [k for k in R['keys']]; ar = R['aclfile_requirepass']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def tl(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
def tab(keys): return [f"{k.strip():<40} {A_[k]:>6} → {B_[k]:>6}" for k in keys]
data_keys = ['redis.conf(CONFIG REWRITE 之后)', 'dump.rdb', 'BGSAVE 进行中的 temp-*.rdb', '  appendonlydir/appendonly.aof.N.base.rdb', '  appendonlydir/appendonly.aof.N.incr.aof', '  appendonlydir/appendonly.aof.manifest', 'users.acl(ACL SAVE)', 'nodes.conf', 'redis.log']
steps = [
    step(f"Redis 自己创建的文件,权限完全跟着进程的 umask 走。umask 022(常见默认):dump.rdb、AOF 各文件、manifest、users.acl、nodes.conf、redis.log 都是 {A_['dump.rdb']}(同机其它用户可读);umask 077:全部是 {B_['dump.rdb']}。", t=tl(['文件(umask 022 → umask 077)'] + tab(data_keys), cur=[2, 3, 4, 5, 6], mark=[7, 8, 9]), kv=KV([['umask 022', A_['dump.rdb']], ['umask 077', B_['dump.rdb']]], ['umask 022'])),
    step(f"BGSAVE 进行中的临时文件 temp-*.rdb 也是同样的权限({A_['BGSAVE 进行中的 temp-*.rdb']} → {B_['BGSAVE 进行中的 temp-*.rdb']}),不存在「先 0644 再改」的窗口(至少这次轮询到的是这个值)。CONFIG REWRITE 之后的 redis.conf 权限是 {A_['redis.conf(CONFIG REWRITE 之后)']} → {B_['redis.conf(CONFIG REWRITE 之后)']}(重写后的文件也跟着 umask)。", t=tl(tab(['BGSAVE 进行中的 temp-*.rdb', 'redis.conf(CONFIG REWRITE 之后)'])), kv=KV([['temp-*.rdb', f"{A_['BGSAVE 进行中的 temp-*.rdb']} → {B_['BGSAVE 进行中的 temp-*.rdb']}"]], ['temp-*.rdb'])),
    step(f"目录:appendonlydir/ 是 Redis 创建的,权限 {A_['appendonlydir/']} → {B_['appendonlydir/']};但 dir 指向的数据目录本身是我自己创建的({A_['数据目录']} 不变)——Redis 不会替你收紧数据目录,要自己 chmod。", t=tl(tab(['数据目录', 'appendonlydir/'])), kv=KV([['数据目录', '需要自己收紧'], ['appendonlydir/', 'Redis 创建,跟 umask']], ['数据目录'])),
    step(f"Unix 套接字文件:没设 unixsocketperm 时权限是 {R['sock'][0]}(跟 umask),设 unixsocketperm 700 后是 {R['sock'][1]}。", n=fl([['未设 unixsocketperm', R['sock'][0]], ['unixsocketperm 700', R['sock'][1]]], mark=[0], done=[1]), kv=KV([['套接字', f"{R['sock'][0]} → {R['sock'][1]}"]], ['套接字'])),
    step(f"配置文件里的凭据:CONFIG REWRITE 之后 redis.conf 里 masterauth 仍是明文(带引号);users.acl 里只有密码哈希,没有明文。所以 redis.conf 的权限比数据文件更该收紧。", n=fl([['redis.conf', '含明文的 masterauth 密码'], ['users.acl', '只有 #哈希']], mark=[0], done=[1]), kv=KV([['redis.conf', '明文密码'], ['users.acl', '哈希']], ['redis.conf'])),
    step(f"附带发现(和权限无关但很危险):aclfile 指向一个没有 default 用户行的文件,同时 redis.conf 里写了 requirepass——不带密码 PING → {ar['ping']},ACL LIST 里 default 仍是 nopass;把 requirepass 写到 aclfile 之前也一样({ar['ping_reordered']})。启动日志里没有相关警告。启用 aclfile 后,default 用户的密码要写进 aclfile。", n=fl([['aclfile(无 default 行)', ''], ['requirepass 写在 redis.conf', '被忽略'], ['不带密码 PING', ar['ping']]], mark=[1, 2]), kv=KV([['aclfile + requirepass', 'requirepass 不生效(本次实测)']], ['aclfile + requirepass'])),
]
A = dict(
    n=132, series='redis', tags='Redis,安全,文件权限,RDB,AOF,真实验证,动画演示',
    desc='Redis 创建的 RDB / AOF / manifest / ACL 文件 / nodes.conf / 日志 / 临时 RDB 的权限完全跟随 umask:022 下是 0644、077 下是 0600;数据目录要自己收紧;unixsocketperm 决定套接字权限;redis.conf 里的密码是明文。另:aclfile + requirepass 时 requirepass 不生效。',
    lead='备份泄露常常不是网络攻击,而是文件权限:RDB 和 AOF 里就是你的全部数据。Redis 自己创建这些文件时用什么权限?要怎么收紧?这篇用两种 umask 各启动一个实例,把每个文件的实际权限列出来。',
    facts=[(f'{A_["dump.rdb"]} → {B_["dump.rdb"]}', 'dump.rdb 的权限:umask 022 → umask 077(其它数据文件同样跟随 umask)'), ('数据目录', '数据目录本身要自己收紧;Redis 只对它创建的 appendonlydir/ 应用 umask'), ('aclfile 吞掉 requirepass', 'aclfile(无 default 行)+ requirepass:requirepass 不生效,不带密码就能 PING(本次实测)')],
    body=[
        sec('各文件的权限', '', term('', blk('r132', 1)), '<p>表里左边是 <code>umask 022</code>,右边是 <code>umask 077</code>。同一套配置:集群模式、AOF 打开、<code>aclfile</code>、Unix 套接字、<code>CONFIG REWRITE</code>、<code>BGSAVE</code>(用 <code>rdb-key-save-delay</code> 放慢以便抓到临时文件)。所有由 Redis 创建的文件都随进程 umask 走,没有单独的「收紧」。</p>'),
        sec('套接字权限', '', term('', blk('r132', 2)), '<p><code>unixsocketperm</code> 显式指定套接字文件的权限。</p>'),
        sec('配置里的凭据', '', term('', blk('r132', 3)), '<p><code>redis.conf</code> 里的 <code>masterauth</code>(以及 <code>requirepass</code>)是明文;ACL 文件里只有 SHA-256 哈希(第 122 篇)。</p>'),
        sec('附带发现:aclfile 会让 requirepass 失效', '', term('', blk('r132', 4)), '<p>这是本文实验里意外看到的。仅限这里测过的情形:aclfile 存在但里面没有 default 用户行。文件里写了 default 用户的密码时是否正常(应当由 aclfile 决定)本文没有验证。</p>'),
        sec('收紧的做法', '', '<ul><li>用 <code>umask 077</code> 启动 Redis 进程(用哪种方式设置取决于你的启动方式:shell、启动脚本或服务管理器,本文只在命令行下用 <code>preexec_fn</code> 设置过 umask)。</li><li>把数据目录 <code>chmod 700</code>。</li><li>给 <code>redis.conf</code>、<code>users.acl</code> 设 <code>600</code>,并限定属主。</li><li>套接字用 <code>unixsocketperm</code> 显式指定。</li><li>备份文件的权限与加密见第 133 篇。</li></ul>'),
        sec('分步演示:同一批文件,两种 umask', '', demo('RDB/AOF 文件权限', [('t', 'term', '权限对比'), ('n', 'flow', '要点'), ('kv', 'kv', '结论')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。umask 通过 subprocess 的 preexec_fn 设置;文件权限用 os.stat 读取', '没有验证:Linux 上的行为(macOS 与 Linux 的默认 umask 和创建规则可能不同)、systemd 的 UMask= / 服务单元、Docker 卷的属主与权限、SELinux / ACL 扩展权限、fsync 与权限的关系、备份工具(cp / rsync / tar)对权限的保留、aclfile 中带 default 用户行时的行为'],
)
