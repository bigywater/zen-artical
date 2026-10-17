from lib import *
S = SS('g68')
steps = [
    step("合并同一个键的并发请求:100 个并发请求同一个键,加载函数耗时 100 ms。不合并:加载函数被调用 100 次,总用时 102 ms;singleflight:被调用 1 次,总用时 102 ms,shared=true 的调用方 100 个。100 个请求分布在 4 个不同的键上:被调用 4 次(不同键不合并)。同一个键顺序调用 3 次(每次等上一次结束):被调用 3 次——singleflight 不是缓存,只合并“正在进行”的调用。", t=tl(S(1)), done=lidx(S(1), 'singleflight → 加载函数被调用 1 次', '分布在 4 个不同的键上'), mark=lidx(S(1), '不合并 → 加载函数被调用 100 次', '顺序调用 3 次'), b=bars([['不合并:加载函数调用次数', 100, '100'], ['singleflight', 1, '1'], ['4 个不同键', 4, '4'], ['顺序 3 次', 3, '3']], 100, done=[1, 2], mark=[0, 3]), kv=KV([['同键并发', '100 次 → 1 次'], ['不同键', '各合并各的(4 次)'], ['顺序调用', '不合并,不是缓存']], ['顺序调用'])),
    step("缓存击穿:热点键刚过期,200 个请求在 50 ms 内陆续到达,后端每次 100 ms。不合并:打到后端 200 次,总用时 150 ms;用 singleflight:打到后端 1 次,总用时 101 ms。", t=tl(S(2)), done=lidx(S(2), '用 singleflight'), mark=lidx(S(2), '不合并'), b=bars([['不合并:打到后端 (次)', 200, '200'], ['singleflight', 1, '1']], 200, mark=[0], done=[1]), kv=KV([['不合并', '后端 200 次,150 ms'], ['singleflight', '后端 1 次,101 ms']], ['singleflight'])),
    step("错误也被共享,调用方的 ctx 被“借用”:三个请求先后到达(0/10/20 ms),第一个的加载函数返回“后端失败”——三个调用方得到的错误都是后端失败。第一个调用方的 ctx 20 ms 后超时、第二个的 ctx 不会超时,但加载函数用的是第一个的 ctx:两个调用方都得到 context deadline exceeded。用 DoChan + select 时,调用方可以自己在 31 ms 超时离开,后台的加载仍会继续。", t=tl(S(3)), done=lidx(S(3), 'DoChan + select'), mark=lidx(S(3), '后端失败 / 后端失败', 'context deadline exceeded'), kv=KV([['错误', '所有等待者得到同一个错误'], ['ctx 借用', '第二个调用方被第一个的超时连累'], ['DoChan', '调用方可以自己超时离开']], ['ctx 借用'])),
    step("加载函数 panic:三个调用方各自 recover,结果都是 recover 到 panic(*singleflight.panicError)——panic 被包装成 panicError 再重新抛给每一个等待者。", t=tl(S(4)), mark=lidx(S(4), 'panicError'), kv=KV([['panic', '所有调用方都会 panic'], ['类型', '*singleflight.panicError'], ['含义', '每个调用方要自己 recover']], ['含义'])),
    step("源码注释:Do 保证对同一个键同一时刻最多只有一次执行在进行;重复的调用方等原调用完成并得到相同的结果;返回值 shared 表示结果是否给了多个调用方。Forget 告诉 singleflight 忘记一个键,之后对这个键的 Do 会调用函数,而不是等待之前的调用完成。", t=tl(S(5)), done=lidx(S(5), 'only one execution is in-flight', 'The return value shared'), mark=lidx(S(5), 'Forget tells the singleflight'), kv=KV([['Do', '同键同时只有一次执行'], ['shared', '结果是否给了多个调用方'], ['Forget', '让之后的调用重新执行']], ['Forget'])),
]
A = mkartg('g68', 68, 'Go,singleflight,缓存击穿,并发,合并请求,真实验证,动画演示',
    '用 golang.org/x/sync v0.24.0 的 singleflight 实测:100 个并发请求同一个键,加载函数从 100 次降到 1 次;缓存刚过期的 200 个请求,后端从 200 次降到 1 次、总用时 150 ms 降到 101 ms;但它不是缓存(顺序调用 3 次就执行 3 次);错误被所有等待者共享;第一个调用方的 ctx 超时会连累第二个调用方;加载函数 panic 会让所有调用方 panic。',
    '热点缓存过期的瞬间,成百上千个请求同时打到后端,这是缓存击穿。singleflight 把同一个键的并发请求合并成一次。这篇实测它能省多少,以及错误共享、ctx 借用、panic 扩散这几个容易忽略的行为。',
    [('100 → 1', '100 个并发请求同一个键,加载函数的调用次数'), ('200 → 1', '缓存刚过期时 200 个陆续到达的请求,打到后端的次数'), ('ctx 借用', '第二个调用方被第一个调用方的超时连累')],
    [('合并的是“正在进行”的调用', '<p>同一个键的并发调用合并成一次:100 个请求加载函数只调用 1 次,而不同键各自合并(4 个键 4 次)。它不是缓存:同一个键顺序调用 3 次就执行 3 次,所以缓存仍要自己做,singleflight 只负责缓存失效时的那一下。</p>'),
     ('缓存击穿的对照', '<p>热点键刚过期,200 个请求在 50 ms 内陆续到达,后端每次 100 ms:不合并打后端 200 次,用 singleflight 只打 1 次,总用时也从 150 ms 降到 101 ms。</p>'),
     ('共享的不只是结果', '<p>错误会被所有等待者共享,所以后到的请求也得到一次失败。更隐蔽的是 ctx:加载函数用了第一个调用方的 ctx,它 20 ms 超时,第二个调用方尽管自己没超时也得到 <code>context deadline exceeded</code>。解决办法是加载函数用不会被某个调用方取消的 ctx,并用 <code>DoChan</code> 让每个调用方自己 <code>select</code> 超时。</p>'),
     ('panic 会扩散', '<p>加载函数 panic 时,每个调用方都收到包装后的 <code>*singleflight.panicError</code> 并 panic。第一个调用方 recover 了,其余的也要。</p>'),
     ('源码注释', '<p><code>Do</code> 保证同一个键同一时刻只有一个在飞行中的执行;<code>shared</code> 告诉你结果有没有给多个调用方;<code>Forget</code> 让下一次调用重新执行而不是等旧的。</p>')],
    steps,
    [ENV_G + '。singleflight 来自 golang.org/x/sync v0.24.0(本机代理下载);每个实验是一个小程序,加载函数用 time.Sleep 模拟后端;第二节的请求到达间隔 250 µs;源码注释摘自 singleflight.go',
     '没有验证:Forget 在实际场景中的用法、DoChan 与 Forget 联用、singleflight 的内存占用、大量不同键时的开销、其它版本的行为(panic 的包装方式可能随版本变化,没有对比)、与带 TTL 的缓存库组合时的细节'],
    'singleflight')
