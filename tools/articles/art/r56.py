import json
from lib import *
R = J('r56')
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
steps = [
    step("默认 replica-read-only = yes。从库能 GET(读到 a=1),但 SET、DEL、EXPIRE、INCR、FLUSHALL 都报 READONLY You can't write against a read only replica;EVAL 里调用写命令同样被拦。", d=cells(['主 a=1', '从 a=1'], done=[0, 1]), kv=KV([['写命令', 'READONLY 错误'], ['EVAL_RO / GET / PUBLISH', '允许']], ['写命令'])),
    step("PUBLISH 在只读从库上也能执行(返回 0,该从库上没有订阅者);EVAL_RO 里只读调用照常返回。只读限制针对的是写命令。", d=cells(['PUBLISH → 0', 'EVAL_RO GET a → "1"'], done=[0, 1]), kv=KV([['只读从库允许', 'PUBLISH、EVAL_RO']], ['只读从库允许'])),
    step("CONFIG SET replica-read-only no:从库现在可以写。写 local=only-on-replica、把 a 改成 changed-on-replica:主库看不到这两处改动(主库 a 仍是 1,没有 local)。数据在两边分叉了。", d=cells(['主 a=1', '从 a=changed', '从 local=only'], mark=[1, 2]), kv=KV([['主库 GET a', '1'], ['从库 GET a', 'changed-on-replica']], ['从库 GET a'])),
    step("主库再写 a=from-master:从库上被覆盖成 from-master;但 local 只存在于从库、主库从没写过,它一直留着。dbsize 主 1 / 从 2。", d=cells(['主 a=from-master', '从 a=from-master', '从 local=only'], done=[0, 1], mark=[2]), kv=KV([['dbsize 主/从', '1 / 2']], ['dbsize 主/从'])),
    step("在可写从库上写带 TTL 的 key(PX 300):600 ms 后从库自己就查不到了——本地写入的 key,从库自己负责过期。", d=cells(['ttl_local PX 300 → 600 ms 后 nil'], done=[0]), kv=KV([['600 ms 后 GET', 'nil']], ['600 ms 后 GET'])),
    step("网络中断期间主库写了约 100 KB(超过 backlog),恢复后触发全量同步(sync_full +1):从库被整体替换,local 消失,dbsize 主/从都是 1001。", d=cells(['主 1001 个 key', '从 1001 个 key(local 已消失)'], done=[0, 1], mark=[1]), kv=KV([['sync_full', '+1'], ['从库 GET local', 'nil']], ['从库 GET local'])),
    step("如果断线期间只写了一点,恢复后是部分重同步(partial_ok +1):从库本地写的 local2 仍然在(主库没有)。只读限制是防止这种分叉的唯一手段。", d=cells(['从 local2=v(仍在)', '主 local2=nil'], mark=[0]), kv=KV([['sync_partial_ok', '+1'], ['从库 GET local2', 'v']], ['从库 GET local2'])),
]
A = dict(
    n=56, series='redis', tags='Redis,复制,只读从库,真实验证,动画演示',
    desc='在本机主从上验证从库只读限制:默认 replica-read-only yes 时 SET/DEL/EXPIRE/INCR/FLUSHALL 与 EVAL 里的写命令都报 READONLY,PUBLISH 和 EVAL_RO 允许;改成 no 后本地写入不会同步给主库、数据分叉;全量重同步会清掉从库本地写入,部分重同步则不会;可写从库上带 TTL 的 key 由从库自己过期。',
    lead='从库默认是只读的。这条限制看起来只是「防止误写」,但关掉它之后会发生什么,很少有人真的试过。这篇把它试了一遍:哪些命令被拦、放开之后数据怎么分叉、重同步时本地写入会不会被保留。',
    facts=[('READONLY', '默认从库对所有写命令的错误(包括 EVAL 里的写)'), ('分叉', '可写从库上的写入不会到主库,主从各有各的数据'), ('全量 vs 部分', '全量重同步清掉本地写入;部分重同步保留')],
    body=[
        sec('默认:哪些命令被拦', '', term('', blk('r56', 1)), '<p><code>replica-read-only</code> 默认是 yes。<code>SET / DEL / EXPIRE / INCR / FLUSHALL</code> 全部报 <code>READONLY You can\'t write against a read only replica</code>;<code>EVAL</code> 脚本里调用写命令同样被拒;<code>PUBLISH</code> 和只读的 <code>EVAL_RO</code> 可以执行(PUBLISH 返回 0 是因为这个从库上没有订阅者)。</p>'),
        sec('关掉之后:分叉', '', term('', blk('r56', 2)), '<p>把 <code>replica-read-only</code> 改成 no 之后,从库上的写入成功,但主库看不到——主库的 <code>a</code> 还是 1,也没有 <code>local</code>。这不是「双向同步」,只是两边各有各的数据。</p>', term('', blk('r56', 3)), '<p>主库之后再写同一个 key <code>a</code>,从库上本地的修改被覆盖;而 <code>local</code> 只在从库上,主库从来没有写过,复制流不会去碰它,所以一直留着,dbsize 变成 主 1 / 从 2。</p>'),
        sec('可写从库上的 TTL', '', term('', blk('r56', 4)), '<p>在可写从库上写带过期时间的 key:600 ms 后 <code>GET</code> 返回 nil。本地写入的 key,是从库自己按 TTL 过期的(我没有在这里对比只读从库上主库同步过来的 key 的过期行为,那部分见第 28 篇)。</p>'),
        sec('重同步会怎样', '', term('', blk('r56', 5)), '<p>用一个可断开的 TCP 转发制造断线。断线期间主库写了约 100 KB、超过 backlog(16 KB),恢复后全量同步,从库的 <code>local</code> 被清掉,dbsize 主从一致(1001)。</p>', term('', blk('r56', 6)), '<p>如果断线期间只写了一点,恢复后是部分重同步,从库的 <code>local2</code> 还在,主库却没有。<b>所以:本地写入是否被保留,取决于这次重同步是全量还是部分——不可预测。</b>这也是默认只读、不建议放开的原因。</p>'),
        sec('分步演示:从库只读与数据分叉', '', demo('从库只读限制', [('d', 'cells', '主库 / 从库的数据'), ('kv', 'kv', '观察')], steps, '本步涉及的数据')),
    ],
    refs=[ENV_R + '。主从之间放了一个可断开的 TCP 转发用来制造断线', '没有验证:可写从库配合 Sentinel / Cluster 的行为、多层级联复制下的本地写入、被拦的写命令是否有遗漏(只测了几个常见命令)'],
)
