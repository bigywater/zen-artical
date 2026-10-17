from lib import *
S = SS('l55')
steps = [
    step("六个提交围绕字符串 foo:C1 新增 foo(1),C2 把参数改成 foo(2),C3 把这行挪到文件末尾,C4 再加一处 foo(3),C5 删掉第一处,C6 删掉全部。整个文件里 foo 出现的次数依次是 1、1、1、2、1、0。git log -S'foo' 只返回次数变化的 4 个提交:C1、C4、C5、C6——C2(改参数)和 C3(挪行)的次数没变,-S 看不到;git log -G'foo' 返回 6 个全部,因为每个提交的 diff 里都有包含 foo 的增删行。-S'foo(2)' 返回 C2 和 C5(foo(2) 出现和消失);-G'foo\\(2\\)' 返回 C2、C3、C5——C3 把这行挪走再加回,diff 里有这个字符串。", t=tl(S(1)), mark=lidx(S(1), "-S'foo'", "-G'foo'", "-S'foo(2)'", "-G'foo\\(2\\)'"), done=lidx(S(1), 'C1 新增 foo 的调用  → 1 次', 'C4 再加一处 foo 调用  → 2 次', 'C6 删掉全部 foo  → 0 次'), b=bars([["-S'foo'", 4, '4 个提交'], ["-G'foo'", 6, '6 个提交']], 6, mark=[1], done=[0]), kv=KV([['-S<字符串>', '出现次数变了的提交'], ['-G<正则>', 'diff 里增删的行匹配的提交'], ['挪行 / 改参数', '-S 看不到,-G 能看到']], ['-S<字符串>'])),
    step("加 -p 看每个命中提交里增删的行:git log -S'foo(3)' -p 先列出 C6(删掉全部 foo)里的 -other = foo(3),再列出 C4(再加一处 foo 调用)里的 +other = foo(3)——也就是同一行代码的“出现”和“消失”两个提交都会命中。-S 回答的是“这个字符串是哪个提交引入的、哪个提交去掉的”。", t=tl(S(2)), mark=lidx(S(2), '-other = foo(3)', '+other = foo(3)'), done=lidx(S(2), 'C6 删掉全部 foo', 'C4 再加一处 foo 调用'), kv=KV([['引入', '出现次数增加的提交'], ['去掉', '出现次数减少的提交'], ['-p', '看增删的具体行']], ['引入'])),
    step("正则:-G 的参数默认就是正则,git log -G'foo\\(.\\)' 返回全部 6 个提交;-S 的参数默认是字面字符串,git log -S'foo\\(.\\)' 什么也没有(字面上没有出现“foo\\(.\\)”这个文本);加 --pickaxe-regex 之后 -S 才按正则处理,返回 C1、C4、C5、C6,与 -S 的“次数变化”语义一致。", t=tl(S(3)), mark=lidx(S(3), '(无)', '--pickaxe-regex'), done=lidx(S(3), "-G'foo", 'C1 新增 foo 的调用 | C2'), kv=KV([['-S', '字面字符串(次数)'], ['-S --pickaxe-regex', '正则(次数)'], ['-G', '正则(增删行)']], ['-S --pickaxe-regex'])),
    step("--pickaxe-all:一个提交同时改了 a.txt(加了 needle)和 b.txt。git log -S'needle' --stat 只显示匹配的 a.txt(1 个文件);加 --pickaxe-all 之后显示这个提交的全部改动,a.txt 和 b.txt(2 个文件)。-S 和 -G 默认只过滤文件,--pickaxe-all 保留整个提交。", t=tl(S(4)), mark=lidx(S(4), '2 files changed'), done=lidx(S(4), '1 file changed', 'a.txt | 1 +'), kv=KV([['默认', '只显示匹配的文件'], ['--pickaxe-all', '显示命中提交的全部改动']], ['--pickaxe-all'])),
    step("大历史上的耗时:3000 个提交,100 个文件,每个提交改其中一个文件,第 2345 个提交引入了字符串 UNIQUE_TOKEN。git log -S 54 ms、git log -G 72 ms、git log -p | grep(把所有补丁打出来再搜)86 ms;不比较内容的 git log --format=%h 是 26 ms(基线)。-S 比 -G 快,因为它只数出现次数,不需要把差异分行。-S 命中了两个提交:第 2345 个(引入)和第 2445 个(同一个文件 f45.txt 的下一次改写,把它去掉了)。", t=tl(S(5)), mark=lidx(S(5), '-S 命中了 2 个提交'), done=lidx(S(5), "git log -S'UNIQUE_TOKEN'", "git log -G'UNIQUE_TOKEN'", 'git log -p | grep', '不比较内容'), b=bars([['无内容比较(基线)', 26, '26 ms'], ['-S', 54, '54 ms'], ['-G', 72, '72 ms'], ['log -p | grep', 86, '86 ms']], 86, mark=[1], done=[0, 2, 3]), kv=KV([['-S', '54 ms'], ['-G', '72 ms'], ['-p | grep', '86 ms'], ['基线', '26 ms(不比较内容)']], ['-S'])),
]
A = mkarti('l55', 55, 'Git,pickaxe,git log -S,git log -G,代码出处,真实验证,动画演示',
    '实测 pickaxe:git log -S 找字符串出现次数发生变化的提交(改参数、挪行不算),-G 找 diff 里增删的行匹配正则的提交(都算);-S 默认是字面字符串,--pickaxe-regex 让它按正则;--pickaxe-all 保留命中提交的全部文件;3000 个提交的历史上 -S 54 ms、-G 72 ms、log -p | grep 86 ms。',
    '想知道某段代码是什么时候加进来、什么时候被删掉的,git log -S 和 -G 是最直接的工具。它们的区别很微妙:一个数出现次数,一个看增删的行。这篇用六个精心设计的提交把差别演示清楚,再测大历史上的耗时。',
    [('4 vs 6', '同样搜 foo,-S 命中 4 个(次数变化),-G 命中 6 个(diff 里出现过)'), ('挪行', '把一行代码挪个位置,-S 看不到,-G 能看到'), ('54 / 72 / 86 ms', '3000 个提交的历史上 -S、-G、log -p | grep 的耗时')],
    [('-S 与 -G', '<p><code>-S&lt;字符串&gt;</code> 找使该字符串在文件中出现次数发生变化的提交——“引入”和“去掉”它的提交;改参数、把行挪个位置、出现次数没变的修改都找不到。<code>-G&lt;正则&gt;</code> 找 diff 里被增加或删除的行匹配正则的提交,所以改参数和挪行也算,命中更多。</p>'),
     ('-p 看具体的行', '<p>加 <code>-p</code> 能看到每个命中提交里增删的具体行:同一行代码的“出现”和“消失”两个提交都会命中,-S 回答的是“这个字符串是哪个提交引入、哪个提交去掉的”。</p>'),
     ('--pickaxe-regex', '<p>-G 的参数默认就是正则;-S 的参数默认是字面字符串(带正则元字符的参数找不到任何东西),加 <code>--pickaxe-regex</code> 后按正则处理,语义仍是“出现次数变化”。</p>'),
     ('--pickaxe-all', '<p>-S 和 -G 默认只保留匹配的文件;<code>--pickaxe-all</code> 在命中的提交里保留全部文件的改动。</p>'),
     ('速度', '<p>两者都需要比较每个提交改动的文件内容,比纯 <code>git log</code> 慢,但比把所有补丁打出来再 grep 快。-S 因为只数次数,略快于 -G。</p>')],
    steps,
    [ENV_I_GIT + '。耗时 5 次中位数,含进程启动;3000 个提交由 git fast-import 生成',
     '没有验证:git log -L(按函数或行范围追踪);二进制文件上的 -S;--follow 与 -S 的配合;更大的仓库(几十万提交)上的耗时;-S 对重命名文件的处理;-i(忽略大小写)'],
    'pickaxe')
