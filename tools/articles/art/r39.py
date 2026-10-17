import json
from lib import *
R = J('r39'); T = out('r39').splitlines()
g = {x['N']: x for x in R['grow']}; mx = {x['me']: x for x in R['maxent']}; lk = R['lookup']; by = {x['vb']: x['keys'] for x in R['bytes']}
same, diff = R['fields']['same'], R['fields']['diff']
def rax(cur=(), done=(), n=(3, 3, 1)):
    return {'values': [[f'{["1000-0","1028-1","1056-2"][i]}', f'{n[i]} 条'] for i in range(3)][:sum(1 for x in n if x)], 'cur': list(cur), 'done': list(done)}
IDS = ['1000-0', '1007-1', '1014-2', '1021-0', '1028-1', '1035-2', '1042-0', '1049-1', '1056-2', '1063-0']
def E(k): return {'values': IDS[:k], 'cur': [k - 1] if k else [], 'done': list(range(k - 1)), 'ptr': {}}
steps = [
    step("把 stream-node-max-entries 调成 4,方便看清节点边界。一个空 Stream 里什么都没有:没有 radix 树节点,也没有 listpack。", ents=E(0), rax={'values': [], 'cur': []}, kv={'items': [['radix-tree-keys', '0']], 'hl': []}),
    step("前 4 条消息(1000-0 … 1021-0)写进同一个 listpack。radix 树里只有一个 key:第一条消息的 ID(16 字节 = ms 与 seq 各 8 字节,大端)。", ents=E(4), rax={'values': [['key 1000-0', '4 条']], 'cur': [0]}, kv={'items': [['radix-tree-keys', '1'], ['节点 0', '4 条 → 25 个 listpack 元素']], 'hl': ['radix-tree-keys']}),
    step("第 5 条 1028-1 放不下了(节点已满 4 条),Redis 新开一个 listpack,并在 radix 树里插入 key = 1028-1。", ents=E(5), rax={'values': [['key 1000-0', '4 条'], ['key 1028-1', '1 条']], 'cur': [1], 'done': [0]}, kv={'items': [['radix-tree-keys', '2']], 'hl': ['radix-tree-keys']}),
    step("继续写到第 8 条,新节点写满;第 9 条 1056-2 再开第三个节点。DUMP 出来的 RDB 数据里恰好是这样:3 个节点,key 分别是 1000-0、1028-1、1056-2。", ents=E(9), rax={'values': [['key 1000-0', '4 条'], ['key 1028-1', '4 条'], ['key 1056-2', '1 条']], 'cur': [2], 'done': [0, 1]}, kv={'items': [['radix-tree-keys', '3'], ['DUMP 解出的 key', '(1000,0) (1028,1) (1056,2)']], 'hl': ['DUMP 解出的 key']}),
    step("第 10 条 1063-0 进最后一个节点。10 条消息 = 3 个 listpack:节点 0、1 各 25 个元素(4 条),节点 2 是 15 个元素(2 条)。", ents=E(10), rax={'values': [['key 1000-0', '4 条'], ['key 1028-1', '4 条'], ['key 1056-2', '2 条']], 'cur': [2], 'done': [0, 1]}, kv={'items': [['listpack 大小', '61 B / 62 B / 42 B'], ['元素数', '25 / 25 / 15']], 'hl': ['元素数']}),
    step(f"按 ID 点查(XRANGE key id id):先在 radix 树里定位节点,再在 listpack 里找。实测 1000 条 → 100 万条,点查耗时 {lk[0]['us']:.1f} → {lk[2]['us']:.1f} µs/次,基本不随长度增长。", ents=E(10), rax={'values': [['key 1000-0', '4 条'], ['key 1028-1', '4 条'], ['key 1056-2', '2 条']], 'cur': [1]}, kv={'items': [['1000 条', f"{lk[0]['us']:.1f} µs/次"], ['10 万条', f"{lk[1]['us']:.1f} µs/次"], ['100 万条', f"{lk[2]['us']:.1f} µs/次"]], 'hl': ['100 万条']}),
]
A = dict(
    n=39, series='redis', tags='Redis,Stream,radix tree,真实验证,动画演示',
    desc=f'用 DUMP 解出 Stream 的底层结构验证:radix 树的每个 key 是节点首条消息的 ID(16 字节大端),value 是一个 listpack;默认每节点 100 条(或 4096 字节),10 万条消息 = {g[100000]["keys"]} 个 key、平均 {g[100000]["mem"]/100000:.1f} 字节/条;按 ID 点查从 1000 条到 100 万条都是 {lk[0]["us"]:.1f}–{lk[2]["us"]:.1f} µs。',
    lead='Stream 不是把每条消息单独存成一个对象。它把很多条消息打包进一段 listpack,再用一棵 radix tree 按消息 ID 把这些 listpack 组织起来。这篇不靠推测:直接用 DUMP 拿到 Stream 的序列化数据,把里面的 key 和 listpack 拆开看,再用几组实验量一量这个结构的内存和查找代价。',
    facts=[(f'{g[100000]["keys"]} 个', '10 万条消息在 radix 树里的 key 数(每个 key 对应一个 listpack)'), (f'{g[100000]["mem"]/100000:.1f} B', '默认配置下每条消息(4 个字段)的 MEMORY USAGE 均值'), (f'{lk[0]["us"]:.1f} → {lk[2]["us"]:.1f} µs', '按 ID 点查:1000 条 → 100 万条')],
    body=[
        sec('先看真实结构:DUMP 拆开 Stream', '把 stream-node-max-entries 调成 4,写入 10 条消息,再解析 DUMP 的字节', term('', out('r39b')),
            '<p>RDB 序列化 Stream 时,直接写出的就是「若干个(radix key, listpack)对」。解出来:key 恒为 16 字节,前 8 字节是毫秒、后 8 字节是序号(大端),值就是该节点<b>第一条消息</b>的 ID:第 1、5、9 条的 ID 正好是三个 key。listpack 头部记录的总字节数与实际长度一致;4 条消息的节点有 25 个元素,2 条的有 15 个元素。</p><p>这些元素数字与「每条消息固定占 5 个元素、节点另有 5 个元素做头部」的算式吻合(4×5+5=25,2×5+5=15),但那是我对这组数字的解读,没有另外拆解每个元素去验证。</p>'),
        sec('节点里能装多少条:默认每个 100 条', 'stream-node-max-entries=100,stream-node-max-bytes=4096', term('', blk('r39', 1)),
            f'<p>10 万条消息只有 {g[100000]["keys"]} 个 radix key,平均每个 key 装 100 条;101 条时就变成 2 个。<code>radix-tree-nodes</code>(树内部节点数)比 key 数小,{g[100000]["nodes"]} 对 {g[100000]["keys"]}:key 之间共享前缀,树把它们压缩了。每条消息的内存从 1 条时的 {g[1]["mem"]} 字节掉到大批量时的 {g[100000]["mem"]/100000:.1f} 字节,因为固定开销被节点里的几十上百条消息摊薄。</p>'),
        sec('两个上限:条数和字节数', '哪个先到,就先开新节点', term('', blk('r39', 3)), f'<p>把 <code>stream-node-max-entries</code> 从 1 调到 10000(同时关掉字节上限),同样 10000 条:max-entries=1 时 10000 个 key、每条 {mx[1]["mem"]/10000:.1f} 字节;10 时降到 {mx[10]["mem"]/10000:.1f} 字节;100 时 {mx[100]["mem"]/10000:.1f} 字节;再往大调收益消失({mx[1000]["mem"]/10000:.1f} 和 {mx[10000]["mem"]/10000:.1f} 字节,反而略高于 100)。</p>',
            term('', blk('r39', 6)), f'<p>默认还有 4096 字节的上限:消息值 10 字节时 1000 条只要 {by[10]} 个节点,值 100 字节时 {by[100]} 个,500 字节时 {by[500]} 个,2000 字节时 {by[2000]} 个(每个节点只装 2 条)。<b>所以「每节点 100 条」只是上限,消息大了先撞到的是字节上限。</b></p>'),
        sec('字段名相同,才省内存', '同一节点里的消息共用第一条消息的字段名', term('', blk('r39', 4)), f'<p>同样是 10000 条、每条 2 个字段:字段名都相同时 {same} 字节({same/10000:.1f} 字节/条),每条字段名都不一样时 {diff} 字节({diff/10000:.1f} 字节/条),约 {diff/same:.2f} 倍。字段名相同的消息不用重复存字段名,这是 Stream 比「每条一个 Hash」省内存的原因之一(这里只对比了 Stream 自身两种写法,没有对比 Hash)。</p>'),
        sec('按 ID 查找:耗时不随长度增长', '20000 次随机点查,管道批量发送', term('', blk('r39', 5)),
            f'<p>流从 1000 条涨到 100 万条(radix key 从 {lk[0]["keys"]} 涨到 {lk[2]["keys"]}),点查耗时从 {lk[0]["us"]:.1f} µs 到 {lk[2]["us"]:.1f} µs,几乎不变。注意:这里含一次管道里的网络往返摊销,只能说明「差别很小」,不能拆出树查找本身的耗时;100 万条那一组,被查的 ID 取自流的头部和尾部各 1 万条,不是全范围均匀随机。</p>'),
        sec('分步演示:消息如何落进 radix 树的节点', '数据取自上面的 DUMP 解析和点查实验',
            demo('Stream 的 radix tree', [('ents', 'cells', '写入的消息 ID(按顺序)'), ('rax', 'chips', 'radix 树的 key(= 节点首条消息 ID)'), ('kv', 'kv', '观察')], steps, '当前写入/查找的对象')),
    ],
    refs=[ENV_R, '没有验证:radix 树内部节点的具体形状(只有 XINFO 给出的 radix-tree-nodes 计数)、listpack 内每个元素的含义(只对元素总数做了算术对照)、查找算法是否用的是「找 ≤ ID 的最大 key」(只从耗时不随长度变化间接推断)、Stream 与 Hash 的内存对比'],
)
