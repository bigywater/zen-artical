from lib import *
S = SS('c19')
steps = [
    step("先说明这个 Docker 的存储:docker info 的 Storage Driver 是 overlayfs,DriverStatus 是 [[driver-type io.containerd.snapshotter.v1]]——不是经典的 overlay2;docker inspect 容器的 GraphDriver 是 null,没有 LowerDir / UpperDir 字段。本文的镜像 bwlab-c19(alpine 加两个小文件和一个 3 MiB 的 big.bin)有 4 层。", t=tl(S(1)), done=lidx(S(1), 'Storage Driver'), mark=lidx(S(1), 'GraphDriver'), kv=KV([['Storage Driver', 'overlayfs(containerd snapshotter)'], ['GraphDriver', 'null'], ['镜像', '4 层']], ['Storage Driver'])),
    step("进到 Docker Desktop 的虚拟机里(用 --privileged --pid=host 的容器 nsenter 进入)找这个容器的挂载:文件系统类型 overlay,挂载点 /var/lib/docker/rootfs/overlayfs/<容器ID>。lowerdir 有 5 个目录,镜像只有 4 层;upperdir 和 workdir 是同一个 snapshot 目录下的 fs 和 work(…/2006/fs、…/2006/work)。逐个看 lower:lower[0] 里只有 /etc/hostname、/etc/resolv.conf、/etc/hosts、/etc/mtab、/.dockerenv、/dev/console,是容器创建时多加的一层;lower[1] 是 big.bin、lower[2] 是 two.txt、lower[3] 是 one.txt、lower[4] 是 alpine 的根文件系统——最上面的一层排在最前面。", t=tl(S(2)), done=lidx(S(2), 'lowerdir 有 5 个目录', 'lower[1]', 'lower[2]', 'lower[3]'), mark=lidx(S(2), 'lower[0] 里的文件', 'upperdir =', 'workdir'), b=bars([['镜像层数', 4, '4'], ['lowerdir 目录数', 5, '5']], 5, done=[0], mark=[1]), kv=KV([['mount 类型', 'overlay'], ['lowerdir', '5 个 = 4 层镜像 + 1 个容器创建时的层'], ['upperdir / workdir', '同一个 snapshot 下的 fs / work']], ['lowerdir'])),
    step("容器刚启动时 upperdir 是空的。在容器里创建 new.txt、新目录 newdir,并往原有的 one.txt 追加一行之后,upperdir 里有 new.txt、newdir、one.txt;one.txt 在 upperdir 里是 “one | changed”(整个文件被复制上来再追加),原来的 one.txt 只在 lower[3] 里,内容 one。没改动的 big.bin 不在 upperdir 里。", t=tl(S(3)), done=lidx(S(3), '没改动的 big.bin'), mark=lidx(S(3), 'upperdir 里的 one.txt', '每个 lower 里的 one.txt'), kv=KV([['新建的文件', '直接出现在 upperdir'], ['修改 lower 里的文件', '先复制到 upperdir 再改'], ['没改的 big.bin', '不在 upperdir']], ['修改 lower 里的文件'])),
    step("合并后的视图:在挂载点上 ls 看到 big.bin、bin、…、new.txt、newdir、one.txt、two.txt 等所有层的并集;挂载点上 cat one.txt 是 “one | changed”,和容器里 cat 的结果一样。容器看到的根目录,就是这个 overlay 挂载点。", t=tl(S(4)), done=lidx(S(4), '挂载点上 cat one.txt'), mark=lidx(S(4), '在挂载点上 ls'), kv=KV([['挂载点 ls', '所有层的并集'], ['cat one.txt', '宿主(虚拟机)与容器内一致']], ['挂载点 ls'])),
    step("删掉容器之后:docker rm -f 前 upperdir 在、/proc/mounts 里有 1 行挂载记录;删除后 upperdir 已删除,挂载记录 0 行,容器创建时的 lower[0] 也被删除;镜像的层 lower[1] 仍在。容器的可写层随容器一起消失,镜像层不受影响。", t=tl(S(5)), done=lidx(S(5), '镜像的层 lower[1]'), mark=lidx(S(5), 'docker rm -f 之后'), kv=KV([['upperdir', '随容器删除'], ['容器创建时的层', '随容器删除'], ['镜像的层', '仍在']], ['upperdir'])),
]
A = mkartc('c19', 19, 'Docker,overlayfs,overlay2,lowerdir,upperdir,容器文件系统,真实验证,动画演示',
    '进到 Docker Desktop 的虚拟机里实测容器的 overlay 挂载:这个 Docker 用 containerd 的 overlayfs snapshotter(不是 overlay2),4 层镜像的容器有 5 个 lowerdir(多出一个容器创建时的层:hostname、resolv.conf、hosts 等),upperdir 初始为空,新建和修改的文件落在 upperdir,docker rm 后 upperdir 随之删除而镜像层仍在。',
    '容器的文件系统到底在磁盘上是什么样?这篇用一个特权容器进入 Docker Desktop 的虚拟机,直接看容器的 overlay 挂载选项,列出每个 lower 目录里的文件,再看容器里写文件时 upperdir 的变化。',
    [('5 个 lowerdir', '4 层镜像的容器,多出的一个是容器创建时加的层(hostname、hosts、resolv.conf 等)'), ('upperdir 初始为空', '容器刚启动时可写层是空的,新建与修改的文件才落进去'), ('overlayfs 而不是 overlay2', 'docker info 的 Storage Driver;containerd snapshotter')],
    [('存储驱动', '<p>这个 Docker Desktop(Docker Engine 29.8.2)用的是 containerd 的 overlayfs snapshotter,<code>docker info</code> 里 Storage Driver 是 <code>overlayfs</code>,<code>docker inspect</code> 的 GraphDriver 是 null,目录在虚拟机里 <code>/var/lib/desktop-containerd/…/snapshots/</code> 下,不是文章里常说的 <code>/var/lib/docker/overlay2</code>。经典 overlay2 驱动的目录结构我没有测。</p>'),
     ('挂载选项', '<p>进入虚拟机(特权容器加 <code>nsenter -t 1</code>)查 <code>/proc/mounts</code>,容器的根是一个 overlay 挂载,选项里有 lowerdir(5 个目录,最上层在前)、upperdir 和 workdir。多出来的那个 lower 里是 hostname、hosts、resolv.conf 等容器创建时生成的文件。</p>'),
     ('写入落在 upperdir', '<p>新建的文件和目录直接出现在 upperdir;修改 lower 里已有的文件,先整个复制进 upperdir 再改(copy-up,见后面的专题),没改动的大文件不会被复制。</p>'),
     ('merged 视图', '<p>挂载点就是合并后的视图:所有层的文件并集,同名文件取最上层的。宿主(虚拟机)上 cat 和容器里 cat 的结果相同。</p>'),
     ('删除容器', '<p>docker rm -f 之后 upperdir 和容器创建时的那一层都被删除,挂载记录消失,镜像的层还在。需要保留的数据应该放在 volume 里。</p>')],
    steps,
    [ENV_C + '。进入虚拟机的方法:docker run --privileged --pid=host alpine:3.20 nsenter -t 1 -m -u -n -i(只读查看,没有修改虚拟机里的任何设置);目录路径里的 snapshot 编号和容器 ID 每次运行都会变;实验后已删除容器和镜像',
     '没有验证:经典 overlay2 驱动下的目录结构、删除文件产生的 whiteout(见后面的专题)、copy-up 的耗时、volume 与 bind mount 在 overlay 里的位置、不同内核版本的挂载选项差别'],
    'overlayfs 目录结构')
