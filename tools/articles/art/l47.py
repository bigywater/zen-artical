from lib import *
S = SS('l47')
steps = [
    step("feature 上的“修复:第 10 行”(作者 Alice)被 Bob 用 git cherry-pick -x 摘到 main:新提交的说明相同,作者仍是 Alice,提交者变成 Bob,parent 是 main 的上一个提交而不是原来的基础提交;-x 在说明末尾追加一行 (cherry picked from commit <原 hash>)。新旧提交的 tree 不同(新的带有 main 在开头加的两行),hash 自然不同。", t=tl(S(1)), mark=lidx(S(1), 'committer=Bob', 'cherry picked from commit'), done=lidx(S(1), 'author=Alice', 'parent', '两个提交的 tree 不同'), kv=KV([['作者', '保留'], ['提交者', '执行 cherry-pick 的人'], ['-x', '说明里追加来源 hash'], ['hash', '新的']], ['-x'])),
    step("cherry-pick 本质是一次三方合并:基础 = 那个提交的 parent,ours = 当前 HEAD,theirs = 那个提交。用 git merge-tree --write-tree --merge-base=<提交>^ HEAD <提交> 手工做同样的合并,得到的 tree(8d786e2a105f…)与 cherry-pick 之后 HEAD 的 tree 完全相同(True)。cherry-pick 就是把这个 tree 配上原作者和说明,做成新提交。", t=tl(S(2)), mark=lidx(S(2), '相同: True'), done=lidx(S(2), 'merge-tree 算出的 tree'), kv=KV([['基础', '提交的 parent'], ['ours / theirs', 'HEAD / 那个提交'], ['结果', '同一个 tree']], ['基础'])),
    step("patch-id 是补丁内容的指纹,忽略行号:同一个补丁 cherry-pick 到别处,原提交与新提交的 patch-id 都是 b2ad9fde2a9c…(相同),尽管 hash 不同,而且修改所在行号从第 10 行变成第 12 行(@@ -7,7 和 @@ -9,7 不同)。用 git patch-id --stable 算几个手写补丁:改第 1 行和同样内容改第 10 行的 patch-id 相同(5e3837421ef7);多一个感叹号变成 4c68380e8a0e;行尾多空白仍是 5e3837421ef7(--stable 忽略空白)。", t=tl(S(3)), mark=lidx(S(3), '原提交的 patch-id', '新提交的 patch-id', '多一个感叹号'), done=lidx(S(3), 'A(改第 1 行)', '@@ -9,7 +9,7 @@', '@@ -7,7 +7,7 @@'), kv=KV([['patch-id', '补丁的指纹'], ['忽略', '行号、空白(--stable)'], ['敏感', '增删的内容']], ['patch-id'])),
    step("git cherry -v main feature 用 patch-id 判断 main 里是否已有等价补丁:cherry-pick 之前,两个提交都是 +(main 里没有);把“修复:第 10 行”摘到 main 之后,它变成 -(main 里已有等价的补丁),“后续提交”仍是 +。git log --left-right --cherry-pick main...feature 同样把互相等价的提交过滤掉,只剩 < main 在文件开头加两行 和 > 后续提交。", t=tl(S(4)), mark=lidx(S(4), '- <sha40> 修复:第 10 行', '--cherry-pick'), done=lidx(S(4), '+ <sha40> 修复:第 10 行', '+ <sha40> 后续提交', '< main 在文件开头加两行'), kv=KV([['git cherry', '+ 还没有 / - 已经有等价补丁'], ['--cherry-pick', '过滤掉等价的提交'], ['依据', 'patch-id']], ['git cherry'])),
    step("冲突之后手工解决的结果往往改变补丁内容:两边都改了第 10 行,cherry-pick 冲突(.git 里有 CHERRY_PICK_HEAD),手工合并成“我手工合并的”后 --continue。新提交的 patch-id(45ea0bf645fd…)与原提交的(e24b90ae0805…)不同,git cherry -v main feature 仍然把原提交标成 +——git 认不出它们是同一个改动。", t=tl(S(5)), mark=lidx(S(5), '相同: False', '+ <sha40> 改第 10 行', 'CONFLICT'), done=lidx(S(5), 'CHERRY_PICK_HEAD'), kv=KV([['手工解决冲突', '补丁内容变了'], ['patch-id', '不再相同'], ['后果', 'git cherry / rebase 认不出重复']], ['手工解决冲突'])),
    step("补丁已经在当前分支里时再 cherry-pick:输出 Auto-merging f.txt,然后 The previous cherry-pick is now empty, possibly due to conflict resolution. If you wish to commit it anyway, use: …——git 发现应用之后没有任何改动,不会自己生成空提交,而是停下来让你选择(--skip 跳过,或 --allow-empty 保留)。", t=tl(S(6)), mark=lidx(S(6), 'now empty'), done=lidx(S(6), 'git cherry-pick', 'Auto-merging'), kv=KV([['已经应用过', '结果是空提交'], ['git 的做法', '停下来问你'], ['选项', '--skip / --allow-empty / --keep-redundant-commits']], ['git 的做法'])),
]
A = mkarti('l47', 47, 'Git,cherry-pick,patch-id,git cherry,真实验证,动画演示',
    '实测 cherry-pick 与 patch-id:cherry-pick 保留作者、换提交者与 parent,-x 追加来源;它等价于以 parent 为基础的三方合并,与 git merge-tree 的结果 tree 一致;patch-id 是忽略行号的补丁指纹,同一补丁摘到别处不变,多改一个字符就变,--stable 忽略空白;git cherry 与 log --cherry-pick 靠它识别等价提交;手工解决冲突后 patch-id 变化;补丁已存在时 cherry-pick 变空。',
    'cherry-pick 摘过去的提交和原来的是同一个提交吗?git 怎么知道两个提交是“同一个补丁”?这篇验证 cherry-pick 的三方合并本质,算 patch-id,再看 git cherry 和 log --cherry-pick 依据什么判断,以及哪些情况会让 patch-id 失效。',
    [('b2ad9fde…', '同一补丁摘到别处,原提交与新提交的 patch-id 完全相同(行号从 10 变成 12)'), ('+ / −', 'git cherry:+ 表示上游还没有等价补丁,- 表示已经有'), ('手工合并', '冲突后手工解决的结果与原补丁的 patch-id 不同,git cherry 认不出')],
    [('cherry-pick 做了什么', '<p>把一个提交的改动在当前分支上再做一遍:新提交保留原作者和说明,提交者换成执行者,parent 不同,hash 当然不同;<code>-x</code> 在说明里记下来源。</p>'),
     ('就是三方合并', '<p>基础是那个提交的 parent,ours 是当前 HEAD,theirs 是那个提交,结果 tree 配上原作者和说明做成新提交。用 <code>git merge-tree</code> 手工做同样的合并,tree 与 cherry-pick 的结果完全一致。</p>'),
     ('patch-id', '<p><code>git patch-id</code> 对补丁的增删内容取指纹,忽略行号;<code>--stable</code> 还忽略空白。所以同一个补丁摘到文件的不同位置仍有相同的 patch-id,改动内容一变就不同。</p>'),
     ('判断重复', '<p><code>git cherry</code>、<code>git log --cherry-pick</code>、rebase 跳过重复补丁都用 patch-id:相同则认为“上游已经有这个改动”。</p>'),
     ('盲点', '<p>冲突后手工合并的结果往往不再是原来的补丁,patch-id 随之改变,上面这些命令就认不出它们是同一个改动;所以 <code>-x</code> 记下来源很有用。</p>'),
     ('空提交', '<p>补丁已经在当前分支里时,cherry-pick 的结果为空,git 会停下来让你选择跳过或保留空提交。</p>')],
    steps,
    [ENV_I_GIT + '。作者与时间固定;patch-id 来自 git patch-id --stable;“手写补丁”的 patch-id 是直接构造文本得到的',
     '没有验证:cherry-pick 合并提交需要的 -m;cherry-pick 一个范围 A..B 与 --no-commit;patch-id 对二进制补丁、重命名补丁的处理;rebase 靠 patch-id 跳过重复(上一篇已经看到);git cherry-pick 的 --strategy 与 -X 选项;context 行不同时 patch-id 的变化(只验证了行号变化,上下文内容相同)'],
    'cherry-pick 与 patch-id')
