from lib import *
S = SS('l52')
steps = [
    step("历史:Alice 写了 P(calculate_total_price)、Q(collect_user_names)和 short 三个函数;Bob 先把 P 和 Q 的位置交换,再把 short 挪到文件开头;Carol 把 P 搬到新文件 b.py(a.py 里只剩 short 和 Q)。git log 的顺序是 Alice、Bob、Bob、Carol。最终 a.py 是 short、Q,b.py 是 P 和 Carol 自己新写的 format_report_header。", t=tl(S(1)), mark=lidx(S(1), 'Carol: Carol 把 P 搬到 b.py'), done=lidx(S(1), 'Alice: Alice 写了三个函数', 'Bob: Bob 交换 P 与 Q', 'def short(a):'), kv=KV([['Alice', '写了 P、Q、short'], ['Bob', '交换 P 和 Q、挪动 short'], ['Carol', '把 P 搬到 b.py']], ['Bob'])),
    step("默认的 git blame 把被挪动的行全算在“挪动者”名下:b.py 里 Carol 搬来的 P 三行都是 Carol;a.py 里 Bob 挪到开头的 short 两行是 Bob。但 Q 没有被 git diff 认为是移动的(Bob 的交换里是 P 被识别为移动),所以仍是 Alice。blame 的“谁写的”其实是“这一行最近一次出现在 diff 的新增里是哪个提交”。", t=tl(S(2)), mark=lidx(S(2), 'Carol | def calculate_total_price', 'Bob   | def short'), done=lidx(S(2), 'Alice | def collect_user_names'), kv=KV([['默认 blame', '挪动的行算挪动者'], ['原因', 'diff 里它们是新增行'], ['后果', '看不出代码的真正作者']], ['默认 blame'])),
    step("-M 追踪同一个文件内移动的行:Bob 的两个提交之后,默认 blame 把被挪到最后的 P 三行算成 Bob;加 -M 之后 P 追回 Alice,Q 一直是 Alice,而 short 两行仍是 Bob——-M 默认只认每行至少 20 个字母数字字符的移动,def short(a): 和 return a 不够。把阈值降到 -M5,这两行也追回 Alice。", t=tl(S(3)), mark=lidx(S(3), '[-M]:', '降低阈值'), done=lidx(S(3), '[默认]', '长函数 P、Q'), kv=KV([['-M', '同一文件里移动的行'], ['阈值', '默认每行 ≥ 20 个字母数字'], ['-M<n>', '调低阈值']], ['阈值'])),
    step("-C 追踪跨文件:Carol 把 P 从 a.py 搬到 b.py。默认和 -M(只看同一个文件)的 blame 都说是 Carol;加 -C 之后 b.py 的 P 追到 Alice,因为这个提交同时修改了来源文件 a.py(-C 会在“同一个提交里被修改的其它文件”里找)。b.py 里 Carol 自己新写的 format_report_header 仍是 Carol。", t=tl(S(4)), mark=lidx(S(4), '[-C]', '[-M]  (-M 只在同一文件里找'), done=lidx(S(4), '[默认] b.py', 'format_report_header'), kv=KV([['-C', '在同一提交修改的其它文件里找来源'], ['-M', '只在本文件里找'], ['自己写的行', '仍算自己']], ['-C'])),
    step("-C 的层级:Carol 在一个提交里只新建了 b.py(拷贝了 P),a.py 在这个提交里没有被修改。默认和 -C 都说 Carol(-C 只在“同一提交里被修改的文件”里找,而 a.py 没被修改);-C -C 和 -C -C -C 都追到了 Alice(-C -C 会连这个提交里新建文件、以及其它文件一起找)。越多 -C,越能追到来源,也越慢。", t=tl(S(5)), mark=lidx(S(5), 'git blame -C -C     b.py → Alice', 'git blame -C -C -C'), done=lidx(S(5), 'git blame           b.py → Carol', 'git blame -C        b.py → Carol'), kv=KV([['-C', '同一提交修改过的文件'], ['-C -C', '也找这个提交里新建的文件'], ['-C -C -C', '找任何提交里的任何文件']], ['-C -C'])),
    step("格式化提交会“偷走”整个文件的 blame:Bob 统一缩进(把两个空格改成四个空格)之后,默认 blame 对 c.py 的 5 行给出 Alice、Bob、Alice、Alice、Bob——Bob 的缩进改动让第 2、5 行成了他的;--ignore-rev <Bob 的提交> 之后 5 行都是 Alice;把提交写进 .git-blame-ignore-revs 并设置 blame.ignoreRevsFile,以后不用每次传参数,结果同样是 5 个 Alice。", t=tl(S(6)), mark=lidx(S(6), '默认: Alice, Bob', '--ignore-rev', 'blame.ignoreRevsFile'), done=lidx(S(6), 'Alice, Alice, Alice, Alice, Alice'), kv=KV([['--ignore-rev', '忽略指定的提交,归给更早的作者'], ['.git-blame-ignore-revs', '一个文件列出所有格式化提交'], ['blame.ignoreRevsFile', '让 blame 自动读取它']], ['.git-blame-ignore-revs'])),
]
A = mkarti('l52', 52, 'Git,blame,-M,-C,ignore-rev,真实验证,动画演示',
    '实测 git blame 的搬运检测:默认把挪动的行算挪动者;-M 追踪同一文件内移动的行(每行至少 20 个字母数字,-M5 降低阈值);-C 追踪同一提交里被修改的其它文件,-C -C 还找新建的文件;--ignore-rev 与 .git-blame-ignore-revs 让格式化提交不再“偷走”整个文件的 blame。',
    'git blame 总说这行是最后搬动它的人写的,怎么找到真正的作者?-M 和 -C 各追什么、门槛是多少?格式化提交把整个文件 blame 到自己名下怎么办?这篇构造一个有交换、挪动、跨文件搬运的历史逐项实测。',
    [('20', '-M / -C 默认只认每行至少 20 个字母数字字符的移动;-M5 降低到 5'), ('-C -C -C', '三层 -C:同一提交修改的文件 → 也找新建文件 → 任何提交里的任何文件'), ('.git-blame-ignore-revs', '列出格式化提交,blame 就不会再把整个文件归给它')],
    [('实验历史', '<p>Alice 写了三个函数 P、Q、short;Bob 交换 P 与 Q 并把 short 挪到开头;Carol 把 P 搬到 b.py。真正的作者是 Alice,但三次改动都让别人的名字出现在 blame 里。</p>'),
     ('默认', '<p>blame 以行为单位,问“这行是哪个提交加进来的”。被挪动的行在 diff 里是新增,于是算给挪动的人。</p>'),
     ('-M', '<p>在同一个文件里检测移动的行,追回原作者。门槛是每行至少 20 个字母数字字符(<code>-M&lt;n&gt;</code> 调整),太短的行(例如 <code>def short(a):</code>)不会被追。</p>'),
     ('-C 跨文件', '<p>在其它文件里找来源。把函数从 a.py 搬到 b.py 的提交同时修改了 a.py,所以 <code>-C</code> 能追回 Alice;<code>-M</code> 只在本文件里找,对跨文件搬运没用。</p>'),
     ('-C 的三个层级', '<p><code>-C</code> 只看同一提交里被修改的文件;<code>-C -C</code> 再加上这个提交新建的文件;<code>-C -C -C</code> 找任何提交里的任何文件。代价是越来越慢。</p>'),
     ('格式化提交', '<p>批量改缩进或格式的提交会把大量行的 blame 改到自己名下。<code>--ignore-rev</code> 让 blame 跳过某些提交,把行归给更早的作者;把这些提交写进 <code>.git-blame-ignore-revs</code> 并设置 <code>blame.ignoreRevsFile</code> 可以让整个团队生效。</p>')],
    steps,
    [ENV_I_GIT + '。blame 的作者来自 --line-porcelain 的 author 字段;所有提交的作者与时间固定;每个场景单独建仓库',
     '没有验证:-w(忽略空白)与 --ignore-rev 的组合;git log -L :函数名:文件 追踪函数历史;超过 20 个字母数字门槛时的具体计算方式(只验证了两个长度的行);大型仓库上 -C -C -C 的耗时;git blame --ignore-revs-file 对合并提交的处理'],
    'blame 的搬运检测')
