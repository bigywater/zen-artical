from lib import *
S = SS('l18')
steps = [
    step("造 6000 个提交的历史(每次改 200 个文件里轮流的一个),git gc 之后只有一个 pack(in-pack: 30000,1 个 pack),pack 目录里是 .idx、.pack、.rev,没有 .bitmap。30,000 个对象 = 6000 个 commit + 18,000 个 tree + 6000 个 blob。", t=tl(S(1)), mark=lidx(S(1), 'in-pack: 30000'), done=lidx(S(1), 'packs: 1', '.rev'), kv=KV([['commit', '6,000'], ['tree', '18,000(每次提交 3 个)'], ['blob', '6,000'], ['bitmap', '还没有']], ['bitmap'])),
    step("没有 bitmap 时,数出 HEAD 可达的全部对象 git rev-list --objects --count HEAD 得到 30000,要从 HEAD 开始逐个读 commit、逐层展开 tree,耗时 32.8 ms(5 次中位数)。", t=tl(S(2)), mark=lidx(S(2), '耗时'), done=lidx(S(2), '30000'), kv=KV([['不用 bitmap', '走遍 commit 和 tree 才能数出对象'], ['30,000 个对象', '约 32.8 ms']], ['不用 bitmap'])),
    step("git repack -adb 写出一个 149,820 字节的 .bitmap。同样的统计加上 --use-bitmap-index,仍然得到 30000,耗时 12.5 ms,比 32.8 ms 快 2.6 倍——不再遍历对象,而是直接数位图里的 1。", t=tl(S(3)), mark=lidx(S(3), '--use-bitmap-index', '快 2.6 倍'), done=lidx(S(3), 'repack -adbq', '149820'), b=bars([['不用 bitmap', 32.8, '32.8 ms'], ['用 bitmap', 12.5, '12.5 ms']], 32.8, mark=[1], done=[0]), kv=KV([['文件', '149,820 字节,6000 个提交'], ['耗时', '32.8 → 12.5 ms'], ['原理', '直接数位图里 1 的个数']], ['原理'])),
    step(".bitmap 的头部:签名 BITM、版本 1、选项 0x0005(FULL_DAG 加 HASH_CACHE)、位图化的提交数 164(6000 个提交里只选了 164 个),随后 20 字节是它配对的 pack 的校验和 bb7adb7a…,与 pack 文件最后 20 字节完全相同。不是每个提交都有位图,git 选一部分(越近越密)的提交存下来。", t=tl(S(4)), mark=lidx(S(4), '签名', '位图化的提交数'), done=lidx(S(4), '头部里记的 pack 校验和', '选项位'), kv=KV([['BITM + 版本 1', '魔数与格式'], ['选项 0x0005', 'FULL_DAG + HASH_CACHE'], ['164 个提交', '6000 个里选出的']], ['164 个提交'])),
    step("头部后面是四张按类型的位图,每个对象占一位:commit 位图共 6,000 位全是 1(pack 里的每个对象是不是 commit);tree 位图 30,000 位里有 18,000 个 1;blob 位图 29,640 位里有 6,000 个 1(末尾全零的位被省略);tag 位图 0 位。四类 1 的个数相加 = 30,000 = pack 里的对象数。位图是 EWAH 压缩的(连续的 0 / 1 用一个游程字表示)。", t=tl(S(5)), mark=lidx(S(5), 'commit 位图', 'tree   位图', 'blob   位图', 'tag    位图'), done=lidx(S(5), '四类相加'), kv=KV([['四张类型位图', 'commit / tree / blob / tag'], ['编码', 'EWAH(按字游程压缩)'], ['用途', '快速判断一个对象的类型']], ['四张类型位图'])),
    step("其后是 164 张提交位图:每张是“从这个提交出发能到达的所有对象”的集合。第 0 张是 HEAD(a41517ee…),30,000 位为 1,与 git rev-list --objects 一致;第 82 张(xor_offset=1,即与前一张做 XOR)有 29,590 个 1;第 163 张是很老的提交,只有 85 个。三张都与 rev-list 数出的对象集合完全相同,每 10 张抽查 17 张全部一致。其中 110 张用 XOR 与前一张做差分存储。注意两个下标:entry 里的 object_pos 是提交在 .idx(hash 排序)里的下标,位图的第 n 位对应 pack 里按偏移排序的第 n 个对象。", t=tl(S(6)), mark=lidx(S(6), '第 163 张', '第  82 张', 'xor_offset 非 0'), done=lidx(S(6), '第   0 张', '集合不一致的', 'HEAD 对应第 0 张'), kv=KV([['提交位图', '从该提交可达的全部对象'], ['XOR 存储', '110 / 164 张是与前一张的差'], ['两种下标', 'object_pos 用 idx 顺序,位用 pack 偏移顺序']], ['两种下标'])),
    step("真正的用途:服务端为 clone 打包。git pack-objects --revs --stdout 对 HEAD 可达的全部对象打包(相当于整库 clone),不用 bitmap 63.3 ms,用 bitmap 21.4 ms(每档 3 次中位数)。位图让服务端不必遍历就知道“该发哪些对象”,仓库越大差别越明显。", t=tl(S(7)), mark=lidx(S(7), 'pack-objects --revs'), done=lidx(S(7), 'pack-objects'), b=bars([['不用 bitmap', 63.3, '63.3 ms'], ['用 bitmap', 21.4, '21.4 ms']], 63.3, mark=[1], done=[0]), kv=KV([['clone 的服务端', '要算出发哪些对象'], ['用位图', '63.3 → 21.4 ms'], ['仓库越大', '遍历成本越高,差别越大']], ['clone 的服务端'])),
]
A = mkarti('l18', 18, 'Git,reachability bitmap,bitmap,repack,真实验证,动画演示',
    '在 6000 个提交(30,000 个对象)的仓库上写 reachability bitmap:git repack -adb 生成 149,820 字节的 .bitmap;数全部可达对象从 32.8 ms 降到 12.5 ms;按字节解析 EWAH 位图:四张类型位图加 164 张提交位图,每 10 张抽查 17 张与 git rev-list --objects 的集合完全相同;pack-objects 打包整库 63.3 → 21.4 ms。',
    '服务端怎么在几十毫秒里算出该给 clone 的人发哪些对象?答案是 reachability bitmap。这篇生成 .bitmap,再用 Python 解码 EWAH 压缩位图:四张类型位图、164 张提交位图,并与 git rev-list --objects 逐个对账。',
    [('2.6 倍', '数出 HEAD 可达的 30,000 个对象,用 bitmap 比不用快的倍数'), ('164 / 6000', '被位图化的提交数,不是每个提交都有'), ('集合一致', '抽查的 17 张提交位图,与 git rev-list --objects 数出的对象集合完全相同')],
    [('实验仓库', '<p>6000 个提交的线性历史,每次改一个文件,共 30,000 个对象(6000 commit、18,000 tree、6000 blob),<code>git gc</code> 之后是一个 pack,没有 bitmap。</p>'),
     ('问题', '<p>“从某个提交出发,能到达哪些对象”需要遍历 commit 和 tree,仓库大时很慢。服务端每次 fetch / clone 都要回答这个问题。不用 bitmap 时,本例数 30,000 个可达对象要 32.8 ms。</p>'),
     ('预先存下可达集合', '<p>reachability bitmap 为一部分提交预先存下“可达对象集合”:pack 里每个对象一位,1 表示可达。之后集合运算(并、差)变成位运算,不再需要遍历。本例同样的统计降到 12.5 ms,快 2.6 倍。</p>'),
     ('文件头与选了多少个', '<p><code>.bitmap</code> 以签名 <code>BITM</code>、版本、选项、位图化的提交数、配对 pack 的校验和开头。6000 个提交里只给 164 个存了位图,约 2.7%;其余的提交从最近的位图出发再走几步。</p>'),
     ('类型位图与 EWAH', '<p>头部后面是 commit / tree / blob / tag 四张类型位图,每个对象一位;位图用 EWAH 压缩(连续的全 0 或全 1 的 64 位字合并成一个游程)。四类 1 的个数相加正好等于 pack 里的对象数。</p>'),
     ('提交位图与两种下标', '<p>每个被选中的提交有一张可达对象位图,相邻的提交位图可以用 XOR 差分(<code>xor_offset</code>)存储。entry 里的 <code>object_pos</code> 是提交在 .idx(hash 排序)里的下标,而位图的第 n 位对应 pack 里按偏移排序的第 n 个对象——实验里用两种顺序分别映射才得到与 git 完全一致的结果。</p>'),
     ('服务端的用途', '<p>git 服务端为 clone 打包时需要知道“该发哪些对象”,位图让它不必遍历。本例整库打包 63.3 → 21.4 ms;仓库越大,遍历越慢,差别越明显。</p>')],
    steps,
    [ENV_I_GIT + '。历史由 git fast-import 造出(6000 个提交,每次改 src/d*/f*.txt 中的一个文件);EWAH 位图由我用 Python 按字节解码(ll.py 的 ewah),对账对象是 git rev-list --objects 和 git verify-pack;耗时是 5 次(pack-objects 是 3 次)中位数,含进程启动',
     '没有验证:git 如何选择哪些提交位图化的完整规则(只记录了本例选了 164 个);多 pack / midx 位图(bitmap 配合 multi-pack-index);lookup table 选项;pseudo-merge 位图;位图对 git rev-list --count 之外命令(如 git log --graph)的影响;pack.useBitmaps 在真实 fetch 服务上的效果'],
    '可达性位图')
