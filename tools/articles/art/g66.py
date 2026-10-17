from lib import *
S = SS('g66')
steps = [
    step("Wait 放在 if 里还是 for 里:8 个消费者,1 个生产者每隔约 50 µs 放一个元素并 Broadcast,共 3000 个元素。Wait 放在 if 里:取走 3000 个,其中醒来后队列里其实没有元素、却照常取走的有 2998 次;Wait 放在 for 循环里:同样取走 3000 个,这样的次数是 0。", t=tl(S(1)), done=lidx(S(1), 'for 循环 里'), mark=lidx(S(1), 'Wait 放在 if 里'), b=bars([['if:空队列照取 (次)', 2998, '2998'], ['for 循环', 0, '0']], 2998, mark=[0], done=[1]), kv=KV([['if', '3000 次取走里 2998 次队列是空的'], ['for', '0 次'], ['原因', 'Broadcast 唤醒 8 个,只有一个有元素可取']], ['原因'])),
    step("Signal 与 Broadcast 唤醒几个:8 个 goroutine 在 Wait,放入 1 个元素后调用 Signal,从 Wait 返回的有 1 个;调用 Broadcast,从 Wait 返回的有 8 个(其中只有 1 个能拿到元素,其余 7 个应该回去继续等)。", t=tl(S(2)), done=lidx(S(2), '调用 Signal'), mark=lidx(S(2), '调用 Broadcast'), b=bars([['Signal 唤醒', 1, '1'], ['Broadcast 唤醒', 8, '8']], 8, done=[0], mark=[1]), kv=KV([['Signal', '唤醒 1 个'], ['Broadcast', '唤醒 8 个(惊群)']], ['Broadcast'])),
    step("信号先发后等会丢:没有 goroutine 在 Wait 时调用 Signal,之后才有消费者调用 Wait:300 ms 后消费者仍卡在 Wait。Cond 不记忆信号,条件必须放在共享变量里、由循环检查。", t=tl(S(3)), mark=lidx(S(3), '信号丢失了'), kv=KV([['Signal 先于 Wait', '300 ms 后仍卡住'], ['原因', 'Cond 不保存信号'], ['做法', '用共享变量记条件,Wait 前检查']], ['做法'])),
    step("用 Cond 和用 channel 来回传递:两个 goroutine 来回传递 20 万次,sync.Cond 308 ns/个来回;无缓冲 channel 261 ns/个来回。Cond 比 channel 慢约 18%,并不是更快的传递方式。", t=tl(S(4)), mark=lidx(S(4), '两个 goroutine 来回传递'), b=bars([['sync.Cond (ns)', 308, '308'], ['无缓冲 channel', 261, '261']], 308, mark=[0], done=[1]), kv=KV([['Cond', '308 ns/个来回'], ['channel', '261 ns/个来回']], ['Cond'])),
    step("文档原文:Wait 原子地解锁 c.L 并挂起调用它的 goroutine;之后恢复执行时,Wait 先给 c.L 加锁再返回。与其它系统不同,Wait 只有被 Broadcast 或 Signal 唤醒才会返回。因为 Wait 等待期间 c.L 没有加锁,调用者通常不能假设 Wait 返回时条件已经成立;而应该在循环里 Wait:c.L.Lock(); for !condition() { c.Wait() } … c.L.Unlock()。", t=tl(S(5)), done=lidx(S(5), 'Wait atomically unlocks', 'Wait locks c.L before returning'), mark=lidx(S(5), 'should Wait in a loop', 'for !condition()'), kv=KV([['Wait', '原子地解锁并挂起;返回前重新加锁'], ['返回时条件', '不保证成立'], ['写法', 'for !condition() { c.Wait() }']], ['写法'])),
]
A = mkartg('g66', 66, 'Go,sync.Cond,条件变量,Wait,Broadcast,真实验证,动画演示',
    '在 Go 1.27.1 里验证 sync.Cond.Wait 为什么要放在循环里:8 个消费者、Broadcast 时,Wait 放 if 里 3000 个元素中有 2998 次醒来后队列是空却照常取,放 for 里是 0 次;Signal 唤醒 1 个、Broadcast 唤醒 8 个;Signal 先于 Wait 会丢(300 ms 后仍卡住);Cond 来回传递 308 ns,比无缓冲 channel 的 261 ns 慢。',
    'sync.Cond 的文档只用一句话要求 Wait 必须放在循环里。如果写成 if 会怎样?这篇用 8 个消费者复现这个 bug,量 Signal 与 Broadcast 唤醒的个数,看信号先发后等会不会丢,并和 channel 比较来回传递的耗时。',
    [('2998 / 0', 'Wait 放 if 里和放 for 里,醒来后队列为空却照常取走的次数(3000 个元素)'), ('1 vs 8', '8 个 goroutine 在 Wait 时,Signal 与 Broadcast 唤醒的个数'), ('308 vs 261 ns', '来回传递:sync.Cond 对无缓冲 channel')],
    [('if 为什么错', '<p>Broadcast 一次唤醒 8 个消费者,但只放入了 1 个元素:它们依次拿到锁,第一个取走元素,其余 7 个醒来后队列是空的。用 <code>if</code> 就会直接往下取,队列变成负数;之后条件(队列≠0)又被误判成立,整段逻辑失控——实验里 3000 个元素有 2998 次取走时队列其实没有元素。用 <code>for</code> 就是 0 次。</p>'),
     ('Signal 与 Broadcast', '<p><code>Signal</code> 唤醒 1 个,<code>Broadcast</code> 唤醒全部 8 个。后者在等待者多、每次只放一个资源时是惊群,代价是 7 个无谓的唤醒和抢锁。</p>'),
     ('信号不排队', '<p>没人在 <code>Wait</code> 时发出的 <code>Signal</code> 直接丢失,之后才来的 <code>Wait</code> 会一直等下去(实验里 300 ms 后仍卡住)。所以条件必须存在共享变量里:先在锁内检查条件,不满足再 <code>Wait</code>。</p>'),
     ('不比 channel 快', '<p>两个 goroutine 来回传递 20 万次,Cond 308 ns,无缓冲 channel 261 ns。Cond 的用武之地是“多个等待者等同一个条件、可能广播”,而不是传值。</p>'),
     ('文档怎么说', '<p><code>Wait</code> 原子地解锁并挂起,返回前重新加锁;但等待期间锁是放开的,条件可能已被别人改掉,所以文档给出的写法就是 <code>for !condition() { c.Wait() }</code>。这与实验里的 bug 完全对应。</p>')],
    steps,
    [ENV_G + '。第一节:8 个消费者、1 个生产者每隔约 50 µs 放一个元素并 Broadcast,3000 个元素;“照常取走”指消费者在队列 ≤ 0 时仍取走元素;其余各节为单独的小程序;来回传递各 20 万次,单次测量;文档引自 go doc sync.Cond.Wait。等待条件用“队列 ≤ 0”,这样 if 版本下队列变成负数也会被算作“没有元素”',
     '没有验证:真正的“虚假唤醒”(Go 的文档说 Wait 只会被 Signal/Broadcast 唤醒,本文没有试图复现别的唤醒)、Cond 的内部实现(notifyList)、Broadcast 后的唤醒顺序、大量等待者时的开销、其它架构'],
    'sync.Cond')
