from lib import *
S = SS('g59')
steps = [
    step("两个 goroutine 各对一个 int 做 1000 次 counter++,用 go build -race 编译:程序打印 counter = 2000,但同时输出 WARNING: DATA RACE——Read at …(goroutine 17)、Previous write at …(goroutine 18),并给出两个 goroutine 的创建位置(main.go:42),随后又报了一次 Write 对 Write 的竞争。进程退出码 66。同一份源码不加 -race 编译:counter = 1367(丢了更新),退出码 0,没有任何提示。", t=tl(S(1)), done=lidx(S(1), 'WARNING: DATA RACE', 'Previous write', 'counter = 2000'), mark=lidx(S(1), '进程退出码:66', 'counter = 1367'), kv=KV([['-race 版', '报告读写竞争,退出码 66,这次 counter = 2000'], ['普通版', '无提示,counter = 1367'], ['含义', '竞争可以存在而结果碰巧是对的']], ['含义'])),
    step("检测的是“有没有 happens-before”,不是“这次碰巧有没有同时发生”。sleepordered:一个 goroutine 写,main 睡 100 ms 后读,没有任何同步:程序读到 42,但仍报 DATA RACE(退出码 66)。atomicmixed:一个 goroutine 用 atomic.StoreInt64 写,main 睡 50 ms 后用普通读:读到 1,同样报 DATA RACE。readonly:4 个 goroutine 只读共享变量:无竞争,退出码 0。", t=tl(S(2)), done=lidx(S(2), 'readonly'), mark=lidx(S(2), 'sleepordered', 'atomicmixed', '读到 42', '普通读到 1'), kv=KV([['睡眠排序的读写', '仍报竞争'], ['原子写 + 普通读', '报竞争'], ['只读', '不报'], ['含义', '靠睡眠“保证顺序”不是同步']], ['含义'])),
    step("没跑到的竞争不会被报告:同一个二进制,有竞争的分支只在环境变量 TRIGGER 设置时才执行。不设:退出码 0,输出 done;设 TRIGGER=1:退出码 66,出现 WARNING: DATA RACE。", t=tl(S(3)), done=lidx(S(3), '[不触发]'), mark=lidx(S(3), '[TRIGGER=1]'), kv=KV([['不触发', '退出码 0'], ['TRIGGER=1', '退出码 66,报 DATA RACE'], ['含义', '只检查这次运行真正执行到的代码']], ['含义'])),
    step("GORACE 选项:GORACE=exitcode=7 时发现竞争的退出码变成 7;GORACE=halt_on_error=1 时只报告 1 次 WARNING: DATA RACE,进程退出码仍是 66(默认)。", t=tl(S(4)), mark=lidx(S(4), 'exitcode=7', 'halt_on_error=1'), kv=KV([['exitcode=7', '发现竞争时退出码 7'], ['halt_on_error=1', '第一次竞争后立即退出,只出现 1 次报告'], ['默认退出码', '66']], ['默认退出码'])),
    step("同时存活的 goroutine 数:-race 版与普通版都能让 10000 个、100000 个 goroutine 同时存活并正常结束(退出码 0)。(我听说旧版本的竞争检测器对同时存活的 goroutine 有 8128 的上限,在 Go 1.27.1 上没有碰到,没有查它是哪个版本取消的。)", t=tl(S(5)), done=lidx(S(5), '-race版本:10000', '-race版本:100000'), mark=lidx(S(5), '普通版本:100000'), kv=KV([['-race,10000 个', '正常'], ['-race,100000 个', '正常'], ['旧上限', '本机未复现(未查哪版取消)']], ['旧上限'])),
    step("代价(各 5 次取中位数):内存密集的循环(1M 个 int 的数组遍历 40 遍),普通版 0.034 s、14 MB,-race 版 1.062 s、48 MB——耗时 31.2 倍,内存 3.6 倍。8 个 goroutine 争锁各 20 万次:普通版 0.148 s、5 MB,-race 版 0.514 s、32 MB——耗时 3.5 倍,内存 5.8 倍。", t=tl(S(6)), done=lidx(S(6), '普通 :'), mark=lidx(S(6), '-race:', '耗时中位数比'), b=bars([['内存密集循环:耗时倍数', 31.2, '31.2×'], ['内存密集循环:内存倍数', 3.6, '3.6×'], ['争锁:耗时倍数', 3.5, '3.5×'], ['争锁:内存倍数', 5.8, '5.8×']], 31.2, mark=[0, 2], done=[1, 3]), kv=KV([['访存密集', '耗时 31.2 倍,内存 3.6 倍'], ['争锁为主', '耗时 3.5 倍,内存 5.8 倍'], ['含义', '开销取决于程序访存的比例,不是固定倍数']], ['含义'])),
]
A = mkartg('g59', 59, 'Go,竞态检测器,race,ThreadSanitizer,data race,真实验证,动画演示',
    '在 Go 1.27.1(arm64 macOS)里实测 -race:counter++ 的竞争被报告(退出码 66)而普通版无提示;睡眠“排序”的读写和原子写+普通读也算竞争;没执行到的竞争分支不报;GORACE 的 exitcode 与 halt_on_error;10 万个 goroutine 同时存活无上限报错;访存密集的循环慢 31.2 倍、内存 3.6 倍,争锁程序慢 3.5 倍、内存 5.8 倍。',
    '竞态检测器能抓到什么、抓不到什么、要花多少钱?这篇用几个小程序实测:它基于 happens-before 而不是碰运气,但只检查实际执行过的路径;开销在不同类型的程序上差很多。',
    [('31.2× / 3.5×', '-race 版相对普通版的耗时:访存密集循环 / 争锁程序'), ('退出码 66', '发现 data race 时 -race 程序的默认退出码,GORACE=exitcode 可改'), ('只检查执行过的', '同一个二进制,竞争分支没执行时退出码 0')],
    [('抓到了,结果却是对的', '<p>两个 goroutine 各做 1000 次 <code>counter++</code>,带 -race 的这次最后打印 2000,看起来没丢更新,但检测器报告了读写竞争并给出两个 goroutine 的创建位置;不带 -race 的版本这次打印 1367。竞争不是“结果错了”,而是没有同步关系。</p>'),
     ('依据是同步关系', '<p><code>time.Sleep</code> 让读发生在写之后几十毫秒,检测器仍然报告竞争,因为两者之间没有锁、channel 或原子操作建立 happens-before。原子写配普通读也同样被报。只读共享则不报。</p>'),
     ('只检查跑过的代码', '<p>竞争分支只在设了环境变量时才执行:不设时即使存在竞争也是退出码 0。所以要用测试覆盖到并发路径,并在 CI 里跑 <code>go test -race</code>(本文没有实验 go test)。</p>'),
     ('GORACE 选项', '<p><code>GORACE=exitcode=7</code> 把发现竞争时的退出码从默认的 66 改成 7;<code>GORACE=halt_on_error=1</code> 让进程在第一次竞争报告后就退出,实验里只出现 1 次报告。</p>'),
     ('goroutine 数量没有撞到旧上限', '<p>我听说旧版本的竞争检测器对同时存活的 goroutine 有 8128 的上限,在这台机器上 10 万个都没问题,所以不能写它仍然存在;至于是哪个版本取消的,我没有查。</p>'),
     ('开销看程序类型', '<p>访存密集的循环慢了 31.2 倍、内存多 3.6 倍;主要是争锁的程序只慢 3.5 倍,但内存多了 5.8 倍。所以别用某一个“慢 5 到 10 倍”的口号估算,要在自己的程序上量。</p>')],
    steps,
    [ENV_G + '。-race 版与普通版由同一份源码用 go build 与 go build -race 编译;内存用 /usr/bin/time -l 的 maximum resident set size(中位数);耗时每个 5 次;GORACE 的两个选项各跑一次;没有读检测器的源码或文档,所有结论来自实测输出',
     '没有验证:go test -race、竞争检测器的内存历史窗口导致的漏报(shadow cell 数量等)、cgo 程序、Linux 上的开销、8128 goroutine 上限的历史、报告的完整格式(只截取了开头),本文的两个开销数字来自两个特定程序'],
    '竞态检测器')
