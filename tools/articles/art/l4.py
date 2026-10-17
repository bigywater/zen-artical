from lib import *
S = SS('l4')
steps = [
    step("数 commit 里 parent 行的个数:根提交 0 个(grep -c 输出 0),普通提交 1 个,合并一个分支的提交 2 个(parent d0bbaee…、parent dd3c813…),一次合并两个分支的“章鱼合并”3 个(bae945c、e3e50e4、c72d0d8)。git log --graph 里章鱼合并 32c113b 画成 *-. 加三条线。所谓合并只是 commit 里多了几行 parent。", t=tl(S(1)), mark=lidx(S(1), 'parent bae945c', 'parent e3e50e4', 'parent c72d0d8', '*-.'), done=lidx(S(1), 'parent d0bbaee', 'parent dd3c813', 'grep -c'), b=bars([['根提交', 0, '0 个 parent'], ['普通提交', 1, '1 个'], ['合并', 2, '2 个'], ['章鱼合并', 3, '3 个']], 3, mark=[3], done=[0, 1, 2]), kv=KV([['根提交', '没有 parent 行'], ['普通提交', '1 个 parent'], ['合并', '2 个或更多 parent'], ['章鱼合并', '一次合并多个分支,parent 行有多个']], ['合并'])),
    step("author 和 committer 是两个角色:Alice 在 10:10 提交,作者和提交者都是 Alice 10:10;Bob 在 30 分钟后 amend,作者还是 Alice 10:10,提交者变成 Bob 10:30;Carol 在 50 分钟后把这个提交 cherry-pick 到另一个分支,作者仍是 Alice 10:10,提交者变成 Carol 10:50。作者记录谁写的这个改动,提交者记录谁把它放进当前这条历史。", t=tl(S(2)), mark=lidx(S(2), '提交者 Bob', '提交者 Carol'), done=lidx(S(2), '提交者 Alice'), kv=KV([['author', '写改动的人与时间,amend / cherry-pick 保留'], ['committer', '创建这个 commit 对象的人与时间,每次重写都会换'], ['amend / cherry-pick', '只换 committer']], ['committer'])),
    step("同一个提交有两个时间:--date=iso 下作者日期 10:10:00,提交日期 10:50:00;git show --format=fuller 把 Author / AuthorDate / Commit / CommitDate 四项都列出来。日常看到的 git log 默认显示的是作者日期,要看提交日期得用 %cd 或 fuller。", t=tl(S(3)), mark=lidx(S(3), '提交日期 2026', 'CommitDate'), done=lidx(S(3), '作者日期 2026', 'AuthorDate'), kv=KV([['git log 默认', '显示作者日期'], ['fuller', '四项全显示'], ['各管各的', '两个时间戳互相独立']], ['git log 默认'])),
    step("头部里的时区:author 张三 1772326800 +0800,committer Dave 1772326800 -0500;两个时间戳数值完全相同(相减 0 秒),只是一个以东八区、一个以西五区显示:2026-03-01 09:00:00 +0800 与 2026-02-28 20:00:00 -0500。git 存的永远是 Unix 时间戳加一个时区偏移字符串,偏移只影响显示。", t=tl(S(4)), mark=lidx(S(4), 'author 张三', 'committer Dave', '相减'), done=lidx(S(4), '+0800 | ', '%at %ct', '1772326800 1772326800'), kv=KV([['存什么', 'Unix 时间戳 + 时区偏移'], ['偏移的作用', '只影响显示,不影响时刻'], ['作者与提交者', '可以有不同的时区']], ['存什么'])),
    step("parent 的顺序有意义:git log --first-parent 只沿第一个 parent 走,章鱼合并 → 合并 → 普通提交 → 根提交,把被合并进来的分支隐藏了;HEAD^1 是合并发生时所在的分支(bae945c),HEAD^2 是 x2(e3e50e4),HEAD^3 是 x3(c72d0d8)。合并者所在的分支永远是第一个 parent。", t=tl(S(5)), mark=lidx(S(5), '--first-parent', 'HEAD^2'), done=lidx(S(5), 'bae945c 合并', 'e3e50e4 x2', 'c72d0d8 x3'), kv=KV([['^1', '合并发生时你所在的分支'], ['^2、^3', '被合并进来的分支,按命令里的顺序'], ['--first-parent', '只看主线']], ['^1'])),
]
A = mkarti('l4', 4, 'Git,commit,parent,author,committer,真实验证,动画演示',
    '在真实仓库里数 commit 对象的 parent 行(根提交 0、普通 1、合并 2、章鱼合并 3);用 amend 和 cherry-pick 验证 author 保留、committer 与时间改变;同一提交的两个时间戳互相独立,头部的时区只影响显示;parent 的顺序决定 HEAD^1 / HEAD^2 / --first-parent 的含义。',
    'commit 对象里的 parent、author、committer 到底各管什么?这篇造了根提交、合并、章鱼合并,又让 Alice、Bob、Carol 分别提交、amend、cherry-pick,看哪些字段变、哪些不变,再看时区是怎么存的。',
    [('3 个', '一次合并两个分支的章鱼合并,commit 里有 3 行 parent'), ('作者不变', 'amend 和 cherry-pick 之后 author 仍是 Alice,只有 committer 变成 Bob / Carol'), ('0 秒', '+0800 和 -0500 两个时区写的 author 与 committer 时间戳相减,同一时刻')],
    [('parent 行', '<p>commit 对象里有几行 <code>parent</code> 就有几个父提交:根提交没有,普通提交一个,合并提交两个或更多。所谓“合并”并没有特殊的对象类型,只是多了 parent 行。</p>'),
     ('author 与 committer', '<p><code>author</code> 是改动的原作者与时间,<code>committer</code> 是创建这个 commit 对象的人与时间。<code>amend</code>、<code>cherry-pick</code>、<code>rebase</code> 都会生成新的 commit 对象,committer 随之变成执行操作的人,author 保持不变。给别人的补丁打上去时,这正是作者署名不丢的原因。</p>'),
     ('两个时间', '<p>两个时间戳互相独立。<code>git log</code> 默认显示作者日期;<code>--format=fuller</code> 或 <code>%cd</code> 才看到提交日期。统计“某天提交了多少”时要弄清用的是哪一个。</p>'),
     ('时区', '<p>头部里存的是 Unix 时间戳和时区偏移。偏移只影响显示,相同的时间戳在不同时区下是同一时刻,作者和提交者可以各写各的时区。</p>'),
     ('parent 的顺序', '<p>parent 行的顺序有意义:第一个是合并时你所在的分支,后面是被合并进来的。<code>HEAD^1</code>、<code>HEAD^2</code> 与 <code>--first-parent</code> 都依赖这个顺序;<code>git revert -m</code> 的编号也是它(后面有专门一篇)。</p>')],
    steps,
    [ENV_I_GIT + '。作者、提交者与时间由环境变量固定;时区一节的 张三 / Dave 两个名字是实验里设的,邮箱沿用默认值',
     '没有验证:带 GPG / SSH 签名的 commit 多出来的 gpgsig 头(后面有 SSH 签名一篇);commit 里的 encoding 头(非 UTF-8 提交说明);mergetag 头(合并签名的标签时才有);作者与提交者相同但时区不同时 git log 的排序细节'],
    'parent 与 author')
