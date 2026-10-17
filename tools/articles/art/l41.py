from lib import *
S = SS('l41')
steps = [
    step("两边改了同一个文件的不同位置(ours 改第 2 行,theirs 改第 8 行):git merge theirs 输出 Auto-merging f.txt 和 Merge made by the 'ort' strategy.,干净合并。用三方合并的底层命令 git merge-file -p(参数是 ours、基础、theirs 三个文件)算同样的输入,输出与 git merge 得到的 f.txt 完全一致(True)。合并就是对每个文件做一次三方合并,基础来自 merge-base。", t=tl(S(1)), mark=lidx(S(1), "Merge made by the 'ort' strategy", 'Auto-merging f.txt'), done=lidx(S(1), 'git merge-file -p'), kv=KV([['三个输入', 'ours、基础(merge-base)、theirs'], ['不重叠的改动', '两边都收'], ['底层命令', 'git merge-file']], ['底层命令'])),
    step("两边改同一行:CONFLICT (content): Merge conflict in f.txt,git status 是 UU f.txt。工作区文件里是 <<<<<<< HEAD / 第 5 行 ours 改 / ======= / 第 5 行 theirs 改 / >>>>>>> theirs 的冲突标记。index 里同一个路径有三个阶段:stage 1(基础:“第 5 行”)、stage 2(ours)、stage 3(theirs),可以用 git show :1:f.txt、:2:、:3: 取出。.git 里多了 MERGE_HEAD(要合并进来的提交)、MERGE_MODE、MERGE_MSG(默认的提交说明,还带 # Conflicts: 提示)。", t=tl(S(2)), mark=lidx(S(2), 'stage1', 'stage2', 'stage3', 'MERGE_HEAD', 'MERGE_MSG'), done=lidx(S(2), 'CONFLICT (content)', 'UU f.txt', '<<<<<<< HEAD', 'stage 1', 'stage 2', 'stage 3'), kv=KV([['stage 1', '基础版本'], ['stage 2', 'ours(HEAD)'], ['stage 3', 'theirs'], ['MERGE_HEAD', '正在合并的提交']], ['stage 1'])),
    step("冲突的边界:两边做了完全相同的改动(都把第 5 行改成同一个文字)→ 不冲突(Merge made by the 'ort' strategy.);改动相邻(ours 改第 5 行、theirs 改第 6 行)→ CONFLICT (content);中间隔一行(第 5 行与第 7 行)→ 不冲突。git 判断冲突的单位是“相邻的改动块”,相邻就算冲突,哪怕改的是不同的行。", t=tl(S(3)), mark=lidx(S(3), 'CONFLICT (content)'), done=lidx(S(3), "Merge made by the 'ort' strategy", 'Auto-merging f.txt'), kv=KV([['相同的改动', '不冲突'], ['相邻的改动', '冲突'], ['隔一行', '不冲突']], ['相邻的改动'])),
    step("文件级冲突:一边删除 f.txt、另一边修改它 → CONFLICT (modify/delete): f.txt deleted in theirs and modified in HEAD. Version HEAD of f.txt left in tree.,状态 UD;两边各自新增同名文件 new.txt 但内容不同 → CONFLICT (add/add): Merge conflict in new.txt,状态 AA,工作区里是两个版本夹在冲突标记里。这两种冲突没有“基础”可比较(基础里不存在或被删除)。", t=tl(S(4)), mark=lidx(S(4), 'modify/delete', 'add/add', 'UD f.txt', 'AA new.txt'), done=lidx(S(4), 'ours 新增的 new', 'theirs 新增的 new'), kv=KV([['modify/delete', '状态 UD,保留修改的版本'], ['add/add', '状态 AA,内容夹在标记里']], ['modify/delete'])),
    step("一边把 old.txt 改名为 renamed.txt(内容不变)、另一边修改了 old.txt 的第 5 行:git merge theirs 输出 Merge made by the 'ort' strategy. 和 rename old.txt => renamed.txt (100%),ls 里只有 renamed.txt,它的第 5 行是“第 5 行 ours 改”——ort 检测到改名,把修改应用到了新名字上。这个机制在下一篇讲相似度阈值。", t=tl(S(5)), mark=lidx(S(5), 'rename old.txt => renamed.txt'), done=lidx(S(5), "Merge made by the 'ort' strategy", 'renamed.txt', '第 5 行 ours 改'), kv=KV([['改名 + 修改', '修改跟着改名走'], ['依据', '检测到改名(内容相似)'], ['结果', '没有冲突']], ['改名 + 修改'])),
    step("策略选项:-X ours 只在冲突的块上选 ours(第 5 行取 ours),不冲突的块两边都收(第 2 行 ours 改、第 9 行 theirs 改、x.txt 取 theirs 改);-X theirs 冲突的块取 theirs(第 5 行是 theirs 改),其余同上。-s ours 完全不同:整个忽略对方的内容(第 9 行仍是原来的、x.txt 仍是 x),但仍然产生一个有两个 parent 的合并提交(parent 数 2)——只是记录“合并过”,不收任何改动。", t=tl(S(6)), mark=lidx(S(6), '-s ours', 'parent'), done=lidx(S(6), '-X ours', '-X theirs'), b=bars([['-X ours 第 5 行', 1, 'ours'], ['-X theirs 第 5 行', 2, 'theirs'], ['-s ours 第 9 行', 0, '保持原样']], 2, mark=[2], done=[0, 1]), kv=KV([['-X ours / theirs', '只在冲突块选边'], ['-s ours', '忽略对方的全部改动,仍然记一次合并'], ['区别', '-X 仍会收对方不冲突的改动']], ['-s ours'])),
    step("git merge --abort 取消合并:status 干净,.git 里的 MERGE_HEAD 等文件都没了,f.txt 恢复成合并之前的“第 5 行 ours 改”。--abort 就是回到合并之前的状态。", t=tl(S(7)), mark=lidx(S(7), 'MERGE_HEAD 等文件都没了'), done=lidx(S(7), 'git merge --abort', '第 5 行 ours 改'), kv=KV([['--abort', '回到合并之前'], ['清除', 'MERGE_HEAD、MERGE_MSG、MERGE_MODE'], ['冲突标记', '随之消失']], ['--abort'])),
]
A = mkarti('l41', 41, 'Git,三方合并,ort,冲突,merge-file,真实验证,动画演示',
    '实测三方合并:不重叠的改动自动合并,结果与 git merge-file 一致;同一处改动产生冲突标记,index 里同一路径有 stage 1/2/3 三个阶段,.git 里出现 MERGE_HEAD、MERGE_MSG、MERGE_MODE;相同的改动不冲突、相邻的改动冲突、隔一行不冲突;modify/delete 和 add/add 文件级冲突;改名后修改跟着走;-X ours/theirs 只在冲突块选边,-s ours 整个忽略对方;--abort 回到合并之前。',
    'git merge 在底层做的就是三方合并:基础、ours、theirs。这篇用小例子把它的行为一项项对出来:什么时候自动合并、什么时候冲突、冲突时 index 和 .git 里留下什么、改名会不会被识别、-X 和 -s 到底差在哪里。',
    [('3 个阶段', '冲突文件在 index 里的 stage 1(基础)、2(ours)、3(theirs)'), ('相邻即冲突', '改动相邻的两行(只隔 0 行)冲突,中间隔一行就不冲突'), ('-X vs -s', '-X ours 只在冲突块选 ours;-s ours 整个忽略对方的内容但仍产生合并提交')],
    [('三方合并', '<p>对每个文件,git 取 merge-base 里的版本为基础,与 ours、theirs 各做一次比较,不重叠的改动两边都收。底层命令是 <code>git merge-file</code>,实测它的输出与合并结果完全一致。</p>'),
     ('冲突时留下什么', '<p>工作区文件里有冲突标记;index 里同一路径保留三个阶段(1 基础、2 ours、3 theirs),可以用 <code>git show :1:文件</code> 取出;<code>.git</code> 里出现 <code>MERGE_HEAD</code>、<code>MERGE_MODE</code> 和 <code>MERGE_MSG</code>。</p>'),
     ('什么算冲突', '<p>相同的改动不冲突;改动块相邻就算冲突(即使改的是不同的行);中间隔一行以上则能自动合并。</p>'),
     ('文件级冲突', '<p>一边删除一边修改是 modify/delete(状态 UD),两边各自新增同名文件内容不同是 add/add(状态 AA)。</p>'),
     ('改名', '<p>一边改名、一边修改内容时,ort 检测到改名,把修改应用到新名字上。检测依据见下一篇。</p>'),
     ('-X 与 -s', '<p><code>-X ours</code>/<code>-X theirs</code> 只在冲突块上选边,其余改动都收;<code>-s ours</code> 不收对方任何改动,但仍记录一次有两个 parent 的合并。</p>'),
     ('取消', '<p><code>git merge --abort</code> 回到合并之前,清除 MERGE_HEAD 等文件。</p>')],
    steps,
    [ENV_I_GIT + '。所有例子在每个场景单独的仓库里重做;作者与时间固定;冲突阶段的 hash 做了省略',
     '没有验证:diff3 / zdiff3 样式的冲突标记(见后面冲突标记一篇);rerere 记住冲突解法(见后面);目录改名检测(见 rename 检测一篇之后);criss-cross 合并时虚拟基础的构造;-X patience、-X ignore-space-change 等其它策略选项;二进制文件的冲突;合并子模块'],
    '三方合并与冲突')
