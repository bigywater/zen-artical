from lib import *
S = SS('l54')
steps = [
    step("历史的形状:R 起点之后,x 分支提交 X1(把 f 改成 2)和 X2,y 分支提交 Y1(也把 f 改成 2)和 Y2,main 上 M1 改了 g;随后依次合并 x、合并 y,再有 M2(f 改成 3)、打标签 v1、M3。git log --graph 画出来:* 是提交,| 是延续的线,|\\ 和 |/ 表示线的分出与合回,合并 x 一行里的 |\\ \\ 表示又多出一条线。", t=tl(S(1)), mark=lidx(S(1), '合并 y', '合并 x', '|\\ \\'), done=lidx(S(1), 'M3 改 hy', 'R 起点', 'X1 改 f 为 2', 'Y1 也把 f 改成 2'), kv=KV([['*', '一个提交'], ['|', '延续的线'], ['\\ 和 /', '分出与合回'], ['合并 x / y', '两个合并提交']], ['*'])),
    step("git log -- f(只看改动了 f 的提交)默认只给出 3 个:M2 改 f 为 3、X1 改 f 为 2、R 起点。Y1 也把 f 改成了 2,却不见了。这就是历史简化:合并 y 的提交里,f 与它的两个 parent 都完全相同(TREESAME),git 只沿第一个 parent 往下走,整条 y 分支被当作“对 f 没有贡献”丢掉了。", t=tl(S(2)), mark=lidx(S(2), 'X1 改 f 为 2', 'X1 和 Y1 都把 f 改成了 2'), done=lidx(S(2), 'M2 改 f 为 3', 'R 起点'), kv=KV([['TREESAME', '合并提交的 f 与某个 parent 相同'], ['默认简化', '只沿这个 parent 走'], ['后果', '另一条分支的提交被隐藏']], ['默认简化'])),
    step("选项对比(都是 -- f):默认 3 个(M2、X1、R);--full-history 5 个(M2、合并 x、Y1、X1、R)——不再丢弃分支,Y1 回来了,同时合并 x 也出现了;--full-history --simplify-merges 也是 5 个,但留下的是合并 y 而不是合并 x(去掉对 f 来说多余的合并,保留能解释历史形状的那个);--full-history --sparse 是 10 个:把所有提交都留下,包括与 f 无关的。", t=tl(S(3)), mark=lidx(S(3), '--full-history                     -- f  ( 5', '--full-history --simplify-merges', '--full-history --sparse'), done=lidx(S(3), 'git log                                    -- f  ( 3'), b=bars([['默认', 3, '3 个'], ['--full-history', 5, '5 个'], ['--simplify-merges', 5, '5 个'], ['--sparse', 10, '10 个']], 10, mark=[1, 2, 3], done=[0]), kv=KV([['默认', '简化:丢弃 TREESAME 的分支'], ['--full-history', '不丢弃分支'], ['--simplify-merges', '再去掉多余的合并'], ['--sparse', '连无关提交也留下']], ['--full-history'])),
    step("加 --graph 才能直观看到:git log --graph --full-history -- f 画出 M2 → 合并 y → 一条分支上的 Y1,另一条上的合并 x 与 X1,最后汇合到 R 起点。多出来的 Y1 和 X1 两条线分别对应 y 和 x 两个分支。", t=tl(S(4)), mark=lidx(S(4), 'Y1 也把 f 改成 2', 'X1 改 f 为 2'), done=lidx(S(4), '合并 y', '合并 x', 'R 起点'), kv=KV([['--graph', '把分支画成 ASCII'], ['配合 --full-history', '看清每条改过 f 的支线']], ['--graph'])),
    step("其它简化选项:--first-parent 只沿第一个 parent:M3、M2、合并 y、合并 x、M1、R 起点(完全不看 x、y 分支里的提交);--ancestry-path R..main 只要“R 的后代并且是 main 的祖先”,x、y 的提交和 M1 都在内;X1..main 的版本只要 X1 的后代:M3、M2、合并 y、合并 x、X2;--simplify-by-decoration 只保留带 ref 的提交(main、v1、y、x、R 起点)和保持图连通所需的合并(合并 y)。", t=tl(S(5)), mark=lidx(S(5), '--first-parent:', '--ancestry-path X1..main:', '--simplify-by-decoration:'), done=lidx(S(5), 'M3 改 hy|M2 改 f 为 3|合并 y|合并 x|M1 改 g|R 起点|', 'M3 改 hy|M2 改 f 为 3|合并 y|合并 x|X2 改 gx|'), kv=KV([['--first-parent', '只沿第一个 parent'], ['--ancestry-path A..B', 'A 的后代 ∩ B 的祖先'], ['--simplify-by-decoration', '只留带 ref 的提交']], ['--ancestry-path A..B'])),
    step("--graph 的画法再看一个例子:章鱼合并 p q r(一次合并三个分支)被画成 *-.,下面三条线 |\\ \\,分别通到 r1、q1、p1,最后在 base 汇合。规则:每行的 * 是提交;其它列里的 | 表示这条线上还有更早的提交;\\ 表示分出一条新线,/ 表示线合回去;*-. 是有三个 parent 的合并。", t=tl(S(6)), mark=lidx(S(6), '*-.', '|\\ \\'), done=lidx(S(6), '章鱼合并 p q r', 'r1', 'q1', 'p1', 'base'), kv=KV([['*-.', '三个 parent 的合并'], ['| \\ /', '线的延续、分出、合回'], ['每个 *', '一个提交']], ['*-.'])),
]
A = mkarti('l54', 54, 'Git,git log,graph,历史简化,full-history,真实验证,动画演示',
    '实测 git log 的历史简化:git log -- f 在 X、Y 两个分支都把 f 改成 2 时只显示 X1(合并 y 与两个 parent 都 TREESAME,只沿第一个 parent 走),--full-history 把 Y1 找回来,--simplify-merges 保留解释形状的合并,--sparse 保留全部 10 个;以及 --first-parent、--ancestry-path、--simplify-by-decoration,和 --graph 的画法。',
    '为什么 git log -- 某个文件 有时候少了一些改过它的提交?这是历史简化。这篇造一个两个分支都改了同一个文件、先后合并的历史,看 --full-history、--simplify-merges、--sparse 各自的结果,再学会读 --graph 的 ASCII 图。',
    [('3 vs 5', '默认的 git log -- f 与 --full-history 显示的提交数;默认少了 Y1'), ('TREESAME', '合并提交的文件与某个 parent 完全一样,git 就只沿那个 parent 往下走'), ('*-.', '章鱼合并在 --graph 里的画法')],
    [('实验历史', '<p>x、y 两个分支各自把 f 改成同样的值 2,先后合并进 main,之后 main 上又有 M2、M3。这是“两条分支做了相同改动”的典型情形。</p>'),
     ('历史简化', '<p>给 <code>git log</code> 加路径后,git 会简化历史:没改动这些路径的提交不显示;遇到合并提交,如果它的路径内容与某一个 parent 完全一样(TREESAME),就只沿那个 parent 走,另一条分支整条被忽略。这能让输出更简洁,但会隐藏掉其它分支里同样改过文件的提交。</p>'),
     ('--full-history', '<p><code>--full-history</code> 不简化合并,所有改动过路径的提交都显示(同时还显示相关的合并)。<code>--simplify-merges</code> 在此基础上去掉对这些路径来说多余的合并;<code>--sparse</code> 把无关的提交也留下。</p>'),
     ('--graph', '<p><code>--graph</code> 用 ASCII 把提交图画出来。与 <code>--full-history</code> 搭配,能看清每条改过文件的支线。</p>'),
     ('其它选项', '<p><code>--first-parent</code> 只沿第一个 parent;<code>--ancestry-path A..B</code> 只显示 A 的后代同时又是 B 的祖先的提交;<code>--simplify-by-decoration</code> 只留带分支/标签的提交以及保持图连通的合并。</p>'),
     ('读图', '<p><code>*</code> 是提交,<code>|</code> 是延续的线,<code>\\\\</code> 与 <code>/</code> 表示分出与合回,<code>*-.</code> 是有三个 parent 的章鱼合并。</p>')],
    steps,
    [ENV_I_GIT + '。历史由脚本构造(X、Y 两个分支做完全相同的 f 改动,先后合并);提交时间固定;各选项的提交数来自 git log --format=%s 的行数',
     '没有验证:--full-history 与 --simplify-merges 在更复杂的真实历史上的区别;--show-pulls;--follow 与历史简化的关系;git log -L;--date-order、--topo-order 对 --graph 画法的影响;--graph 的颜色'],
    'log 的 --graph 与历史简化')
