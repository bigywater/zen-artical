from lib import *
S = SS('c2')
steps = [
    step("没有 .dockerignore:目录里有 30 MiB 的 node_modules/big.bin,Dockerfile 是 COPY . /app。COPY 一步传输了 31.47MB,构建 1625 ms,镜像里的 /app 有 11 个文件——Dockerfile、README.md、build.log、build/out.bin、main.txt、node_modules/big.bin、notes.md、src/a.txt、src/b.log、src/build/inner.txt、tmp/x/y/temp,什么都带进来了。", t=tl(S(1)), mark=lidx(S(1), '31.47MB', '11 个文件'), kv=KV([['传输', '31.47 MB'], ['镜像里的文件', '11 个,含 30 MiB 的 big.bin'], ['用时', '1625 ms']], ['传输'])),
    step("写一个 .dockerignore(node_modules、*.log、/build、**/temp、*.md、!README.md):COPY 一步只传输 509B,构建 285 ms,镜像里 /app 剩 7 个文件。被忽略的是 build.log、build/out.bin、node_modules/big.bin、notes.md、tmp/x/y/temp。没被忽略的:src/b.log(`*.log` 只匹配根目录这一层)、src/build/inner.txt(`/build` 只匹配根目录的 build)、README.md(`!README.md` 把它加回来,后面的规则覆盖前面的)。", t=tl(S(2)), done=lidx(S(2), '509B', '被忽略的文件'), mark=lidx(S(2), '7 个文件', '说明'), b=bars([['无 .dockerignore:传输 (MB)', 31.47, '31.47'], ['有 .dockerignore:传输', 0.000509, '509 B']], 31.47, mark=[0], done=[1]), kv=KV([['`*.log`', '只管根目录这一层'], ['`/build`', '只匹配根目录的 build'], ['`**/temp`', '任意深度'], ['`!README.md`', '后一条规则覆盖前一条']], ['`*.log`'])),
    step("`**/*.log` 才匹配任意深度的 log 文件:换成这条规则后,镜像里没有任何 log 文件了。", t=tl(S(3)), mark=lidx(S(3), '(没有)'), kv=KV([['`**/*.log`', '匹配所有层级'], ['结果', '镜像里没有 log']], ['结果'])),
    step("忽略一个经常变化的文件可以让 COPY . 这一层保持缓存:只改 build.log 后再构建——不忽略它时,COPY 层重新执行(250 ms);在 .dockerignore 里忽略它时,COPY 层命中缓存 CACHED(235 ms)。", t=tl(S(4)), mark=lidx(S(4), '不忽略 build.log'), done=lidx(S(4), '忽略 build.log]'), kv=KV([['不忽略', 'COPY 层重新执行'], ['忽略', 'COPY 层 CACHED']], ['忽略'])),
    step("Dockerfile 与 .dockerignore 即使写进了 .dockerignore,COPY . 也不会把它们带进镜像:只有 .dockerignore(写了 Dockerfile、.dockerignore、b.txt)时,镜像里 /app 只有 ['./a.txt']。再加一个 Dockerfile.dockerignore(只写了 a.txt)后,它取代了 .dockerignore 而不是叠加:镜像里是 ['./.dockerignore', './Dockerfile', './Dockerfile.dockerignore', './b.txt']。", t=tl(S(5)), done=lidx(S(5), '只有 .dockerignore'), mark=lidx(S(5), 'Dockerfile.dockerignore'), kv=KV([['写了 Dockerfile', '它不会被 COPY 带进镜像'], ['Dockerfile.dockerignore', '取代 .dockerignore,不是叠加']], ['Dockerfile.dockerignore'])),
]
A = mkartc('c2', 2, 'Docker,dockerignore,构建上下文,构建缓存,BuildKit,真实验证,动画演示',
    '在 Docker Engine 29.8.2(BuildKit)里实测 .dockerignore:30 MiB 的 node_modules 不忽略时传输 31.47 MB,忽略后只传 509 B(285 ms 对 1625 ms);`*.log` 只管根目录、`/build` 只匹配根目录的 build、`**/` 才匹配任意深度、`!` 例外规则后者覆盖前者;忽略经常变化的文件让 COPY 层保持缓存;Dockerfile.dockerignore 取代 .dockerignore。',
    '.dockerignore 看起来只是“少传点文件”,但它同时决定了镜像里有什么、COPY 层的缓存能不能命中。它的匹配规则又不是 .gitignore 的那一套:`*.log` 只管根目录。这篇用一个故意塞满各种文件的目录,逐条验证规则的效果。',
    [('31.47 MB → 509 B', '30 MiB 的 node_modules 加入 .dockerignore 前后,COPY 一步的传输量'), ('只管根目录', '`*.log` 和 `/build` 只匹配上下文根目录这一层,src/b.log 与 src/build/ 都没被忽略'), ('取代而不是叠加', 'Dockerfile.dockerignore 存在时,.dockerignore 不再生效')],
    [('不写会怎样', '<p>没有 <code>.dockerignore</code>,<code>COPY . /app</code> 把 30 MiB 的 node_modules、日志、构建产物全带进镜像,上下文传输 31.47 MB,构建 1625 ms。</p>'),
     ('规则逐条看', '<p>写了 6 行规则后传输降到 509 B、285 ms:<code>node_modules</code> 与 <code>**/temp</code> 把目录整个忽略;<code>*.md</code> 之后的 <code>!README.md</code> 把 README 加回来(后面的规则覆盖前面的)。陷阱是 <code>*.log</code> 和 <code>/build</code> 只匹配根目录那一层,<code>src/b.log</code>、<code>src/build/inner.txt</code> 都还在镜像里。</p>'),
     ('任意深度要写 **', '<p><code>**/*.log</code> 才能忽略所有层级的 log。这和 .gitignore 的直觉不同,是最容易漏的地方。</p>'),
     ('缓存', '<p>只改了 <code>build.log</code>:不忽略它时 <code>COPY . /app</code> 层要重新执行,忽略它时这一层命中缓存。把日志、构建输出、临时文件加进 <code>.dockerignore</code>,能让依赖 <code>COPY .</code> 的后续层不被无关变化打断。</p>'),
     ('Dockerfile 自己', '<p>把 <code>Dockerfile</code> 和 <code>.dockerignore</code> 写进规则,<code>COPY .</code> 不会把它们带进镜像(它们仍然会被发给构建器)。每个 Dockerfile 可以有自己的 <code>Dockerfile.dockerignore</code>,它存在时完全取代 <code>.dockerignore</code>,实验里原来的规则一条都没生效。</p>')],
    steps,
    [ENV_C + '。上下文含 os.urandom 生成的 30 MiB 文件;镜像里的文件用 docker run … find 列出;缓存命中通过构建输出里 COPY 步骤的 CACHED 判断;每种情形各一次;实验后已删除所有镜像和临时目录',
     '没有验证:.dockerignore 里更复杂的 Go filepath.Match 语法(如 ? 和 [] )、规则很多时的匹配成本、符号链接的处理、docker compose 的 build 上下文、Docker 文档里对规则的描述(本机没有这份文档,规则全部来自实测)'],
    '.dockerignore')
