from lib import *
S = SS('l7')
steps = [
    step("两个仓库内容完全相同。sha256 仓库用 git init --object-format=sha256 创建:git rev-parse --show-object-format 输出 sha256,本地配置里多了 extensions.objectformat=sha256,同时 core.repositoryformatversion 从 0 变成 1(版本 1 才允许有 extensions)。sha1 仓库只有 repositoryformatversion=0。", t=tl(S(1)), mark=lidx(S(1), 'extensions.objectformat=sha256', 'core.repositoryformatversion=1'), done=lidx(S(1), '[sha1]', '[sha256]', 'core.repositoryformatversion=0'), kv=KV([['object-format', '创建仓库时决定,之后不能改'], ['配置', 'extensions.objectformat=sha256'], ['repositoryformatversion', '0 → 1']], ['object-format'])),
    step("同样 10 个文件的提交:sha1 仓库的 HEAD 是 5bda956e…(40 位十六进制),sha256 仓库是 21e5ed72…(64 位)。松散对象路径变成 objects/95/ 加 62 位的文件名。git log 默认缩写仍是 7 位(21e5ed7),--abbrev=10 就是 21e5ed7262。", t=tl(S(2)), mark=lidx(S(2), '64 位十六进制', '.git/objects/95/af096e'), done=lidx(S(2), '40 位十六进制', 'git log --oneline'), b=bars([['sha1 的 hash', 40, '40 位'], ['sha256 的 hash', 64, '64 位']], 64, mark=[1], done=[0]), kv=KV([['SHA-1', '40 位十六进制,20 字节'], ['SHA-256', '64 位十六进制,32 字节'], ['松散对象文件名', '前 2 位目录 + 后 62 位']], ['SHA-256'])),
    step("公式没有变,只是换了哈希函数:sha256 仓库里 f03.txt 的 blob 是 a35f338c…;用 hashlib.sha256 对 \"blob 长度\\0内容\" 手算,得到完全相同的值。", t=tl(S(3)), mark=lidx(S(3), '一致: True'), done=lidx(S(3), 'git:  a35f', '手算: a35f'), kv=KV([['公式', 'SHA-256("blob 长度\\0内容")'], ['验证', '手算与 git 一致']], ['验证'])),
    step("tree 条目里的 hash 从 20 字节变成 32 字节:同样 10 个条目,sha1 的 tree 解压后 359 字节(头部 tree 350),sha256 的 479 字节(tree 470)。每个条目多 12 字节,10 个条目多 120 字节。", t=tl(S(4)), mark=lidx(S(4), '[sha256]'), done=lidx(S(4), '[sha1]'), b=bars([['sha1 的 tree', 359, '359 字节'], ['sha256 的 tree', 479, '479 字节']], 479, mark=[1], done=[0]), kv=KV([['条目 hash', '20 字节 → 32 字节'], ['10 个条目', '多 120 字节(359 → 479)']], ['条目 hash'])),
    step("代价:同样 10 个文件的暂存区 .git/index,sha1 是 786 字节,sha256 是 970 字节(每个条目多 12 字节,加上末尾校验和多 12 字节,共 184 字节);tree 对象 359 → 479 字节。体积变化很小,不是选择的主要考虑。", t=tl(S(5)), mark=lidx(S(5), '[sha256]'), done=lidx(S(5), '[sha1]'), b=bars([['sha1 的 index', 786, '786 字节'], ['sha256 的 index', 970, '970 字节']], 970, mark=[1], done=[0]), kv=KV([['index', '786 → 970 字节'], ['tree', '359 → 479 字节'], ['结论', '体积影响很小']], ['结论'])),
    step("两种格式不能互通:sha1 仓库去 fetch sha256 仓库报 fatal: mismatched algorithms: client sha1; server sha256,反过来也一样。git clone 一个 sha256 仓库则能直接得到 sha256 的副本(rev-parse --show-object-format 为 sha256),clone 会自动采用服务器的格式。已有的 sha1 仓库不能就地转换成 sha256。", t=tl(S(6)), mark=lidx(S(6), 'mismatched algorithms: client sha256', 'mismatched algorithms: client sha1'), done=lidx(S(6), 'git clone -q'), kv=KV([['fetch', '算法不同直接 fatal'], ['clone', '自动采用服务器的算法'], ['转换', '不能就地转换']], ['fetch'])),
]
A = mkarti('l7', 7, 'Git,SHA-256,object-format,对象模型,真实验证,动画演示',
    '在真实 git 2.54.0 里创建 --object-format=sha256 仓库并与 sha1 仓库对比:repositoryformatversion 变成 1,hash 40 位变 64 位,blob 公式换成 SHA-256 手算一致,tree 条目的 hash 20 字节变 32 字节(10 个文件 359 → 479 字节),index 786 → 970 字节;两种仓库之间 fetch 直接报 mismatched algorithms。',
    'SHA-256 仓库和普通仓库有什么不同?这篇在同一份内容上创建两种仓库,对比配置、hash 长度、tree 和 index 的字节数,手算 SHA-256 的 blob hash,最后试试两种仓库能不能互相 fetch。',
    [('64 位', 'SHA-256 仓库的 hash 长度(SHA-1 是 40 位)'), ('359 → 479', '同样 10 个文件,tree 对象解压后的字节数'), ('mismatched', '两种格式互相 fetch 的结果:fatal: mismatched algorithms')],
    [('创建时决定', '<p><code>git init --object-format=sha256</code> 决定整个仓库的哈希算法,写进 <code>extensions.objectformat</code>,并把 <code>core.repositoryformatversion</code> 提到 1。之后无法改变。</p>'),
     ('hash 变长', '<p>hash 从 40 位十六进制变成 64 位,松散对象的文件名也变成“2 位目录加 62 位文件名”。<code>git log</code> 的默认缩写仍然是 7 位。</p>'),
     ('公式不变', '<p>对象格式没有变,仍是“类型 长度 NUL 内容”,只是换了 SHA-256。手算 blob 的 hash 与 git 一致。</p>'),
     ('体积', '<p>tree 条目的 hash 从 20 字节变成 32 字节,10 个条目的 tree 从 359 字节变成 479 字节;索引文件也相应变大。仓库里 hash 出现的地方都会变大,但相对于文件内容本身通常很小。</p>'),
     ('索引与对象总大小', '<p>同样 10 个文件,<code>.git/index</code> 从 786 字节增加到 970 字节。</p>'),
     ('互不兼容', '<p>两种仓库之间不能 fetch / push,会立刻报 <code>mismatched algorithms</code>。clone 一个 sha256 的远程会自动得到 sha256 的本地仓库。这就是 SHA-256 仓库在实际使用中要考虑的最大障碍:服务器、客户端和工具链都要支持。</p>')],
    steps,
    [ENV_I_GIT + '。两个仓库内容与作者时间完全相同;字节数是对象解压后的长度和 .git/index 文件大小',
     '没有验证:compatObjectFormat(两种哈希之间的映射,新版本的过渡功能,本文没有启用);主流托管服务和各种工具对 SHA-256 仓库的支持;SHA-256 的性能与 SHA-1(SHA1_DC)的比较;在 sha256 仓库里使用 GPG / SSH 签名的行为'],
    'SHA-256 仓库')
