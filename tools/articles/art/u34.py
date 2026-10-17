import re
from lib import *
S = SS('u34')
ms = [int(x) for x in re.findall(r'约 (\d+) ms', '\n'.join(S(4)))]
steps = [
    step("Mutex<T> 保护的是数据本身:m 不是 mut,m.lock().unwrap() 返回 MutexGuard,通过它才能访问里面的 Vec(push(4))。持有 guard 时 try_lock() 失败(is_err 为 true);guard 离开作用域自动解锁,之后 try_lock() 成功,值是 [1, 2, 3, 4];*m.lock().unwrap() = vec![9] 的临时 guard 在语句结束时就释放,再读到 [9]。", t=tl(S(1)), done=lidx(S(1), 'try_lock', '[9]'), kv=KV([['访问数据', '必须先拿到 MutexGuard'], ['解锁', 'guard drop 时自动']], ['解锁'])),
    step("中毒(poisoning):持锁的线程 panic 了(「持锁时 panic」),它的 join 返回 Err,锁被标记为中毒:is_poisoned() = true,之后 m.lock() 返回 Err(PoisonError)。数据并没有丢,e.into_inner() 仍能取出 5 —— 由你决定要不要继续使用可能处于不一致状态的数据。", t=tl(S(2)), mark=lidx(S(2), 'is_poisoned', 'PoisonError'), kv=KV([['持锁时 panic', '锁中毒'], ['into_inner()', '仍可取出数据']], ['持锁时 panic'])),
    step("死锁:同一个线程里第二次 m.lock() 会一直等自己 —— Mutex 不可重入:程序打印「第一次 lock 成功,准备第二次 lock ...」后挂住,3 秒超时被杀。更隐蔽的版本:println!(\"{} {}\", m.try_lock().is_ok(), m.lock().unwrap()) 也挂住:try_lock() 返回的 Result<MutexGuard> 是临时值,要到整条语句结束才 drop,所以后面的 lock() 还在等它。(这个死锁是我第一次写第一节的示例时意外撞上的。)", t=tl(S(3)), mark=lidx(S(3), '仍未结束'), kv=KV([['重复 lock', '死锁'], ['临时值里的 guard', '活到语句结束,也会死锁']], ['临时值里的 guard'])),
    step(f"锁的粒度:4 个线程各在锁内睡 50 ms,总耗时约 {ms[0]} ms(完全串行,≈ 4 × 50);把慢操作挪到锁外、只在锁内做 +1,总耗时约 {ms[1]} ms(并行,≈ 50)。持锁时间越短,并发越高。", t=tl(S(4)), mark=lidx(S(4), '在锁内睡'), b=bars([['锁内睡 50 ms', ms[0], f'{ms[0]} ms'], ['锁外睡、锁内只 +1', ms[1], f'{ms[1]} ms']], ms[0], mark=[0], done=[1]), kv=KV([['持锁做慢操作', f'约 {ms[0]} ms'], ['只在锁内改数据', f'约 {ms[1]} ms']], ['持锁做慢操作'])),
    step("空间:Mutex<u32> 是 16 字节(u32 是 4 字节):多出来的是锁本身(以及中毒标志)。", t=tl(S(5)), mark=lidx(S(5), 'Mutex<u32>'), kv=KV([['Mutex<u32>', '16 字节']], ['Mutex<u32>'])),
]
A = mkart('u34', 34, 'Rust,Mutex,内部可变性,死锁,真实验证,动画演示',
    f'用真实运行验证 Mutex<T>:guard 自动解锁、try_lock;持锁线程 panic 后锁中毒、into_inner 仍可取数据;同一线程重复 lock 以及临时值里的 guard 导致的死锁(3 秒超时);持锁做慢操作 {ms[0]} ms 而只在锁内改数据 {ms[1]} ms;Mutex<u32> 16 字节。',
    'Mutex 是线程之间「共享且可修改」的标准方案,它把锁和数据绑在一起 —— 不拿锁就拿不到数据。这篇验证 guard 的生命周期、锁中毒的行为、两种真实的死锁写法(包括一个很隐蔽的),以及持锁时间对并发度的影响。',
    [('poisoned', '持锁线程 panic 后 is_poisoned() = true,数据仍可 into_inner'), ('3 s 超时', '同一线程重复 lock 的程序在 3 秒后仍未结束(死锁)'), (f'{ms[0]} vs {ms[1]} ms', '4 个线程持锁睡 50 ms 与锁外睡 50 ms 的总耗时')],
    [('guard 与解锁', None), ('中毒', None), ('死锁', '<p>临时值的存活范围在 edition 2024 的 if let 里有变化(见<a href="rust-if-let-let-else.html">if let 与 let else</a>)。</p>'), ('锁的粒度', '<p>读多写少时可以用 RwLock,见<a href="rust-mutex-vs-rwlock.html">Mutex 与 RwLock</a>。</p>'), ('大小', None)],
    steps, [ENV_U + '。耗时为单次运行,包含线程创建开销', '没有验证:parking_lot 的 Mutex(无中毒、更小)、公平性与饥饿、锁顺序死锁(两把锁互相等)、MutexGuard 不是 Send 的编译错误、Condvar 配合使用(见 Condvar 一篇)'], 'Mutex<T>')
