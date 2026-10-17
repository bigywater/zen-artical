from lib import *
S = SS('c24')
steps = [
    step("docker run --tmpfs /t1 --tmpfs /t2:size=10m:两个都是 tmpfs 类型,选项 rw,nosuid,nodev,noexec,relatime(注意默认带 noexec)。/t1 没指定大小,df 显示 3967 MiB,正好是容器看到的 MemTotal(7934 MiB)的一半;/t2 的选项里多了 size=10240k,df 显示 10 MiB。", t=tl(S(1)), done=lidx(S(1), '/t2'), mark=lidx(S(1), '/t1', 'MemTotal'), b=bars([['MemTotal (MiB)', 7934, '7934'], ['/t1 默认大小 (MiB)', 3967, '3967'], ['/t2 size=10m (MiB)', 10, '10']], 7934, done=[2], mark=[1]), kv=KV([['/t1 默认', '内存的一半,3967 MiB'], ['/t2 size=10m', '10 MiB'], ['挂载选项', 'rw,nosuid,nodev,noexec,relatime']], ['/t1 默认'])),
    step("往 size=10m 的 /t2 写 20 MiB:dd 退出码 1,报 No space left on device;11+0 records in、10+0 records out,/t2/big 最终正好是 10485760 字节(10 MiB)。写满是文件系统层面的报错,不是进程被杀。", t=tl(S(2)), done=lidx(S(2), 'dd 写 20 MiB'), kv=KV([['写 20 MiB', 'No space left on device,dd 退出码 1'], ['文件大小', '10485760 字节 = 10 MiB']], ['写 20 MiB'])),
    step("docker restart 之后:写在容器可写层里的 /layer.txt 还在(内容 layer);tmpfs 的 /t1 里的文件数是 0——tmpfs 里的数据随容器重启消失。", t=tl(S(3)), done=lidx(S(3), 'docker restart'), kv=KV([['可写层的文件', '重启后还在'], ['tmpfs 里的文件', '重启后没了(0 个)']], ['tmpfs 里的文件'])),
    step("tmpfs 的数据是占内存的:容器的 cgroup memory.current,写入前 5.9 MiB,往 tmpfs 写 100 MiB 后 106.3 MiB(增加 100.4 MiB),删掉文件后回落到 8.3 MiB。对比同样 100 MiB 写到容器可写层:8.9 → 111.2 MiB(增加 102.3 MiB),因为写入的数据也会进页缓存并计入容器的内存。", t=tl(S(4)), done=lidx(S(4), '删掉文件后'), mark=lidx(S(4), '写入前', '对比'), b=bars([['tmpfs 写 100 MiB 增加 (MiB)', 100.4, '100.4'], ['可写层写 100 MiB 增加 (MiB)', 102.3, '102.3']], 102.3, done=[0], mark=[1]), kv=KV([['tmpfs 写 100 MiB', '内存 +100.4 MiB,删文件后回落'], ['可写层写 100 MiB', '内存 +102.3 MiB(页缓存)']], ['tmpfs 写 100 MiB'])),
    step("有内存限制时:--memory 64m --memory-swap 64m,tmpfs size=200m,往里写 150 MiB:dd 退出码 137(被杀);容器本身 ExitCode 0(shell 还活着、打印了结果),但 OOMKilled = true。tmpfs 的 size 上限大于容器的内存上限时,写入会先撞到内存上限,表现为进程被 OOM 杀死,而不是 No space left。", t=tl(S(5)), done=lidx(S(5), '--memory 64m'), kv=KV([['--memory 64m', 'tmpfs size=200m 写 150 MiB'], ['dd', '退出码 137'], ['容器', 'ExitCode 0,OOMKilled=true']], ['dd'])),
    step("--mount 的写法:type=tmpfs,destination=/m1 的目录权限是 drwxrwxrwt(1777,默认所有人可写);加 tmpfs-mode=0700,tmpfs-size=5m 后是 drwx------。", t=tl(S(6)), done=lidx(S(6), '--mount type=tmpfs,destination=/m1'), mark=lidx(S(6), 'tmpfs-mode=0700'), kv=KV([['默认', 'drwxrwxrwt'], ['tmpfs-mode=0700', 'drwx------']], ['tmpfs-mode=0700'])),
]
A = mkartc('c24', 24, 'Docker,tmpfs,内存文件系统,size限制,OOM,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 tmpfs 挂载:默认大小是内存的一半(3967 MiB,MemTotal 7934 MiB),size=10m 写满报 No space left on device;容器重启后数据消失;写 100 MiB 内存增加 100.4 MiB;--memory 64m 时往 200m 的 tmpfs 写 150 MiB,dd 被 OOM 杀死(137)。',
    'tmpfs 挂载的数据放在哪里?默认能写多少?写满了会怎样?容器内存限制和它是什么关系?这篇逐项实测。',
    [('3967 MiB', '没指定 size 的 --tmpfs 的大小,正好是 MemTotal(7934 MiB)的一半'), ('+100.4 MiB', '往 tmpfs 写 100 MiB,容器 cgroup 的内存用量增加'), ('137 / OOMKilled', '内存限制 64m 时往 200m 的 tmpfs 写 150 MiB 的结果')],
    [('默认大小', '<p><code>--tmpfs /t1</code> 不带 size,df 显示 3967 MiB,等于容器看到的内存(7934 MiB)的一半;带 <code>size=10m</code> 就是 10 MiB。挂载选项默认带 <code>noexec</code>,不能在上面直接执行程序(本文没有演示)。</p>'),
     ('写满', '<p>写满后报的是 <code>No space left on device</code>,文件停在正好 10 MiB。</p>'),
     ('重启', '<p>tmpfs 里的数据在 <code>docker restart</code> 后没了,可写层里的文件还在。</p>'),
     ('占内存', '<p>往 tmpfs 写 100 MiB,容器的 memory.current 增加了 100.4 MiB,删掉文件后回落;写到可写层同样会增加(页缓存),但那部分在内存紧张时可以回收,tmpfs 的数据不行——这一点我没有实验,是对机制的理解。</p>'),
     ('配合内存限制', '<p>容器内存上限 64m 而 tmpfs 允许 200m 时,写 150 MiB 到一半,dd 被内核 OOM 杀死(退出码 137),<code>OOMKilled</code> 为 true,但容器因为 shell 还活着,ExitCode 是 0。看容器的退出码不一定能发现内存被打爆,要看 OOMKilled(详见后面的 OOM 一篇)。</p>'),
     ('--mount 写法', '<p><code>--mount type=tmpfs,destination=…</code> 的目录默认是 1777;<code>tmpfs-mode</code> 和 <code>tmpfs-size</code> 可以调整。</p>')],
    steps,
    [ENV_C + '。容器的 MemTotal 7934 MiB(Docker Desktop 虚拟机内存);memory.current 取自容器内的 /sys/fs/cgroup/memory.current;每个场景只运行一次(OOM 和写满都是确定性的现象,数值有 ±几 MiB 抖动);实验后已删除容器',
     '没有验证:noexec 的实际影响、tmpfs 与 swap 的关系、Linux 宿主机上的 tmpfs 默认大小、tmpfs 在 docker commit / docker cp 里的表现、Kubernetes 的 emptyDir medium: Memory'],
    'tmpfs 挂载')
