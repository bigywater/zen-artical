from lib import *
S = SS('l50')
steps = [
    step("起点,三个区域各不相同:HEAD 是 c3(提交里 x=版本 3),暂存区里 x 是“版本 3 + 暂存的改动”(已经 git add),工作区里的 x 又多了一层“+ 工作区的改动”(没有 add),另外还有未跟踪文件 z。reset 的三种模式就是对这三个区域动手的程度不同。", t=tl(S(1)), mark=lidx(S(1), 'HEAD=c3'), done=lidx(S(1), '暂存区 x', '工作区 x', '未跟踪 z 还在'), kv=KV([['HEAD', 'c3'], ['暂存区', 'x + 暂存的改动'], ['工作区', 'x + 暂存的改动 + 工作区的改动'], ['未跟踪', 'z']], ['暂存区'])),
    step("都 reset 到 HEAD~1(c2)。--soft:只动 HEAD(变成 c2),暂存区和工作区原样(x 仍是“版本 3 + 暂存的改动”,工作区也不变)——这个模式常用来“撤销提交但保留所有改动”,改动会作为已暂存的状态留下来。--mixed(默认):动 HEAD 和暂存区(x=版本 2),工作区不动(x 仍带两层改动)。--hard:三个区域都动(x=版本 2),工作区的改动没了;未跟踪文件 z 三种模式下都还在。", t=tl(S(2)), mark=lidx(S(2), 'git reset --soft', 'git reset --mixed', 'git reset --hard'), done=lidx(S(2), '规律'), b=bars([['--soft', 1, '动 HEAD'], ['--mixed', 2, '动 HEAD + 暂存区'], ['--hard', 3, '动 HEAD + 暂存区 + 工作区']], 3, mark=[2], done=[0, 1]), kv=KV([['--soft', '只动 HEAD'], ['--mixed(默认)', 'HEAD + 暂存区'], ['--hard', '三个都动'], ['未跟踪文件', '都不碰']], ['--hard'])),
    step("--hard 会丢掉工作区的改动,但不是所有东西都丢了:被 reset 掉的 c3 还在对象库里(True);暂存过的 blob(“版本 3 + 暂存的改动”)还能用 git cat-file 读出来;从来没有 git add 的“工作区的改动”没有对象,真的丢了。reflog 里有 reset: moving to HEAD~1 和上一条 commit: c3,ORIG_HEAD 指向被 reset 掉的 c3(True)。", t=tl(S(3)), mark=lidx(S(3), '没有对象,真的丢了', 'ORIG_HEAD 指向被 reset 掉的 c3'), done=lidx(S(3), 'reset: moving to HEAD~1', 'commit: c3'), kv=KV([['已提交的', 'reflog / ORIG_HEAD 能找回'], ['add 过的', 'blob 还在,fsck 能找回'], ['没 add 过的', '真的丢了']], ['没 add 过的'])),
    step("--keep 和 --merge 是更安全的 --hard:遇到会被覆盖的本地改动就拒绝。本例 x 在 c2 和 c3 之间变了,同时本地有暂存和工作区改动,--keep 报 error: Entry 'x' would be overwritten by merge. Cannot merge.,--merge 报 error: Entry 'x' not uptodate. Cannot merge.,HEAD 与两个区域都原样。对比另一个仓库:本地改的是 y(c1 到 c2 之间没碰过 y),--keep 可以成功,HEAD 回到 c1,x 变成 1,y 的本地改动保留。", t=tl(S(4)), mark=lidx(S(4), 'would be overwritten by merge', 'not uptodate'), done=lidx(S(4), 'git reset --keep', 'git reset --merge', '对比'), kv=KV([['--keep', '不覆盖有本地改动的文件,否则拒绝'], ['--merge', '同样保护,对未暂存的更宽松'], ['--hard', '无条件覆盖']], ['--keep'])),
    step("带路径的 reset 只动暂存区:git reset HEAD~1 -- x 把 x 在暂存区里的内容换成 c2 的(x='版本 2'),HEAD 没动(True),工作区的 x 也没动。git status 显示 MM x:暂存区的版本 2 与 HEAD 的版本 3 有差,工作区又与暂存区有差。git reset -- x(不带提交,默认 HEAD)把暂存区里的 x 恢复成 HEAD 的版本,状态变成 ' M x'——这就是平常说的“取消暂存”。", t=tl(S(5)), mark=lidx(S(5), 'MM x', ' M x', 'HEAD 没动: True'), done=lidx(S(5), 'git reset HEAD~1 -- x', 'Unstaged changes after reset'), kv=KV([['reset <提交> -- 路径', '只改暂存区这一项'], ['reset -- 路径', '取消暂存'], ['不动', 'HEAD 和工作区']], ['reset -- 路径'])),
    step("reset 只移动“当前分支”:先 git branch keep 留一个指针在 c3,再 git reset --hard HEAD~2:git log --all --decorate 里 keep 仍在 c3,main(HEAD)回到了 c1,中间的 c2 也在 keep 的历史里。reset 不会改别的分支;被 reset 的分支指针可以再用 reflog 或其它分支找回。", t=tl(S(6)), mark=lidx(S(6), '(HEAD -> main) c1', '(keep) c3'), done=lidx(S(6), 'git log --oneline --all'), kv=KV([['reset', '只移动当前分支的指针'], ['其它分支', '不受影响'], ['找回', 'reflog、其它分支']], ['reset'])),
]
A = mkarti('l50', 50, 'Git,reset,soft,mixed,hard,暂存区,真实验证,动画演示',
    '用同一个三区域各不相同的起点实测 reset:--soft 只动 HEAD,--mixed 动 HEAD 和暂存区,--hard 三个都动;--hard 丢的是从没 add 过的工作区改动,已提交或 add 过的仍能找回;--keep 与 --merge 遇到会被覆盖的本地改动就拒绝;带路径的 reset 只动暂存区;reset 只移动当前分支。',
    '--soft、--mixed、--hard 到底各改变了哪几个区域?哪些改动会真的丢失?--keep 和 --merge 又保护什么?这篇用同一个起点(HEAD、暂存区、工作区各不相同)逐个模式对账。',
    [('1 / 2 / 3', '--soft 动 1 个区域(HEAD),--mixed 动 2 个(+ 暂存区),--hard 动 3 个(+ 工作区)'), ('没 add 过', '--hard 真正丢掉的只有从没 git add 过的工作区改动;已提交的有 reflog,add 过的有 blob'), ('-- 路径', '带路径的 reset 只改暂存区,HEAD 和工作区都不动,等价于“取消暂存”')],
    [('三个区域', '<p>git 里一份文件有三个版本:HEAD(最近提交)、暂存区、工作区。reset 的三种模式决定向这三个区域里的几个同步到目标提交。</p>'),
     ('三种模式', '<p><code>--soft</code> 只移动 HEAD(及当前分支);<code>--mixed</code>(默认)再让暂存区与目标一致,工作区不动;<code>--hard</code> 连工作区也改成目标的内容。未跟踪文件三种模式都不碰。</p>'),
     ('会丢什么', '<p><code>--hard</code> 覆盖掉的工作区改动里,只有从来没 <code>git add</code> 过的部分是真的丢了;add 过的内容作为 blob 仍在对象库里,被 reset 掉的提交可以通过 reflog 和 ORIG_HEAD 找回。</p>'),
     ('--keep 与 --merge', '<p>两者在会覆盖有本地改动的文件时拒绝执行,不像 <code>--hard</code> 无条件覆盖;只改了目标无关的文件时则正常成功并保留本地改动。</p>'),
     ('带路径的 reset', '<p><code>git reset &lt;提交&gt; -- 路径</code> 只替换暂存区里这些路径的内容,HEAD 和工作区都不动;不写提交就是用 HEAD,即“取消暂存”。</p>'),
     ('只动当前分支', '<p>reset 只是移动当前分支的指针,别的分支不受影响。</p>')],
    steps,
    [ENV_I_GIT + '。每个模式在单独的仓库里重做;状态摘要来自 git log、git show :x、cat;提交时间固定',
     '没有验证:reset 到不是当前历史祖先的提交;reset 的 --recurse-submodules;reset 与 sparse-checkout、skip-worktree 的交互(见相关两篇);--patch(reset -p);rebase 过程中的 reset;git restore / git switch 与 reset 的对应关系(restore --staged 等价于 reset -- 路径,没有实测)'],
    'reset 的三种模式')
