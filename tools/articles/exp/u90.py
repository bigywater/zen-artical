import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u90'); R = {}
print('== 一:Mutex 一次只让一个线程进入;RwLock 允许多个读者同时持有(各持 50 ms,4 个线程)')
r = tryit('u90a', '''
    use std::{sync::{Mutex, RwLock}, thread, time::{Duration, Instant}};
    fn main() {
        let m = Mutex::new(0); let rw = RwLock::new(0);
        let t = Instant::now();
        thread::scope(|s| { for _ in 0..4 { s.spawn(|| { let g = m.lock().unwrap(); thread::sleep(Duration::from_millis(50)); let _ = *g; }); } });
        let tm = t.elapsed().as_millis();
        let t = Instant::now();
        thread::scope(|s| { for _ in 0..4 { s.spawn(|| { let g = rw.read().unwrap(); thread::sleep(Duration::from_millis(50)); let _ = *g; }); } });
        let tr = t.elapsed().as_millis();
        println!("Mutex:     4 个线程各持锁 50 ms,总耗时约 {} ms(串行)", (tm / 10) * 10);
        println!("RwLock 读: 4 个线程各持读锁 50 ms,总耗时约 {} ms(并行)", (tr / 10) * 10);
        let t = Instant::now();
        thread::scope(|s| { for _ in 0..4 { s.spawn(|| { let mut g = rw.write().unwrap(); thread::sleep(Duration::from_millis(50)); *g += 1; }); } });
        println!("RwLock 写: 4 个线程各持写锁 50 ms,总耗时约 {} ms(写锁互斥,串行)", (t.elapsed().as_millis() / 10) * 10);
    }
''', quiet_src=True); R['par'] = r['out']
print()
print('== 二:写者阻塞读者:写锁被持有时,try_read / try_write 都得到 WouldBlock;读锁被持有时 try_write 失败、try_read 成功')
r = tryit('u90b', '''
    use std::sync::{RwLock, Mutex, TryLockError};
    fn kind<T>(r: Result<T, TryLockError<T>>) -> &'static str { match r { Ok(_) => "成功", Err(TryLockError::WouldBlock) => "WouldBlock", Err(TryLockError::Poisoned(_)) => "Poisoned" } }
    fn main() {
        let rw = RwLock::new(1);
        { let _w = rw.write().unwrap(); println!("持有写锁时:try_read = {}  try_write = {}", kind(rw.try_read()), kind(rw.try_write())); }
        { let _r = rw.read().unwrap(); println!("持有读锁时:try_read = {}  try_write = {}", kind(rw.try_read()), kind(rw.try_write())); }
        let m = Mutex::new(1);
        { let _g = m.lock().unwrap(); println!("Mutex 持有时:try_lock = {}", kind(m.try_lock())); }
        println!("释放后:try_lock = {}", kind(m.try_lock()));
    }
''', quiet_src=True); R['try'] = r['out']
print()
print('== 三:同一线程重复加锁会死锁(不会报错);这里用 try_lock 与超时的子线程证明')
r = tryit('u90c', '''
    use std::{sync::{Arc, Mutex, mpsc}, thread, time::Duration};
    fn main() {
        let m = Arc::new(Mutex::new(0)); let (tx, rx) = mpsc::channel();
        let m2 = m.clone();
        thread::spawn(move || { let _a = m2.lock().unwrap(); tx.send("拿到第一把锁").unwrap(); let _b = m2.lock().unwrap(); tx.send("拿到第二把锁(不应出现)").unwrap(); });
        println!("{}", rx.recv().unwrap());
        println!("再等 300 ms:{:?}(同一线程第二次 lock 阻塞了)", rx.recv_timeout(Duration::from_millis(300)));
        println!("主线程 try_lock: {}", if m.try_lock().is_err() { "拿不到,锁被卡住的线程占着" } else { "拿到了" });
        std::process::exit(0);
    }
''', quiet_src=True); R['deadlock'] = r['out']
print()
print('== 四:临界区很小时,RwLock 并不比 Mutex 快:4 个线程各读 200 万次(release,各 3 次取最小)')
r = tryit('u90d', '''
    use std::{sync::{Mutex, RwLock}, thread, time::Instant};
    fn main() {
        let m = Mutex::new(5u64); let rw = RwLock::new(5u64); let n = 2_000_000;
        let (mut bm, mut br) = (f64::MAX, f64::MAX);
        for _ in 0..3 {
            let t = Instant::now(); thread::scope(|s| { for _ in 0..4 { s.spawn(|| { let mut x = 0u64; for _ in 0..n { x += *m.lock().unwrap(); } std::hint::black_box(x); }); } }); bm = bm.min(t.elapsed().as_secs_f64() * 1e3);
            let t = Instant::now(); thread::scope(|s| { for _ in 0..4 { s.spawn(|| { let mut x = 0u64; for _ in 0..n { x += *rw.read().unwrap(); } std::hint::black_box(x); }); } }); br = br.min(t.elapsed().as_secs_f64() * 1e3);
        }
        println!("Mutex  4 线程 × 200 万次读:{:>8.1} ms", bm);
        println!("RwLock 4 线程 × 200 万次读:{:>8.1} ms", br);
        println!("size_of::<Mutex<u64>>() = {}  size_of::<RwLock<u64>>() = {}  size_of::<u64>() = {}", std::mem::size_of::<Mutex<u64>>(), std::mem::size_of::<RwLock<u64>>(), std::mem::size_of::<u64>());
    }
''', quiet_src=True, release=True); R['bench'] = r['out']
save('u90', R)
