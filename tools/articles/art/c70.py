from lib import *
S = SS('c70')
steps = [
    step("docker stats --no-stream --format json 的字段:BlockIO、CPUPerc、Container、ID、MemPerc、MemUsage、Name、NetIO、PIDs。容器里 2 个满负荷进程:CPUPerc = 198.98%,PIDs = 3,MemUsage 13.41MiB / 7.748GiB(MemPerc 0.17%)。自己从 cgroup 的 cpu.stat 算:CPU 时间增量 ÷ 墙钟时间 = 200%。虚拟机有 10 个 CPU,所以 CPUPerc 的 100% 是一个核,可以超过 100%。", t=tl(S(1)), done=lidx(S(1), '2 个满负荷进程', '自己从 cgroup'), mark=lidx(S(1), '虚拟机 CPU 数'), b=bars([['docker stats CPUPerc (%)', 198.98, '198.98'], ['从 cpu.stat 算 (%)', 200, '200']], 200, done=[0, 1]), kv=KV([['CPUPerc', '198.98%,100% = 一个核'], ['cpu.stat 算出', '200%'], ['虚拟机 CPU 数', '10,所以上限 1000%']], ['CPUPerc'])),
    step("MemUsage 不含页缓存:写 200 MiB 文件前 docker stats 的 MemUsage 是 544KiB / 512MiB,写完是 6.102MiB / 512MiB;同一时刻从 cgroup 读 memory.current = 214.0 MiB,其中 inactive_file 就有 200.0 MiB(页缓存)、anon 6.2 MiB。cgroup 的总用量涨了约 200 MiB,docker stats 只涨了几 MiB。(这次从 cgroup 读用了一个 docker exec 进程,自己会多占几 MiB。)", t=tl(S(2)), done=lidx(S(2), 'docker stats 的 MemUsage'), mark=lidx(S(2), '对比', '写完之后从 cgroup 读'), b=bars([['写文件前 MemUsage (MiB)', 0.53, '0.53'], ['写文件后 MemUsage (MiB)', 6.1, '6.1'], ['写文件后 memory.current (MiB)', 214, '214']], 214, done=[0, 1], mark=[2]), kv=KV([['docker stats MemUsage', '不含页缓存(+约 5.5 MiB)'], ['cgroup memory.current', '含 200 MiB 页缓存(214.0 MiB)']], ['docker stats MemUsage'])),
    step("NetIO 和 BlockIO:容器里 ping 20 个包前后 eth0 的 rx / tx 增量是 21406 / 20924 字节,启动以来累计 rx=22096、tx=21008,docker stats 的 NetIO = 22.1kB / 21kB,与内核的累计计数吻合。用 oflag=direct 写 50 MiB 后,BlockIO = 0B / 52.4MB(读 / 写)。", t=tl(S(3)), done=lidx(S(3), 'docker stats NetIO', 'BlockIO'), kv=KV([['NetIO', '= eth0 的累计 rx / tx (22.1kB / 21kB)'], ['BlockIO', '写 50 MiB 后写入 52.4MB']], ['NetIO'])),
]
A = mkartc('c70', 70, 'Docker,docker stats,监控,CPU百分比,内存页缓存,NetIO,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 docker stats:两个满负荷进程的 CPUPerc 是 198.98%(与从 cgroup cpu.stat 算出的 200% 一致,100% 是一个核);MemUsage 不含页缓存(写 200 MiB 文件后 cgroup 的 memory.current 涨了约 200 MiB,docker stats 只涨几 MiB);NetIO 与 eth0 的内核计数一致;BlockIO 记录写入量。',
    'docker stats 里的 CPU%、内存、网络和磁盘数字到底怎么算的?为什么 CPU 能超过 100%?为什么写了一大堆文件内存却没涨?这篇和 cgroup、内核计数器对照着验证。',
    [('198.98%', '两个满负荷进程在 docker stats 里的 CPUPerc(10 个 CPU 的虚拟机里上限是 1000%)'), ('214.0 vs 6.1 MiB', '写 200 MiB 文件后,cgroup 的 memory.current 与 docker stats 的 MemUsage'), ('22.1kB / 21kB', 'docker stats 的 NetIO,与 eth0 的内核累计计数一致')],
    [('CPU', '<p>CPUPerc 以一个 CPU 核为 100%,两个忙等进程大约 200%;我用 cgroup 的 <code>cpu.stat</code> 的 usage_usec 增量算出 200%,与 stats 的 198.98% 吻合。</p>'),
     ('内存', '<p>MemUsage 不包含页缓存(inactive_file)。写大文件会让 cgroup 的 memory.current 涨很多,但 docker stats 看不出来。判断容器会不会因为内存被杀,要看 cgroup 的实际限制行为,而不只是这个数字(页缓存在内存紧张时可回收,我没有在这里测)。</p>'),
     ('网络与磁盘', '<p>NetIO 是容器 eth0 的累计收发字节,和 <code>/sys/class/net/eth0/statistics</code> 一致;BlockIO 是块设备读写累计,direct I/O 写 50 MiB 后写入是 52.4MB。</p>')],
    steps,
    [ENV_C + '。docker stats 用 --no-stream --format json;cgroup 值从容器里读 /sys/fs/cgroup(通过 docker exec,exec 出来的进程自己会占用几 MiB);CPU 用 2 个 Python 忙等进程;每种情形运行一次;实验后已删除容器',
     '没有验证:docker stats 内存的精确计算公式(我只确认了不含页缓存)、多容器时的 CPU 汇总、Windows 容器、docker stats 的采样间隔与平滑、cgroup v1 的差别、NetIO 在多网卡容器里的汇总方式'],
    'docker stats')
