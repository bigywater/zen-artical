from lib import *
S = SS('l34')
steps = [
    step("工作区里有 4 处改动(第 3、5、20、38 行),git diff 只切出 3 个 hunk:@@ -1,8 +1,8 @@、@@ -17,7 +17,7 @@、@@ -35,6 +35,6 @@。第 3 行与第 5 行之间只隔着一行,两处改动各带 3 行上下文,上下文互相重叠,所以合成了第一个 hunk(8 行)。hunk 的边界由上下文行数决定,不是由“改动的个数”决定。", t=tl(S(1)), mark=lidx(S(1), '@@ -1,8 +1,8 @@'), done=lidx(S(1), '@@ -17,7 +17,7 @@', '@@ -35,6 +35,6 @@', '上下文重叠'), kv=KV([['hunk', '一段带上下文的连续改动'], ['上下文', '默认 3 行,重叠就合并'], ['4 处改动', '3 个 hunk']], ['hunk'])),
    step("git add -p 对每个 hunk 问一次。用管道喂 n、y、y:第一个 hunk 不要,后两个要。提示行里能看出哪些 hunk 可以拆:第一个 hunk 的选项里有 s,后面两个没有(它们只有一处改动)。结果:git diff --cached 里只有 @@ -17,7 +17,7 @@ 和 @@ -35,6 +35,6 @@(第 20、38 行),git diff 里剩下 @@ -1,8 +1,8 @@(第 3、5 行)——暂存区和工作区按 hunk 为单位分开了。", t=tl(S(2)), mark=lidx(S(2), '(1/3) Stage this hunk', '(2/3)', '(3/3)'), done=lidx(S(2), '行 20 改了', '行 38 改了', '行 03 改了', '行 05 改了'), kv=KV([['y / n', '暂存 / 跳过这个 hunk'], ['s', '只有包含多处改动时才可拆分'], ['结果', 'cached 与工作区各一部分']], ['s'])),
    step("s 把一个 hunk 拆成更小的:对第一个 hunk 输入 s,git 回答 Split into 2 hunks.(第 3 行与第 5 行的改动被分开),再对拆出的第一块输 y、第二块输 n、然后 q。git diff --cached 里只有 @@ -1,6 +1,6 @@ 的第 3 行改动。拆分只能发生在两处改动之间隔着未改动行的地方,拆出来的 hunk 的上下文会收窄。", t=tl(S(3)), mark=lidx(S(3), 'Split into 2 hunks'), done=lidx(S(3), '@@ -1,6 +1,6 @@', '行 03 改了'), kv=KV([['s', '拆成多个更小的 hunk'], ['条件', '改动之间必须隔着未改动的行'], ['拆出来的 hunk', '各自带上下文']], ['条件'])),
    step("e 手工编辑 hunk:在编辑器里把 +行 03 改了 改成 +行 03 我手工改的,并且删掉 +行 05 改了 这一行(只留下 -行 05)。保存退出后暂存区里的 hunk 头自动重算成 @@ -1,8 +1,7 @@(新一侧少了一行),内容是:行 03 被换成我手工写的版本,行 05 被删除。git show :f.txt 第 3 行是“行 03 我手工改的”,第 5 行是“行 06”(原来的第 5 行没了);工作区文件不变。删掉一个 + 行,等于只暂存“删除”那一半。", t=tl(S(4)), mark=lidx(S(4), '@@ -1,8 +1,7 @@', '行 03 我手工改的'), done=lidx(S(4), '-行 03', '-行 05', '工作区'), kv=KV([['e', '在编辑器里改补丁'], ['删掉 + 行', '只暂存对应的删除'], ['@@ 头', 'git 自动重算行数']], ['e'])),
    step("暂存的内容到底是什么:add -p 用 n、y、n 选中第 2 个 hunk 之后,暂存的 blob 是 a5d5288f9632…;另一个仓库里把完整的 git diff 存成补丁、只取第 2 个 hunk 的部分用 git apply --cached,得到的 blob 同样是 a5d5288f9632…,完全相同(True)。工作区文件没有动(True)。add -p 就是“在 HEAD 版本上只应用你选的 hunk,把结果写进暂存区”。", t=tl(S(5)), mark=lidx(S(5), '相同: True'), done=lidx(S(5), '工作区文件没动'), kv=KV([['暂存的 blob', 'HEAD 版本 + 选中的 hunk'], ['等价命令', 'git apply --cached 选中的补丁'], ['工作区', '不会被改动']], ['暂存的 blob'])),
    step("新文件(untracked)用 git add -p 会得到 No changes.(没有 hunk 可选);先 git add -N new.txt(intent-to-add,git status 显示 ' A new.txt'),之后 git add -p new.txt 才出现 @@ -0,0 +1,6 @@ 和 (1/1) Stage addition 的询问。同一套机制还用于反方向:对已暂存的文件 git reset -p,输入 n、y、n,把第 2 个 hunk(第 20 行)从暂存区撤下来,留下第 1、3 个 hunk 仍在暂存区。", t=tl(S(6)), mark=lidx(S(6), 'No changes.', '(1/1) Stage addition', 'git reset -p'), done=lidx(S(6), 'git add -N new.txt', '@@ -0,0 +1,6 @@', '行 38 改了'), kv=KV([['untracked 文件', '先 git add -N 才有 hunk'], ['reset -p', '按 hunk 撤销暂存'], ['checkout -p / stash -p', '同一套选择机制']], ['untracked 文件'])),
]
A = mkarti('l34', 34, 'Git,git add -p,hunk,暂存,补丁,真实验证,动画演示',
    '用管道喂答案驱动真实的 git add -p:4 处改动按上下文切成 3 个 hunk(相隔一行的两处合并为一个);y/n 决定每个 hunk 是否暂存;s 拆分只在改动之间隔着未改动行时可用;e 编辑补丁时删掉 + 行等于只暂存删除,@@ 头自动重算;暂存的 blob 与手工 git apply --cached 选中的补丁得到的 blob 完全相同;新文件要 git add -N;reset -p 同理。',
    'git add -p 是怎么把一个文件切成一块一块让你选的?hunk 的边界怎么定、s 什么时候能拆、e 编辑之后行数怎么重算、最后暂存区里到底是什么?这篇用脚本喂答案跑真实的 git add -p,一项项对账。',
    [('3 个 hunk', '4 处改动被切成 3 个 hunk,相隔一行的两处合并在一起'), ('相同', 'add -p 选中第 2 个 hunk 暂存的 blob,与手工用 git apply --cached 应用同一个 hunk 得到的 blob 完全一致'), ('@@ 头', '手工编辑 hunk 之后,git 自动重算 @@ 头里的行数')],
    [('hunk 怎么切', '<p>git diff 把连续的改动连同上下文(默认 3 行)切成 hunk,两处改动的上下文重叠就合并成一个。所以 4 处改动只切出 3 个 hunk。</p>'),
     ('y / n', '<p><code>git add -p</code> 对每个 hunk 问一次:y 暂存、n 跳过。暂存区和工作区于是按 hunk 为单位分开,<code>git diff --cached</code> 与 <code>git diff</code> 各看到一部分。</p>'),
     ('s 拆分', '<p>一个 hunk 里有多处改动、且它们之间隔着未改动的行时,可以用 s 拆成更小的 hunk,分别决定取舍。只有一处改动的 hunk 没有 s 选项。</p>'),
     ('e 编辑', '<p>e 把这个 hunk 当补丁交给编辑器。改 + 行就是改要暂存的内容;删掉一个 + 行相当于“只暂存对应的删除”;保存后 git 重算 <code>@@</code> 头里的行数。工作区文件不受影响。</p>'),
     ('本质', '<p>暂存的内容 = HEAD 版本加上被选中的 hunk,和 <code>git apply --cached</code> 一个补丁得到的 blob 完全相同。</p>'),
     ('边界', '<p>untracked 文件没有 hunk,要先 <code>git add -N</code>(intent-to-add);<code>reset -p</code>、<code>checkout -p</code>、<code>stash -p</code> 用同一套选择机制,方向相反。</p>')],
    steps,
    [ENV_I_GIT + '。git add -p 不是在终端里,而是用 printf 通过管道喂答案(非 tty 输入);e 的编辑器是我写的一个小 Python 脚本(GIT_EDITOR),机械地改补丁;hunk 的行号来自 git diff 的输出',
     '没有验证:真终端里 interactive.singleKey 的单键模式;g(跳转)、/(搜索)、a/d/k/j 等其它选项;二进制文件与模式变更(chmod)在 add -p 里的处理;diff.context 与 --inter-hunk-context 调整 hunk 边界;add -p 的 patch 模式(git add -i)'],
    'git add -p')
