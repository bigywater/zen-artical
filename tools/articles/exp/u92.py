import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u92'); R = {}
print('== 一:原子计数 vs「先读后写」的伪原子计数:4 个线程各加 100 万次')
r = tryit('u92a', '''
    use std::{sync::atomic::{AtomicUsize, Ordering::*}, thread};
    fn main() {
        let a = AtomicUsize::new(0); let b = AtomicUsize::new(0);
        thread::scope(|s| { for _ in 0..4 { s.spawn(|| { for _ in 0..1_000_000 { a.fetch_add(1, Relaxed); } }); } });
        thread::scope(|s| { for _ in 0..4 { s.spawn(|| { for _ in 0..1_000_000 { let v = b.load(Relaxed); b.store(v + 1, Relaxed); } }); } });
        println!("fetch_add:      期望 4000000,实际 {}", a.load(Relaxed));
        println!("load + store:   期望 4000000,实际 {}(丢失了更新)", b.load(Relaxed));
    }
''', quiet_src=True, release=True); R['count'] = r['out']
print()
print('== 二:Ordering 的成本:单线程 5000 万次 fetch_add,Relaxed / AcqRel / SeqCst;4 线程竞争时同一变量')
r = tryit('u92b', '''
    use std::{sync::atomic::{AtomicU64, Ordering::{self, *}}, thread, time::Instant, hint::black_box};
    fn single(o: Ordering) -> f64 { let a = AtomicU64::new(0); let t = Instant::now(); for _ in 0..50_000_000 { black_box(&a).fetch_add(1, o); } t.elapsed().as_secs_f64() * 1e9 / 5e7 }
    fn multi(o: Ordering) -> f64 { let a = AtomicU64::new(0); let t = Instant::now(); thread::scope(|s| { for _ in 0..4 { s.spawn(|| { for _ in 0..5_000_000 { black_box(&a).fetch_add(1, o); } }); } }); t.elapsed().as_secs_f64() * 1e9 / 2e7 }
    fn best(f: impl Fn(Ordering) -> f64, o: Ordering) -> f64 { (0..3).map(|_| f(o)).fold(f64::MAX, f64::min) }
    fn main() {
        for (n, o) in [("Relaxed", Relaxed), ("AcqRel", AcqRel), ("SeqCst", SeqCst)] { println!("{:<8} 单线程 {:>5.2} ns/次   4 线程争用 {:>6.2} ns/次(每次操作的平均墙钟时间)", n, best(single, o), best(multi, o)); }
    }
''', quiet_src=True, release=True); R['cost'] = r['out']
LITMUS = '''
    use std::{sync::atomic::{AtomicU32, Ordering::{self, *}}, thread};
    fn spin_until(a: &AtomicU32, v: u32) { while a.load(Acquire) != v { std::hint::spin_loop(); } }
    // 消息传递(MP):线程 A 写 data 再写 flag;线程 B 读 flag,若为 1 再读 data。data 读到 0 就是「看到了 flag 却没看到 data」。
    fn mp(store_o: Ordering, load_o: Ordering, iters: u32) -> u32 {
        let data = AtomicU32::new(0); let flag = AtomicU32::new(0); let go = AtomicU32::new(0); let fin = AtomicU32::new(0); let bad = AtomicU32::new(0);
        thread::scope(|s| {
            s.spawn(|| { for i in 1..=iters { spin_until(&go, i); data.store(1, Relaxed); flag.store(1, store_o); fin.fetch_add(1, AcqRel); } });
            s.spawn(|| { for i in 1..=iters { spin_until(&go, i); let mut f = 0; for _ in 0..200 { f = flag.load(load_o); if f == 1 { break; } } if f == 1 && data.load(Relaxed) == 0 { bad.fetch_add(1, Relaxed); } fin.fetch_add(1, AcqRel); } });
            for i in 1..=iters { data.store(0, Relaxed); flag.store(0, Relaxed); fin.store(0, Relaxed); go.store(i, Release); while fin.load(Acquire) != 2 { std::hint::spin_loop(); } }
        });
        bad.load(Relaxed)
    }
    fn main() {
        let n = 1_000_000;
        println!("消息传递测试,{} 轮:", n);
        println!("  flag 用 Relaxed 写 / Relaxed 读:看到 flag=1 却读到 data=0 的次数 = {}", mp(Relaxed, Relaxed, n));
        println!("  flag 用 Release 写 / Acquire 读:看到 flag=1 却读到 data=0 的次数 = {}", mp(Release, Acquire, n));
    }
'''
print()
print('== 三:弱内存序真的会出现:消息传递测试(aarch64 是弱内存模型的 CPU)')
r = tryit('u92c', LITMUS, quiet_src=True, release=True, show_run=False)
runs = []
for k in range(4):
    o = run(r['bin'])[1]
    rel = int(re.search(r'Relaxed 读:.*?= (\d+)', o).group(1)); acq = int(re.search(r'Acquire 读:.*?= (\d+)', o).group(1)); runs.append((rel, acq))
    print(f'  第 {k + 1} 次运行(每次 100 万轮):Relaxed/Relaxed 异常 {rel} 次;Release/Acquire 异常 {acq} 次')
R['mp'] = runs
save('u92', R)
