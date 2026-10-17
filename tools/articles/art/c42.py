from lib import *
S = SS('c42')
steps = [
    step("在 10 个位置试着写文件。默认:全部可写(/、/tmp、/var/tmp、/dev/shm、/run、/etc/hosts、/etc/resolv.conf、/etc/hostname、/data、/usr/local),根的挂载选项是 rw。--read-only:除了 /dev/shm 可写,其它全是 EROFS(Read-only file system),根的挂载选项变成 ro——包括 /etc/hosts、/etc/resolv.conf、/etc/hostname 也变成只读;Python 的 tempfile 报 FileNotFoundError:No usable temporary directory found in ['/tmp', '/var/tmp', '/usr/tmp'…]。", t=tl(S(1)), done=lidx(S(1), '默认:', '/dev/shm/x=可写'), mark=lidx(S(1), '--read-only:'), b=bars([['默认可写的位置', 10, '10'], ['--read-only 可写的位置', 1, '1']], 10, done=[0], mark=[1]), kv=KV([['默认', '10 个位置都可写,根是 rw'], ['--read-only', '只有 /dev/shm 可写,根是 ro'], ['tempfile', '--read-only 下找不到可用的临时目录']], ['--read-only'])),
    step("给只读的容器开一些可写的口子:--tmpfs /tmp --tmpfs /run 后,/tmp 和 /run 可写、tempfile 恢复可用,/var/tmp 和 /new-file 仍是 EROFS;挂命名卷到 /data 后只有 /data 可写;命名卷加 :ro 则 /data 也是 EROFS。/dev/shm 始终可写。", t=tl(S(2)), done=lidx(S(2), '--read-only --tmpfs /tmp --tmpfs /run:', '命名卷:/data:'), mark=lidx(S(2), '命名卷:/data:ro'), kv=KV([['--tmpfs /tmp --tmpfs /run', '/tmp、/run 可写,tempfile 可用'], ['-v 卷:/data', '只有 /data 可写'], ['-v 卷:/data:ro', '/data 也只读']], ['--tmpfs /tmp --tmpfs /run'])),
    step("HostConfig.ReadonlyRootfs = true。只读容器里往 /tmp(tmpfs)写文件后,docker diff 输出是空的——tmpfs 的内容不在可写层;往 /root 写:退出码 1,Read-only file system。对比不带 --read-only 的容器写 /root/a 和 /tmp/b 后,docker diff 是“C /tmp ; A /tmp/b ; C /root ; A /root/a”。docker diff 只记录可写层的改动。", t=tl(S(3)), done=lidx(S(3), 'docker diff 输出', '对比'), mark=lidx(S(3), '往 /root 写'), kv=KV([['只读容器写 tmpfs', 'docker diff 为空'], ['普通容器写文件', 'A(新增)/ C(改动)出现在 docker diff']], ['只读容器写 tmpfs'])),
]
A = mkartc('c42', 42, 'Docker,read-only,只读根文件系统,tmpfs,EROFS,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 --read-only:10 个位置里只剩 /dev/shm 可写,其它(包括 /etc/hosts、/etc/resolv.conf)都是 EROFS,Python 的 tempfile 找不到可用临时目录;--tmpfs /tmp --tmpfs /run、命名卷可以开出可写的口子;tmpfs 里的写入不进 docker diff。',
    '给容器加上 --read-only 之后,到底哪些地方还能写?为什么程序会因为找不到临时目录而启动失败?这篇逐个位置验证,并演示用 tmpfs 和 volume 开口子。',
    [('只剩 1 个', '--read-only 下 10 个测试位置里仍可写的个数(/dev/shm)'), ('EROFS', '只读容器里写任何镜像路径得到的错误,包括 /etc/hosts'), ('docker diff 为空', '只读容器往 tmpfs 里写文件之后的 docker diff 输出')],
    [('哪里还能写', '<p>默认容器里到处可写;加 <code>--read-only</code> 后根文件系统是 ro,连 Docker 生成的 /etc/hosts、/etc/resolv.conf、/etc/hostname 也变成只读。/dev/shm 仍然可写。</p>'),
     ('常见的启动失败', '<p>很多程序默认往 /tmp 写临时文件。只读容器里 Python 的 <code>tempfile</code> 直接报找不到可用的临时目录。给 <code>--tmpfs /tmp</code> 就能恢复(c24 讲了 tmpfs 的大小和内存占用)。要保存的数据放命名卷或 bind mount,加 <code>:ro</code> 则也变只读。</p>'),
     ('docker diff', '<p>只读容器里没有可写层的改动,往 tmpfs 写的内容也不会出现在 <code>docker diff</code>;普通容器则会列出新增(A)和改动(C)。</p>')],
    steps,
    [ENV_C + '。测试程序是 python:3.12-alpine 里的脚本,用 os.open 尝试创建或打开写;errno 取自异常;每种配置运行一次;实验后已删除容器、卷和镜像',
     '没有验证:真实应用(nginx、postgres)在只读下需要开放哪些路径、/proc 与 /sys 的只读性、--read-only 与 --tmpfs 选项(noexec 等)的组合、Compose 的 read_only: true、Kubernetes 的 readOnlyRootFilesystem'],
    '只读根文件系统')
