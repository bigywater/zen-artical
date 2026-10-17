from lib import *
import re
S = SS('u103')
R = J('u103')
b = re.search(r'std::sync::Mutex\s+4 任务 × 100 万次:\s+([\d.]+) ms.*\n.*tokio::sync::Mutex\s+4 任务 × 100 万次:\s+([\d.]+) ms', R['bench']); bs, bt = b.group(1), b.group(2); rr = round(float(bt) / float(bs), 1)
steps = [
    step("std::sync::MutexGuard 跨 await 持有:tokio::spawn 要求 Future 是 Send,编译器报 error: future cannot be sent between threads safely,help 写「the trait `Send` is not implemented for `std::sync::MutexGuard<'_, i32>`」,note 精确指出「future is not `Send` as this value is used across an await」—— 指向 g 的类型和 await 的位置。", t=tl(S(1)), mark=lidx(S(1), 'error: future cannot be sent', 'MutexGuard', 'used across an await'), kv=KV([['std MutexGuard', '不是 Send'], ['跨 await 持有', 'Future 不是 Send']], ['跨 await 持有'])),
    step("换成 tokio::sync::Mutex:lock() 是 async 的,guard 可以跨 await。4 个任务各自「持锁 → sleep 20 ms(跨 await)→ +1」,最终值 4,没有丢更新;任务在等锁时挂起,不占着线程。", t=tl(S(2)), done=lidx(S(2), '最终值 4'), kv=KV([['tokio Mutex', 'lock().await,guard 可跨 await'], ['结果', '4']], ['tokio Mutex'])),
    step("不跨 await 就不需要 tokio 的锁:std Mutex 只在 { m.lock().unwrap().push(i); } 这个块里持有,guard 在块结束时释放,之后再 await,Future 仍然是 Send,可以 spawn,四个任务按睡眠时间的先后得到 [3, 2, 1, 0]。", t=tl(S(3)), done=lidx(S(3), 'std Mutex'), kv=KV([['guard 不跨 await', 'Future 仍是 Send']], ['guard 不跨 await'])),
    step("在单线程运行时里,std Mutex 跨 await 会死锁(用 LocalSet 绕过 Send 检查):任务 A 持锁后 await 让出线程,任务 B 在同一个线程上调用 lock() 把整个线程阻塞,A 再没有机会运行释放锁。实测程序 6 秒内没有退出,连外层 500 ms 的 timeout 也没有触发(因为线程被阻塞)。", t=tl(S(4)), mark=lidx(S(4), '没有退出'), kv=KV([['A 持锁 await', '线程交给 B'], ['B lock()', '阻塞唯一的线程 → 死锁']], ['B lock()'])),
    step(f"短临界区、不 await 时 std Mutex 更便宜:4 个任务各锁 100 万次 +1(multi_thread,4 线程,release,取 3 次最小),std::sync::Mutex {bs} ms,tokio::sync::Mutex {bt} ms,约 {rr} 倍。据此的经验:能用 std Mutex 就不用 tokio Mutex,只在必须跨 await 持有时才用后者。", t=tl(S(5)), done=lidx(S(5), 'std::sync::Mutex', 'tokio::sync::Mutex'), b=bars([['std::sync::Mutex', float(bs), f'{bs} ms'], ['tokio::sync::Mutex', float(bt), f'{bt} ms']], float(bt), cur=[1], done=[0]), kv=KV([['std', f'{bs} ms'], ['tokio', f'{bt} ms(约 {rr}×)']], ['tokio'])),
]
A = mkart('u103', 103, 'Rust,tokio,Mutex,异步,死锁,真实验证,动画演示',
    f'下载 tokio 验证异步里的 Mutex 边界:std MutexGuard 跨 await 让 Future 不是 Send(编译器指出 used across an await);tokio::sync::Mutex 可跨 await;guard 不跨 await 时 std Mutex 可用;单线程运行时里跨 await 持 std 锁会死锁(6 秒不退出);无 await 的短临界区 std {bs} ms 对 tokio {bt} ms。',
    '异步代码里该用 std::sync::Mutex 还是 tokio::sync::Mutex?答案不是「异步就用异步的锁」。这篇用编译错误、真实死锁和 400 万次加锁的计时,说清楚两者各自的边界。',
    [('used across an await', '编译器指出 std MutexGuard 导致 Future 不是 Send 的原因'), ('死锁', '单线程运行时里 std Mutex 跨 await 持有的结局'), (f'{rr}×', '无 await 的短临界区里,tokio Mutex 比 std Mutex 慢的倍数')],
    [('std MutexGuard 跨 await', '<p>Send 的规则见<a href="rust-send-sync.html">Send 与 Sync</a>;spawn 的约束见<a href="rust-spawn-static.html">spawn 与 \'static</a>。</p>'), ('tokio::sync::Mutex', None), ('不跨 await 的 std Mutex', None), ('单线程上的死锁', '<p>阻塞线程的更多后果见<a href="rust-blocking-in-async.html">阻塞代码混入异步任务</a>。</p>'), ('性能', '<p>这是 macOS aarch64 上的一次微基准,只测了高争用的短临界区。</p>')],
    steps, [ENV_U + '。tokio 1.x', '没有验证:跨 await 持有 tokio Mutex 的公平性、parking_lot Mutex 的行为、try_lock 的用法、RwLock 的异步版本、LocalSet 里 !Send Future 的其它风险、死锁时具体卡在哪一行(没有用调试器附加)'], '异步 Mutex')
