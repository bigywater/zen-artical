from lib import *
S = SS('l53')
steps = [
    step("同一对小文件(旧:} else { / y(); / { / } / } else { / return; / x(); / return;,新版在中间插入了几行),四种算法给出的 diff 不一样:myers 与 minimal 都是 +6 −1(一个 hunk),histogram 同样 +6 −1;patience 是 +8 −3,把 { 之后的 } 和 } else { return; 当作被删除又重新加回,diff 反而更长。都是正确的补丁(应用后得到同一个新文件),只是对齐方式不同。", t=tl(S(1)), mark=lidx(S(1), '[patience] +8 -3', '[myers] +6 -1', '[histogram] +6 -1'), done=lidx(S(1), '[minimal] +6 -1', '旧:', '新:'), b=bars([['myers', 7, '+6 −1 = 7 行'], ['minimal', 7, '7 行'], ['histogram', 7, '7 行'], ['patience', 11, '+8 −3 = 11 行']], 11, mark=[3], done=[0, 1, 2]), kv=KV([['myers(默认)', '最短编辑脚本的快速近似'], ['minimal', '保证最少'], ['patience', '先对齐唯一出现的行,更“可读”但可能更长'], ['histogram', 'patience 的改进版']], ['patience'])),
    step("300 次随机编辑(200 行的文件做 3~8 次插入、删除、整段搬动),统计四种算法给出的改动行数:myers 合计 10,741、minimal 同样是 10,741(两者在这批数据里完全一致,各 300/300 次最少);patience 10,823(290 次最少);histogram 10,763(294 次最少)。300 次里只有 14 次四种算法给出的改动行数不全相同。hunk 数合计:myers/minimal 1,608,patience 1,604,histogram 1,610,差别很小。", t=tl(S(2)), mark=lidx(S(2), 'patience', 'histogram'), done=lidx(S(2), 'myers', 'minimal', '300 次里有 14 次'), b=bars([['myers', 10741, '10,741'], ['minimal', 10741, '10,741'], ['histogram', 10763, '10,763'], ['patience', 10823, '10,823']], 10823, mark=[3], done=[0, 1, 2]), kv=KV([['随机编辑', '绝大多数情况四种算法结果一致'], ['差异', '300 次里只有 14 次改动行数不同'], ['最少改动', 'myers = minimal,patience 略多']], ['差异'])),
    step("速度:20 万行的文件,约 2% 的行被改动(4000 次替换、插入、删除),git diff --stat 的耗时(5 次中位数):myers 54.3 ms、minimal 54.0 ms、patience 56.1 ms、histogram 63.4 ms。在这个规模上差异不到 20%,选算法的依据应该是可读性,而不是速度。", t=tl(S(3)), mark=lidx(S(3), 'histogram'), done=lidx(S(3), 'myers', 'minimal', 'patience'), b=bars([['myers', 54.3, '54.3 ms'], ['minimal', 54.0, '54.0 ms'], ['patience', 56.1, '56.1 ms'], ['histogram', 63.4, '63.4 ms']], 63.4, mark=[3], done=[0, 1, 2]), kv=KV([['20 万行', '四种都在 54~63 ms'], ['结论', '速度差别不大']], ['结论'])),
    step("怎么选:diff.algorithm 没设置时默认是 myers(git config 没有输出),设成 histogram 之后 git diff --stat 变成 6 insertions、1 deletion(同 histogram);--diff-algorithm=myers 命令行选项覆盖配置,也是 6 和 1;--patience 是 8 和 3,--histogram 与 --minimal 都是 6 和 1。配置只是改默认,命令行随时可以覆盖。", t=tl(S(4)), mark=lidx(S(4), '--patience'), done=lidx(S(4), 'diff.algorithm 未设置', 'histogram'), kv=KV([['默认', 'myers'], ['配置', 'diff.algorithm=histogram'], ['命令行', '--patience / --histogram / --minimal / --diff-algorithm=']], ['配置'])),
]
A = mkarti('l53', 53, 'Git,diff,myers,patience,histogram,真实验证,动画演示',
    '对比 git diff 的四种算法:在一个随机搜出的例子里 myers/minimal/histogram 给出 +6 −1,patience 给出 +8 −3;300 次随机编辑中 myers 与 minimal 合计 10,741 行改动(一致),patience 10,823,histogram 10,763,只有 14 次改动行数不全相同;20 万行文件上四种算法耗时 54~63 ms;diff.algorithm 默认 myers。',
    'myers、patience、histogram 这几个 diff 算法到底差在哪?会不会真的给出不同的补丁?哪个更快?这篇用随机搜出的反例、300 次随机编辑的统计和 20 万行文件的计时来回答,结论可能和流传的说法有些不同。',
    [('14 / 300', '300 次随机编辑里,四种算法给出的改动行数不全相同的次数'), ('10,741 / 10,823', 'myers 与 patience 在 300 次随机编辑上的改动行数合计'), ('54 ~ 63 ms', '20 万行的文件上四种算法的耗时范围')],
    [('同样正确,但不同', '<p>四种算法给出的补丁都能把旧文件变成新文件。差别在于怎样对齐:myers 找(近似)最短的编辑脚本,patience 先对齐在两个文件里都只出现一次的行,histogram 是 patience 的改进。</p>'),
     ('不是 patience 一定更好', '<p>在随机搜出的反例里,patience 的补丁反而更长(+8 −3,对比 myers 的 +6 −1);在 300 次随机编辑的统计里,myers 与 minimal 的改动行数最少,patience 略多。patience 的好处是在“有很多相同的括号、空行”的代码里更容易读,而不是更短。</p>'),
     ('速度', '<p>20 万行、约 2% 改动的文件上,四种算法耗时都在 54~63 ms,差别不到 20%。</p>'),
     ('怎么选', '<p><code>diff.algorithm</code> 设置默认算法(不设就是 myers),命令行 <code>--patience</code>、<code>--histogram</code>、<code>--minimal</code>、<code>--diff-algorithm=</code> 可随时覆盖。选哪个看可读性。</p>')],
    steps,
    [ENV_I_GIT + '。随机数据由固定种子生成;例子是从随机小文件里搜出的第一个 myers 与 patience 输出不同的一对;“改动行数”是 git diff 输出中以 + 或 - 开头的行数;耗时 5 次中位数,含进程启动',
     '没有验证:真实代码仓库上的 diff 可读性对比(用随机行代替);git merge 时 -X patience/-X histogram 对冲突的影响;--anchored 选项;--minimal 在更大文件上的耗时(这里与 myers 相同);word-diff、--color-moved 等其它显示方式'],
    'diff 算法')
