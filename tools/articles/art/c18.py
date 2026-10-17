from lib import *
S = SS('c18')
steps = [
    step("一个基础镜像(alpine 加 20 MiB 随机文件)和三个 FROM 它、各自再加 1 MiB 随机文件的镜像 x、y、z。docker system df -v:基础镜像单独存在时 SIZE 55.5MB、SHARED 13.58MB(与 alpine:3.20 共用的部分)、UNIQUE 41.96MB。三个子镜像各自 SIZE 57.6MB、SHARED 55.53MB、UNIQUE 2.104MB;基础镜像的 UNIQUE 变成 1.512kB——它的层现在被子镜像共用。四个镜像的 SIZE 加起来是 228.3 MB,但基础镜像的 SIZE 加三个子镜像各自的 UNIQUE SIZE 只有 61.8 MB——共用的层只有一份,把 docker images 里的大小相加会严重高估。", t=tl(S(1)), done=lidx(S(1), '61.8 MB'), mark=lidx(S(1), '228.3 MB'), b=bars([['单个子镜像 SIZE (MB)', 57.6, '57.6'], ['其中 SHARED (MB)', 55.53, '55.53'], ['其中 UNIQUE (MB)', 2.104, '2.1']], 57.6, done=[2], mark=[1]), kv=KV([['基础镜像单独', 'SIZE 55.5MB,UNIQUE 41.96MB'], ['子镜像 x/y/z', 'SIZE 57.6MB,SHARED 55.53MB,UNIQUE 2.104MB'], ['基础镜像(有子镜像后)', 'UNIQUE 1.512kB']], ['子镜像 x/y/z'])),
    step("docker rmi 删掉基础镜像的名字:退出码 0,只输出 Untagged: bwlab-c18base:latest。剩下的 x、y、z 不受影响:x 的 SIZE、SHARED、UNIQUE 仍是 57.6MB、55.53MB、2.104MB,运行 x 退出码 0,/f-x.bin 是 1048576 字节。共用的层只要还有镜像引用就不会被删。", t=tl(S(2)), done=lidx(S(2), '运行 x'), mark=lidx(S(2), 'Untagged'), kv=KV([['rmi 基础镜像', '只去掉名字(Untagged)'], ['子镜像', '大小不变,仍能运行']], ['子镜像'])),
    step("SIZE 的含义:另一个 5 MiB 随机文件的镜像,docker images 显示 DISK USAGE 24.1MB、CONTENT SIZE 9.34MB,docker system df -v 的 SIZE 也是 24.1MB(SHARED 13.58MB、UNIQUE 10.49MB)。随机文件几乎不可压缩,所以前面“1 MiB 文件的 UNIQUE 是 2.104MB”约等于压缩内容加解包后的层各 1 MiB 左右——这是按数字推断的,我没有逐项核对。", t=tl(S(3)), done=lidx(S(3), 'docker system df -v'), mark=lidx(S(3), 'docker images'), b=bars([['CONTENT SIZE (MB)', 9.34, '9.34'], ['DISK USAGE / SIZE (MB)', 24.1, '24.1']], 24.1, done=[0], mark=[1]), kv=KV([['DISK USAGE', '24.1MB(docker system df -v 的 SIZE 相同)'], ['CONTENT SIZE', '9.34MB(压缩内容)']], ['DISK USAGE'])),
]
A = mkartc('c18', 18, 'Docker,层共享,磁盘占用,docker system df,镜像大小,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测层共享的磁盘占用:3 个镜像共用一个 55.5MB 的基础镜像,每个的 SIZE 都是 57.6MB(SHARED 55.53MB、UNIQUE 2.104MB),四个 SIZE 相加 228.3MB,而基础加三个 UNIQUE 只有 61.8MB;删掉基础镜像的名字不影响子镜像。',
    '多个镜像共用同一层,磁盘上到底占多少?docker images 里每个镜像都写着几十 MB,加起来是不是真实占用?这篇用 docker system df -v 的 SHARED / UNIQUE 两列实测。',
    [('228.3 vs 61.8 MB', '四个镜像的 SIZE 直接相加,与基础镜像加三个 UNIQUE SIZE 的差别'), ('2.104MB', '子镜像里 1 MiB 随机文件对应的 UNIQUE SIZE,约等于压缩内容加解包层'), ('Untagged', 'rmi 基础镜像只去掉名字,子镜像大小不变、继续可用')],
    [('SHARED、UNIQUE 与不能直接相加', '<p><code>docker system df -v</code> 比 <code>docker images</code> 多了 SHARED SIZE 和 UNIQUE SIZE 两列。子镜像 x、y、z 各自 SIZE 57.6MB,其中 55.53MB 是与别的镜像共用的,只有 2.104MB 是自己独有的。基础镜像在有了子镜像以后,UNIQUE 掉到 1.512kB。</p><p>四个 SIZE 加起来 228.3 MB,而更接近真实占用的数字(基础镜像的 SIZE 加三个 UNIQUE SIZE)是 61.8 MB。估算镜像占了多少磁盘时,别把 <code>docker images</code> 的大小相加。我没有去磁盘上量字节数来核对 61.8 MB,它是 docker 自己的统计。</p>'),
     ('删基础镜像', '<p>基础镜像的名字被 <code>docker rmi</code> 去掉后,子镜像的 SIZE、SHARED、UNIQUE 都没变,也能照常运行:被引用的层不会被删。</p>'),
     ('SIZE 是什么', '<p>这个镜像存储下的 SIZE 把压缩内容和解包后的层加在一起(24.1MB 对压缩内容 9.34MB),所以它不是文件系统里文件的总大小。</p>')],
    steps,
    [ENV_C + '。随机文件用 os.urandom 生成(几乎不可压缩);镜像大小取 docker system df -v 与 docker images 的输出;镜像在本机构建(--provenance=false --sbom=false);实验后已删除镜像。Docker Desktop 里还有别的镜像和容器,但本文只看名字以 bwlab-c18 开头的镜像',
     '没有验证:去 Docker Desktop 虚拟机磁盘里量真实字节数、容器可写层的占用、经典存储驱动下 SHARED / UNIQUE 的算法、build cache 对占用的影响'],
    '层共享与磁盘占用')
