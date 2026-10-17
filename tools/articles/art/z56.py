from lib import *
R = J('z56'); raw = R['raw']; zk = R['zk']
def S(k): return [l for l in out('z56').split('== ')[k].splitlines()[1:] if l.strip()]
ks = list(raw.keys())
steps = [
    step(f"裸刷盘延迟(写 512 字节再刷盘,500 次):Python 的普通 os.fsync 在 macOS 上中位只有 {raw[ks[0]]['fsync'][0]:.3f} ms(APFS)/ {raw[ks[1]]['fsync'][0]:.3f} ms(HFS+ 映像)——它没有真正要求存储设备落盘;fcntl 的 F_FULLFSYNC 才是真正的落盘,中位 {raw[ks[0]]['full'][0]:.2f} / {raw[ks[1]]['full'][0]:.2f} ms。两者差 100 倍以上。", t=tl(S(1)), b=bars([['os.fsync(APFS)', raw[ks[0]]['fsync'][0], f"{raw[ks[0]]['fsync'][0]:.3f} ms"], ['F_FULLFSYNC(APFS)', raw[ks[0]]['full'][0], f"{raw[ks[0]]['full'][0]:.2f} ms"]], raw[ks[0]]['full'][0] * 1.1, mark=[0], done=[1]), kv=KV([['macOS 上', 'fsync ≠ 真正落盘,F_FULLFSYNC 才是']], ['macOS 上'])),
    step(f"ZooKeeper 的事务日志放在两种位置(同一块物理盘上的 APFS 目录与 HFS+ 磁盘映像):同步写 p50 {zk[ks[0]]['p50']:.2f} ms(服务端 fsync 平均 {zk[ks[0]]['fsync']} ms)与 {zk[ks[1]]['p50']:.2f} ms(fsync 平均 {zk[ks[1]]['fsync']} ms)。ZooKeeper 的 fsync 耗时(约 2~3 ms)与 F_FULLFSYNC 的耗时(约 3 ms)接近,而不是与普通 fsync(0.02 ms)接近——这是一个推断(Java 的 FileChannel.force 在 macOS 上与 F_FULLFSYNC 同量级),我没有读 JDK 源码确认。", t=tl(S(2)), done=[0, 1], kv=KV([['ZooKeeper 的 fsync', '与 F_FULLFSYNC 同量级']], ['ZooKeeper 的 fsync'])),
    step(f"forceSync=no 后同步写 p50 {R['nosync']:.2f} ms:几乎只剩网络与处理链的耗时(约 0.3 ms)。所以这块盘上,同步写延迟 ≈ fsync 耗时 + 约 0.3 ms。换用 fsync 更慢的存储(机械盘、网络盘、云盘),写延迟就会按 fsync 耗时线性上去——这一点我只能从公式推出,没有实测。", t=tl(S(3)), done=[0], kv=KV([['写延迟', '≈ fsync + ~0.3 ms']], ['写延迟'])),
]
A = dict(
    n=56, series='zookeeper', tags='ZooKeeper,磁盘,fsync,写延迟,真实验证,动画演示',
    desc=f'磁盘类型与提交延迟:macOS 上普通 os.fsync 中位 {raw[ks[0]]["fsync"][0]:.3f} ms、F_FULLFSYNC 中位 {raw[ks[0]]["full"][0]:.2f} ms;ZooKeeper 同步写 p50 {zk[ks[0]]["p50"]:.2f} ms(fsync 平均 {zk[ks[0]]["fsync"]} ms),去掉 fsync 后 {R["nosync"]:.2f} ms——写延迟 ≈ fsync 耗时 + 约 0.3 ms。',
    lead='ZooKeeper 的写延迟取决于事务日志所在磁盘的 fsync 速度。我只有一块 SSD,没法比较 SSD、机械盘、云盘,但可以弄清楚「fsync 到底占了写延迟的多少」,以及一个 macOS 上的坑:有的 fsync 并没有真正落盘。',
    facts=[(f'{raw[ks[0]]["fsync"][0]:.3f} vs {raw[ks[0]]["full"][0]:.2f} ms', 'macOS 上普通 fsync 与 F_FULLFSYNC 的中位耗时'), (f'{zk[ks[0]]["p50"]:.2f} → {R["nosync"]:.2f} ms', 'ZooKeeper 同步写 p50:有 fsync → 无 fsync'), ('≈ fsync + 0.3 ms', '这块盘上同步写延迟的经验公式')],
    body=[
        sec('裸刷盘延迟', '', term('', blk('z56', 1))),
        sec('ZooKeeper 的事务日志放在不同位置', '', term('', blk('z56', 2)), '<p>两个位置虽然是不同的文件系统,但物理上是同一块盘,所以差别很小(+1 ms 左右可能是 HFS+ 映像多了一层)。这不是「SSD 与机械盘的比较」。</p>'),
        sec('fsync 是下限', '', term('', blk('z56', 3))),
        sec('没有验证的部分', '', '<p>机械硬盘、网络磁盘、云盘、带电池缓存的 RAID 卡;Linux 上的 ext4 / xfs(本机是 macOS)。这些场景的 fsync 延迟差别很大,是 ZooKeeper 运维里最重要的变量之一——部署前应当用 fio 之类的工具测目标盘的 fsync 延迟。</p>'),
        sec('分步演示', '', demo('磁盘与写延迟', [('t', 'term', '输出'), ('b', 'bars', '数字'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。两个位置:本机 APFS 临时目录、256 MiB 的 HFS+ 磁盘映像(同一块物理盘);裸刷盘每种 500 次', '没有验证:机械盘 / 网络盘 / 云盘、Linux 文件系统、RAID 缓存、事务日志与快照放同一块盘还是分开的实测差别'],
)
