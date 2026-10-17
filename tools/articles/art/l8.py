from lib import *
S = SS('l8')
steps = [
    step("在新仓库里建两个空目录 empty_dir 和 logs,git add empty_dir logs 退出码是 0(没报错),但 git status --short 一行输出都没有,完整的 git status 还是 nothing to commit。git 对空目录既不拒绝也不记录。", t=tl(S(1)), mark=lidx(S(1), '退出码 0', 'nothing to commit'), done=lidx(S(1), 'empty_dir', 'logs'), kv=KV([['git add 空目录', '成功,但什么也没加'], ['git status', '看不到空目录'], ['原因', '见后面几节']], ['git add 空目录'])),
    step("提交了 a.txt 之后:git ls-tree -r HEAD 里只有 a.txt;从这个仓库 git clone 出去的副本里 ls 也只有 a.txt。空目录在本地存在,但没有进入任何 commit,换一台机器检出就没有。", t=tl(S(2)), mark=lidx(S(2), 'git clone'), done=lidx(S(2), 'git ls-tree -r HEAD', '100644 blob 78981922'), kv=KV([['本地', '空目录一直在磁盘上'], ['commit / clone', '空目录不在其中'], ['后果', '换一台机器就没有']], ['后果'])),
    step("原因:git ls-files -s 列出的暂存区每一项都是一个文件路径(100644 … a.txt),没有“目录条目”这回事,空目录没有任何文件可以记。空 tree 4b825dc… 是合法对象(git cat-file -t 得到 tree,里面 0 个条目),git mktree 不给输入就得到它,但正常的 add / commit 不会把它作为子目录放进提交。", t=tl(S(3)), mark=lidx(S(3), 'git ls-files -s', '4b825dc642cb6eb9a060e54bf8d69288fbee4904'), done=lidx(S(3), 'git cat-file -t', '       0'), kv=KV([['暂存区', '只有文件路径'], ['空 tree', '合法对象,0 个条目'], ['add / commit', '不会生成空子目录条目']], ['暂存区'])),
    step("手工造一个:git mktree 构造一个 tree,其中有一个指向空 tree 的 040000 条目 empty,再用 git commit-tree 做成提交 7d2deb2…。git ls-tree 看得到 empty 这个条目,git fsck 也不报错(只提示它是悬空的);但是 git checkout 到这个提交后,磁盘上并没有 empty 目录(ls: empty: No such file or directory)。就算对象库里记了空目录,检出时 git 也不会创建它。", t=tl(S(4)), mark=lidx(S(4), 'ls: empty: No such file', '040000 tree 4b825dc'), done=lidx(S(4), 'git mktree', 'dangling commit'), kv=KV([['mktree + commit-tree', '可以记录空 tree 条目'], ['fsck', '不报错'], ['checkout', '不会创建空目录']], ['checkout'])),
    step("通行做法一:目录里放一个占位文件(常叫 .gitkeep,但名字不重要),git add 之后 status 出现 A empty_dir/.gitkeep 和 A logs/.gitkeep,两个文件的 blob 都是 e69de29…(空 blob,与 git hash-object -t blob /dev/null 相同)。做法二:目录里放一个 .gitignore,内容是“*”加“!.gitignore”,这样目录里其它文件(例如 tmp1.dat)都被忽略,只有 .gitignore 被提交。", t=tl(S(5)), mark=lidx(S(5), 'A  empty_dir/.gitkeep', 'A  cache/.gitignore'), done=lidx(S(5), 'e69de29bb2d1', 'cache/.gitignore'), kv=KV([['.gitkeep', '约定名,空 blob e69de29…'], ['目录自带 .gitignore', '"*" 加 "!.gitignore",忽略其余文件'], ['本质', '目录必须含至少一个被跟踪的文件']], ['本质'])),
]
A = mkarti('l8', 8, 'Git,空目录,.gitkeep,tree,真实验证,动画演示',
    '在真实仓库里验证空目录提交不了:git add 成功但什么都不加,clone 出来没有它;暂存区只有文件路径;手工用 mktree / commit-tree 造出带空 tree 条目的提交,fsck 不报错,检出时 git 也不会创建空目录;常用的 .gitkeep 与 .gitignore 两种占位做法。',
    '为什么 git 提交不了空目录?这篇先看 add、status、clone 的表现,再看暂存区的结构,甚至手工造出一个带空 tree 的提交,最后验证两种常见的占位做法。',
    [('0', 'git add 空目录的退出码是 0,但没有加入任何东西'), ('空 tree', '手工 mktree 可以造出带空目录条目的提交,fsck 不报错,但检出时 git 不创建目录'), ('e69de29', '.gitkeep 占位文件就是一个空 blob')],
    [('现象', '<p><code>git add</code> 一个空目录既不报错也不加入任何东西,<code>git status</code> 也看不到它;提交之后 <code>git ls-tree -r</code> 里没有它,clone 出来的副本里自然也没有。</p>'),
     ('为什么会这样', '<p>本地的空目录一直在磁盘上,但它从没有进入过 commit;换一台机器检出就没有。</p>'),
     ('暂存区没有目录条目', '<p>暂存区(index)记录的是文件路径,没有“目录”这种条目,空目录里没有文件,就没有任何可记的。空 tree 本身是合法对象,但正常的 add / commit 不会把它作为子目录写进提交。</p>'),
     ('手工造一个', '<p>用 <code>git mktree</code> 和 <code>git commit-tree</code> 可以造出带空 tree 条目的提交,git 不认为这有问题;但检出这个提交不会创建对应的空目录,所以这条路并不能真正“提交空目录”。</p>'),
     ('占位文件', '<p>通行做法是放一个被跟踪的占位文件,<code>.gitkeep</code> 只是约定的名字,它的 blob 是空 blob <code>e69de29</code>。另一种是在目录里放 <code>.gitignore</code>,写 <code>*</code> 和 <code>!.gitignore</code>,让目录里的其它文件都被忽略,既保留目录又不会误提交运行时产生的文件。</p>')],
    steps,
    [ENV_I_GIT + '。所有结果来自 git add / status / clone / mktree / commit-tree / checkout 的真实运行',
     '没有验证:其它版本的 git 对空 tree 条目的行为(本文只在 2.54.0 上试过);git archive、sparse-checkout 对空目录的处理;工作树里已有空目录时 git clean -d 会不会删除它;Windows 与 macOS 文件系统的差别'],
    '空目录')
