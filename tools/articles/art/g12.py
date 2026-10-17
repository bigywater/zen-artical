from lib import *
S = SS('g12')
L3 = S(3)
steps = [
    step("没有同步地并发操作 map,运行时直接 fatal(退出码 2),不是 panic:两个 goroutine 同时写:fatal error: concurrent map writes;一个写一个读:fatal error: concurrent map read and map write;一个遍历一个写:fatal error: concurrent map iteration and map write。三个程序都用 defer + recover() 包住了 main,输出里没有 \"recover 收到\"——defer 没有机会执行。", t=tl(S(1)), done=lidx(S(1), '模式 ww', '模式 rw', '模式 iw'), mark=lidx(S(1), 'defer + recover()'), kv=KV([['两个 goroutine 同时写', 'fatal error: concurrent map writes,退出码 2'], ['一个写、一个读', 'fatal error: concurrent map read and map write'], ['一个遍历、一个写', 'fatal error: concurrent map iteration and map write'], ['recover()', '接不住:defer 没执行']], ['recover()'])),
    step("检测是尽力而为:同一个程序各跑 30 次。两个 goroutine 各写 10 万次:30 次里 fatal 30 次、正常结束 0 次;两个 goroutine 各只写 3 次:30 次里只有 2 次 fatal、28 次正常结束(这个比例每次运行会不同)。没触发 fatal 不代表程序没有竞态。", t=tl(S(2)), done=lidx(S(2), '各写 10 万次'), mark=lidx(S(2), '各只写 3 次'), b=bars([['各写 10 万次:fatal 次数', 30, '30 / 30'], ['各写 3 次:fatal 次数', 2, '2 / 30']], 30, done=[0], mark=[1]), kv=KV([['各写 10 万次', '30 / 30 次 fatal'], ['各只写 3 次', '2 / 30 次 fatal(其余 28 次悄悄结束)']], ['各只写 3 次'])),
    step("原理:runtime 源码里 Map 有一个 writing 标志(注释写的是“toggled (XOR 1) while the map is being written”),写入前发现它非 0 就 fatal(\"concurrent map writes\"),写完发现它是 0 也 fatal,否则 XOR 1;读的路径发现它非 0 就报 \"concurrent map read and map write\";迭代器在 table.go 里检查同一个标志,报 \"concurrent map iteration and map write\"。", t=tl(L3), done=lidx(L3, 'map.go:507', 'map.go:432'), mark=lidx(L3, 'table.go:882', 'writing is a flag'), kv=KV([['写入前', 'writing != 0 → fatal 并发写'], ['写完时', 'writing == 0 → fatal 并发写;否则 XOR 1'], ['读', 'writing != 0 → fatal 读与写并发'], ['遍历', 'writing != 0 → fatal 遍历与写并发']], ['写入前'])),
    step("加了同步之后:sync.Mutex 保护的 map、sync.Map 各跑 10 次,都是 10 次正常结束、0 次 fatal。用 -race 编译无保护的 ww 模式:退出码 2,输出里先是 WARNING: DATA RACE(Write at … by goroutine 7、Previous write at … by goroutine 8),随后仍是 fatal error: concurrent map writes;-race 编译的 mutex 模式退出码 0、正常结束(len = 200000)。", t=tl(S(4)), done=lidx(S(4), 'mutex:10 次', 'syncmap:10 次', 'mutex 模式'), mark=lidx(S(4), 'ww 模式'), kv=KV([['sync.Mutex + map', '10 / 10 次正常结束'], ['sync.Map', '10 / 10 次正常结束'], ['-race 编译的无保护 map', 'WARNING: DATA RACE,随后 fatal error'], ['-race 编译的 mutex 版本', '退出码 0']], ['-race 编译的无保护 map'])),
]
A = mkartg('g12', 12, 'Go,map,并发,fatal,竞态,真实验证,动画演示',
    '在 Go 1.27.1 里实测并发读写 map:运行时用 map 里的 writing 标志检测并直接 fatal(concurrent map writes / read and map write / iteration and map write,退出码 2),recover 接不住;检测是尽力而为——两个 goroutine 各写 10 万次 30 次全部 fatal,各只写 3 次 30 次里只有 2 次;sync.Mutex 与 sync.Map 都不再出错;-race 先报 DATA RACE 再 fatal。',
    'map 不是并发安全的,但 Go 的运行时会尽力把这种错误变成一个立即的崩溃,而不是悄悄写坏数据。这篇用真实程序触发三种 fatal,验证 recover 接不住,量出检测的命中率,再读源码里检测用的那个标志,最后看加锁与 -race 的结果。',
    [('退出码 2', '并发读写 map 触发的是 fatal error,不是 panic,defer 和 recover 都不会执行'), ('2 / 30', '两个 goroutine 各只写 3 次,30 次运行里被检测到的次数;各写 10 万次则是 30 / 30'), ('writing', 'Map 里的标志位:写入期间被翻转,别的 goroutine 看到它不对就 fatal')],
    [('三种 fatal', '<p>写与写、读与写、遍历与写都被检测。它们是 <code>fatal error</code>,等价于运行时认定程序已经不可恢复,所以 <code>recover</code> 接不住,进程以退出码 2 结束并打印所有 goroutine 的栈。生产环境里没法靠 <code>recover</code> 兜底这类错误。</p>'),
     ('不保证发现', '<p>检测靠的是两个 goroutine 恰好同时处在 map 的写入窗口里。写 10 万次时窗口大量重叠,30 次全中;每个只写 3 次时,窗口几乎不重叠,28 次安静地结束。没触发 fatal 的程序仍然有数据竞争,<code>-race</code> 才是可靠的检查手段。</p>'),
     ('检测的原理', '<p>源码里 <code>Map.writing</code> 的注释写得很明确:写入期间它被“XOR 1”翻转;注释里还说明了为什么是翻转而不是置位:多个写者同时进入时,翻转能提高两边都检测到的概率。读路径与迭代器也检查这个标志。这是一个<b>廉价的运行时检查</b>,而不是锁:它不阻止竞争,只是在发现时崩溃。</p>'),
     ('加同步与 -race', '<p>用 <code>sync.Mutex</code> 包住 map,或者换成 <code>sync.Map</code>,都不再出错。<code>-race</code> 编译无保护的版本时,竞态检测器先报告 <code>DATA RACE</code>(并指出两个 goroutine 的写位置),运行时的 fatal 随后依然触发。读多写少的场景可以用 <code>sync.RWMutex</code>(见后面的 RWMutex 一篇),<code>sync.Map</code> 适用的场景见 sync.Map 一篇。</p>')],
    steps,
    [ENV_G + '。每个模式是同一个程序的不同命令行参数,作为独立进程运行(退出码与输出来自真实进程);“30 次”的统计每次运行会有变化;读过的源码:internal/runtime/maps/map.go(writing 标志与各处 fatal 调用)与 table.go(迭代器里的检查)',
     '没有验证:Swiss map 以外的类型(如自己用切片实现的查找表)的行为、sync.Map 与 RWMutex 的性能比较(见各自的文章)、检测在 GOARCH 其它平台上的命中率、cgo 回调里的并发写'],
    '并发读写 map')
