from lib import *
S = SS('c22')
steps = [
    step("命名卷 bwlab-c22-named 和一个匿名卷(-v /anon,名字是 64 位随机串)挂在容器上,容器退出后两个卷都在。docker rm(不带 -v)之后:命名卷在,匿名卷也还在(成了没有容器引用的“孤儿”)。新容器挂上命名卷,读到 /data/f.txt = keep。另一个匿名卷用 docker rm -v 删容器,匿名卷随之被删除(在?False)。", t=tl(S(1)), done=lidx(S(1), '新容器挂上命名卷', 'docker rm -v 之后'), mark=lidx(S(1), 'docker rm(不带 -v)之后'), kv=KV([['命名卷', 'docker rm 后还在,可再挂载'], ['匿名卷', 'docker rm 后还在;docker rm -v 才删'], ['数据', '新容器读到 keep']], ['匿名卷'])),
    step("卷里的初始内容从哪来:镜像 /app 里有 hello.txt。空的命名卷挂到 /app,ls 看到 hello.txt——第一次挂载时,镜像里该目录的内容被复制进卷。空的宿主机目录 bind mount 到 /app,ls 是空的,镜像里的内容被盖住了,宿主机目录事后也没有文件。镜像重建(hello.txt 改成 from-image-v2)后再挂同一个卷,读到的还是 from-image,卷里已有的内容不会被新镜像覆盖。", t=tl(S(2)), done=lidx(S(2), '空的命名卷挂到 /app'), mark=lidx(S(2), '空的宿主机目录 bind mount', 'cat /app/hello.txt'), kv=KV([['空的命名卷', '复制进镜像该目录的内容'], ['bind mount', '盖住镜像内容,宿主机目录仍是空的'], ['已有内容的卷', '不被新镜像覆盖']], ['bind mount'])),
    step("读写速度(Python 在容器内计时,3 轮取中位数,128 MiB 以内):写 64 MiB 含 fsync:容器可写层 62 ms、命名卷 36 ms、macOS 宿主机 bind mount 167 ms;建 1000 个小文件:42、20、361 ms;顺序读 64 MiB:21、18、51 ms;listdir 20 次:4、4、57 ms。bind mount 在小文件和目录遍历上慢得多(361 ms 对 20 ms)。", t=tl(S(3)), done=lidx(S(3), '命名卷'), mark=lidx(S(3), 'bind mount(宿主机目录)'), b=bars([['建 1000 个小文件:命名卷 (ms)', 20, '20'], ['建 1000 个小文件:可写层 (ms)', 42, '42'], ['建 1000 个小文件:bind mount (ms)', 361, '361']], 361, done=[0, 1], mark=[2]), kv=KV([['命名卷', '写 36 / 小文件 20 / 读 18 / listdir 4 ms'], ['可写层', '写 62 / 小文件 42 / 读 21 / listdir 4 ms'], ['bind mount', '写 167 / 小文件 361 / 读 51 / listdir 57 ms']], ['bind mount'])),
    step("挂一个宿主机上不存在的路径:-v <路径>:/x 退出码 0,宿主机上现在多了这个目录(True);--mount type=bind,source=<路径> 退出码 125,报 invalid mount config for type \"bind\": bind source path does not exist,宿主机上没有创建(False)。", t=tl(S(4)), done=lidx(S(4), '-v c22-missing-v'), mark=lidx(S(4), '--mount type=bind'), kv=KV([['-v 路径不存在', '自动创建目录,退出码 0'], ['--mount type=bind', '报错,退出码 125,不创建']], ['--mount type=bind'])),
]
A = mkartc('c22', 22, 'Docker,volume,bind mount,数据持久化,文件系统性能,真实验证,动画演示',
    '在 Docker Desktop(macOS)上实测 volume 与 bind mount:docker rm 不删命名卷也不删匿名卷(要 rm -v);空卷第一次挂载会复制镜像该目录的内容而 bind mount 会盖住它;建 1000 个小文件命名卷 20 ms、可写层 42 ms、宿主机 bind mount 361 ms;-v 会自动创建不存在的宿主机目录而 --mount 报错。',
    '数据放 volume 还是 bind mount?它们在生命周期、初始内容、速度和写错路径时的行为上差别不小。这篇在 macOS 的 Docker Desktop 上逐项实测。',
    [('361 ms vs 20 ms', '建 1000 个小文件:宿主机 bind mount 与命名卷'), ('匿名卷还在', 'docker rm 不带 -v 时,匿名卷不会被删'), ('退出码 125', '--mount type=bind 指向不存在的宿主机路径时直接报错')],
    [('生命周期', '<p>命名卷在容器删除后还在,新容器可以再挂载读到数据。匿名卷也是:<code>docker rm</code> 不带 <code>-v</code> 时它成了没人引用的孤儿,要用 <code>docker rm -v</code> 才会随容器删除。</p>'),
     ('初始内容', '<p>空的命名卷第一次挂载到镜像里有内容的目录时,docker 会把镜像该目录的内容复制进去;bind mount 不会,宿主机目录会把镜像里的内容整个盖住。卷里已有内容之后,新镜像的内容不会覆盖它。</p>'),
     ('速度', '<p>这是 macOS 上的数字:命名卷在 Docker Desktop 虚拟机自己的磁盘上(我的理解,没有在虚拟机里核对路径),速度和容器可写层同一量级;bind mount 要经过宿主机与虚拟机之间的文件共享,大文件顺序读写慢约 3~5 倍,小文件创建慢约 18 倍(361 ms 对 20 ms),目录遍历慢约 14 倍。Linux 宿主机上的 bind mount 不一定是这样,我没有测。每个场景只有 3 轮,数字有抖动,看量级。</p>'),
     ('路径写错', '<p><code>-v /不存在的路径:/x</code> 会在宿主机上悄悄创建这个目录;<code>--mount type=bind,source=…</code> 则直接报错。路径拼错时,后者更容易发现。</p>')],
    steps,
    [ENV_C + '。性能测试在 python:3.12-alpine 容器里用 time.perf_counter 计时:写 64 MiB(含 fsync)、建 1000 个 1 字节文件、顺序读 64 MiB、listdir 20 次;三种位置各 3 轮取中位数;bind mount 的宿主机目录在本项目的临时目录下(位于 macOS 的 APFS 上);实验后已删除容器、卷、镜像和宿主机上的临时目录',
     '没有验证:Linux 宿主机上的 bind mount 速度、Docker Desktop 的其它文件共享实现、bind mount 的权限映射(见后面的挂载卷权限一篇)、NFS 或远程卷驱动、卷的备份与迁移'],
    'volume 与 bind mount')
