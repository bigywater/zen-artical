from lib import *
S = SS('l42')
steps = [
    step("同一个冲突(ours 把第 4 行改成“ours 的修改”并在后面新增“共同新增的一行”,theirs 把第 4 行改成“theirs 的修改”并新增同样的一行)用默认的 merge 样式:冲突标记里只有 ours(HEAD)和 theirs 两段,两边共同新增的“共同新增的一行”在冲突块的外面——git 已经把两边相同的部分挪出了块。", t=tl(S(1)), mark=lidx(S(1), '<<<<<<< HEAD', '=======', '>>>>>>> theirs'), done=lidx(S(1), '第 4 行 ours 的修改', '第 4 行 theirs 的修改', '共同新增的一行'), kv=KV([['merge 样式', '<<<<<<<  =======  >>>>>>> 两段'], ['共同新增的行', '在块外'], ['看不到', '基础版本']], ['merge 样式'])),
    step("diff3 样式(merge.conflictStyle=diff3)多出一段 ||||||| <基础提交>,里面是基础版本的“第 4 行”,能看出两边各自是从什么改过去的。但共同新增的“共同新增的一行”在 ours 和 theirs 两侧各被重复写进了冲突块里,块变长了,更难读。", t=tl(S(2)), mark=lidx(S(2), '|||||||'), done=lidx(S(2), '<<<<<<< HEAD', '第 4 行', '>>>>>>> theirs'), kv=KV([['diff3', '多一段 ||||||| 基础版本'], ['缺点', '共同行被重复写进两边']], ['diff3'])),
    step("zdiff3 样式:保留 ||||||| 基础版本那一段,同时把 ours 与 theirs 共同的“共同新增的一行”挪到冲突块外面,块里只剩真正有分歧的部分:ours 的“第 4 行 ours 的修改”、基础的“第 4 行”、theirs 的“第 4 行 theirs 的修改”。兼顾了 diff3 的信息量和 merge 样式的简洁,所以很多人把 merge.conflictStyle 设成 zdiff3。", t=tl(S(3)), mark=lidx(S(3), '|||||||', '共同新增的一行'), done=lidx(S(3), '<<<<<<< HEAD', '>>>>>>> theirs'), kv=KV([['zdiff3', 'diff3 + 把共同行挪出块'], ['结果', '有基础版本,块里只留分歧']], ['zdiff3'])),
    step("解决到一半想换样式:git checkout --conflict=diff3 f.txt 用 index 里的三个阶段重新生成标记,输出 Recreated 1 merge conflict,标记行是 <<<<<<< ours(第 4 行)、||||||| base(第 7 行)、=======(第 9 行)、>>>>>>> theirs(第 12 行)——可以看到这里的标签是 ours / base,而不是合并时的 HEAD;再 --conflict=merge 换回两段式,|||||||行的个数是 0。注意这会覆盖你已经手工做的编辑。", t=tl(S(4)), mark=lidx(S(4), 'Recreated 1 merge conflict', '7:|||||||'), done=lidx(S(4), '4:<<<<<<< ours', '12:>>>>>>> theirs', '  0'), kv=KV([['git checkout --conflict=<样式>', '按 index 的三个阶段重新生成标记'], ['代价', '覆盖手工编辑'], ['标签', 'ours / base / theirs']], ['git checkout --conflict=<样式>'])),
    step("冲突期间 git diff 显示 combined diff(diff --cc):@@@ 的头里有两个范围,每行前面有两列,分别表示相对 ours 和相对 theirs 的变化。“++<<<<<<< HEAD”前面的两个 + 表示这行相对两边都是新增。git diff --base、--ours、--theirs 则把工作区文件分别和 stage 1/2/3 比较:--base 看到的是基础的“-第 4 行”换成了整个冲突块;--ours 只多出 theirs 的那一半;--theirs 只多出 ours 的那一半。", t=tl(S(5)), mark=lidx(S(5), 'diff --cc', '@@@', '++<<<<<<< HEAD', '--- --ours:', '--- --theirs:'), done=lidx(S(5), 'git diff | sed', '--base'), kv=KV([['diff --cc', '两列前缀:对 ours / 对 theirs'], ['--base / --ours / --theirs', '分别与 stage 1 / 2 / 3 比']], ['diff --cc'])),
    step("rebase 里 ours 与 theirs 的含义调转:git rebase main 在你自己的提交(feature 上的“我的提交”)上重放时发生冲突,标记里 <<<<<<< HEAD 这一侧是正在 rebase 到的新基础(main 上的“第 4 行 ours 的修改”,即上游),另一侧 >>>>>>> 8008ba9 (我的提交) 才是你自己的提交。所以 rebase 时的 HEAD 是上游而不是你;--ours / --theirs 的含义也随之颠倒。", t=tl(S(6)), mark=lidx(S(6), '<<<<<<< HEAD', '>>>>>>> 8008ba9 (我的提交)'), done=lidx(S(6), 'CONFLICT (content)', 'Rebasing (1/1)'), kv=KV([['merge', 'HEAD = 你,theirs = 被合并的分支'], ['rebase', 'HEAD = 上游新基础,另一侧 = 你的提交'], ['结论', 'rebase 时 ours / theirs 颠倒']], ['rebase'])),
    step("git log --merge --left-right:只列出触及冲突文件的、两边各自的提交,< 是 ours 一侧(“ours”提交),> 是 theirs 一侧(“theirs”提交)。冲突时想知道“是谁改了这个文件”,这条命令比翻完整历史快。", t=tl(S(7)), mark=lidx(S(7), '< ', '> '), done=lidx(S(7), 'git log --merge'), kv=KV([['log --merge', '只显示与冲突文件相关的提交'], ['--left-right', '< ours,> theirs']], ['log --merge'])),
]
A = mkarti('l42', 42, 'Git,冲突标记,diff3,zdiff3,merge,真实验证,动画演示',
    '对比同一个冲突在 merge、diff3、zdiff3 三种样式下的标记:merge 只有两段,diff3 多一段基础版本但共同新增的行被重复写进两边,zdiff3 保留基础版本并把共同行挪到块外;git checkout --conflict 重新生成标记;冲突期间的 combined diff;rebase 里 HEAD 一侧是上游,ours/theirs 调转;git log --merge 只列相关提交。',
    '冲突标记 merge、diff3、zdiff3 有什么区别?这篇用同一个冲突、三种样式并排看清,再看 checkout --conflict、combined diff、rebase 时 ours/theirs 调转,以及 log --merge 怎么帮你找相关的提交。',
    [('3 种样式', 'merge.conflictStyle 的 merge、diff3、zdiff3'), ('|||||||', 'diff3 / zdiff3 多出的一段:基础版本,能看出两边各自改了什么'), ('rebase', 'rebase 冲突时 <<<<<<< HEAD 一侧是上游的新基础,不是你自己的提交')],
    [('merge 样式', '<p>默认样式只有 ours 和 theirs 两段。两边完全相同的开头或结尾行已经被挪到冲突块外面。</p>'),
     ('diff3', '<p>多出 <code>|||||||</code> 一段,显示基础版本,便于看出两边各自的改动。缺点是共同的行被重复写进两侧,块更长。</p>'),
     ('zdiff3', '<p>在 diff3 基础上把两边共同的行挪出冲突块,块里只留真正有分歧的部分。信息量和简洁兼得,<code>merge.conflictStyle=zdiff3</code> 是常见的推荐配置。</p>'),
     ('换样式', '<p><code>git checkout --conflict=diff3 文件</code> 用 index 里的三个阶段重新生成标记,但会覆盖你已经做的手工编辑。重新生成的标签是 ours / base / theirs。</p>'),
     ('combined diff', '<p>冲突期间 <code>git diff</code> 输出 <code>diff --cc</code>,每行前面两列分别表示相对 ours 与 theirs 的变化;<code>--base</code>、<code>--ours</code>、<code>--theirs</code> 分别与 stage 1/2/3 比较。</p>'),
     ('rebase', '<p>rebase 是把你的提交一个个重放到新基础上,所以冲突标记里 <code>HEAD</code> 一侧是新基础(上游),另一侧才是你的提交。<code>--ours</code>/<code>--theirs</code> 的含义也因此颠倒。</p>'),
     ('log --merge', '<p><code>git log --merge --left-right</code> 只列出触及冲突文件、两边各自的提交,快速定位谁改了什么。</p>')],
    steps,
    [ENV_I_GIT + '。三种样式用同一个冲突在三个仓库里重做;标记里基础提交的缩写 hash 在输出中省略;rebase 一节的冲突提交 hash 做了固定时间,可复现',
     '没有验证:merge.conflictStyle 的取值以外的 mergetool 工作流;冲突标记长度(conflict-marker-size 属性);二进制文件的冲突;git rerere 记录与重放冲突(见 rerere 一篇);图形化合并工具;多于两方的 octopus 合并冲突'],
    '冲突标记')
