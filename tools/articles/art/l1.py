from lib import *
S = SS('l1')
steps = [
    step("两次提交(第二次只改了 README)之后 .git/objects 里恰好 8 个文件:2 个 commit、3 个 tree(第一次的根、src/、第二次的根)、3 个 blob(README 的两个版本加 main.py)。文件名是 hash 的前 2 位当目录名、后 38 位当文件名;git log 里看到的 f9b1362 和 4591541 就是其中两个文件名的开头。", t=tl(S(1)), mark=lidx(S(1), 'f9b1362', '4591541', 'wc -l'), done=lidx(S(1), 'find .git/objects -type f | sort'), kv=KV([['对象总数', '8 = 2 commit + 3 tree + 3 blob'], ['路径规则', 'objects/<hash 前 2 位>/<后 38 位>'], ['内容相同不重复', 'src/ 在两次提交里是同一个 tree']], ['对象总数'])),
    step("拿 src/main.py 的 blob 来解压:磁盘上的文件只有 28 字节,zlib 解压后 20 字节,前 8 字节是头部 blob 12 加一个 NUL(0x00),后 12 字节才是 print(\"hi\") 加换行。文件内容本身只有 12 字节,头部加压缩的固定开销让这个小文件在磁盘上反而比内容大。git cat-file -t / -s / -p 分别给出类型、长度、内容,和手工解压的结果一致。", t=tl(S(2)), mark=lidx(S(2), 'blob 12', '0000  62 6c 6f 62'), done=lidx(S(2), '28 字节', 'git cat-file -t'), b=bars([['文件内容', 12, '12 字节'], ['解压后(含头部)', 20, '20 字节'], ['磁盘上(zlib)', 28, '28 字节']], 28, mark=[1], done=[0, 2]), kv=KV([['头部', '"blob 12\\0":类型 + 空格 + 长度 + NUL'], ['内容', '原样的文件字节,没有任何包装'], ['磁盘大小', '小文件被压缩后可能比原内容还大']], ['头部'])),
    step("tree 对象解压后 75 字节:头部 tree 67 说明后面有 67 字节。每个条目是“模式 空格 名字 NUL 20 字节二进制 hash”,条目之间没有任何分隔符,靠 NUL 和固定的 20 字节切分。两个条目:100644 README.md 与 src;注意 src 的模式在 tree 里存成 40000(少一个前导 0),git ls-tree 显示时才补成 040000。hash 是 20 字节原始二进制,不是 40 个十六进制字符。", t=tl(S(3)), mark=lidx(S(3), '条目 1', '条目 2'), done=lidx(S(3), '头部: tree 67', 'git ls-tree'), kv=KV([['条目格式', '模式 名字\\0 20 字节二进制 hash'], ['目录的模式', 'tree 里存 40000,ls-tree 显示 040000'], ['hash 长度', '20 字节原始值,不是 40 位文本']], ['条目格式'])),
    step("commit 对象是纯文本,解压后 226 字节:tree 行指向根 tree,parent 行指向上一次提交,author 与 committer 各一行(名字、邮箱、Unix 时间戳、时区),然后一个空行,后面是提交说明。第一次提交没有 parent 行。git cat-file -p HEAD 打印的就是这段文本本身。", t=tl(S(4)), mark=lidx(S(4), '| tree 0152', '| parent 4591', '| author', '| committer'), done=lidx(S(4), '头部: commit 215', 'git cat-file -p HEAD'), kv=KV([['tree', '本次提交的根目录快照'], ['parent', '上一个 commit,首次提交没有'], ['author / committer', '名字 邮箱 时间戳 时区'], ['空行之后', '提交说明']], ['tree'])),
    step("完全不用 git:读 .git/HEAD 得到 ref: refs/heads/main,读这个 ref 文件得到 commit 的 hash,解压 commit 取出 tree 行,递归解压 tree,遇到模式 40000 就继续往下走,最后得到的两个文件(100644 README.md 与 src/main.py,hash 一致)与 git ls-tree -r HEAD 逐行相同。整个读取过程只用了 zlib 解压和按字节切分。", t=tl(S(5)), mark=lidx(S(5), '.git/HEAD', 'refs/heads/main: f9b1'), done=lidx(S(5), 'Python 走出来的', '完全一致'), kv=KV([['HEAD', 'ref: refs/heads/main(符号引用)'], ['ref 文件', '40 位 commit hash'], ['验证', '手写解析结果与 ls-tree -r 完全一致']], ['验证'])),
]
A = mkarti('l1', 1, 'Git,对象存储,blob,tree,commit,zlib,真实验证,动画演示',
    '在真实的 git 2.54.0 仓库里手工解开 .git/objects:blob 是“blob 长度\\0内容”,tree 是模式、名字、20 字节二进制 hash 的连续条目,commit 是几行头加说明的纯文本;只用 Python 的 zlib 沿 HEAD 往下走一遍,结果与 git ls-tree -r 完全一致。',
    '.git/objects 里那些名字像乱码的文件到底是什么?这篇用 zlib 把松散对象逐个解压,看原始字节:blob 的头部与内容、tree 里没有分隔符的二进制条目、commit 的纯文本结构,最后不用 git 命令,自己从 HEAD 走到每个文件。',
    [('8 个', '两次提交共 8 个对象:2 个 commit、3 个 tree、3 个 blob'), ('20 字节', 'tree 条目里每个 hash 是 20 字节二进制,而不是 40 位十六进制文本'), ('完全一致', '只用 zlib 手工解析 HEAD→tree→blob,与 git ls-tree -r 的输出逐行相同')],
    [('松散对象的路径', '<p>每个对象是 <code>.git/objects/</code> 下的一个文件,路径由 hash 决定:前 2 位十六进制当目录名,后 38 位当文件名。内容相同的对象 hash 相同,所以只存一份——第二次提交没碰 <code>src/</code>,它的 tree 与 blob 就直接复用,对象总数才只有 8 个。</p>'),
     ('blob:头部加原始字节', '<p>松散对象是 zlib 压缩的。解压后固定是“类型 空格 长度 NUL 内容”,blob 的内容就是文件的原始字节,不带文件名,也不带权限。很小的文件经过头部和压缩的固定开销,磁盘上的文件可以比内容还大。</p>'),
     ('tree:没有分隔符的二进制', '<p>tree 对象把目录里每个条目写成“模式 空格 名字 NUL 20 字节二进制 hash”,条目首尾相接。目录模式在这里是 <code>40000</code>,<code>git ls-tree</code> 显示时才补成 <code>040000</code>。因为 hash 是原始字节,直接用文本编辑器看 tree 对象会是乱码。</p>'),
     ('commit:纯文本', '<p>commit 对象是几行头部加空行加提交说明:<code>tree</code>、<code>parent</code>(可以有零个、一个或多个)、<code>author</code>、<code>committer</code>。所谓“提交”就是这样一段文本,它指向某个目录快照和上一个提交。</p>'),
     ('从 HEAD 走到文件', '<p><code>HEAD</code> 是一个符号引用,指向 <code>refs/heads/main</code> 这个文件,文件里是 commit 的 hash;commit 里的 tree 行、tree 里的条目一层层往下,就能走到每个 blob。整个 git 的读取就是这条链。</p>')],
    steps,
    [ENV_I_GIT + '。第五节的 Python 解析只用 zlib 与字节切分,没有调用 git;所有 hash 因作者、时间固定而可复现',
     '没有验证:对象存在 packfile 里时的读取方式(见后面 packfile 的文章);SHA-256 仓库里的 hash 长度(32 字节,后面单独一篇);带符号链接、子模块的 tree 条目(下一篇有四种模式);GPG 签名提交多出来的 gpgsig 头'],
    '手工解开对象')
