from lib import *
S = SS('c89')
steps = [
    step("容器里 Python 的 time.time_ns() 与 Mac 上调用前后时间的中点相比,差值在 17~28 毫秒(7 次;主要是 docker exec 往返的不对称),容器没有独立的时钟,用的是虚拟机内核的时钟。容器有自己的时间命名空间(/proc/self/ns/time = time:[4026535132],与虚拟机 PID 1 的 time:[4026531834] 不同),但偏移 /proc/self/timens_offsets 的 monotonic 和 boottime 都是 0 0,所以 /proc/uptime 与虚拟机一样(19317 秒)——容器看到的“开机时间”是虚拟机的。", t=tl(S(1)), done=lidx(S(1), '容器里 Python 的 time.time_ns()', 'timens_offsets'), mark=lidx(S(1), '时间命名空间', '/proc/uptime'), kv=KV([['时钟', '与虚拟机相同,与 Mac 差约 20 毫秒(测量误差)'], ['时间命名空间', '独立,偏移 0'], ['uptime', '虚拟机的,不是容器的']], ['时间命名空间'])),
    step("时区:默认容器 date 是 UTC(14:42),Mac 上是 CST(22:42);-e TZ=Asia/Shanghai 在 alpine 镜像里没有效果(镜像里没有 /usr/share/zoneinfo,仍是 UTC);TZ=CST-8 这种 POSIX 写法不需要时区数据库,date 显示 22:42 CST;python:3.12-alpine 自带 /usr/share/zoneinfo,TZ=Asia/Shanghai 有效,datetime.now() 是 22:42 且 time.tzname 是 ('CST', 'CST');把 Mac 的 /etc/localtime 只读挂进去(-v /etc/localtime:/etc/localtime:ro)退出码 0,date 显示 22:42 CST。", t=tl(S(2)), done=lidx(S(2), 'TZ=CST-8', 'python:3.12-alpine', '/etc/localtime:/etc/localtime:ro'), mark=lidx(S(2), 'TZ=Asia/Shanghai(alpine', '默认容器的 date'), kv=KV([['默认', 'UTC'], ['TZ=Asia/Shanghai', '镜像里要有 zoneinfo 才生效'], ['TZ=CST-8', '不需要 zoneinfo'], ['挂 /etc/localtime', '有效(Mac 上)']], ['TZ=Asia/Shanghai'])),
    step("容器里不能改系统时间:date -s \"2000-01-01 00:00:00\" 先打印出新时间,随后报 date: can't set date: Operation not permitted(docker exec 的退出码仍是 0);紧接着再看 date 还是当前时间,没被改动;CapEff 里没有 sys_time(c40)。", t=tl(S(3)), done=lidx(S(3), '紧接着再看'), mark=lidx(S(3), 'date -s', 'sys_time'), kv=KV([['date -s', "can't set date: Operation not permitted"], ['时间', '没有被改'], ['sys_time', '默认容器没有']], ['date -s'])),
    step("日志时间戳固定是 UTC:TZ=Asia/Shanghai 的容器自己 date 输出 22:42:33 CST,docker logs -t 给的是 2026-10-10T14:42:33.557078303Z;docker inspect 的 StartedAt 也是 UTC(14:42:33)。", t=tl(S(4)), done=lidx(S(4), '容器自己 date 的输出'), mark=lidx(S(4), 'StartedAt'), kv=KV([['容器内 date', '随 TZ'], ['docker logs -t / StartedAt', '总是 UTC']], ['docker logs -t / StartedAt'])),
]
A = mkartc('c89', 89, 'Docker,时间,时区,TZ,时间命名空间,date,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测容器的时间:容器用虚拟机内核的时钟(与 Mac 差约 20 毫秒的测量误差),有独立的时间命名空间但偏移为 0,uptime 是虚拟机的;alpine 里 TZ=Asia/Shanghai 无效(没有 zoneinfo),TZ=CST-8 或自带 zoneinfo 的镜像有效,挂 /etc/localtime 也行;date -s 被拒绝;docker logs -t 与 StartedAt 永远是 UTC。',
    '容器的时间从哪来?为什么 alpine 里设了 TZ 却还是 UTC?容器能改系统时间吗?日志时间戳按哪个时区?这篇逐项实测。',
    [('偏移 0', '容器的时间命名空间里 monotonic 和 boottime 的偏移'), ('CST-8 有效', 'alpine 里 TZ=Asia/Shanghai 不生效,POSIX 写法 CST-8 生效'), ('UTC', 'docker logs -t 的时间戳与 docker inspect 的 StartedAt 的时区')],
    [('时钟', '<p>容器没有自己的时钟:读到的就是虚拟机内核的时间。容器有独立的时间命名空间,但没有设置偏移,所以时钟和 uptime 都和虚拟机一致(uptime 是 19317 秒,不是容器自己的运行时间)。</p>'),
     ('时区', '<p>Alpine 镜像里没有时区数据库,<code>TZ=Asia/Shanghai</code> 查不到,于是退回 UTC;用 POSIX 写法 <code>TZ=CST-8</code>、安装 tzdata、挂宿主的 <code>/etc/localtime</code>,或用自带 zoneinfo 的镜像(python:3.12-alpine)都可以。</p>'),
     ('改时间', '<p>默认没有 CAP_SYS_TIME,<code>date -s</code> 被拒绝,而且改的是整个虚拟机的时钟(所以我没有去加这个 capability 测试)。</p>'),
     ('日志', '<p>docker 自己打的时间戳(logs -t、StartedAt、events)是 UTC,不随容器的 TZ。程序自己打印的时间才随 TZ。</p>')],
    steps,
    [ENV_C + '。时间差用 Python 的 time.time_ns() 取 docker exec 前后 Mac 时间的中点比较;时区实验用 alpine:3.20 与 python:3.12-alpine;没有给任何容器加 SYS_TIME(会改动虚拟机时钟);实验后已删除容器',
     '没有验证:Mac 睡眠唤醒后虚拟机时钟的校正、NTP 同步、CLONE_NEWTIME 偏移的设置方法(docker 没有提供)、Linux 宿主机上 /etc/localtime 的挂载、tzdata 的安装方式差别'],
    '容器的时间')
