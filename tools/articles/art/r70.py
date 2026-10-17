import json
from lib import *
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
steps = [
    step("key foo 的槽位是 12182,属于主库 7342。客户端把 GET foo 发给 7340(不负责这个槽):节点不代办、不转发,只回一条 MOVED 12182 127.0.0.1:7342——告诉你这个槽现在归谁。SET foo 也一样。", n=fl([['7340', '不负责'], ['7341', ''], ['7342', '槽 12182 的主']], cur=[0], done=[2]), t=tm(['> (7340) GET foo', '(error) MOVED 12182 127.0.0.1:7342', '> (7342) GET foo', '"bar"'], cur=[1], mark=[3]), kv=KV([['MOVED', '槽 12182 → 127.0.0.1:7342']], ['MOVED'])),
    step("从库(7344)也回 MOVED——默认从库不服务读请求。先发 READONLY,这条连接上的读请求就能被从库直接处理。", n=fl([['7342 主', ''], ['7344 从', 'READONLY 之后可读']], cur=[1]), t=tm(['> (7344) GET foo', '(error) MOVED 12182 127.0.0.1:7342', '> READONLY', '"OK"', '> GET foo', '"bar"'], cur=[1], mark=[5]), kv=KV([['READONLY', '连接级开关']], ['READONLY'])),
    step("开始迁移槽 12182 到 7340:先在目标上 CLUSTER SETSLOT 12182 IMPORTING <源 ID>,再在源上 CLUSTER SETSLOT 12182 MIGRATING <目标 ID>。槽里目前有 2 个 key(foo 和 {foo}exists)。", n=fl([['源 7342', 'MIGRATING'], ['目标 7340', 'IMPORTING']], cur=[0, 1]), t=tm(['> (7340) CLUSTER SETSLOT 12182 IMPORTING <7342>', '"OK"', '> (7342) CLUSTER SETSLOT 12182 MIGRATING <7340>', '"OK"', '> CLUSTER COUNTKEYSINSLOT 12182', '(integer) 2'], cur=[0, 2]), kv=KV([['槽内 key 数', '2']], ['槽内 key 数'])),
    step("迁移中,源节点:已存在的 {foo}exists 照常服务('1');不存在的 {foo}notthere 回 ASK 12182 127.0.0.1:7340;新写入 SET {foo}newkey 也回 ASK(新 key 只能去目标)。MGET 同时要「有」和「没有」的 key → TRYAGAIN。", n=fl([['源 7342', '存在的 key:自己处理;不存在的:ASK']], cur=[0]), t=tm(['> GET {foo}exists', '"1"', '> GET {foo}notthere', '(error) ASK 12182 127.0.0.1:7340', '> SET {foo}newkey 1', '(error) ASK 12182 127.0.0.1:7340', '> MGET {foo}exists {foo}notthere', '(error) TRYAGAIN Multiple keys request during rehashing of slot'], mark=[3, 5, 7]), kv=KV([['ASK', '这一次去目标问,不更新槽位表'], ['TRYAGAIN', '稍后重试']], ['ASK'])),
    step("去目标节点 7340:直接发 GET {foo}notthere 被打回 MOVED(目标还不「拥有」这个槽);先发 ASKING,紧接着的下一条命令就会被处理((nil)),SET 也成功。ASKING 只对紧接着的那一条有效——再发 GET {foo}newkey 又是 MOVED。", n=fl([['目标 7340', 'IMPORTING:只认 ASKING 之后的一条']], cur=[0]), t=tm(['> GET {foo}notthere', '(error) MOVED 12182 127.0.0.1:7342', '> ASKING → GET {foo}notthere', '(nil)', '> ASKING → SET {foo}newkey ...', '"OK"', '> GET {foo}newkey', '(error) MOVED 12182 127.0.0.1:7342'], cur=[2, 3, 4, 5], mark=[1, 7]), kv=KV([['ASKING', '一次性']], ['ASKING'])),
    step("MIGRATE 把已存在的 key 一个个搬过去:MIGRATE 127.0.0.1 7340 {foo}exists 0 5000 → OK。搬完后源节点上这个 key 也变成 ASK;去目标 ASKING 后读到 '1'。", n=fl([['源 7342', '{foo}exists 已搬走'], ['目标 7340', '{foo}exists = 1']], done=[1], cur=[0]), t=tm(['> MIGRATE 127.0.0.1 7340 {foo}exists 0 5000', '"OK"', '> (源) GET {foo}exists', '(error) ASK 12182 127.0.0.1:7340', '> (目标) ASKING → GET {foo}exists', '"1"'], cur=[1], mark=[3]), kv=KV([['MIGRATE', '搬一个 key 并删除源端']], ['MIGRATE'])),
    step("最后把 foo 也搬过去,在两端执行 CLUSTER SETSLOT 12182 NODE <7340 的 ID> 完成迁移:之后源节点 GET foo 回 MOVED 12182 127.0.0.1:7340(永久);7340 直接返回 \"bar\"。客户端此时应更新槽位表。", n=fl([['源 7342', '不再拥有槽 12182'], ['目标 7340', '现在是槽 12182 的主']], done=[1], mark=[0]), t=tm(['> MIGRATE 127.0.0.1 7340 foo 0 5000', '"OK"', '> CLUSTER SETSLOT 12182 NODE <7340>(两端)', '"OK"', '> (源) GET foo', '(error) MOVED 12182 127.0.0.1:7340', '> (目标) GET foo', '"bar"'], cur=[2], mark=[5], ), kv=KV([['MOVED', '槽的归属已永久改变']], ['MOVED'])),
]
A = dict(
    n=70, series='redis', tags='Redis,Cluster,MOVED,ASK,真实验证,动画演示',
    desc='在本机 3 主 3 从集群上逐步复现 MOVED 与 ASK:把请求发给不负责的节点得到 MOVED(槽已永久归属别处,从库也一样,除非 READONLY);槽迁移中,源节点上不存在的 key 回 ASK(一次性),目标节点要先 ASKING 才处理,多 key 命令跨两端回 TRYAGAIN;SETSLOT NODE 完成迁移后源节点回 MOVED。',
    lead='集群客户端最先遇到的两个错误是 MOVED 和 ASK,看起来都是「去别的节点问」,含义却完全不同。一个说「这个槽归它了,永远」,一个说「这一次去它那里问,别改你的地图」。这篇不靠概念,直接用 redis-cli 一样的原始命令,在一个正在迁移槽位的真实集群上,把两者出现的每一种情形都跑出来。',
    facts=[('MOVED', '槽的归属已经(永久)改变:客户端应更新槽位表'), ('ASK', '槽正在迁移,这一条命令去目标问:不要更新槽位表,先发 ASKING'), ('TRYAGAIN', '迁移中的多 key 命令,keys 分在源和目标两边')],
    body=[
        sec('MOVED:请求发错了节点', '', term('', blk('r70', 1)), '<p>槽 12182 属于 7342。发给另一个主库 7340 的 <code>GET foo</code>、<code>SET foo x</code> 都得到 <code>MOVED 12182 127.0.0.1:7342</code>:节点不会代办转发,只指路。</p>'),
        sec('从库:READONLY', '', term('', blk('r70', 2)), '<p>从库默认也回 MOVED。在连接上发一次 <code>READONLY</code>,之后这条连接上的读命令可以被从库自己处理(我只测了读命令)。</p>'),
        sec('槽迁移的两端状态', '', term('', blk('r70', 3)), '<p>迁移一个槽分两步设置:目标节点 <code>CLUSTER SETSLOT 槽 IMPORTING 源节点ID</code>,源节点 <code>CLUSTER SETSLOT 槽 MIGRATING 目标节点ID</code>。此时槽仍然属于源节点,槽里有 2 个 key(foo 和 <code>{foo}exists</code>,后者用 hash tag 落在同一个槽,第 72 篇)。</p>'),
        sec('迁移中的源节点:ASK', '', term('', blk('r70', 4)), '<p>源节点对「自己还有的 key」照常服务(<code>GET {foo}exists</code> 得到 "1");对「自己没有的 key」——无论是读一个不存在的 key,还是新写入一个 key——回 <code>ASK 12182 127.0.0.1:7340</code>:这个 key 如果存在,就一定已经在目标那里了;新 key 也只能写到目标。<code>MGET</code> 同时带一个存在、一个不存在的 key,两边各有一部分,回 <code>TRYAGAIN</code>。</p>'),
        sec('去目标节点:ASKING', '', term('', blk('r70', 5)), '<p>目标节点此时还不「拥有」这个槽,所以直接发命令会被打回 <code>MOVED</code> 指向源。必须先发 <code>ASKING</code>,紧接着的下一条命令才会被处理(GET 返回 nil、SET 成功)。<code>ASKING</code> 只管一条命令——第二次直接读同一个 key 又是 MOVED。<b>所以 ASK 是「这一次」的指路,不应该更新客户端缓存的槽位表;MOVED 才是。</b></p>'),
        sec('MIGRATE 与迁移完成', '', term('', blk('r70', 6)), '', term('', blk('r70', 7)), '<p><code>MIGRATE</code> 把 key 从源搬到目标(第 81 篇)。搬完一个 key,源上再读它也变成 ASK。把槽里的 key 都搬完之后,在两端各执行 <code>CLUSTER SETSLOT 槽 NODE 目标ID</code> 完成迁移:源节点从此回的是 <code>MOVED</code>,目标直接服务。(生产里用 <code>redis-cli --cluster reshard</code> 自动完成这些步骤,第 79 篇。)</p>'),
        sec('分步演示:一个槽的迁移', '', demo('MOVED 与 ASK', [('n', 'flow', '节点状态'), ('t', 'term', '请求与回复'), ('kv', 'kv', '要点')], steps, '本步的请求')),
    ],
    refs=[ENV_R + '。3 主 3 从;节点 ID 从 CLUSTER NODES 取得;所有命令都是我手写客户端发的原始命令', '没有验证:迁移中源节点上某个 key 恰好正在被 MIGRATE 时的行为、客户端库对 ASK/MOVED 的具体实现差异、cluster-allow-reads-when-down 等选项'],
)
