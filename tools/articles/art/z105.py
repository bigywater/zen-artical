from lib import *
R = J('z105'); rk = R['rs_kill']; mk = R['m_kill']
def S(k): return [x for x in out('z105').split('== ')[k].splitlines()[1:] if x.strip()]
steps = [
    step("HBase 2.6.6:1 个 master + 2 个 region server(hbase.zookeeper.quorum 指向 ZooKeeper,znode 根 /hbase)启动后 /hbase 下是这些:master(临时,当前 active master)、backup-masters、rs/<host,port,startcode>(临时,每个 region server 一个)、meta-region-server(hbase:meta 由哪个进程托管,这次的数据里是 master:7960,即 master 进程自己)、hbaseid(集群 ID)、running(集群启动时间)、table 与 namespace(目录,里面还有 hbase:meta 等的状态)、splitWAL、draining、flush-table-proc、online-snapshot(子目录叫 abort / acquired / reached;用途我没有验证)。数据都是 PBUF 开头的 protobuf。", t=tl(S(1)), done=[0], kv=KV([['active master', '/hbase/master(临时)'], ['region server', '/hbase/rs/<host,port,start>(临时)']], ['active master'])),
    step("建一个预分 6 个 region 的表 t1(3 个 region 在 7961,3 个在 7963),写 300 行:ZooKeeper 里只多了 /hbase/table/t1(表状态目录);region 的分配信息在 hbase:meta 表里,不在 ZooKeeper;ZooKeeper 只存 meta 表托管在哪个进程(/hbase/meta-region-server,这次是 master:7960)。", t=tl(S(2)), done=[0, 1], kv=KV([['新增 znode', '/hbase/table/t1'], ['region 位置', '在 hbase:meta 表里']], ['新增 znode'])),
    step(f"kill -9 持有 3 个 region 的 region server:/hbase/rs 下它的临时节点 {rk['t_rs']:.1f} s 后消失(会话超时设 6 s),master 日志「RegionServerTracker: RegionServer ephemeral node deleted, processing expiration」随即开始处理崩溃的 server。客户端每 100 ms 一次 put+get:{rk['errs']} 次操作失败,受影响的时间窗约 {rk['span']:.1f} s({rk['probes']} 次探测里),之后恢复 —— 重新分配 region 并不快,不仅仅是 ZooKeeper 的会话超时。默认 90 s 会话超时的话,这个窗口会长得多(我没有测默认值)。", t=tl(S(3)), mark=[0], b=bars([['节点消失', rk['t_rs'], f"{rk['t_rs']:.1f} s"], ['客户端受影响窗口', rk['span'], f"{rk['span']:.1f} s"]], 8, done=[0, 1]), kv=KV([['rs 节点消失', f"{rk['t_rs']:.1f} s"], ['客户端失败操作', f"{rk['errs']} 次"]], ['rs 节点消失'])),
    step(f"backup master:再起一个 master,/hbase/backup-masters 下出现它(临时节点)。kill -9 active master:/hbase/master 在 {mk['t_m']:.1f} s 后换成新 master;这期间客户端 {mk['probes']} 次读写失败 {mk['errs']} 次 —— 没有失败(我的推断:读写直接访问 region server,不经过 master,没有进一步验证)。", t=tl(S(4)), done=[0], kv=KV([['master 切换', f"{mk['t_m']:.1f} s"], ['客户端失败', f"{mk['errs']} / {mk['probes']}"]], ['master 切换'])),
]
A = dict(
    n=105, series='zookeeper', tags='ZooKeeper,HBase,Region Server,真实验证,动画演示',
    desc=f'真实运行 HBase 2.6.6(1 master + 2 region server + backup master)连我的 ZooKeeper:列出 /hbase 下的真实 znode 与数据;region 位置不在 ZooKeeper;kill -9 region server 后节点 {rk["t_rs"]:.1f} s 消失、客户端 {rk["errs"]} 次失败;kill -9 active master 后 {mk["t_m"]:.1f} s 切到 backup、读写 0 失败。',
    lead='HBase 是 ZooKeeper 最重的使用者之一。这篇真起一个 HBase 2.6.6,看它在 /hbase 下到底放了哪些节点、哪些信息在 ZooKeeper 里(谁是 master、哪些 region server 活着、meta 在哪)、哪些不在(region 的位置),再杀 region server 与 master,量切换时间和客户端受影响的程度。',
    facts=[('/hbase/rs', '每个 region server 一个临时节点,master 靠它发现崩溃'), ('不在 ZooKeeper', 'region 的位置存在 hbase:meta 表里'), (f'{mk["errs"]} / {mk["probes"]}', 'kill -9 active master 期间客户端失败的读写数')],
    body=[
        sec('/hbase 下的真实节点', '', term('', blk('z105', 1)), '<p>HBase 默认 <code>zookeeper.session.timeout</code> 是 90000 ms(读自 hbase-default.xml);我把它设为 6000 才能在合理时间里观察切换。</p>'),
        sec('建表之后', '', term('', blk('z105', 2))),
        sec('region server 崩溃', '', term('', blk('z105', 3)), '<p>和<a href="zookeeper-service-discovery.html">服务发现</a>一样靠临时节点的会话过期发现崩溃;但 HBase 还要把崩溃 server 的 region 重新分配、回放 WAL,所以客户端的受影响窗口比节点消失的时间更长。</p>'),
        sec('master 切换', '', term('', blk('z105', 4)), '<p>master 选举与<a href="zookeeper-master-election.html">Master 选举</a>那篇的做法一致:谁创建 /hbase/master 谁是 active,其余在 backup-masters 下等待。</p>'),
        sec('分步演示', '', demo('HBase 与 ZooKeeper', [('t', 'term', '输出'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。HBase 2.6.6(archive.apache.org 的 hbase-2.6.6-bin.tar.gz),分布式模式、hbase.rootdir 指向本地文件系统(hbase.unsafe.stream.capability.enforce=false),没有 HDFS;zookeeper.session.timeout=6000;客户端是我写的 Java 程序(put + get 循环,hbase.client.operation.timeout=4000 ms、重试 3 次);znode 数据只抽取了其中可打印的字符串', '没有验证:HDFS 上的 HBase、默认 90 s 会话超时下的切换、region 重新分配与 WAL 回放各自耗多少、复制(replication)与快照等用到的 znode、/hbase/table 在不同版本的含义、client 读写为什么不受 master 切换影响(只观察到 0 失败)'],
)
