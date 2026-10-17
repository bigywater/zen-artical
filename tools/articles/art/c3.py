from lib import *
S = SS('c3')
steps = [
    step("创建一个 20 MiB 的随机文件,在下一个 RUN 里删掉它,镜像变小了吗?alpine:3.20 本身 docker images 显示 DISK USAGE 13.6MB、CONTENT SIZE 4.09MB(inspect 的 Size = 13.58 MB)。两个 RUN(先 dd,再 rm):DISK USAGE 55.5MB、CONTENT SIZE 25.1MB,inspect 的 Size 比 alpine 多 41.96 MB;一个 RUN(dd && rm):13.6MB / 4.1MB,和 alpine 一样。这个 Docker 的 Size 是压缩内容加上解包后的层:随机数据压不动,所以 20 MiB 的层被算了两遍,约 42 MB。", t=tl(S(1)), mark=lidx(S(1), '两个 RUN', '55.5MB'), done=lidx(S(1), '一个 RUN', 'alpine:3.20 的 docker images'), b=bars([['alpine:3.20 (MB)', 13.58, '13.58'], ['先 dd 再 rm(两层)', 55.54, '55.54'], ['dd && rm(一层)', 13.58, '13.58']], 55.54, mark=[1], done=[0, 2]), kv=KV([['两个 RUN', '比 alpine 多 41.96 MB(层 + 解包各算一次)'], ['一个 RUN', '多 0.00 MB'], ['结论', '删除在新的一层里,不会把旧的层变小']], ['结论'])),
    step("docker history 的每一层大小:两个 RUN 的镜像——rm /big.bin 那一层 4.1kB,dd 那一层 21MB,CMD 0B,alpine 基础层 9.49MB;一个 RUN 的镜像——dd && rm 那一层只有 4.1kB,CMD 0B,基础层 9.49MB。", t=tl(S(2)), mark=lidx(S(2), '21MB'), done=lidx(S(2), 'bwlab-c3b'), kv=KV([['dd 那一层', '21MB'], ['rm 那一层', '4.1kB'], ['合并成一个 RUN', '只有 4.1kB']], ['dd 那一层'])),
    step("用 docker save 导出,打开每一层的 tar:两个 RUN 的镜像有 3 层,dd 那一层(20.98 MB)里有 big.bin(20971520B),rm 那一层(0.00 MB)里只有一个条目 .wh.big.bin(0B)——这就是 whiteout 文件。一个 RUN 的镜像只有 2 层,dd && rm 那一层没有任何条目(条目 0 个)。", t=tl(S(3)), mark=lidx(S(3), 'big.bin(20971520B)', '.wh.big.bin(0B)'), done=lidx(S(3), '条目 0 个'), kv=KV([['删除的记录', '.wh.<原文件名> 的空文件(whiteout)'], ['原文件', '仍然完整地躺在下面的层里'], ['同一层里创建又删除', '什么都不留下']], ['删除的记录'])),
    step("删除只是在上面盖了一层。把 Dockerfile 拆成两个阶段并单独构建 gen 阶段:从 gen 阶段的镜像启动,ls -la /big.bin 看到 20971520 字节的文件;从最终镜像(多了 rm 那一层)启动,同一条命令得到 No such file or directory。", t=tl(S(4)), mark=lidx(S(4), 'gen 阶段', '20971520'), done=lidx(S(4), '最终镜像'), kv=KV([['gen 阶段的镜像', '/big.bin 在,20971520 字节'], ['最终镜像', '看不到,但文件还在下层']], ['最终镜像'])),
    step("多阶段构建:生成阶段用掉 20 MiB(创建又删除),最终阶段只 COPY --from 一个小文件:镜像 13.59 MB,比 alpine 多 0.01 MB。只拷需要的东西进最终镜像,才真正变小。", t=tl(S(5)), mark=lidx(S(5), '13.59 MB'), b=bars([['alpine (MB)', 13.58, '13.58'], ['多阶段最终镜像', 13.59, '13.59'], ['两个 RUN 的镜像', 55.54, '55.54']], 55.54, done=[0, 1], mark=[2]), kv=KV([['多阶段', '13.59 MB,多 0.01 MB'], ['做法', '临时文件留在前一个阶段,只 COPY --from 需要的']], ['做法'])),
]
A = mkartc('c3', 3, 'Docker,镜像层,whiteout,多阶段构建,docker save,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测“删除文件不会减小镜像”:先 dd 20 MiB 再下一个 RUN 里 rm,镜像比 alpine 多 41.96 MB(Size 把压缩内容和解包层各算一次),而同一个 RUN 里 dd && rm 多 0.00 MB;docker save 的层 tar 里,删除那一层只有一个 0 字节的 .wh.big.bin;从 gen 阶段启动能看到文件,最终镜像看不到;多阶段构建后只多 0.01 MB。',
    '“我在 Dockerfile 里 rm 了,镜像怎么没变小?”是最经典的镜像体积问题。答案在层的结构:每个 RUN 产生一层,删除只是在上面盖一层。这篇用 docker history、docker save 打开层的 tar 看到那个 0 字节的 whiteout 文件,并验证三种做法的体积差别。',
    [('+41.96 MB', '20 MiB 的随机文件先创建、下一层再删除后,镜像比基础镜像多出的 Size'), ('.wh.big.bin', '删除那一层里唯一的条目:0 字节的 whiteout 文件'), ('+0.01 MB', '多阶段构建只 COPY --from 一个小文件后,最终镜像比 alpine 多出的体积')],
    [('分两层与合并一层', '<p>两个 <code>RUN</code>(先 <code>dd</code>、再 <code>rm</code>):<code>docker history</code> 里 dd 那层 21MB,rm 那层 4.1kB,镜像 DISK USAGE 55.5MB。同一个 <code>RUN</code> 里 <code>dd &amp;&amp; rm</code>:只留下 4.1kB 的元数据层,镜像和 alpine 一样大。这个 Docker 的 <code>Size</code> 是压缩内容加解包后的层,随机数据压不动,所以 20 MiB 的层被算了两遍。</p>'),
     ('whiteout 是什么', '<p><code>docker save</code> 导出后,dd 那一层的 tar 里有 <code>big.bin</code>(20971520 字节),rm 那一层只有一个 0 字节的 <code>.wh.big.bin</code>。叠加文件系统看到 <code>.wh.</code> 前缀的条目,就把下层同名的文件隐藏起来——文件还在,只是看不见。</p>'),
     ('文件还在下层', '<p>把 Dockerfile 拆成两个阶段并单独构建到 gen 阶段,从那个镜像启动能 <code>ls</code> 到 20971520 字节的 <code>/big.bin</code>;最终镜像看不到它。所以任何曾经写进镜像的秘密或大文件,都会一直躺在某一层里,拿到镜像的人可以从层里取出来。</p>'),
     ('真正变小的办法', '<p>要么在同一个 <code>RUN</code> 里创建又删除(层里什么都不留),要么用多阶段构建把临时文件留在前一个阶段,只 <code>COPY --from</code> 需要的。后者的实验结果是 13.59 MB,比 alpine 只多 0.01 MB。</p>'),
     ('没测到的', '<p>压缩算法(gzip/zstd)对层大小的影响、不同的镜像存储(经典 overlay2 与 containerd 快照)对 <code>Size</code> 口径的影响、<code>docker build --squash</code>(下面会有专门一篇)都没有在本文实验。</p>')],
    steps,
    [ENV_C + '。随机文件由 dd if=/dev/urandom 生成;层的内容通过 docker save 导出的 tar 用 Python tarfile 解析;大小口径用 docker image inspect 的 Size 与 docker images 的 DISK USAGE / CONTENT SIZE;每种情形各一次;实验后已删除所有镜像',
     '没有验证:经典 overlay2 镜像存储下的 Size 口径(本机是 containerd 镜像存储)、zstd 压缩的层、OCI 与 Docker 格式 whiteout 的细微差别(opaque 目录在后面的文章)、镜像仓库里压缩后的真实传输大小'],
    '层与 whiteout')
