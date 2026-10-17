from lib import *
S = SS('l2')
steps = [
    step("blob 的 hash 公式:SHA-1(\"blob \" + 内容长度 + NUL + 内容)。三个内容(带换行的 hello world、不带换行的 hello world、空内容)手算的结果都和 git hash-object 完全一致;用 shell 的 printf 加 shasum -a 1 也能复现 3b18e51…。如果漏掉头部直接对内容算 SHA-1,得到 2259636…,git 里没有任何对象是这个 hash。空文件的 blob 是 e69de29…,空 tree 是 4b825dc…,这两个常数在 git 世界里随处可见。", t=tl(S(1)), mark=lidx(S(1), '22596363', 'printf', 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391', '4b825dc642cb'), done=lidx(S(1), '内容 \'hello world\\n\'', '一致=True'), kv=KV([['公式', 'SHA-1("blob " + 长度 + "\\0" + 内容)'], ['漏掉头部', '得到 git 里不存在的 hash'], ['空 blob', 'e69de29…'], ['空 tree', '4b825dc…']], ['公式'])),
    step("tree 和 commit 用同一个公式,只是内容更复杂。手算:sub/ 的 tree(一个条目 100644 b.txt 加 20 字节二进制 hash)得到 45785ef…,与 git 一致;再把它和 a.txt 拼成根 tree,得到 0b2908b…,与 git write-tree 一致;最后拼出 commit 文本(tree 行、author、committer、空行、说明),算出的 6ee12d6… 与 git commit 真实产生的 hash 逐位相同。注意 tree 里用的是 40000 而不是 040000。", t=tl(S(2)), mark=lidx(S(2), '手算 sub/', '手算根 tree'), done=lidx(S(2), '手算 commit', '一致= True'), kv=KV([['tree', '按条目拼接后加头 "tree 长度\\0"'], ['commit', '文本整体加头 "commit 长度\\0"'], ['结论', '三种对象、一个公式']], ['结论'])),
    step("改一个字节(world 的最后一个字母 d 改成 D):3b18e51… 变成 4c7ace6…,160 位里有 86 位不同(54%),约等于随机。而同样内容 same 的三个文件,不管叫 one.txt、放在 dir/two.txt,还是有可执行权限的 x.sh,blob 的 hash 都是 1275430…,文件名和权限不在 blob 里,它们记录在 tree 的条目中(100644 / 100755)。", t=tl(S(3)), mark=lidx(S(3), '86 位', 'x.sh'), done=lidx(S(3), 'hello world\\n :', 'dir/two.txt', 'one.txt'), b=bars([['改一个字节后不同的位', 86, '86 / 160 位']], 160, mark=[0]), kv=KV([['改一个字节', '约一半的位翻转'], ['改文件名 / 权限', 'blob 的 hash 不变'], ['名字和权限', '记录在 tree 的条目里']], ['改一个字节'])),
    step("同样的 12 个字节 hello world 加换行,放进四种对象类型,hash 完全不同:blob 3b18e51…、tree f6b9a70…、commit 5c0b41f…、tag 9848898…。类型名是头部的第一个词,会进入 hash,所以不可能把一个 blob 冒充成同内容的 tree 或 commit。", t=tl(S(4)), mark=lidx(S(4), '类型 tree', '类型 commit', '类型 tag'), done=lidx(S(4), '类型 blob'), kv=KV([['类型', '头部的第一个词,进入 hash'], ['同内容异类型', 'hash 各不相同'], ['作用', '防止类型混淆']], ['类型'])),
    step("这台机器的 git 构建选项显示 SHA-1: SHA1_DC(检测碰撞攻击的实现)、SHA-256: SHA256_BLK、default-hash: sha1。按生日界估算,160 位 hash 要约 2^80(1.21e24)个对象才有一半概率撞车;1 亿个对象里出现一对随机碰撞的概率约 3.42e-33。这是随机碰撞的数学估算;有预谋的攻击是另一回事,所以才有 SHA1_DC 和 SHA-256 仓库。", t=tl(S(5)), mark=lidx(S(5), 'SHA1_DC', '3.42e-33'), done=lidx(S(5), 'SHA256_BLK', '2^80'), kv=KV([['SHA-1 实现', 'SHA1_DC,检测已知的碰撞构造'], ['随机碰撞', '1 亿对象时约 3.4e-33'], ['默认哈希', 'sha1(可选 sha256 仓库)']], ['SHA-1 实现'])),
]
A = mkarti('l2', 2, 'Git,SHA-1,hash-object,对象模型,真实验证,动画演示',
    '用 Python 的 hashlib 手算 git 的 hash:blob 是 SHA-1("blob 长度\\0内容"),tree 与 commit 同一公式,手算结果与 git hash-object、write-tree、commit 全部一致;改一个字节 160 位里有 86 位翻转;同内容不同文件名或权限的 blob hash 相同;同样 12 字节放进四种对象类型得到四个不同的 hash。',
    'git 的 hash 到底是怎么算出来的?这篇不靠记忆,直接用 hashlib 和 shasum 手算 blob、tree、commit 的 hash,逐个对照 git 的真实输出,再看改一个字节、换文件名、换对象类型分别会怎样。',
    [('3 种对象', 'blob、tree、commit 的 hash 都用同一个公式手算,与 git 的结果逐位一致'), ('86 / 160 位', '内容只改一个字节,SHA-1 的 160 位里翻转的位数'), ('3.42e-33', '1 亿个对象里出现一对随机碰撞的估算概率')],
    [('公式', '<p>git 对象的 hash 是对“类型 空格 长度 NUL 内容”整体做 SHA-1。blob 的内容是文件字节,tree 的内容是拼接好的条目,commit 的内容是那段文本。头部里的长度是内容的字节数,不含头部本身。漏掉头部直接算内容的 SHA-1,得到的值在 git 里不存在。</p>'),
     ('tree 与 commit', '<p>tree 的内容里每个条目的 hash 是 20 字节二进制,目录模式写成 <code>40000</code>;commit 的内容是 tree、parent、author、committer 几行加空行加说明。先算出子对象的 hash,才能算出父对象的 hash——这就是 git 的 Merkle 结构。作者与时间戳固定后 commit 的 hash 是可复现的。</p>'),
     ('雪崩与“内容决定身份”', '<p>改一个字节,约一半的位翻转;而文件名、目录位置、可执行权限都不属于 blob,所以内容相同的文件天然共用一个 blob。名字和权限由 tree 条目记录。</p>'),
     ('类型进入 hash', '<p>同样的字节放进 blob、tree、commit、tag,头部不同,hash 不同,所以对象类型无法被混淆。</p>'),
     ('SHA-1 够不够', '<p>随机碰撞的概率在实际仓库规模下可以忽略;真正的风险是人为构造的碰撞,因此 git 使用检测碰撞特征的 SHA1_DC 实现,并提供 SHA-256 仓库(见后面的文章)。</p>')],
    steps,
    [ENV_I_GIT + '。手算部分用 Python hashlib 与 shasum,不调用 git;git 的真实值来自 git hash-object / write-tree / commit;“碰撞概率”是公式估算 n²/2^161,不是实验测得',
     '没有验证:SHAttered 等真实的碰撞样本被 SHA1_DC 拒绝的行为(没有下载样本);SHA-256 仓库的 hash 计算(下一篇之后单独验证);tag 对象的内容格式(后面有注解标签一篇)'],
    'hash 的手算')
