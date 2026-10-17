from lib import *
S = SS('c91')
steps = [
    step("默认容器的 /dev/shm 是 64 MiB(挂载选项 rw,nosuid,nodev,noexec,relatime,size=65536k),docker inspect 的 HostConfig.ShmSize = 67108864 字节;--shm-size 256m → 256 MiB(size=262144k);--shm-size 1g → 1024 MiB。", t=tl(S(1)), done=lidx(S(1), '默认:', '--shm-size 256m'), mark=lidx(S(1), 'HostConfig.ShmSize'), b=bars([['默认 (MiB)', 64, '64'], ['--shm-size 256m (MiB)', 256, '256'], ['--shm-size 1g (MiB)', 1024, '1024']], 1024, done=[0], mark=[1, 2]), kv=KV([['默认', '64 MiB'], ['--shm-size 256m', '256 MiB'], ['挂载选项', 'noexec,nosuid,nodev']], ['默认'])),
    step("用 dd 往 /dev/shm 写 100 MiB:默认 64 MiB 时写到 64 个块就停了(65+0 records in、64+0 records out),文件大小 67108864 字节,第 65 个块写不下;--shm-size 128m 则 100 个块全部写完,文件 104857600 字节。", t=tl(S(2)), done=lidx(S(2), '--shm-size 128m'), mark=lidx(S(2), '默认 64 MiB'), kv=KV([['默认,写 100 MiB', '只写进 64 MiB'], ['--shm-size 128m', '全部写进']], ['默认,写 100 MiB'])),
    step("用 mmap 方式(Python multiprocessing.shared_memory,每 4096 字节写一次,碰到所有页)写 100 MiB 的共享内存:默认 64 MiB → 进程退出码 135(128 + 7,SIGBUS),只打印了“ftruncate 成功”,没有“所有页都写完了”——创建(ftruncate)时没有报错,空间不够是在写某一页时才被信号杀死;--shm-size 128m → 退出码 0,所有页写完。", t=tl(S(3)), done=lidx(S(3), '--shm-size 128m,共享内存'), mark=lidx(S(3), '默认 64 MiB,共享内存'), kv=KV([['默认 64 MiB', '退出码 135 (SIGBUS)'], ['--shm-size 128m', '退出码 0']], ['默认 64 MiB'])),
    step("/dev/shm 占内存:往 /dev/shm 写 80 MiB,容器的 memory.current 从 5.2 MiB 增加到 85.7 MiB(+80.5 MiB)。所以 --memory 64m --shm-size 200m 时,往 /dev/shm 写 120 MiB,dd 被杀(输出 Killed),容器 OOMKilled = True(容器本身 ExitCode 0,因为 sh 还活着)——--shm-size 比 --memory 大没有意义,先撞上的是内存上限。", t=tl(S(4)), done=lidx(S(4), '往 /dev/shm 写 80 MiB'), mark=lidx(S(4), '--memory 64m、--shm-size 200m'), kv=KV([['写 80 MiB 到 /dev/shm', '容器内存 +80.5 MiB'], ['--memory 64m + --shm-size 200m', 'dd 被 OOM 杀死']], ['写 80 MiB 到 /dev/shm'])),
    step("共享:容器 b 用 --ipc container:a 加入容器 a(--ipc shareable)的 IPC 命名空间后,两者的 IPC 命名空间相同(True),b 能读到 a 写在 /dev/shm 的文件(from-a)——/dev/shm 跟着 IPC 命名空间走。", t=tl(S(5)), done=lidx(S(5), 'b 通过 --ipc container:a'), mark=lidx(S(5), '两者的 IPC 命名空间相同吗'), kv=KV([['--ipc shareable + --ipc container:a', '共用 IPC 命名空间和 /dev/shm'], ['b 读 a 写的文件', 'from-a']], ['--ipc shareable + --ipc container:a'])),
]
A = mkartc('c91', 91, 'Docker,shm-size,/dev/shm,共享内存,SIGBUS,ipc,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 /dev/shm:默认 64 MiB,--shm-size 可调;dd 写 100 MiB 只能写进 64 MiB;mmap 写 100 MiB 的共享内存在默认下被 SIGBUS 杀死(退出码 135),--shm-size 128m 则正常;/dev/shm 的占用算进容器内存(+80.5 MiB),--memory 更小时先被 OOM;--ipc container: 能共享 /dev/shm。',
    '浏览器、数据库、多进程程序在容器里莫名崩溃,往往因为 /dev/shm 只有 64 MiB。这篇实测默认大小、写满时 dd 与 mmap 的不同表现(报错与 SIGBUS)、它算不算容器的内存、以及怎么在容器之间共享。',
    [('64 MiB', '默认容器 /dev/shm 的大小'), ('退出码 135', '默认 /dev/shm 下 mmap 写满 100 MiB 共享内存时进程的退出码(SIGBUS)'), ('+80.5 MiB', '往 /dev/shm 写 80 MiB 后容器内存的增加量')],
    [('大小', '<p>默认 64 MiB,<code>--shm-size</code> 可以改,单位 b/k/m/g。挂载选项带 noexec。</p>'),
     ('write 写满', '<p>用 write 写满返回 ENOSPC:dd 只写进 64 MiB,第 65 个块写不下。</p>'),
     ('mmap 写满', '<p>用 mmap 的程序(Python 的 shared_memory、浏览器、很多数据库)在创建时不会报错,写到没空间的页时才被 SIGBUS 杀死,退出码 135,很难一眼看出原因。</p>'),
     ('占内存', '<p>/dev/shm 是内存文件系统,写进去的内容算在容器的内存里;--memory 比 --shm-size 小的话,先触发的是 OOM,不是 No space left(与 c24 的 tmpfs 一致)。</p>'),
     ('共享', '<p>/dev/shm 属于 IPC 命名空间,<code>--ipc shareable</code> 加 <code>--ipc container:名字</code> 让两个容器共用同一个 /dev/shm。</p>')],
    steps,
    [ENV_C + '。mmap 测试用 Python 3.12 的 multiprocessing.shared_memory,每 4096 字节写一个字节让所有页都被触碰;dd 与 mmap 各一次;内存取自 /sys/fs/cgroup/memory.current(docker exec 读取,含 exec 进程的几 MiB);OOM 由 --memory 64m 触发;实验后已删除容器',
     '没有验证:浏览器(Chrome / Chromium)实际崩溃场景与 --disable-dev-shm-usage 的效果、--ipc host 对 /dev/shm 的影响、Kubernetes 的 emptyDir medium: Memory 替代方案、/dev/shm 与 hugepages'],
    '/dev/shm')
