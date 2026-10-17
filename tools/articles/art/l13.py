from lib import *
S = SS('l13')
steps = [
    step("5 个提交(每次改 doc.txt 的一行)git gc 之后,对象库里只剩一个 pack(.pack、.idx、.rev 三个文件),松散对象 count: 0,in-pack: 15。pack 文件开头 12 字节:50 41 43 4b 是 \"PACK\",00 00 00 02 是版本 2,00 00 00 0f 是对象数 15;整个文件 4,888 字节。", t=tl(S(1)), mark=lidx(S(1), '0000  50 41 43 4b', '版本 2,对象数 15'), done=lidx(S(1), 'in-pack: 15', 'count: 0'), kv=KV([['魔数', '"PACK"'], ['版本', '2'], ['对象数', '4 字节大端整数:15']], ['魔数'])),
    step("逐个解析条目:每个条目先是 1 个或几个头部字节——高位是继续标志,接着 3 位类型、4 位大小,后续字节每个补 7 位大小——然后是 zlib 压缩的数据。15 个条目依次是 5 个 commit(偏移 12~573)、1 个 blob(偏移 685,解压后 7998 字节、包内 3846 字节)、若干 tree,以及 4 个 delta。我自己解析的大小、偏移、包内大小和 git verify-pack -v 的同一行完全一致;delta 条目解压后很小(12、17、22、12 字节),verify-pack 把它们还原成 blob 并标出深度。", t=tl(S(2)), mark=lidx(S(2), 'ofs-delta', '685  blob'), done=lidx(S(2), '12  commit', '152  commit', '292  commit', '433  commit', '573  commit'), kv=KV([['头部', '类型 3 位 + 大小变长整数'], ['数据', 'zlib 压缩'], ['对照', '偏移、大小、包内大小与 verify-pack 一致']], ['对照'])),
    step("OFS_DELTA 的头部后面多一个“向后偏移量”,指向基础对象:偏移 4623、4692、4768 的三个 delta 都以偏移 685 的 blob 为基础(向后 3938、4007、4083 字节);偏移 4846 的以 4768 的 delta 为基础(向后 78 字节),所以 verify-pack 里它的深度是 2。完整存放的 blob 恰好是最新版本(HEAD:doc.txt),旧版本都存成对它的 delta——最常被读取的版本不需要还原。", t=tl(S(3)), mark=lidx(S(3), '偏移 4846', '最新版本'), done=lidx(S(3), '偏移 4623', '偏移 4692', '偏移 4768'), kv=KV([['OFS_DELTA', '用向后偏移指向基础对象'], ['REF_DELTA', '用基础对象的 hash 指向(类型 7)'], ['基础', '可以是另一个 delta(深度 2)'], ['谁是基础', '本例是最新版本']], ['谁是基础'])),
    step("解开偏移 4623 的 delta:delta 本体只有 12 字节,先是源长度 7998、目标长度 7986 两个变长整数,然后两条 copy 指令:copy 源[0:4276] 和 copy 源[4288:7998]——中间被跳过的 12 个字节就是这个版本比最新版本少的那行改动。应用后的内容重新按“blob 长度\\0内容”做 SHA-1,得到 cb2faa7…,与 verify-pack 列出的完全相同;全部 15 个对象(含 4 个 delta)还原后都一致。", t=tl(S(4)), mark=lidx(S(4), 'copy 源[0:4276]', 'copy 源[4288:7998]'), done=lidx(S(4), 'delta 本体 12 字节', '重建出的 blob 的 sha', '全部 15 个对象'), kv=KV([['delta 本体', '源长度、目标长度、指令序列'], ['copy', '从基础对象复制一段(偏移 + 长度)'], ['insert', '直接带上新内容'], ['验证', '还原后 sha 与 verify-pack 一致']], ['验证'])),
    step("pack 文件最后 20 字节是前面全部内容的 SHA-1:尾部 b125bfd…,我对前面内容重新计算得到完全相同的值,pack 的文件名 pack-b125bfd….pack 里的 hash 也是它。git verify-pack 通过。", t=tl(S(5)), mark=lidx(S(5), '尾部', '重新算', '文件名'), done=lidx(S(5), 'verify-pack 通过'), kv=KV([['末尾 20 字节', '整个 pack 内容的 SHA-1'], ['文件名', 'pack-<这个 hash>.pack'], ['校验', 'verify-pack / index-pack']], ['末尾 20 字节'])),
]
A = mkarti('l13', 13, 'Git,packfile,delta,OFS_DELTA,gc,真实验证,动画演示',
    '用 Python 逐字节解析真实的 packfile:12 字节头部(PACK、版本 2、对象数)、每个条目的类型与大小变长整数、zlib 数据;OFS_DELTA 的向后偏移指向基础对象(最新版本完整存放,旧版本存成 delta);按 copy / insert 指令还原 delta,15 个对象的 sha 全部与 git verify-pack 一致;末尾 20 字节是整个 pack 的 SHA-1。',
    'packfile 里到底是什么?这篇不用 git 命令,而是用 Python 逐字节解析一个真实的 pack:文件头、每个对象条目的头部编码、OFS_DELTA 的偏移,甚至自己按 copy / insert 指令把 delta 还原,最后和 git verify-pack 对账。',
    [('15 / 15', '手工解析并还原的对象,sha 与 git verify-pack 一致的个数'), ('12 字节', '一个 delta 条目的本体大小,还原出 7986 字节的 blob'), ('最新版本完整', '被完整存放的 blob 是 HEAD 的版本,旧版本都是对它的 delta')],
    [('文件头', '<p>pack 以 12 字节开头:魔数 <code>PACK</code>、版本号 2(4 字节大端)、对象个数(4 字节大端)。后面紧接着第一个对象条目。</p>'),
     ('条目头', '<p>每个条目的第一个字节:最高位是“后面还有头部字节”,接着 3 位类型(1 commit、2 tree、3 blob、4 tag、6 OFS_DELTA、7 REF_DELTA)和 4 位大小;如果还有后续字节,每个字节补 7 位大小。然后是这个对象 zlib 压缩后的数据。条目之间没有分隔符。</p>'),
     ('OFS_DELTA', '<p>delta 条目在头部后面多一个“向后偏移量”(变长编码),指出基础对象在 pack 里的位置;REF_DELTA 则直接放基础对象的 hash。基础对象本身可以是另一个 delta,所以形成链(本例最深为 2)。git 选择让最新版本完整存放、旧版本做 delta,最常用的版本读取最快。</p>'),
     ('delta 指令', '<p>delta 的本体先是源长度和目标长度两个变长整数,然后是指令序列:最高位为 1 的是 copy(从基础对象复制 偏移 + 长度),其余是 insert(后面直接跟着新字节)。本例中一行改动只需要两条 copy 指令。</p>'),
     ('校验和', '<p>pack 末尾 20 字节是前面全部内容的 SHA-1,也是文件名的一部分;<code>git verify-pack</code> 会校验它。</p>')],
    steps,
    [ENV_I_GIT + '。解析器是我用 Python 写的(ll.py 里的 parse_pack / apply_delta),只读 .pack,不依赖 git;对账对象是 git verify-pack -v;pack 是 git gc 生成的(5 个提交,每次改一行,doc.txt 约 8 KB)',
     '没有验证:REF_DELTA(thin pack 或 --no-delta-base-offset 时才出现,本例全是 OFS_DELTA);大对象(大小编码超过 4 字节)与 64 位偏移的 .idx;pack 版本 3;多个 pack、cruft pack;git 选择基础对象的算法(window / depth,见后面 delta 链一篇)'],
    'packfile 的字节')
