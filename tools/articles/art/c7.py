from lib import *
S = SS('c7')
steps = [
    step("ARG 与 ENV 在镜像里留下的痕迹。构建用 --build-arg TOKEN=abc123SECRET --build-arg VERSION=2.0。BuildKit 给出警告:SecretsUsedInArgOrEnv: Do not use ARG or ENV instructions for sensitive data (ARG \"TOKEN\") (line 2)。运行时:APP_MODE=prod(ENV 留下了),TOKEN 和 VERSION 都是空的(ARG 只在构建期存在);docker inspect 的 Config.Env 只有 PATH 和 APP_MODE。但是 docker history --no-trunc 里有 3 行含 abc123SECRET:RUN |2 TOKEN=abc123SECRET VERSION=2.0 /bin/sh -c echo \"版本 $VERSION\" …、RUN |2 TOKEN=abc123SECRET VERSION=2.0 /bin/sh -c echo \"构建时 TOKEN=$TOKEN\" …,以及 ARG TOKEN=abc123SECRET。docker save 导出的 tar 里有 1 个文件含这个字符串。", t=tl(S(1)), done=lidx(S(1), 'APP_MODE=prod', 'Config.Env'), mark=lidx(S(1), 'SecretsUsedInArgOrEnv', 'abc123SECRET', 'docker save'), kv=KV([['运行时环境变量', 'ENV 在,ARG 不在'], ['docker history', '三行含构建参数的明文值'], ['docker save 的 tar', '1 个文件含明文(配置 JSON)'], ['BuildKit 警告', '敏感数据别放 ARG / ENV']], ['docker history'])),
    step("ARG 的值是缓存键的一部分(每次运行前加了一个随机的 salt 层,避免命中之前的缓存)。什么都不变:第 3、4 步的 RUN 都 CACHED;只改 VERSION:两个 RUN 都重新执行,包括只用到 TOKEN 的那一个;只改 TOKEN:两个 RUN 同样都重新执行。", t=tl(S(2)), done=lidx(S(2), '什么都不变'), mark=lidx(S(2), '只改 VERSION', '只改 TOKEN'), b=bars([['什么都不变:重新执行的 RUN', 0, '0'], ['只改 VERSION', 2, '2'], ['只改 TOKEN', 2, '2']], 2, done=[0], mark=[1, 2]), kv=KV([['ARG 声明之后的所有 RUN', '缓存键里带着全部 ARG 的值'], ['改任意一个 ARG', '后面所有 RUN 都重做,即使它们没用到这个 ARG']], ['改任意一个 ARG'])),
    step("ARG 在 FROM 之前的作用域:`ARG BASE=alpine:3.20` 写在 FROM 之前,FROM ${BASE} 能用;FROM 之后的阶段里直接用 $BASE 得到空值(FROM 之后直接用 BASE=[]);在阶段里重新写一行 ARG BASE,才得到 alpine:3.20。", t=tl(S(3)), mark=lidx(S(3), 'FROM 之后直接用'), done=lidx(S(3), '重新声明'), kv=KV([['FROM 之前的 ARG', '只能给 FROM 用'], ['进入阶段后', '需要重新声明 ARG 才能用']], ['进入阶段后'])),
    step("ENV 可以在运行时覆盖:docker run -e APP_MODE=dev 之后容器里 APP_MODE=dev(镜像里写的是 prod)。", t=tl(S(4)), mark=lidx(S(4), 'APP_MODE=dev'), kv=KV([['ENV', '镜像里的默认值,docker run -e 可覆盖'], ['ARG', '构建完就没有了']], ['ENV'])),
]
A = mkartc('c7', 7, 'Docker,ARG,ENV,构建参数,密钥泄漏,构建缓存,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 ARG 与 ENV 留下的痕迹:ARG 运行时不存在,但 --build-arg 的明文值写进了 docker history(3 行)和镜像配置(docker save 的 tar 里 1 个文件含它),BuildKit 对敏感 ARG 给出警告;改任何一个 ARG 都会让它之后所有 RUN 的缓存失效;FROM 之前的 ARG 进入阶段后要重新声明才能用;ENV 可在运行时用 -e 覆盖。',
    '很多人以为 ARG 只在构建时可见、用完就消失,所以拿它传 token。这篇用一个故意传了假 token 的构建,把它留在了哪些地方一处处找出来,并验证 ARG 对构建缓存的影响。',
    [('3 行', 'docker history --no-trunc 里含有 --build-arg 明文值的行数'), ('2 个 RUN 都重做', '只改 VERSION 这个 ARG 时,连只用到 TOKEN 的 RUN 也重新执行'), ('空值', 'FROM 之后的阶段里没有重新声明 ARG 就读不到 FROM 之前声明的 ARG')],
    [('ARG 不是秘密', '<p>运行时环境变量里确实没有 <code>TOKEN</code>,但镜像的构建历史把它写得清清楚楚:<code>RUN |2 TOKEN=abc123SECRET VERSION=2.0 …</code> 和 <code>ARG TOKEN=abc123SECRET</code>,而且 <code>docker save</code> 导出的配置里也有。拿到镜像的人不需要运行它。BuildKit 构建时自己就警告 <code>SecretsUsedInArgOrEnv</code>。需要在构建期使用密钥,用下面会讲的 <code>--mount=type=secret</code>。</p>'),
     ('ARG 与缓存', '<p>ARG 声明之后的每个 <code>RUN</code>,缓存键里都带着所有 ARG 的值(<code>history</code> 里的 <code>|2 TOKEN=… VERSION=…</code> 前缀)。所以改任何一个 ARG,后面所有 <code>RUN</code> 都要重新执行,哪怕有的 <code>RUN</code> 根本没用到它。把经常变化的 ARG(比如构建号)放在 Dockerfile 的靠后位置。</p>'),
     ('作用域', '<p>写在 <code>FROM</code> 之前的 ARG 只能用在 <code>FROM</code> 行本身,进入阶段后得到空值,要在阶段里再写一行 <code>ARG BASE</code> 才能用。</p>'),
     ('ENV', '<p>ENV 会一直留在镜像配置里并成为容器环境变量,<code>docker run -e</code> 可以覆盖。放默认配置可以,放密钥不行(<code>docker inspect</code> 能直接看到,环境变量泄漏那一篇会专门验证)。</p>')],
    steps,
    [ENV_C + '。假的 token 字符串 abc123SECRET;docker history --no-trunc、docker inspect、docker save + Python tarfile 搜索字符串;缓存判断来自构建输出里各 RUN 步骤的 CACHED;每次运行前加了一个带时间戳的 RUN 层避免命中之前实验的缓存;实验后已删除所有镜像',
     '没有验证:多阶段构建中 ARG 是否泄漏到最终阶段的镜像历史(各阶段的 history 不同)、docker buildx imagetools 看 provenance 里是否记录 build-arg、预定义 ARG(HTTP_PROXY、TARGETARCH 等)、层压缩(squash)后历史是否还在'],
    'ARG 与 ENV')
