from lib import *
S = SS('c23')
steps = [
    step("macOS(宿主机用户 uid=501)上的 bind mount:容器里 root(uid 0)创建的 by-root.txt,在宿主机上是 uid=501 gid=20 mode=0o644——属于宿主机用户,不是 root。反过来,宿主机用户创建的 by-host.txt(uid=501 mode=0o640),在容器里 ls -ln 看到的属主是 0 0(root)。文件的 uid 在两边被互相映射了。", t=tl(S(1)), done=lidx(S(1), 'by-root.txt'), mark=lidx(S(1), 'by-host.txt'), kv=KV([['容器 root 创建的文件', '宿主机上 uid=501(宿主机用户)'], ['宿主机用户的文件', '容器里显示属主 0:0']], ['宿主机用户的文件'])),
    step("容器里非 root 用户(--user 1000:1000)往宿主机上 mode 755、属主是宿主机用户的目录写文件:退出码 0,写成功;文件在宿主机上仍是 uid=501。在容器里把 by-root.txt chown 1234:1234、chmod 600:容器里看到 -rw------- 1234 1234,宿主机上却是 uid=501 gid=20 mode=0o600——chmod 生效,chown 没有真的改变宿主机上的属主。这里 uid 并不起通常意义上的权限检查作用。", t=tl(S(2)), done=lidx(S(2), '写成功', '文件在宿主机上'), mark=lidx(S(2), 'chown 1234:1234'), kv=KV([['uid 1000 写 755 目录', '成功(目录属主是 501)'], ['容器里 chown 1234', '容器里显示 1234,宿主机仍是 501'], ['chmod 600', '宿主机上也变成 0600']], ['容器里 chown 1234'])),
    step("命名卷里的权限取决于卷里目录的属主:镜像里 /rootonly 属主是 root(0:0),空命名卷挂上去,--user 1000 写入 → 退出码 1,Permission denied。镜像里 /owned 属主是 1000:1000(含 seed.txt),空命名卷挂上去,卷里是 drwxr-xr-x 1000 1000,seed.txt 也是 1000:1000,--user 1000 写入成功。事后对空卷的根目录用 root chown 1000:1000,再用 --user 1000 写入也成功。", t=tl(S(3)), done=lidx(S(3), '/owned', '事后用 root chown'), mark=lidx(S(3), '/rootonly'), kv=KV([['卷挂在 root 属主的目录', 'uid 1000 写入:Permission denied'], ['卷挂在 1000 属主的目录', '属主一起复制进卷,写入成功'], ['事后 chown', '也可以']], ['卷挂在 root 属主的目录'])),
    step("到 Docker Desktop 的虚拟机里看命名卷的目录 /var/lib/docker/volumes/bwlab-c23-owned/_data:f.txt 和 seed.txt 的属主都是 1000 1000——卷里存的是真实的 uid/gid(与 bind mount 不同,没有映射到宿主机用户)。", t=tl(S(4)), done=lidx(S(4), 'bwlab-c23-owned'), kv=KV([['bind mount(macOS)', 'uid 被映射成宿主机用户'], ['命名卷', '存真实 uid/gid,如 1000 1000']], ['命名卷'])),
]
A = mkartc('c23', 23, 'Docker,volume,bind mount,文件权限,uid,macOS,真实验证,动画演示',
    '在 Docker Desktop(macOS)上实测挂载卷的权限:bind mount 里容器 root 创建的文件在宿主机上是宿主机用户(uid 501)的,uid 1000 的容器用户可以写 755 的宿主机目录,容器里 chown 不改变宿主机属主;命名卷存真实 uid,镜像目录属主是 root 时 uid 1000 写入 Permission denied,属主是 1000 时空卷会继承并写入成功。',
    '容器里的 uid 和宿主机的 uid 是什么关系?为什么有时候卷里的目录非 root 用户写不进去?这篇分别在 bind mount 和命名卷上实测文件属主的映射规则。',
    [('uid 501', '容器 root 在 bind mount 里创建的文件,在 macOS 宿主机上的属主'), ('Permission denied', 'root 属主的空命名卷目录,--user 1000 写入的结果'), ('1000 1000', '命名卷在虚拟机里的真实属主')],
    [('bind mount(macOS)', '<p>容器里 root 创建的文件,在宿主机上归宿主机用户(uid 501);宿主机用户的文件在容器里显示成 root 的(0 0)。<strong>这是 Docker Desktop 在 macOS 上的行为,不能推广到 Linux 宿主机</strong>——Linux 上 bind mount 的 uid 是原样的,我没有测。</p>'),
     ('写入权限与 chown', '<p>uid 1000 的容器用户可以往宿主机上 755、属主是宿主机用户的目录里写文件;容器里 chown 1234:1234 之后容器里看到 1234,宿主机上仍是 501;chmod 600 则在宿主机上也生效。也就是说,在这种 bind mount 上不要指望靠 uid 做访问控制。</p>'),
     ('命名卷与镜像目录的属主', '<p>空命名卷第一次挂载时,镜像里该目录的内容连同属主一起复制进卷(根目录本身也一样)。镜像里目录是 root 的,非 root 的容器用户就写不进去;在 Dockerfile 里先 <code>chown</code> 目录是一种做法,事后用 root 容器 chown 卷的根目录是另一种。</p>'),
     ('卷里的真实 uid', '<p>进入虚拟机看卷的目录,文件属主就是 1000 1000,没有映射。所以同一个命名卷换一个 uid 不同的镜像去用,就可能遇到权限问题(本文没有演示这个场景)。</p>')],
    steps,
    [ENV_C + '。宿主机用户 uid 501(macOS);bind mount 的宿主机目录在本项目临时目录下;命名卷属主在虚拟机里用特权容器加 nsenter 读取(方法见 c19);实验后已删除容器、卷、镜像和临时目录',
     '没有验证:Linux 宿主机的 bind mount、--userns-remap(见后面的 userns 一篇)、SELinux 标签(:z / :Z)、docker run --user 与 fsGroup 之类的 Kubernetes 方案、NFS 卷、Windows 宿主机'],
    '挂载卷的权限')
