from lib import *
S = SS('l59')
steps = [
    step("2000 个提交的仓库(每次改 50 个文件之一,约 3 KB 的随机文本),完整 pack 4.26 MiB、6000 个对象。本地路径 clone --depth 1 /路径 只是输出 warning: --depth is ignored in local clones; use file:// instead.,深度被忽略;用 file:// 才真的浅克隆:git log 只有一个提交(提交 2000),.git/shallow 里是这个提交的 hash(边界提交),git rev-parse --is-shallow-repository 为 true。HEAD 提交对象里仍写着 parent 的 hash,但那个 parent 在本地并不存在(git cat-file -t 报 could not get object info),shallow 文件告诉 git“把这里当作历史的起点”。", t=tl(S(1)), mark=lidx(S(1), 'depth is ignored', '.git/shallow', 'could not get object info', 'true'), done=lidx(S(1), 'cb08777 提交 2000', 'parent <sha40>'), kv=KV([['.git/shallow', '边界提交的 hash'], ['边界提交', 'parent 字段在,对象不在'], ['本地路径 clone', '忽略 --depth,要用 file://']], ['.git/shallow'])),
    step("不同深度的克隆对比:完整 2,000 个提交、6,000 个对象、pack 4197 KB;--depth 50:50 个提交、199 个对象、199 KB;--depth 10:10 个提交、79 个对象、115 KB;--depth 1:1 个提交、52 个对象、96 KB(那一个提交的完整 tree 和所有 blob,不管多少历史)。深度 1 的 pack 只有完整克隆的约 2%。", t=tl(S(2)), mark=lidx(S(2), '--depth 1'), done=lidx(S(2), '完整', '--depth 50', '--depth 10'), b=bars([['完整', 4197, '4197 KB'], ['--depth 50', 199, '199 KB'], ['--depth 10', 115, '115 KB'], ['--depth 1', 96, '96 KB']], 4197, mark=[3], done=[0, 1, 2]), kv=KV([['--depth 1', '52 个对象,96 KB'], ['--depth 50', '199 个对象,199 KB'], ['完整', '6,000 个对象,4197 KB']], ['--depth 1'])),
    step("加深与恢复:从 --depth 1 开始 git fetch --deepen 9,可见提交变成 10 个,.git/shallow 仍有 1 行(新的边界);git fetch --unshallow 取回全部,可见提交变成 2000,git rev-parse --is-shallow-repository 为 false,.git/shallow 文件被删除(ls: No such file or directory)。", t=tl(S(3)), mark=lidx(S(3), 'unshallow', '2000', 'false', 'No such file'), done=lidx(S(3), '--deepen 9', 'shallow 文件行数'), kv=KV([['--deepen N', '再取 N 层'], ['--unshallow', '取回全部历史'], ['.git/shallow', 'unshallow 后删除']], ['--unshallow'])),
    step("浅克隆(这里 --depth 5)让依赖完整历史的命令受限:git log 只能看到 5 个提交;git blame 对 f07.txt 的每一行显示 ^b4f5741(开头的 ^ 表示追到了边界,不再往前找);git describe --always 退化成只给提交 hash;源仓库里 HEAD~100 的对象在这个克隆里根本不存在(git cat-file -t 报 could not get object info);git log HEAD~10 报 unknown revision。", t=tl(S(4)), mark=lidx(S(4), '^b4f5741', 'could not get object info', 'unknown revision'), done=lidx(S(4), 'git log 能看到的提交数: 5', '<sha>'), kv=KV([['blame', '到边界为止,标记 ^'], ['describe', '只剩 hash'], ['更早的提交', '对象不存在']], ['blame'])),
    step("按时间或按引用截断:--shallow-since=<第 1990 个提交的时间> 得到 11 个提交(第 1990 到 2000);--shallow-exclude=mark1950(一个打在倒数第 51 个提交上的标签)得到 50 个提交——标签之后的提交,标签本身被排除。不是按层数而是按“到哪里为止”来定义深度,适合“只要最近一个月”之类的需求。", t=tl(S(5)), mark=lidx(S(5), '--shallow-since', '--shallow-exclude'), done=lidx(S(5), '11 个', '50 个'), kv=KV([['--shallow-since', '这个时间之后的提交'], ['--shallow-exclude', '该 ref 之后的提交(不含它)'], ['--depth', '按层数']], ['--shallow-since'])),
]
A = mkarti('l59', 59, 'Git,浅克隆,--depth,shallow,真实验证,动画演示',
    '实测浅克隆:本地路径 clone 会忽略 --depth(warning),file:// 才生效;.git/shallow 记录边界提交,边界提交的 parent 字段在但对象不在;2000 个提交的仓库 --depth 1 只有 52 个对象、96 KB(完整是 6000 个对象、4197 KB);--deepen 与 --unshallow 恢复;blame、describe 等命令在边界处受限;--shallow-since、--shallow-exclude 按时间或引用截断。',
    '--depth 1 的 clone 又快又小,代价是什么?.git/shallow 里记着什么?什么命令会因为历史不完整而出问题?这篇在 2000 个提交的仓库上实测不同深度的对象数与体积,再看加深、恢复,以及按时间或引用截断。',
    [('52 vs 6,000', '--depth 1 与完整克隆的对象数'), ('96 vs 4197 KB', '--depth 1 与完整克隆的 pack 大小'), ('^ 边界', 'git blame 在浅克隆里追到边界就停,行首显示 ^')],
    [('本地路径会忽略,shallow 文件', '<p>用本地路径做 <code>git clone --depth 1 /路径</code> 只会得到警告 <code>--depth is ignored in local clones; use file:// instead</code>,要用 <code>file://</code> 才真的浅克隆。浅克隆的 <code>.git/shallow</code> 列出边界提交的 hash:边界提交的对象里仍写着 parent,但那个 parent 在本地不存在,git 读到 shallow 文件就把这里当作历史的起点。</p>'),
     ('体积', '<p>浅克隆拿到的是最近 N 个提交以及它们完整的 tree(所有 blob),不是只取差异。深度 1 时 96 KB,完整是 4197 KB,约 2%;深度越大越接近完整。</p>'),
     ('恢复', '<p><code>git fetch --deepen N</code> 再多取 N 层;<code>--unshallow</code> 取回全部并删除 shallow 文件。</p>'),
     ('受限的命令', '<p><code>git log</code> 和 <code>git blame</code> 只能到边界;<code>describe</code> 找不到标签就只给 hash;边界之前的提交根本不存在,按 hash 访问会失败。</p>'),
     ('按时间或引用', '<p><code>--shallow-since</code> 与 <code>--shallow-exclude</code> 按“到哪里为止”定义深度,而不是层数。</p>')],
    steps,
    [ENV_I_GIT + '。仓库由 git fast-import 生成(2000 个提交,每次改 50 个文件之一);“对象数”是 count-objects 的 count + in-pack;pack 大小是 .git/objects/pack/*.pack 文件大小之和;克隆都走 file://;耗时太小没有引用',
     '没有验证:浅克隆之后 push 的限制;浅克隆与子模块;--depth 对多个分支的影响(--no-single-branch);shallow.lock 与并发;浅克隆上 git gc 的行为;partial clone(--filter)是另一种减小克隆的方法,见下一篇'],
    '浅克隆')
