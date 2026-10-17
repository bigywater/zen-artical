from lib import *
S = SS('m35')
steps = [
    step("8,000,000 个文档(约 1 GB),在 k(随机整数)上建索引,同时有一个线程不停地 find_one 和 insert_one 同一个集合:建索引耗时 7.9 s。", t=tl(S(1)), mark=lidx(S(1), '建索引耗时 7.9 s'), done=lidx(S(1), '建索引耗时'), kv=KV([['集合', '8,000,000 个文档'], ['建索引耗时', '7.9 s'], ['并发', '一个线程持续读写']], ['建索引耗时'])),
    step("建索引之前 / 期间 / 之后的延迟:读(find_one by _id)中位数 0.18 / 0.17 / 0.17 ms,p99 0.39 / 0.43 / 0.31 ms;写(insert_one)中位数 0.09 / 0.09 / 0.11 ms,p99 0.17 / 0.19 / 0.20 ms;建索引的 7.9 s 里并发线程完成了 29,390 次读和 29,390 次写,没有任何错误。读写都没有被阻塞。", t=tl(S(2)), mark=lidx(S(2), '建期间'), done=lidx(S(2), '建之前', '建之后', '并发线程遇到的错误数'), b=bars([['读 p99 建之前', 0.39, '0.39 ms'], ['读 p99 建期间', 0.43, '0.43 ms'], ['写 p99 建之前', 0.17, '0.17 ms'], ['写 p99 建期间', 0.19, '0.19 ms']], 0.43, mark=[1, 3], done=[0, 2]), kv=KV([['读写', '建索引期间照常进行'], ['p99', '读 0.39 → 0.43 ms,写 0.17 → 0.19 ms'], ['错误', '0']], ['读写'])),
    step("currentOp 在建索引期间能看到进度:先是 scanning collection 16% → 32% → 50% → 60% → 69% → 86%(1,337,622 / 8,009,093 …),再进入 inserting keys from external sorter into index(5.5 s 时 13%,1,059,877 / 8,023,600)。", t=tl(S(3)), mark=lidx(S(3), 'inserting keys from external sorter'), done=lidx(S(3), 'scanning collection'), kv=KV([['阶段 1', 'scanning collection'], ['阶段 2', 'inserting keys from external sorter'], ['进度', 'done / total 百分比']], ['阶段 2'])),
    step("建索引期间插入的文档也在索引里:最终文档数 8,043,929,validate 显示 _id_ 与 k_1 各 8,043,929 条,一条不差;之后 find({k: {$gte: 0, $lt: 100000}}) 走 k_1(FETCH > IXSCAN),检查 799 个键。", t=tl(S(4)), mark=lidx(S(4), '8,043,929'), done=lidx(S(4), 'IXSCAN(k_1)', 'keysExamined: 799'), kv=KV([['建索引期间的写入', '会被合并进索引'], ['条目数', '= 文档数 8,043,929']], ['建索引期间的写入'])),
    step("唯一索引:对 u 建唯一索引时(5.3 s),另一个线程在建的过程中插入了 50 个和已有文档重复的 u=123 的文档——这 50 次插入都成功了(并发插入没有被拒绝);建索引最终失败:Index build failed ... E11000 duplicate key error ... index: u_1 dup key: { u: 123 };索引列表只剩 _id_ 和 k_1,u=123 的文档有 51 个。", t=tl(S(5)), mark=lidx(S(5), 'dup key: { u: 123 }', '成功了 50 次'), done=lidx(S(5), '索引列表', '51'), kv=KV([['并发重复插入', '建索引期间不拒绝'], ['建索引', '最后失败,E11000'], ['结果', '索引没建出来,重复的文档留下了']], ['结果'])),
    step("建 z 索引 1.5 s 后另一个连接 drop 整个集合:drop 成功,只花 0.05 s,没有等索引建完;建索引的线程在 1.53 s 时收到 Index build failed ... caused by :: Collection test.t ... 的错误——drop 会中止正在进行的索引构建。", t=tl(S(6)), mark=lidx(S(6), 'drop ok'), done=lidx(S(6), 'Index build failed'), kv=KV([['drop', '不等索引建完,0.05 s 返回'], ['建索引', '被中止并报错']], ['drop'])),
]
A = mkartm('m35', 35, 'MongoDB,建索引,index build,阻塞,currentOp,真实验证,动画演示',
    '实测建索引期间读写会不会被阻塞:800 万个文档上建索引 7.9 s,并发线程的读写 p99 几乎不变且没有错误;currentOp 显示 scanning collection 与 inserting keys 的进度;期间插入的文档也被建进索引;唯一索引期间并发插入的重复值不会被拒绝,建索引最后以 E11000 失败;drop 会中止构建。',
    '建索引会阻塞读写吗?这篇在 800 万个文档的集合上建索引,同时用一个线程不停读写,对比建索引前后的延迟,再看进度、并发写入、唯一索引冲突和 drop 的结果。',
    [('0.43 / 0.19 ms', '建索引期间并发读 / 写的 p99 延迟(建之前 0.39 / 0.17 ms)'), ('0 个', '建索引的 7.9 s 里并发线程遇到的错误数'), ('50 次', '唯一索引构建期间并发插入重复值成功的次数,构建最终失败')],
    [('不阻塞', '<p>800 万个文档上建索引 7.9 s,并发线程的读写延迟几乎没有变化(p99 读 0.39 → 0.43 ms,写 0.17 → 0.19 ms),没有任何错误。</p>'),
     ('进度', '<p><code>currentOp</code> 显示两个阶段:<code>scanning collection</code> 扫描集合,<code>inserting keys from external sorter</code> 把排好序的键写进索引,都带 <code>done / total</code>。</p>'),
     ('并发写入', '<p>构建期间插入的文档也会进入索引,最终索引条目数等于文档数。</p>'),
     ('唯一索引', '<p>构建期间对重复值的并发插入不会被拒绝;构建结束时发现重复而失败(E11000),索引没有建出来,重复的文档还在。</p>'),
     ('drop', '<p>在构建期间 drop 集合会立即成功(0.05 s),并中止构建,构建一侧收到失败的错误。</p>'),
     ('适用范围', '<p>这是单节点、1 GB 数据、SSD 上的结果。副本集上的 commitQuorum、构建在 secondary 上的行为没有测。</p>')],
    steps,
    [ENV_M + '。集合 800 万个文档、缓存 0.5 GB;并发线程用 pymongo 持续读写;进度每 0.5 秒取样 currentOp',
     '没有验证:副本集上的 commitQuorum 与 secondary 构建;建索引的起止瞬间的短暂排他锁(采样间隔下没有看到,但不代表没有);更大数据集(缓存放不下)时对前台的影响;多个索引同时构建;内存限制(maxIndexBuildMemoryUsageMegabytes)与磁盘溢出;collMod 和其它 DDL 与建索引的冲突'],
    '建索引与阻塞')
