from lib import *
S = SS('c17')
steps = [
    step("docker save 把一个 2 层(alpine 加一个 512 KB 随机文件)的镜像导出成 tar:退出码 0,约 100 ms,tar 大小 4518 KB;docker image inspect 的 Size 却是 14290 KB——Size 把压缩内容和解包后的层加在一起,tar 里放的是压缩内容。tar 里 9 个条目,顶层是 blobs、index.json、manifest.json、oci-layout(与 c14 看到的一样);再整体 gzip 只剩 4491 KB(压缩比 0.99),层本来就是 gzip,随机数据也不可压缩。", t=tl(S(1)), done=lidx(S(1), 'docker save 退出码'), mark=lidx(S(1), '再 gzip'), b=bars([['docker save 的 tar (KB)', 4518, '4518'], ['docker image inspect Size (KB)', 14290, '14290'], ['tar 再 gzip (KB)', 4491, '4491']], 14290, done=[0], mark=[2]), kv=KV([['tar', '4518 KB,压缩内容'], ['inspect Size', '14290 KB,压缩加解包'], ['再 gzip', '4491 KB,几乎没变']], ['tar'])),
    step("rmi 之后镜像没了(docker image inspect 退出码 1),docker load -i 把它装回来:退出码 0,约 100 ms,输出 Loaded image: bwlab-c17a:latest。镜像 ID 前后相同(True),tag 也恢复了(True),运行结果 MODE=a、f.bin 524288 字节,都还对。", t=tl(S(2)), done=lidx(S(2), '镜像 ID 前后相同吗?True'), mark=lidx(S(2), 'docker load 退出码'), kv=KV([['load 之后', 'ID 相同、tag 恢复'], ['运行', 'MODE=a,f.bin 524288 字节']], ['load 之后'])),
    step("两个镜像共用 alpine 基础层:各自 save 是 a.tar 4518 KB 加 b.tar 4518 KB,共 9037 KB;放进同一次 docker save a b 得到 ab.tar 5036 KB,少了 4001 KB,与 alpine 基础层压缩后的 4092319 字节(约 3996 KB)只差几 KB——共用的层在 tar 里只存一份。", t=tl(S(3)), done=lidx(S(3), '一起 save 的 ab.tar'), b=bars([['分开保存两个 tar (KB)', 9037, '9037'], ['一起保存 (KB)', 5036, '5036']], 9037, done=[1], mark=[0]), kv=KV([['分开', '4518 + 4518 = 9037 KB'], ['一起', '5036 KB'], ['差', '4001 KB ≈ 基础层']], ['一起'])),
    step("docker export 导出的是容器的文件系统,不是镜像:tar 9408 KB(解包后的内容,没有压缩),523 个条目,含 f.bin,没有 manifest.json / index.json。docker import 把它变回镜像后,层数从 2 变成 1,Env 是 None(原来有 MODE=a),Cmd 是 None(原来是 cat /f.bin),镜像 ID 与原镜像不同;直接 docker run 它,退出码 125,报 no command specified。", t=tl(S(4)), done=lidx(S(4), '原镜像'), mark=lidx(S(4), 'import 出来的镜像', 'no command specified'), b=bars([['原镜像层数', 2, '2'], ['import 后层数', 1, '1']], 2, done=[0], mark=[1]), kv=KV([['docker save / load', '保留层、Env、Cmd、ID'], ['docker export / import', '压成 1 层,丢掉 Env、Cmd,ID 变']], ['docker export / import'])),
]
A = mkartc('c17', 17, 'Docker,docker save,docker load,docker export,docker import,镜像导出,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测镜像的导出与导入:docker save 的 tar 是 4518 KB(压缩内容,而 inspect 的 Size 是 14290 KB);rmi 后 docker load 得到相同的镜像 ID;两个共用基础层的镜像一起 save 比分开少 4001 KB;docker export / import 会把镜像压成 1 层并丢掉 Env 和 Cmd。',
    '没有网络的机器怎么搬镜像?docker save / load 和 docker export / import 名字很像,结果完全不同。这篇实测导出的文件多大、装回来还是不是同一个镜像,以及两个命令各自丢了什么。',
    [('4001 KB', '两个共用基础层的镜像一起 save,比分别 save 少的体积,约等于 alpine 基础层压缩后的大小'), ('2 层 → 1 层', 'docker export 再 import 之后,镜像从 2 层变成 1 层'), ('Env、Cmd 丢失', 'import 出来的镜像没有环境变量和默认命令,直接 run 会报 no command specified')],
    [('save 导出什么', '<p>docker save 导出的是 OCI 布局的 tar,放的是压缩后的层:这个 2 层镜像是 4518 KB,而 <code>docker image inspect</code> 的 Size(14290 KB)是压缩内容加上解包后的层,不是 tar 的大小。再 gzip 一次没有用(0.99)。</p>'),
     ('load 装回来', '<p>删掉镜像再 <code>docker load -i</code>,镜像 ID、tag、运行结果都和之前一样,约 100 ms。这个镜像很小,大镜像的耗时本文没有测。</p>'),
     ('多个镜像一起 save', '<p>两个镜像共用 alpine 基础层:分开存 9037 KB,一起存 5036 KB,差的 4001 KB 与基础层压缩后的大小只差几 KB。要搬运一批相关镜像,放进同一个 tar 更省。</p>'),
     ('export / import', '<p><code>docker export</code> 导出的是容器的文件系统(未压缩的 9408 KB,523 个条目),没有任何镜像元数据。<code>docker import</code> 把它变成一层的新镜像,Env 和 Cmd 都没有了(None),ID 也不同,直接 run 会报 <code>no command specified</code>。需要保留镜像的历史、环境变量和命令时,用 save / load。</p>')],
    steps,
    [ENV_C + '。镜像在本机构建(--provenance=false --sbom=false),大小来自 os.path.getsize,「f.bin」是 os.urandom 随机数据;docker export 用 docker create 出来的容器;实验后已删除镜像、容器和 tar 文件',
     '没有验证:大镜像的 save / load 耗时、docker save 的 tar 通过管道直接 docker load 到另一台机器、zstd 压缩、docker save 指定平台、多平台镜像的 save、import 时用 --change 恢复 CMD 等元数据'],
    '镜像导出与导入')
