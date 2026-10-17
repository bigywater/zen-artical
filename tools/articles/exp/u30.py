import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u30'); R = {}
print('== 一:Arc<T> = 原子引用计数的 Rc,可以跨线程共享所有权')
r = tryit('u30a', '''
    use std::sync::Arc;
    use std::thread;
    fn main() {
        let data = Arc::new(vec![1, 2, 3, 4, 5, 6, 7, 8]);
        let mut hs = vec![];
        for i in 0..4 {
            let d = Arc::clone(&data);
            hs.push(thread::spawn(move || { let s: i32 = d[i * 2..i * 2 + 2].iter().sum(); (i, s) }));
        }
        for h in hs { let (i, s) = h.join().unwrap(); println!("线程 {i} 求和 = {s}"); }
        println!("全部线程结束后 strong_count = {}", Arc::strong_count(&data));
    }
''', quiet_src=False)
print()
print('== 二:Arc 只给共享所有权、不给可变性;要修改配合 Mutex')
r = tryit('u30b', '''
    use std::sync::Arc;
    fn main() { let a = Arc::new(5); *a += 1; }
''', maxlines=20); R['e594'] = r['diag'].split('\n')[0]
r = tryit('u30c', '''
    use std::sync::{Arc, Mutex};
    use std::thread;
    fn main() {
        let counter = Arc::new(Mutex::new(0u64));
        let hs: Vec<_> = (0..4).map(|_| { let c = Arc::clone(&counter); thread::spawn(move || { for _ in 0..10_000 { *c.lock().unwrap() += 1; } }) }).collect();
        for h in hs { h.join().unwrap(); }
        println!("4 个线程各加 10000 次,counter = {}(期望 40000)", *counter.lock().unwrap());
    }
''', quiet_src=False)
print()
print('== 三:Arc<T> 要求 T: Send + Sync:Cell 不行')
r = tryit('u30d', '''
    use std::cell::Cell;
    use std::sync::Arc;
    use std::thread;
    fn main() {
        let a = Arc::new(Cell::new(1));
        let b = Arc::clone(&a);
        thread::spawn(move || b.set(2)).join().unwrap();
    }
''', maxlines=30); R['e277'] = r['diag'].split('\n')[0]
print()
print('== 四:克隆的代价:Rc(非原子)、Arc(原子,单线程)、Arc(4 线程同时克隆同一个 Arc,缓存行争用)')
r = tryit('u30e', '''
    use std::hint::black_box;
    use std::rc::Rc;
    use std::sync::Arc;
    use std::thread;
    use std::time::Instant;
    const N: u64 = 2_000_000;
    fn main() {
        let rc = Rc::new(1u64);
        let t = Instant::now(); for _ in 0..N { let c = black_box(Rc::clone(&rc)); black_box(&c); }
        let rc_ns = t.elapsed().as_nanos() as f64 / N as f64;
        let arc = Arc::new(1u64);
        let t = Instant::now(); for _ in 0..N { let c = black_box(Arc::clone(&arc)); black_box(&c); }
        let arc1 = t.elapsed().as_nanos() as f64 / N as f64;
        let t = Instant::now();
        thread::scope(|s| { for _ in 0..4 { s.spawn(|| { for _ in 0..N { let c = black_box(Arc::clone(&arc)); black_box(&c); } }); } });
        let shared_ms = t.elapsed().as_secs_f64() * 1000.0;
        let t = Instant::now();
        thread::scope(|s| { for _ in 0..4 { s.spawn(|| { let mine = Arc::new(1u64); for _ in 0..N { let c = black_box(Arc::clone(&mine)); black_box(&c); } }); } });
        let sep_ms = t.elapsed().as_secs_f64() * 1000.0;
        println!("Rc::clone + drop                          每次约 {:.2} ns", rc_ns);
        println!("Arc::clone + drop(单线程)                每次约 {:.2} ns", arc1);
        println!("4 个线程各克隆 {} 次,共用同一个 Arc:    墙钟 {:.0} ms", N, shared_ms);
        println!("4 个线程各克隆 {} 次,各用自己的 Arc:    墙钟 {:.0} ms", N, sep_ms);
        println!("共用同一个计数器比各用各的慢 {:.1} 倍(我的推断:同一个计数器所在的缓存行在 4 个核之间来回传递,没有用性能计数器验证)", shared_ms / sep_ms);
    }
''', release=True, quiet_src=True); R['clone_cost'] = r['out']
save('u30', R)
