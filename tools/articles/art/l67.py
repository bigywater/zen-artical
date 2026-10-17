from lib import *
S = SS('l67')
steps = [
    step("git bundle create --all 把仓库打成一个文件(2457 字节)。用 Python 读它的字节:文件开头是文本,第一行 # v2 git bundle,然后每行“hash ref名”——refs/heads/dev、refs/heads/main、refs/tags/v1、HEAD,最后一个空行把文本头和后面的数据隔开;空行之后就是一个标准的 packfile(PACK 头,版本 2,对象数 30)。源仓库 git rev-list --objects --all 数出的可达对象也是 30 个——bundle 里装的就是全部可达对象。也就是说 bundle = “ref 列表 + 一个 pack”。", t=tl(S(1)), mark=lidx(S(1), '# v2 git bundle', 'PACK 头:版本 2,对象数 30'), done=lidx(S(1), 'refs/heads/dev', 'refs/heads/main', 'refs/tags/v1', 'HEAD', '最后有一个空行'), kv=KV([['文本头', '# v2 git bundle + ref 列表'], ['分隔', '一个空行'], ['数据', '标准 packfile']], ['数据'])),
    step("git bundle verify 报告 The bundle records a complete history. 和 The bundle uses this hash algorithm: sha1;git bundle list-heads 列出 dev、main、v1、HEAD 四个 ref。用 bundle 当远程 git clone:得到 10 个提交、分支 main 与 origin/dev、origin/main、标签 v1,remote.origin.url 就是 bundle 文件的路径(…/l67full.bundle)。bundle 在 git 眼里就是一个只读的远程仓库。", t=tl(S(2)), mark=lidx(S(2), 'complete history', 'clone 出来的提交数: 10', 'l67full.bundle'), done=lidx(S(2), 'list-heads', 'remotes/origin/dev', 'v1'), kv=KV([['verify', '检查 bundle 是否完整可用'], ['list-heads', '列出 bundle 里的 ref'], ['clone', '把 bundle 当远程']], ['clone'])),
    step("增量 bundle:源仓库又提交了 3 个新提交,只打包“某个提交之后”的:git bundle create inc.bundle main ^<已有的提交>。文本头多了一行 -<sha> 提交 10(以 - 开头的是前置条件 prerequisites:接收方必须已经有这个提交),pack 里只有 9 个对象,文件 855 字节(完整 bundle 是 30 个对象、2,457 字节)。在没有那个提交的空仓库里验证:error: Repository lacks these prerequisite commits;在已经 clone 过的仓库里验证:/work/l67inc.bundle is okay,并说明 The bundle contains this ref / The bundle requires this ref。", t=tl(S(3)), mark=lidx(S(3), '-<sha40> 提交 10', 'Repository lacks these prerequisite commits', 'is okay'), done=lidx(S(3), 'pack 里的对象数 9', '855 字节'), b=bars([['完整 bundle', 2457, '2,457 字节'], ['增量 bundle', 855, '855 字节']], 2457, mark=[1], done=[0]), kv=KV([['^<提交>', '排除接收方已有的历史'], ['前置条件', '文本头里以 - 开头的行'], ['接收方没有前置提交', 'verify 报 lacks prerequisite']], ['前置条件'])),
    step("从 bundle fetch 和从远程 fetch 一样:git fetch inc.bundle main:refs/remotes/bundle/main 输出 * [new branch] main -> bundle/main,bundle/main 有 13 个提交(10 个旧的加 3 个新的)。用移动介质(U 盘、邮件)传仓库的场景,就是反复生成增量 bundle 然后 fetch。", t=tl(S(4)), mark=lidx(S(4), 'new branch', '13'), done=lidx(S(4), 'From <bundle>'), kv=KV([['fetch <bundle>', '像普通远程一样更新引用'], ['场景', '没有网络时同步仓库']], ['fetch <bundle>'])),
    step("bundle 里的 PACK 部分和直接用 git pack-objects 打包同样的全部对象大小差不多:pack-objects 直接打包 3,099 字节,bundle 里的 PACK 部分 2,894 字节,文本头 230 字节。差别来自 bundle 创建时使用了 ofs-delta 等选项(没有逐项验证)。结论:bundle 没有额外的格式开销,就是 pack 加一个小文本头。", t=tl(S(5)), mark=lidx(S(5), '3,099', '2,894'), done=lidx(S(5), 'pack-objects'), kv=KV([['bundle', '文本头 + pack'], ['开销', '几百字节的文本头'], ['pack 本身', '与 pack-objects 同级']], ['bundle'])),
]
A = mkarti('l67', 67, 'Git,bundle,packfile,离线传输,真实验证,动画演示',
    '解析 git bundle 的字节:文本头(# v2 git bundle、每行 hash ref,增量时多出以 - 开头的前置条件行)加一个空行加一个标准 packfile;完整 bundle 的 pack 含 30 个对象,与可达对象数一致;git bundle verify / list-heads;把 bundle 当远程 clone 或 fetch;增量 bundle 只有 9 个对象、855 字节,接收方缺少前置提交时 verify 报错。',
    '没有网络怎么传一个 git 仓库?git bundle 把若干个 ref 和对应的对象打成一个文件。这篇拆开这个文件看它到底由什么组成,再看增量 bundle 的前置条件、clone 与 fetch 的用法。',
    [('30 个对象', '完整 bundle 里 pack 的对象数,等于 git rev-list --objects --all 的可达对象数'), ('855 vs 2,457 字节', '增量 bundle(9 个对象)与完整 bundle(30 个对象)的文件大小'), ('- 开头的行', 'bundle 文本头里的前置条件,接收方必须已经有这些提交')],
    [('文件结构', '<p>bundle 文件开头是文本:<code># v2 git bundle</code>,然后每行 <code>hash ref名</code>,增量 bundle 还有以 <code>-</code> 开头的前置条件行;一个空行之后就是标准的 packfile。用 Python 逐字节读出来,对象数与源仓库的可达对象数一致。</p>'),
     ('verify 与 clone', '<p><code>git bundle verify</code> 检查完整性与前置条件,<code>list-heads</code> 列出其中的 ref;git 可以把 bundle 当只读的远程直接 <code>git clone x.bundle</code>。</p>'),
     ('增量', '<p><code>git bundle create inc.bundle main ^&lt;已有的提交&gt;</code> 只打包新对象,在文本头里记录前置条件。接收方缺少前置提交时 verify 报 <code>Repository lacks these prerequisite commits</code>。</p>'),
     ('fetch', '<p><code>git fetch x.bundle main:refs/remotes/…</code> 和从普通远程 fetch 一样更新引用,适合用 U 盘、邮件同步仓库。</p>'),
     ('开销', '<p>bundle 没有额外的格式负担:pack 部分的大小和 <code>git pack-objects</code> 同级,再加几百字节的文本头。</p>')],
    steps,
    [ENV_I_GIT + '。bundle 文件由我用 Python 按字节读取(文本头加 PACK),pack 内容复用上一系列的 parse_pack;“与 pack-objects 同级”只比较了一个小仓库(30 个对象)',
     '没有验证:bundle v3(object-format、capability 行,如 filter);--since / 日期范围打包;git bundle unbundle;包含标签注解对象的情形;很大仓库上 bundle 的耗时与大小;通过邮件传输时的编码'],
    'bundle')
