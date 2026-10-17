from lib import *
S = SS('c21')
steps = [
    step("镜像里有 /gone.txt。容器启动时 upperdir 是空的;在容器里 rm /gone.txt 之后,容器里 ls 报 No such file,upperdir 里却多了一个叫 gone.txt 的条目:character special file(字符设备),主设备号:次设备号 = 0:0,大小 0 字节。这个 0:0 的字符设备就是 OverlayFS 的 whiteout——告诉合并视图“下层的这个名字被删除了”。", t=tl(S(1)), done=lidx(S(1), 'rm /gone.txt 之后'), mark=lidx(S(1), 'upperdir/gone.txt 是'), kv=KV([['rm 镜像里的文件', 'upperdir 里出现 gone.txt'], ['类型', 'character special file,0:0,0 字节'], ['效果', '合并视图里该文件消失']], ['类型'])),
    step("删除只存在于可写层的文件不会留下 whiteout:在 /tmp 里创建又删除 only-upper.txt,upperdir/tmp 里是空的。whiteout 只在下层真的有这个名字时才需要。", t=tl(S(2)), done=lidx(S(2), 'upperdir/tmp'), kv=KV([['只在可写层的文件', '删除后不留痕迹'], ['下层有的文件', '删除要留 whiteout']], ['只在可写层的文件'])),
    step("删除整个目录:rm -rf /dir 之后 upperdir/dir 也是 0:0 的字符设备,容器里 ls /dir 报 No such file。再 mkdir /dir 并写入 c.txt:upperdir/dir 变回普通目录,里面只有 c.txt,它的扩展属性是 {trusted.overlay.opaque: y};容器里 ls /dir 只有 c.txt——原来下层的 a.txt、b.txt 被 opaque 目录整个盖住了,不再透出。", t=tl(S(3)), done=lidx(S(3), '重新 mkdir /dir'), mark=lidx(S(3), 'upperdir/dir 的扩展属性'), kv=KV([['删除目录', '同名 0:0 字符设备'], ['删除后重建', '普通目录 + trusted.overlay.opaque=y'], ['效果', '下层目录内容不再透出']], ['删除后重建'])),
    step("删除文件再用同名重新创建:rm /keep.txt 然后 echo again > /keep.txt,upperdir/keep.txt 是普通文件(regular file),内容 again——新文件直接取代了下层的同名文件,不需要 whiteout。", t=tl(S(4)), done=lidx(S(4), 'upperdir/keep.txt'), kv=KV([['删除再重建的文件', '普通文件,内容 again'], ['whiteout', '不需要']], ['删除再重建的文件'])),
    step("把这个容器 docker commit 成镜像:新镜像共 3 层,最后一层(只含这个容器的改动)的 tar 条目是 dir、dir/.wh.a.txt、dir/.wh.b.txt、dir/c.txt、.wh.gone.txt、keep.txt。镜像层里的 whiteout 是 tar 里的 .wh.<名字> 文件(c3 里讲过),不是 0:0 的字符设备。dir 这一项里我没有看到 .wh..wh..opq 标记,而是对 a.txt、b.txt 各写了一个 .wh. 条目。", t=tl(S(5)), done=lidx(S(5), 'commit 退出码'), kv=KV([['运行时(upperdir)', '0:0 字符设备 + trusted.overlay.opaque'], ['镜像层(tar)', '.wh.<名字> 文件'], ['commit 后的 dir', '.wh.a.txt、.wh.b.txt、c.txt']], ['镜像层(tar)'])),
]
A = mkartc('c21', 21, 'Docker,OverlayFS,whiteout,opaque,删除文件,容器文件系统,真实验证,动画演示',
    '进入 Docker Desktop 虚拟机实测 OverlayFS 的删除:删除镜像里的文件会在 upperdir 里留下 0:0 的字符设备(whiteout),删除又重建的目录带 trusted.overlay.opaque=y,删除再同名重建的文件是普通文件;docker commit 之后镜像层里则是 .wh.名字 条目,而不是字符设备。',
    '容器里 rm 一个来自镜像的文件,下层的文件明明还在,怎么就“消失”了?这篇直接读 upperdir:whiteout 是什么类型的文件,删除后重建目录为什么带一个 opaque 属性,以及 docker commit 后它们在镜像层里变成什么。',
    [('0:0', '被删除的镜像文件在 upperdir 里是主次设备号都为 0 的字符设备'), ('opaque=y', '删除后重建的目录,upperdir 里带 trusted.overlay.opaque=y,盖住下层同名目录的全部内容'), ('.wh.gone.txt', 'docker commit 之后,被删文件在镜像层的 tar 里的名字')],
    [('删除一个文件', '<p>下层(镜像层)是只读的,删除只能在可写层里“标记”。upperdir 里出现一个同名的字符设备,主设备号 0、次设备号 0,大小 0 字节;合并视图因此不再显示这个文件。</p>'),
     ('不是所有删除都要标记', '<p>删除只存在于可写层的文件,upperdir 里不留痕迹:下层没有这个名字,就没什么需要遮住。</p>'),
     ('目录与 opaque', '<p>rm -rf 一个目录,在 upperdir 里是同名的 0:0 字符设备。之后再 mkdir 同名目录,它是普通目录,但带 <code>trusted.overlay.opaque=y</code> 扩展属性,下层同名目录里的文件(a.txt、b.txt)不再透出。我是用特权容器挂载 upperdir 后用 Python 读到的这个属性。</p>'),
     ('同名重建', '<p>文件删除后又用同名创建,upperdir 里只是一个普通文件,不需要 whiteout。</p>'),
     ('commit 以后', '<p>运行时的 whiteout 和镜像层里的 whiteout 是两种形式:docker commit 后,新层 tar 里是 <code>.wh.gone.txt</code>、<code>dir/.wh.a.txt</code> 这样的条目。这次 commit 里目录没有出现 <code>.wh..wh..opq</code>,而是逐个文件写了 <code>.wh.</code>——别的构建方式(Dockerfile 里的 RUN rm)产生什么,见 c3。</p>')],
    steps,
    [ENV_C + '。进入虚拟机的方法见 c19(特权容器加 nsenter);读扩展属性是用特权的 python:3.12-alpine 容器只读挂载 upperdir 后 os.getxattr;docker commit 后用 docker save 读出最后一层的 tar;实验后已删除容器和镜像',
     '没有验证:经典 overlay2 驱动、metacopy 与 redirect_dir 的影响、用 Dockerfile 的 RUN rm -rf 构建出的层里是否有 .wh..wh..opq、rename 目录在 overlay 里的表现、内核版本差异'],
    '删除与 opaque')
