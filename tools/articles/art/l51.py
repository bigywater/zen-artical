from lib import *
S = SS('l51')
steps = [
    step("1000 个提交的线性历史,第 1 个是好的、第 1000 个是坏的。git bisect start 之后 git 立刻检出中间的“提交 500”,并输出 Bisecting: 499 revisions left to test after this (roughly 9 steps)。我们按 bug 在第 637 个提交引入来回答:500 是 good → 还剩 249(roughly 8 steps),检出 750;750 是 bad → 还剩 124(7 步),检出 625;625 good → 还剩 62(6 步),检出 687;687 bad → 还剩 30(5 步)。每次剩余的可疑提交数约减半。git bisect log 记下了每一步,可以保存并重放。", t=tl(S(1)), mark=lidx(S(1), '499 revisions left', '249 revisions left', '124 revisions left', '62 revisions left', '30 revisions left'), done=lidx(S(1), '版本 500', '版本 750', '版本 625', '版本 687', 'git bisect log'), b=bars([['开始', 999, '999 个可疑'], ['第 1 步后', 499, '499'], ['第 2 步后', 249, '249'], ['第 3 步后', 124, '124'], ['第 4 步后', 62, '62'], ['第 5 步后', 30, '30']], 999, mark=[5], done=[0, 1, 2, 3, 4]), kv=KV([['每一步', '检出可疑范围的中点'], ['你的回答', 'good / bad'], ['剩余', '约减半']], ['每一步'])),
    step("git bisect run 让脚本自动回答 good / bad(退出码决定)。bug 在第 637 个提交引入:脚本被调用 10 次,每次输出一行 Bisecting: …(共 9 行,从 249 revisions left 一路到 0 revisions left),最后输出 <sha> is the first bad commit,找到的就是“提交 637”,和预期一致。", t=tl(S(2)), mark=lidx(S(2), 'first bad commit', '提交 637'), done=lidx(S(2), '脚本被调用 10 次', 'Bisecting: 249', 'Bisecting: 0 revisions'), kv=KV([['bisect run <脚本>', '脚本退出码 0 = good,非 0 = bad'], ['次数', '10 次测试找到 1000 个里的 1 个'], ['结果', 'first bad commit']], ['bisect run <脚本>'])),
    step("100 个随机的 bug 位置(在 2 到 1000 之间)各跑一次 bisect run:100 个全部找对(100/100);测试次数最少 9、最多 10,平均 9.95(log2(1000) = 9.97)。分布:9 次的 5 个、10 次的 95 个。二分的次数就是 ⌈log2 N⌉,不管 bug 在哪。", t=tl(S(3)), mark=lidx(S(3), '找对了', '平均'), done=lidx(S(3), '分布'), b=bars([['9 次', 5, '5 个'], ['10 次', 95, '95 个']], 95, mark=[1], done=[0]), kv=KV([['找对', '100 / 100'], ['测试次数', '9 ~ 10,平均 9.95'], ['理论', '⌈log2 1000⌉ = 10']], ['测试次数'])),
    step("历史不是直线时,bisect 按“可疑集合里每个提交加上它的祖先的个数”来折半,而不是按时间。例子:M1 之后 main 有 13 个可疑提交(M2、M3,侧枝的 S1~S8,合并提交,M4、M5)。每个候选的计数:S1~S8 是 1~8,M2、M3 是 1、2,合并提交是 11,M4、M5 是 12、13。一半是 6.5,S6(=6)和 S7(=7)一样接近;git bisect start 检出的是 S6,输出 Bisecting: 6 revisions left to test after this (roughly 3 steps)。", t=tl(S(4)), mark=lidx(S(4), 'S6', '6 revisions left'), done=lidx(S(4), 'M5', 'S1=1', '可疑集合是 13 个'), kv=KV([['可疑集合', 'bad 的祖先减去 good 的祖先'], ['选择标准', '让两边的可疑数尽量相等'], ['不看', '提交时间']], ['选择标准'])),
    step("脚本退出 125 表示“这个提交无法测试,跳过”:这里把版本 500~520 当作无法编译的区间(脚本 exit 125),bisect 仍然找到“提交 637”,一共 10 步;前三步:499 → 439 → 219 revisions left——第 2 步剩余不是 249 而是 439,因为中点落在了不能测的区间里,git 把它们排除后换了一个提交。退出码约定:0 = good;1~124、126、127 = bad;125 = skip;≥128 = 终止整个 bisect。", t=tl(S(5)), mark=lidx(S(5), '439 revisions left', '提交 637'), done=lidx(S(5), '499 revisions left', '219 revisions left', '退出码'), kv=KV([['exit 125', '跳过这个提交'], ['≥ 128', '终止 bisect'], ['跳过的代价', '可能多几步']], ['exit 125'])),
]
A = mkarti('l51', 51, 'Git,bisect,二分查找,bisect run,真实验证,动画演示',
    '在 1000 个提交的历史上实测 git bisect:手工回答时剩余可疑提交数 499 → 249 → 124 → 62 → 30 逐步减半;bisect run 用 10 次测试找到第 637 个提交;100 个随机 bug 位置全部找对,测试次数 9~10(平均 9.95);非线性历史按“可疑集合折半”选提交;脚本退出 125 可跳过无法测试的提交。',
    '1000 个提交里找出引入 bug 的那一个,要测试几次?bisect 选提交的依据是什么?历史里有合并时它怎么选?脚本不能测试某些提交怎么办?这篇用 1000 个提交的历史做了 100 次实验。',
    [('10 次', '1000 个提交里找到引入 bug 的那个所需的测试次数上限(⌈log2 1000⌉)'), ('100 / 100', '随机的 100 个 bug 位置全部找对,测试次数 9~10,平均 9.95'), ('exit 125', '脚本用它表示“跳过这个无法测试的提交”')],
    [('二分', '<p>git bisect 在“好的提交”和“坏的提交”之间检出中点,你回答 good 或 bad,可疑范围折半。1000 个提交最多 10 次测试。</p>'),
     ('bisect run', '<p><code>git bisect run 脚本</code> 用脚本的退出码自动回答:0 为 good,1~124/126/127 为 bad,125 为跳过,≥128 终止。整个过程不需要人工参与,最后输出 <code>is the first bad commit</code>。</p>'),
     ('次数', '<p>随机 100 个 bug 位置的实验里,测试次数全部在 9 到 10 之间,和 ⌈log₂1000⌉ 吻合,而且全部找对。</p>'),
     ('非线性历史', '<p>历史里有合并时,bisect 选的是能把“可疑集合”(坏提交的祖先减去好提交的祖先)分成最接近两半的提交,按祖先个数而不是提交时间。</p>'),
     ('跳过', '<p>无法编译或无法测试的提交让脚本 exit 125,bisect 排除它们、换一个相邻的提交继续,可能多花几步。</p>')],
    steps,
    [ENV_I_GIT + '。1000 个提交由 git fast-import 生成;“bug”由测试脚本模拟(f.txt 里的版本号 ≥ K 为坏),而不是真正的代码缺陷;步数是脚本被调用的次数;输出里的 hash 做了省略',
     '没有验证:bisect 在含大量合并的真实历史上的步数;git bisect skip 手工跳过多个提交后“只剩被跳过的提交”的情形;自定义术语 git bisect terms(old/new);--first-parent 选项;bisect visualize;子模块或构建很慢时的使用技巧'],
    'bisect')
