from lib import *
S = SS('g98')
steps = [
    step("go test -cover 的百分比:被测包有 17 个语句(Classify 8 个、Unused 3 个、Hot 6 个);测试只调用了 Classify:ok lab 0.112s coverage: 47.1% of statements(8/17)。", t=tl(S(1)), mark=lidx(S(1), 'coverage: 47.1%'), b=bars([['包里的语句数', 17, '17'], ['被覆盖的语句数', 8, '8']], 17, done=[1], mark=[0]), kv=KV([['语句总数', '17'], ['被覆盖', '8(Classify 全部)'], ['覆盖率', '47.1%']], ['覆盖率'])),
    step("三种 -covermode 生成的覆盖率文件。每行格式:文件:起始行.列,结束行.列 语句数 计数。set 模式:被执行过的块计数都是 1,没执行的是 0;count 模式:记录每个块执行了几次——Classify 里 n < 0 判断那一块 6 次(测试调用了 6 次),返回“负数”的块 1 次,n == 0 判断 5 次,返回“零”1 次,循环头 4 次,合数判断 5 次,返回“合数”1 次,最后返回 3 次;Unused 与 Hot 的各块都是 0。atomic 模式的各行计数与 count 模式完全相同(单线程测试里没有区别)。", t=tl(S(2)), done=lidx(S(2), '-covermode=set', 'f.go:4.2,4.11 1 6', 'f.go:19.2,22.1 3 0'), mark=lidx(S(2), '-covermode=count', '-covermode=atomic'), kv=KV([['set', '执行过吗(0 或 1)'], ['count', '执行了几次'], ['atomic', '多线程下计数正确,代价更大']], ['count'])),
    step("go tool cover -func(用 count 模式的文件)按函数汇总:Classify 100.0%;Unused 0.0%;Hot 0.0%;total (statements) 47.1%。", t=tl(S(3)), mark=lidx(S(3), 'Unused', 'Hot'), done=lidx(S(3), 'Classify', 'total'), kv=KV([['Classify', '100.0%'], ['Unused / Hot', '0.0%'], ['总计', '47.1%']], ['总计'])),
    step("插桩的开销:Hot(1000) 的基准(每种取 3 次最小)。不插桩 304 ns/op;-covermode=set 710 ns/op(2.33 倍);count 1930 ns/op(6.34 倍);atomic 8038 ns/op(26.41 倍)。循环里每次迭代都要更新计数器,atomic 的代价最大。", t=tl(S(4)), mark=lidx(S(4), '不插桩'), b=bars([['不插桩 (ns/op)', 304, '304'], ['set', 710, '710'], ['count', 1930, '1930'], ['atomic', 8038, '8038']], 8038, done=[0], mark=[1, 2, 3]), kv=KV([['set', '2.33 倍'], ['count', '6.34 倍'], ['atomic', '26.41 倍'], ['说明', '这是只有几条语句的紧循环,真实代码的比例会小得多']], ['说明'])),
    step("不是测试的程序也能收集覆盖率:go build -cover 编译,运行时设 GOCOVERDIR,程序输出 “质数或 1 负数”,GOCOVERDIR 里生成了 2 个文件;go tool covdata percent 汇总:包 lab 覆盖 35.3% 的语句,lab/cmd 覆盖 100.0%。", t=tl(S(5)), mark=lidx(S(5), 'GOCOVERDIR', 'coverage: 35.3%', '100.0%'), kv=KV([['编译', 'go build -cover'], ['运行', '设 GOCOVERDIR 目录,退出时写出数据'], ['汇总', 'go tool covdata percent -i=目录']], ['汇总'])),
    step("go help testflag 里 -covermode 的说明:可取 set、count、atomic;默认是 set,除非启用了 -race,那时默认是 atomic。set:布尔,这条语句执行过吗?count:整数,这条语句执行了几次?atomic:整数,和 count 一样,但在多线程测试里是正确的,明显更贵。", t=tl(S(6)), done=lidx(S(6), '-covermode'), kv=KV([['默认', 'set(开了 -race 则为 atomic)'], ['count', '每条语句执行次数'], ['atomic', '多线程正确,明显更贵']], ['默认'])),
]
A = mkartg('g98', 98, 'Go,覆盖率,go test -cover,covermode,插桩,真实验证,动画演示',
    '在 Go 1.27.1 里实测覆盖率:17 个语句里 8 个被覆盖(47.1%);覆盖率文件按“块”记录起止行列、语句数和计数;set/count/atomic 三种模式的计数含义;紧循环里插桩的开销 set 2.33 倍、count 6.34 倍、atomic 26.41 倍;go build -cover 配合 GOCOVERDIR 让普通程序也能收集覆盖率。',
    'go test -cover 只给你一个百分比,背后是编译器在每个代码块里插入计数器。这篇看覆盖率文件里到底写了什么,三种模式有什么区别,插桩对速度的影响有多大,以及怎样给不是测试的程序收集覆盖率。',
    [('47.1%', '17 个语句里 8 个被测试覆盖到'), ('2.33 / 6.34 / 26.41 倍', '紧循环里 set / count / atomic 模式相对不插桩的耗时倍数'), ('GOCOVERDIR', 'go build -cover 编译的程序,运行时靠它指定覆盖率数据的输出目录')],
    [('百分比', '<p>包里共 17 个语句(按覆盖率文件里各块的语句数相加:Classify 8 个、Unused 3 个、Hot 6 个),测试只调了 Classify,覆盖 8 个,47.1%。</p>'),
     ('覆盖率文件', '<p>每一行是一个“块”:<code>f.go:4.2,4.11 1 6</code> 表示第 4 行第 2 列到第 4 行第 11 列的块,含 1 个语句,执行了 6 次。set 模式只记 0/1,count 记次数,atomic 的数值相同但多线程下正确。</p>'),
     ('按函数看', '<p><code>go tool cover -func</code> 把块汇总成每个函数的百分比,方便快速找到完全没被测到的函数(Unused、Hot 都是 0.0%)。</p>'),
     ('插桩的代价', '<p>对一个只有几条语句的紧循环,set 模式让耗时变成 2.33 倍,count 6.34 倍,atomic 26.41 倍。真实函数里每条语句的工作量大得多,比例会小很多;但说明了为什么 <code>-race</code> 默认配 atomic、测基准时别带 <code>-cover</code>。</p>'),
     ('普通程序的覆盖率', '<p><code>go build -cover</code> 编译出来的程序,运行时把数据写到 <code>GOCOVERDIR</code> 指定的目录;用 <code>go tool covdata percent</code> 汇总,实验里 lab 包 35.3%、lab/cmd 100.0%。可以用来收集集成测试、手工运行的覆盖率。</p>'),
     ('文档', '<p><code>go help testflag</code> 对三种模式的说明与实验一致:set 是“执行过吗”,count 是“几次”,atomic 是多线程正确的 count。</p>')],
    steps,
    [ENV_G + '。被测包是自己写的三个函数;覆盖率文件、-func 汇总来自 go test -coverprofile 与 go tool cover;开销用 go test -bench(-benchtime=300ms),每种取 3 次最小;读过的文档:go help testflag 中 -covermode',
     '没有验证:覆盖率插桩的实现方式(编译器还是源码改写,没有读源码)、-coverpkg 跨包覆盖、多线程测试里 count 与 atomic 的计数差别、html 报告(go tool cover -html)、语句覆盖率与分支覆盖率的区别'],
    '覆盖率')
