from lib import *
S = SS('c1')
steps = [
    step("上下文里放一个 50 MiB 的无关随机文件 big.bin,外加 app.txt 和 sub/x.txt。Dockerfile 只写 COPY app.txt /app.txt:BuildKit 的 [internal] load build context 只传了 40B,整个构建 564 ms;改成 COPY . /ctx/:传了 52.44MB(0.5s),构建 1923 ms。#3 transferring context: 2B 是读取 .dockerignore。", t=tl(S(1)), done=lidx(S(1), '只 COPY app.txt', 'transferring context: 40B'), mark=lidx(S(1), 'COPY . /ctx/]', '52.44MB'), b=bars([['只 COPY app.txt:传输 (字节)', 40, '40 B'], ['COPY . /ctx/:传输', 52440000, '52.44 MB']], 52440000, done=[0], mark=[1]), kv=KV([['只 COPY 一个小文件', '传输 40 B'], ['COPY .', '传输 52.44 MB'], ['含义', 'BuildKit 只传 Dockerfile 实际用到的文件']], ['含义'])),
    step("同一个上下文再构建一次(没有任何改动):transferring context 只有 137B,COPY 那一步显示 CACHED,构建用时 304 ms。", t=tl(S(2)), mark=lidx(S(2), '第 2 次', '137B'), done=lidx(S(2), 'CACHED'), kv=KV([['第 2 次传输', '137 B(推测是元数据比对)'], ['COPY 层', 'CACHED'], ['用时', '304 ms,对比第 1 次 1923 ms']], ['第 2 次传输'])),
    step("改动一个小文件(app.txt 改了内容)后再构建:transferring context 只有 155B——50 MiB 的大文件没有重传(它没变);COPY . 这一层因为目录内容变了需要重做,构建用时 1450 ms。", t=tl(S(3)), mark=lidx(S(3), '改了 app.txt', '155B'), kv=KV([['传输', '155 B,不是 52 MB'], ['COPY 层', '内容变了,必须重建(1450 ms)']], ['传输'])),
    step("不给上下文(Dockerfile 从标准输入读):Dockerfile 里 COPY app.txt,退出码 1,错误是 failed to calculate checksum of ref <id>: \"/app.txt\": not found。没有上下文,COPY 就找不到任何文件。", t=tl(S(4)), mark=lidx(S(4), '退出码 1'), kv=KV([['docker build -', '没有上下文'], ['COPY', '报 \"/app.txt\": not found']], ['docker build -'])),
    step("Dockerfile 想 COPY 上下文目录之外的文件(COPY ../secret.txt /secret.txt):退出码 1,错误是 \"/secret.txt\": not found——`..` 不会让它走出上下文,只是被当成上下文根目录下的路径,所以找不到。", t=tl(S(5)), mark=lidx(S(5), '退出码 1'), kv=KV([['COPY ../secret.txt', 'not found,不会泄露上下文外的文件'], ['含义', '上下文是 COPY 能看到的全部世界']], ['含义'])),
    step("用 -f 指定上下文之外的 Dockerfile:Dockerfile 放在别处(97B),上下文是最后那个目录参数;构建成功,退出码 0,用时 209 ms。上下文和 Dockerfile 的位置是两回事。", t=tl(S(6)), mark=lidx(S(6), '退出码 0', 'transferring dockerfile: 97B'), kv=KV([['-f', '指定 Dockerfile 位置'], ['最后一个参数', '决定上下文']], ['最后一个参数'])),
]
A = mkartc('c1', 1, 'Docker,构建上下文,BuildKit,docker build,COPY,真实验证,动画演示',
    '在 Docker Engine 29.8.2(BuildKit)里实测构建上下文:目录里有 50 MiB 的无关文件,Dockerfile 只 COPY 一个小文件时只传输 40 B(564 ms),COPY . 时传输 52.44 MB(1923 ms);再构建一次传输只有 137 B 且命中缓存;改一个小文件只传 155 B;没有上下文或想 COPY 上下文之外的文件都会 not found。',
    '很多人以为 docker build 会把整个目录打包发给守护进程。BuildKit 其实只传 Dockerfile 里用到的文件,而且是增量的。这篇用一个带 50 MiB 无关文件的目录实测:到底传了多少、第二次传了多少、改一个文件传了多少,以及上下文之外的东西为什么够不着。',
    [('40 B vs 52.44 MB', '同一个目录,Dockerfile 只 COPY 一个小文件与 COPY . 的上下文传输量'), ('137 B', '什么都没改时,再次构建传输的上下文大小'), ('155 B', '改了一个小文件之后,重新构建传输的上下文大小(大文件没有重传)')],
    [('只传用到的文件', '<p>BuildKit 的 <code>[internal] load build context</code> 一步,在 Dockerfile 只 <code>COPY app.txt</code> 时只传了 40 B,尽管目录里有 50 MiB 的随机文件;改成 <code>COPY .</code> 才传 52.44 MB。所以“上下文很大导致构建慢”主要发生在 <code>COPY .</code> 这类写法上。</p>'),
     ('增量传输', '<p>再构建一次,上下文传输只有 137 B(我推测只是比对了文件元数据,没有验证),COPY 层 CACHED,304 ms;改了 <code>app.txt</code> 后传输 155 B,50 MiB 的大文件没重传。但 <code>COPY . /ctx/</code> 这一层因为目录内容变了仍要重做,1450 ms。</p>'),
     ('上下文之外的世界', '<p>用 <code>docker build -</code> 从标准输入读 Dockerfile 没有上下文,<code>COPY</code> 找不到文件;<code>COPY ../secret.txt</code> 也出不了上下文,报的是 “not found”。用 <code>-f</code> 可以把 Dockerfile 放在别处,上下文由最后一个目录参数决定。</p>'),
     ('没测到的', '<p>压缩传输、远程上下文(git URL)、<code>.dockerignore</code> 的影响(下一篇)和旧的非 BuildKit 构建器都没有在本文实验。</p>'),
     ('怎么读构建输出', '<p><code>--progress plain</code> 输出里,<code>transferring context: N</code> 前面的编号对应哪一步,<code>#3</code> 是读取 <code>.dockerignore</code>,<code>[internal] load build context</code> 才是真正传文件的那一步。</p>'),
     ('小结', '<p>上下文的成本是“Dockerfile 用到的文件”的成本,而不是“目录有多大”。真正要避免的是 <code>COPY . .</code> 这种把一切都纳入的写法,以及这一层随便一个文件变化都要重建的后果。</p>')],
    steps,
    [ENV_C + '。构建上下文是 dtmp 下的临时目录,含一个 os.urandom 生成的 50 MiB 文件;用 docker build --progress plain 的输出读传输量;每种情形只运行一次;实验后已删除所有镜像和临时目录',
     '没有验证:旧版构建器、git/tar URL 作为上下文、.dockerignore 的影响、Docker Desktop 里宿主机到虚拟机的文件共享对上下文传输的影响、多阶段构建里 COPY --from 的传输、构建缓存被清空后的首次传输'],
    '构建上下文')
