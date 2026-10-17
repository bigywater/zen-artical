from lib import *
S = SS('g93')
steps = [
    step("一个藏着 bug 的函数:只有输入以 \"Go!?\" 开头才会 panic(随机猜中这 4 个固定字节的概率是 2 的 −32 次方)。不开 fuzz,go test 只跑种子语料 hello 和 Gx 两条:全部 PASS,看不出任何问题。", t=tl(S(1)), done=lidx(S(1), 'seed#0', 'seed#1', 'PASS'), mark=lidx(S(1), 'FuzzParse'), kv=KV([['bug 的触发条件', '输入以 \"Go!?\" 开头(4 个特定字节)'], ['种子语料', 'hello、Gx,都通过'], ['盲目随机', '约 2⁻³² 的概率']], ['bug 的触发条件'])),
    step("go test -fuzz=FuzzParse -fuzztime=60s(冷启动,先清空 GOCACHE/fuzz):先收集基线覆盖率(2/2 completed),开 4 个 worker;很快发现失败输入 31 字节,进入 minimizing 缩小;总共 1.3 秒就结束,FAIL;输出 “Failing input written to testdata/fuzz/FuzzParse/a7e5da185dd54932” 以及重放命令 go test -run=FuzzParse/a7e5da185dd54932。重复 5 次冷启动:每次 0.62–0.77 秒内找到,最初的失败输入都是 31 字节,最终都缩小到 string(\"Go!?\")。同一个函数的“不会 panic”版本 FuzzSafe 跑 10 秒:约 29 万次/秒,共约 300 万次执行,只发现 4 个“有新覆盖”的输入(总计 5)。", t=tl(S(2)), done=lidx(S(2), 'gathering baseline coverage: 2/2', 'minimizing 31-byte'), mark=lidx(S(2), '--- FAIL: FuzzParse', 'Failing input written', 'elapsed: 10s', '第 1 次', '第 5 次'), b=bars([['冷启动找到 bug (ms)', 700, '≈0.7 秒'], ['FuzzSafe 10 秒执行 (万次)', 300, '≈300 万'], ['执行速度 (万次/秒)', 28.5, '≈29 万/秒']], 700, done=[0], mark=[1, 2]), kv=KV([['找到 bug', '0.62–0.77 秒(5 次)'], ['缩小', '31 字节 → 4 字节 \"Go!?\"'], ['执行速度', '约 29 万次/秒(这个小函数)'], ['新覆盖', '10 秒只发现 4 个有趣的输入']], ['缩小'])),
    step("失败的输入被存到 testdata/fuzz/FuzzParse/ 目录,文件名是内容哈希(a7e5da18…);文件内容是两行:go test fuzz v1,以及 string(\"Go!?\")。", t=tl(S(3)), mark=lidx(S(3), 'go test fuzz v1', 'string('), kv=KV([['位置', 'testdata/fuzz/FuzzParse/<哈希>'], ['内容', 'go test fuzz v1 + 输入的 Go 字面量'], ['含义', '可以直接提交进版本库']], ['含义'])),
    step("之后普通的 go test(不开 -fuzz)会自动重放这个失败输入:退出码 1,--- FAIL: FuzzParse/a7e5da185dd54932,panic: 找到了 bug [recovered, repanicked]。也就是说 testdata 里的失败输入变成了回归测试。", t=tl(S(4)), mark=lidx(S(4), '--- FAIL', 'panic'), kv=KV([['普通 go test', '自动重放 testdata 里的输入'], ['结果', 'FAIL,直到修好 bug'], ['作用', '回归测试']], ['作用'])),
    step("语料缓存在 GOCACHE/fuzz 里:最后一次冷启动之后有 3 个语料文件,共 93 字节——这是 fuzz 过程中发现的“有新覆盖”的输入。缓存会让下一次 fuzz 更快找到 bug(我在没有清缓存时测过,0.1–0.4 秒就找到)。", t=tl(S(5)), mark=lidx(S(5), 'GOCACHE/fuzz'), kv=KV([['语料缓存', 'GOCACHE/fuzz'], ['最后一次', '3 个文件,93 字节'], ['影响', '之后的 fuzz 以这些输入为起点']], ['影响'])),
    step("go help testflag 里的说明:-fuzz regexp 运行匹配的 fuzz 测试,命令行必须只匹配主模块里的一个包,regexp 必须只匹配该包里的一个 fuzz 测试;fuzz 会在测试、基准测试、种子语料之后进行。-fuzzminimizetime t 每次缩小尝试中运行足够多次 fuzz 目标以耗费 t 时间,默认 60 秒;特殊写法 Nx 表示运行目标 N 次。", t=tl(S(6)), done=lidx(S(6), '-fuzz regexp'), mark=lidx(S(6), '-fuzzminimizetime'), kv=KV([['-fuzz', '只能匹配一个包里的一个 fuzz 测试'], ['-fuzzminimizetime', '默认 60 秒,Nx 表示 N 次'], ['顺序', '先跑普通测试和种子,再 fuzz']], ['-fuzzminimizetime'])),
]
A = mkartg('g93', 93, 'Go,模糊测试,fuzz,覆盖率引导,缩小用例,真实验证,动画演示',
    '在 Go 1.27.1(arm64 macOS)里实测 go test -fuzz:藏在 4 个特定字节之后的 panic,种子语料全部通过;fuzz 冷启动 0.62–0.77 秒就找到,失败输入 31 字节被缩小到 4 字节 "Go!?",写入 testdata/fuzz/FuzzParse/<哈希>,之后普通 go test 自动重放成回归测试;无 bug 的版本约 29 万次/秒;语料缓存在 GOCACHE/fuzz。',
    '随机输入猜中“Go!?”这 4 个字节的概率是 40 亿分之一,但 go test -fuzz 不到一秒就找到了。靠的是覆盖率引导:每当一个输入走到了新的代码分支,就把它留作后续变异的起点。这篇用一个藏着 bug 的小函数实测发现、缩小、保存、重放的全过程。',
    [('0.62–0.77 秒', '5 次冷启动里,fuzz 发现 4 字节才能触发的 panic 所用的时间'), ('31 → 4 字节', '最初失败的输入与缩小后保存的输入 "Go!?"'), ('约 29 万次/秒', '这个小函数上 fuzz 的执行速度(4 个 worker)')],
    [('种子语料看不出问题', '<p>种子 <code>hello</code> 与 <code>Gx</code> 都通过,普通的 <code>go test</code> 没有任何异常。bug 藏在要求输入以 4 个特定字节开头的分支后面,盲目随机几乎不可能碰到。</p>'),
     ('覆盖率引导', '<p>fuzz 每走到新的代码分支就保留这个输入再变异:先凑出 <code>G</code>,再凑出 <code>Go</code>,依次逐字节逼近。冷启动 5 次都在 0.62–0.77 秒内命中;无 bug 的对照版本跑 10 秒只留下 4 个“有新覆盖”的输入,执行速度约 29 万次/秒。</p>'),
     ('缩小用例', '<p>找到的失败输入先是 31 字节,fuzz 随后进入 minimizing 阶段把它缩短,最终保存的是只有 4 字节的 <code>"Go!?"</code>——正是触发条件本身。5 次实验的结果完全一致。</p>'),
     ('回归测试', '<p>失败输入以 <code>go test fuzz v1</code> 格式存进 <code>testdata/fuzz/FuzzParse/</code>。之后普通 <code>go test</code> 会重放它,bug 修好之前一直 FAIL,修好之后就是永久的回归测试,可以提交进版本库。</p>'),
     ('语料缓存', '<p>fuzz 过程中发现的“有趣”输入缓存在 <code>GOCACHE/fuzz</code>,下一次从它们开始,所以重复运行更快(没清缓存时我测到 0.1–0.4 秒)。本文的冷启动数据是清空缓存之后的结果。</p>'),
     ('命令行参数', '<p><code>-fuzz</code> 只能匹配一个包里的一个 fuzz 函数,<code>-fuzzminimizetime</code> 控制缩小阶段的预算。本文只用了 <code>-fuzztime</code> 与 <code>-parallel</code>。</p>')],
    steps,
    [ENV_G + '。被测函数是自己写的四层嵌套条件(只有 "Go!?" 触发 panic);冷启动 = 每次清空 GOCACHE/fuzz 和 testdata 后运行;执行速度来自 FuzzSafe(同样的分支结构、不 panic)运行 10 秒的统计;-parallel=4;读过的文档:go help testflag 中 -fuzz 与 -fuzzminimizetime',
     '没有验证:fuzz 的变异策略细节(没有读源码)、真实项目里 bug 的发现时间、更复杂输入类型(结构体、多参数)的 fuzz、-fuzzminimizetime 的实际效果、CI 里运行 fuzz 的做法、Linux 上的速度'],
    '模糊测试')
