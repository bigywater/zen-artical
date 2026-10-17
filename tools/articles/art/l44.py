from lib import *
S = SS('l44')
steps = [
    step("快进:main 停在 M1,feature 比它多 F1、F2。git merge feature 输出 Updating <旧>..<新> 和 Fast-forward;对象数 8 → 8(新增 0 个)——只是把 main 这个分支指针挪到了 feature 的位置(main 与 feature 现在是同一个提交)。main 的 reflog 多了一行 merge feature: Fast-forward;历史是一条直线 F2 → F1 → M1。", t=tl(S(1)), mark=lidx(S(1), 'Fast-forward', '新增 0 个', 'merge feature: Fast-forward'), done=lidx(S(1), 'main 现在等于 feature', '* F2', '* F1', '* M1'), kv=KV([['快进', '只移动分支指针'], ['新对象', '0 个'], ['历史', '一条直线']], ['快进'])),
    step("--no-ff:同样的情形强制创建合并提交。git merge --no-ff -m \"合并 feature\" feature 输出 Merge made by the 'ort' strategy.;对象数 8 → 9(只新增 1 个,合并提交本身)。合并提交的 tree 就是 feature 末端的 tree(同一个对象,True),有 2 个 parent。git log --graph 画出一个菱形:合并 feature 在最上面,F2、F1 在一条支线上,M1 在底部。", t=tl(S(2)), mark=lidx(S(2), "Merge made by the 'ort' strategy", '新增 1 个', 'parent 数: 2'), done=lidx(S(2), '*   合并 feature', '| * F2', '| * F1'), b=bars([['快进:新增对象', 0, '0 个'], ['--no-ff:新增对象', 1, '1 个']], 1, mark=[1], done=[0]), kv=KV([['--no-ff', '总是创建合并提交'], ['tree', '复用 feature 末端的 tree'], ['新对象', '只有 1 个 commit']], ['--no-ff'])),
    step("main 也有了新提交 M2(分叉),就无法快进。git merge --ff-only feature 直接拒绝:提示 Diverging branches can't be fast-forwarded,并给出 fatal: Not possible to fast-forward, aborting.,提交数不变;merge.ff=only 配置同样让普通 git merge 拒绝。不加 --ff-only 的 git merge 则生成合并提交(Merge made by the 'ort' strategy.)。", t=tl(S(3)), mark=lidx(S(3), 'fatal', 'hint'), done=lidx(S(3), "Merge made by the 'ort' strategy"), kv=KV([['--ff-only', '不能快进就拒绝'], ['merge.ff=only', '把它变成默认'], ['pull --ff-only', '同理,避免意外产生合并提交']], ['--ff-only'])),
    step("历史形状:快进之后是一条直线(F2、F1、M1),git log --first-parent 也是同样三个,--merges 数出 0 个。--no-ff 之后 git log --graph 有菱形,--first-parent 只剩 合并 feature 和 M1 两个——把功能分支的提交折叠成一个入口;--merges 数出 1 个。--no-ff 在主线上留下“这几个提交曾经是一个功能”的标记。", t=tl(S(4)), mark=lidx(S(4), '[--no-ff]', '合并feature'), done=lidx(S(4), '[快进]', '--first-parent'), kv=KV([['快进', '看不出功能分支'], ['--no-ff', '主线上有合并提交'], ['--first-parent', '只看主线,折叠功能分支']], ['--no-ff'])),
    step("--squash:git merge --squash feature 输出 Squash commit -- not updating HEAD,把 feature 的全部改动放进暂存区(A  f),HEAD 没动;自己 git commit 之后得到一个只有 1 个 parent 的提交,它的 tree 与 feature 末端的 tree 相同(True),但提交图里没有任何指向 feature 的链接。因此 git branch --merged 里没有 feature,git branch -d feature 报 error: the branch 'feature' is not fully merged,要用 -D 才能删。", t=tl(S(5)), mark=lidx(S(5), 'Squash commit', 'not fully merged', '(--merged 里没有 feature)'), done=lidx(S(5), '新提交的 parent 数: 1', 'A  f'), kv=KV([['--squash', '压成一个单 parent 的提交'], ['树', '与 feature 末端相同'], ['代价', 'feature 不算已合并,-d 会拒绝']], ['--squash'])),
]
A = mkarti('l44', 44, 'Git,fast-forward,no-ff,merge,squash,真实验证,动画演示',
    '对比三种合并形态:快进只移动分支指针(新增对象 0 个);--no-ff 创建只新增 1 个对象的合并提交,其 tree 就是 feature 末端的 tree;分叉后无法快进,--ff-only 与 merge.ff=only 直接拒绝;--no-ff 在主线留下合并提交,--first-parent 把功能分支折叠;--squash 得到单 parent 的提交,feature 不算已合并。',
    '什么时候 git merge 只是“挪一下指针”?--no-ff 到底多出了什么?--ff-only 又在什么情况下拒绝?这篇逐种实测,数新增了几个对象,看历史的形状,以及 --squash 为什么会让 git branch -d 说“没合并”。',
    [('0 个', '快进合并新增的对象数'), ('1 个', '--no-ff 新增的对象数:合并提交本身,tree 复用 feature 末端的'), ('not fully merged', '--squash 之后 git branch -d feature 的回答——提交图里没有链接')],
    [('快进', '<p>当前分支是被合并分支的祖先时,合并只是把分支指针挪到对方的位置:没有新提交、没有新对象,历史是一条直线。reflog 里记着 <code>merge feature: Fast-forward</code>。</p>'),
     ('--no-ff', '<p>强制创建合并提交,即使可以快进。新提交的 tree 就是 feature 末端的 tree(复用同一个对象),有两个 parent,整个合并只新增 1 个对象。好处是主线上留下功能边界,<code>--first-parent</code> 可以把一个功能折叠成一行。</p>'),
     ('分叉', '<p>双方都有对方没有的提交时无法快进。默认生成合并提交;<code>--ff-only</code>(或 <code>merge.ff=only</code>、<code>pull --ff-only</code>)改为直接拒绝,提示 <code>Not possible to fast-forward</code>。</p>'),
     ('历史形状', '<p>快进是直线,看不出哪些提交属于同一个功能;<code>--no-ff</code> 有菱形,<code>git log --merges</code> 能数出合并次数。</p>'),
     ('--squash', '<p><code>--squash</code> 把对方分支的所有改动放进暂存区,由你提交为一个单 parent 的普通提交。结果的 tree 相同,但提交图里没有指向 feature 的连线,所以 git 不认为它“已合并”,<code>git branch -d</code> 会拒绝。</p>')],
    steps,
    [ENV_I_GIT + '。对象数 = git count-objects -v 里的 count + in-pack;提交使用真实时间,输出里的 hash 做了去除',
     '没有验证:merge.ff=false 配置、git pull 的 fast-forward 行为(上面只用 --ff-only 做了对比);rebase 之后再快进合并的历史形状;--no-ff 对 git bisect、git revert -m 的影响(见后面几篇);GitHub 等托管平台的 “Squash and merge” 按钮'],
    'fast-forward 与 --no-ff')
