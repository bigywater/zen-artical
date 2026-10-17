from lib import *
S = SS('g64')
steps = [
    step("一万个键,每次操作随机读或写,800 万次操作分给 G 个 goroutine(顺序 sync.Map / RWMutex+map / Mutex+map,ns/次,每格 3 次中位数)。只读:G=1 29.6 / 16.8 / 17.0,G=8 5.2 / 131.9 / 154.6。99% 读:G=1 33.8 / 17.3 / 17.3,G=8 6.1 / 98.3 / 157.4。50% 写(共享键):G=1 68.8 / 23.5 / 21.7,G=8 32.0 / 85.9 / 195.6。50% 写(每个 goroutine 只碰自己的键区间):G=1 74.1 / 29.6 / 23.3,G=8 31.8 / 94.7 / 193.9。", t=tl(S(1)), done=lidx(S(1), '只读(0% 写,共享键)', '99% 读 1% 写'), mark=lidx(S(1), '50% 读 50% 写(共享键)', '每个 goroutine 只碰自己的键区间'), b=bars([['只读 G=8:sync.Map (ns)', 5.2, '5.2'], ['只读 G=8:RWMutex+map', 131.9, '131.9'], ['只读 G=1:sync.Map', 29.6, '29.6'], ['只读 G=1:RWMutex+map', 16.8, '16.8']], 131.9, done=[0, 3], mark=[1, 2]), kv=KV([['G=1', 'sync.Map 慢(29.6 对 16.8 ns)'], ['G=8 读多', 'sync.Map 5.2–6.1 ns,RWMutex 98–132 ns'], ['G=8 50% 写', 'sync.Map 32 ns,RWMutex 86–95 ns,Mutex 194–196 ns']], ['G=1'])),
    step("内存:100 万个 int→int,普通 map 占堆 37.8 MB;sync.Map 占堆 121.6 MB,是普通 map 的 3.2 倍(key 和 value 都要装箱成 any,还要有字典树的节点)。", t=tl(S(2)), mark=lidx(S(2), '100 万个 int→int'), b=bars([['普通 map (MB)', 37.8, '37.8'], ['sync.Map', 121.6, '121.6']], 121.6, done=[0], mark=[1]), kv=KV([['普通 map', '37.8 MB'], ['sync.Map', '121.6 MB(3.2 倍)']], ['sync.Map'])),
    step("文档与实现:sync.Map 文档说它是专门化的,大多数代码应该用普通 map 加单独的锁;它为两种场景优化:(1) 键只写一次、读很多次(只增长的缓存),(2) 多个 goroutine 读写互不相交的键集合。源码里 Map 结构体的核心字段是 m isync.HashTrieMap[any, any]——Go 1.27.1 的 sync.Map 建立在内部的并发哈希字典树上,internal/sync/hashtriemap.go 的注释说它围绕频繁的 Load 设计,Store 和 Delete 也有不错的表现,尤其是在 map 更大时。", t=tl(S(3)), done=lidx(S(3), 'Map is like a Go map', 'The Map type is specialized', 'optimized for two common use cases'), mark=lidx(S(3), 'isync.HashTrieMap', 'internal/sync/hashtriemap.go'), kv=KV([['文档的态度', '大多数代码用普通 map + 锁'], ['适用场景', '只写一次读多次;读写不相交的键'], ['实现', 'internal/sync.HashTrieMap(并发哈希字典树)']], ['实现'])),
]
A = mkartg('g64', 64, 'Go,sync.Map,并发map,HashTrieMap,真实验证,动画演示',
    '在 Go 1.27.1(arm64 macOS)里量 sync.Map:8 个 goroutine 读多写少时 5.2–6.1 ns,RWMutex+map 要 98–132 ns;50% 写时 32 ns 对 86–95 ns;但单 goroutine 下反而更慢(29.6 对 16.8 ns),100 万个键的内存是普通 map 的 3.2 倍;并确认它在 1.27 里建立在内部的 HashTrieMap 上。',
    'sync.Map 什么时候真的比 map 加锁快?这篇用同一个一万键的负载,在 1 个和 8 个 goroutine、从只读到 50% 写的组合下量 sync.Map、RWMutex+map、Mutex+map,再看内存开销,并读源码确认它的实现。',
    [('5.2 vs 131.9 ns', '8 个 goroutine 只读时,sync.Map 对 RWMutex+map'), ('29.6 vs 16.8 ns', '单 goroutine 只读时,sync.Map 反而更慢'), ('3.2 倍', '100 万个 int→int 时 sync.Map 占的堆是普通 map 的倍数')],
    [('并发时赢很多,单线程反而慢', '<p>8 个 goroutine 读多写少,<code>sync.Map</code> 每次 5.2–6.1 ns,<code>RWMutex+map</code> 98–132 ns,<code>Mutex+map</code> 约 155 ns;写占到 50% 时 sync.Map 仍是 32 ns,明显优于另外两者(86–95 ns 和约 195 ns)。但只有 1 个 goroutine 时,sync.Map 29.6 ns,加锁的普通 map 只要 16.8–17.0 ns;50% 写时 68.8 对约 22 ns。没有并发竞争的时候不要用它。文档说“键互不相交”是它优化的第二种场景,我专门测了:50% 写、G=8 时 31.8 ns,和共享键的 32.0 ns 几乎一样,在这个测法下没有看到额外优势。</p>'),
     ('内存', '<p>100 万个 int→int,sync.Map 占堆 121.6 MB,普通 map 37.8 MB。键和值都要装箱成 <code>any</code>,再加上字典树的节点(这个原因是我的推断,没有逐项量)。</p>'),
     ('实现已经换了', '<p>1.27.1 里 <code>sync.Map</code> 的核心字段是 <code>isync.HashTrieMap[any, any]</code>,一个并发哈希字典树,注释说它围绕频繁的 Load 设计。我没有读它的具体算法,上面的快慢是实测。文档的态度仍然是:大多数代码应该用普通 map 加单独的锁。</p>')],
    steps,
    [ENV_G + '。负载:预先放入 1 万个键,每次随机选键,按写比例决定读或写;800 万次操作平均分给 G 个 goroutine,墙钟时间 ÷ 800 万,每格 3 次取中位数,GOMAXPROCS=8;内存是 runtime.GC 两次后的 HeapAlloc 差;读过的源码与文档:go doc sync.Map,src/sync/map.go,src/internal/sync/hashtriemap.go 开头的注释',
     '没有验证:HashTrieMap 的具体算法与扩容、遍历(Range)在并发修改下的行为、键很少或很多时的曲线、非 int 键(字符串、结构体)的表现、Linux 上的结果、旧实现(Go 1.23 之前的 read/dirty)与现在的对比'],
    'sync.Map')
