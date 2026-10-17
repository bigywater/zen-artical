import json
from lib import *
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("三个 key:key0(槽 13252,节点 7372)、key4(槽 13120,也在节点 7372,但槽不同)、key1(槽 9189,节点 7371)。", t=tm(['key0 → 槽 13252 @7372', 'key4 → 槽 13120 @7372', 'key1 → 槽  9189 @7371'], cur=[0, 1, 2]), kv=KV([['关键', 'key0 与 key4 同节点、不同槽']], ['关键'])),
    step("MSET key0 1 key4 2:发给两个 key 都在的节点 7372,仍然是 CROSSSLOT Keys in request don't hash to the same slot。判据是「槽」,不是「节点」。同样的错误也出现在 DEL、MGET、RENAME、SUNION、SINTERSTORE。", t=tm(['> MSET key0 1 key4 2', "(error) CROSSSLOT Keys in request don't hash to the same slot", '> DEL / MGET / RENAME / SUNION key0 key4', '(error) CROSSSLOT …'], mark=[1, 3]), kv=KV([['判据', '槽位是否相同']], ['判据'])),
    step("用 hash tag 就对了:MSET {t}1 1 {t}2 2 → OK,MGET 返回 1、2。同一个 key 在 SUNION key0 key0 里出现两次也没问题(还是同一个槽)。", t=tm(['> MSET {t}1 1 {t}2 2', '"OK"', '> MGET {t}1 {t}2', '1) "1"  2) "2"', '> SUNION key0 key0', '1) "1"'], cur=[1, 3, 5]), kv=KV([['结论', '同槽即可,同一个 key 重复出现不算跨槽']], ['结论'])),
    step("事务:MULTI 后 SET key0、SET key4 都回 QUEUED,EXEC 时整体拒绝:CROSSSLOT。换成 {t}a、{t}b(同一个槽)EXEC 成功,返回 OK、OK。", t=tm(['> MULTI; SET key0 1; SET key4 2', 'QUEUED, QUEUED', '> EXEC', '(error) CROSSSLOT …', '> MULTI; SET {t}a 1; SET {t}b 2; EXEC', '1) "OK"  2) "OK"'], mark=[3], cur=[5]), kv=KV([['事务', '所有 key 必须同槽,否则整个 EXEC 被拒']], ['事务'])),
    step("Lua 脚本:KEYS 里声明的两个 key 不同槽 → CROSSSLOT;声明同槽({t}x、{t}y)→ 成功。", t=tm(['> EVAL … 2 key0 key4', '(error) CROSSSLOT …', '> EVAL … 2 {t}x {t}y', '"ok"'], mark=[1], cur=[3]), kv=KV([['KEYS 声明', '必须同槽']], ['KEYS 声明'])),
    step("但脚本里通过 ARGV 传入、没在 KEYS 里声明的 key:如果它在别的节点 → 报「Script attempted to access a non local key」;如果和声明的 key 在同一个节点、只是不同槽 → 竟然执行成功(SET key4 返回 OK)。集群只拦「不在本节点」的,不拦「不在同一个槽」——绕过声明的写法在槽迁移时不安全。", t=tm(["> EVAL \"SET KEYS[1]; SET 'undeclared'\" 1 key0", '(error) ERR Script attempted to access a non local key …', '> EVAL "DEL KEYS[1]; SET ARGV[1] 2" 1 key0 key4', '"OK"(key4 与 key0 同节点、不同槽)'], mark=[1], cur=[3]), kv=KV([['不同节点', '报错'], ['同节点不同槽', '通过(风险)']], ['同节点不同槽'])),
    step("流水线里的多条单 key 命令(SET key0、GET key0、INCR key0)完全没有问题:每条命令只涉及一个槽。分属不同节点的 key 发 MSET 同样是 CROSSSLOT。", t=tm(["pipeline: SET / GET / INCR key0 → OK, '1', 2", '> MSET key0 1 key1 2', '(error) CROSSSLOT …'], cur=[0], mark=[2]), kv=KV([['规律', '限制的是「一条命令里的 key」']], ['规律'])),
]
A = dict(
    n=73, series='redis', tags='Redis,Cluster,CROSSSLOT,真实验证,动画演示',
    desc='实测 Redis Cluster 的 CROSSSLOT:多 key 命令(MSET、DEL、MGET、RENAME、SUNION、SINTERSTORE、MULTI/EXEC、EVAL)只要 key 不同槽就报错——哪怕两个 key 在同一个节点上;hash tag 让它们同槽后全部成功;Lua 里用 ARGV 绕过 KEYS 声明时,同节点不同槽的 key 竟然执行成功,只有非本节点的 key 才被拦。',
    lead='CROSSSLOT 是从单机迁到 Redis Cluster 时最常见的报错之一。很多人以为它的意思是「这两个 key 不在同一个节点」,其实不是。这篇用一个 3 主集群,找一对「同节点、不同槽」的 key 来证明这一点,再看哪些命令会触发它、事务和 Lua 怎么处理,以及一个容易被忽略的 Lua 漏洞。',
    facts=[('判据 = 槽', '同一个节点上的两个 key,只要槽不同,多 key 命令仍然 CROSSSLOT'), ('EXEC 整体拒绝', 'MULTI 里的 key 跨槽时,EXEC 报 CROSSSLOT,不会部分执行'), ('同节点通过', 'Lua 里用 ARGV 传、没在 KEYS 里声明的 key,只要在本节点就不被拦(即使不同槽)')],
    body=[
        sec('CROSSSLOT 不是「跨节点」', '', term('', blk('r73', 1)), '<p>选了 <code>key0</code>(槽 13252)和 <code>key4</code>(槽 13120):它们都在节点 7372 上,槽不同。直接发给 7372 的 <code>MSET key0 1 key4 2</code> 仍然报 <code>CROSSSLOT Keys in request don\'t hash to the same slot</code>。改成 hash tag <code>{t}1</code>、<code>{t}2</code> 就成功。原因不深:槽是集群迁移和路由的最小单位,服务器只保证「同一个槽的 key 会一起搬」。</p>'),
        sec('触发 CROSSSLOT 的命令', '', term('', blk('r73', 2)), '<p>所有「一条命令里涉及多个 key」的命令都要求它们同槽:<code>DEL</code>、<code>MGET</code>、<code>RENAME</code>、<code>SUNION</code>、<code>SINTERSTORE</code>……(<code>SADD key0 1</code> 只有一个 key,当然没问题。)</p>', term('', blk('r73', 3)), '<p>同一个 key 在一条命令里出现多次不算跨槽;单个 key 的命令(<code>SCARD key0</code>)当然也不会。</p>'),
        sec('事务:EXEC 整体拒绝', '', term('', blk('r73', 4)), '<p><code>MULTI</code> 之后的两条 <code>SET</code> 都返回 <code>QUEUED</code>,<code>EXEC</code> 时因为两个 key 不同槽整体被拒:<code>CROSSSLOT</code>,一条都没有执行。改成同槽的 <code>{t}a</code>、<code>{t}b</code> 之后正常提交。</p>'),
        sec('Lua 脚本:KEYS 声明与绕过', '', term('', blk('r73', 5)), '<p>KEYS 里声明两个不同槽的 key → <code>CROSSSLOT</code>;声明同槽的 → 成功。<b>更需要小心的是没有声明的 key</b>:在脚本里直接写字符串或通过 ARGV 传入的 key,如果它属于别的节点,服务器报 <code>Script attempted to access a non local key in a cluster node</code>;<b>但如果它和声明的 key 在同一个节点、只是槽不同(如 key4),脚本竟然执行成功</b>。服务器只检查「是否在本节点」,不检查「是否同槽」。这样写的脚本在单个节点上能跑,但如果这个槽被迁移走,脚本会突然失败——所以脚本要访问的所有 key 都应该老老实实声明在 KEYS 里、并且同槽。</p>'),
        sec('流水线与跨节点', '', term('', blk('r73', 6)), '<p>流水线里的多条单 key 命令没有限制——每条命令只涉及一个槽。</p>', term('', blk('r73', 7)), '<p>分属不同节点的两个 key 发 <code>MSET</code> 同样是 <code>CROSSSLOT</code>(而不是 MOVED)。</p>'),
        sec('分步演示:CROSSSLOT 的边界', '', demo('Redis Cluster 的 CROSSSLOT', [('t', 'term', '请求与回复'), ('kv', 'kv', '要点')], steps, '本步的请求')),
    ],
    refs=[ENV_R + '。3 主 3 从;key0 / key4 / key1 是我从 key0…key199 里挑出的满足条件的样例', '没有验证:集群外的 Redis(单机)上同样命令的行为(单机没有槽的概念)、Redis 8 关于跨槽命令的新配置(如果有,本文没有涉及)、Lua 绕过声明的行为在迁移中槽上的具体表现(只在稳定集群测了)'],
)
