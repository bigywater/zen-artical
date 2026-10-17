import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u91'); R = {}
print('== 一:Condvar 的标准用法:Mutex 保护条件,wait 会释放锁并睡眠,被唤醒后重新拿锁并重新检查条件')
r = tryit('u91a', '''
    use std::{sync::{Arc, Mutex, Condvar}, thread, time::{Duration, Instant}};
    fn main() {
        let pair = Arc::new((Mutex::new(false), Condvar::new()));
        let p2 = pair.clone();
        let t = Instant::now();
        let h = thread::spawn(move || { thread::sleep(Duration::from_millis(100)); let (m, cv) = &*p2; *m.lock().unwrap() = true; cv.notify_one(); });
        let (m, cv) = &*pair;
        let mut ready = m.lock().unwrap();
        while !*ready { ready = cv.wait(ready).unwrap(); }
        println!("等到条件为真,等了约 {} ms(取整到 50)", (t.elapsed().as_millis() / 50) * 50);
        h.join().unwrap();
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:wait 期间锁是释放的:另一个线程可以拿到同一把锁')
r = tryit('u91b', '''
    use std::{sync::{Arc, Mutex, Condvar}, thread, time::Duration};
    fn main() {
        let pair = Arc::new((Mutex::new(0), Condvar::new())); let p2 = pair.clone();
        let h = thread::spawn(move || { let (m, cv) = &*p2; let mut g = m.lock().unwrap(); while *g == 0 { g = cv.wait(g).unwrap(); } *g });
        thread::sleep(Duration::from_millis(100));
        let (m, cv) = &*pair;
        let got = m.try_lock().is_ok();
        println!("子线程正在 wait 时,主线程 try_lock 成功: {}(wait 释放了锁)", got);
        *m.lock().unwrap() = 7; cv.notify_one();
        println!("子线程醒来读到 {}", h.join().unwrap());
    }
''', quiet_src=True); R['release'] = r['out']
print()
print('== 三:通知丢失:先 notify 后 wait,如果没有状态变量记录,这次通知就白发了(用带超时的 wait 证明);用 bool 状态变量可以避免')
r = tryit('u91c', '''
    use std::{sync::{Arc, Mutex, Condvar}, thread, time::Duration};
    fn main() {
        // 错误写法:notify 先发生,wait 才开始,没有记录“已经通知过”
        let pair = Arc::new((Mutex::new(()), Condvar::new()));
        pair.1.notify_one();
        let g = pair.0.lock().unwrap();
        let (_g, res) = pair.1.wait_timeout(g, Duration::from_millis(300)).unwrap();
        println!("先 notify 后 wait(没有状态变量):wait_timeout 超时了吗? {}(通知丢失)", res.timed_out());
        // 正确写法:用 bool 记录
        let pair = Arc::new((Mutex::new(false), Condvar::new()));
        { *pair.0.lock().unwrap() = true; pair.1.notify_one(); }
        let g = pair.0.lock().unwrap();
        let (g, res) = pair.1.wait_timeout_while(g, Duration::from_millis(300), |ready| !*ready).unwrap();
        println!("先通知(置 true)后 wait_while:超时了吗? {}  条件 = {}", res.timed_out(), *g);
        let _ = thread::current();
    }
''', quiet_src=True); R['lost'] = r['out']
print()
print('== 四:notify_one 与 notify_all:5 个线程在等,各发一次通知,统计被唤醒的线程数')
r = tryit('u91d', '''
    use std::{sync::{Arc, Mutex, Condvar, atomic::{AtomicUsize, Ordering::SeqCst}}, thread, time::Duration};
    fn trial(all: bool) -> usize {
        let pair = Arc::new((Mutex::new(false), Condvar::new())); let woke = Arc::new(AtomicUsize::new(0)); let waiting = Arc::new(AtomicUsize::new(0));
        let hs: Vec<_> = (0..5).map(|_| { let (p, w, wt) = (pair.clone(), woke.clone(), waiting.clone()); thread::spawn(move || {
            let g = p.0.lock().unwrap(); wt.fetch_add(1, SeqCst);
            // 不检查条件,只等一次通知(演示 notify 的数量语义);带超时避免永远等待
            let (_g, res) = p.1.wait_timeout(g, Duration::from_millis(400)).unwrap(); if !res.timed_out() { w.fetch_add(1, SeqCst); }
        }) }).collect();
        while waiting.load(SeqCst) < 5 { thread::sleep(Duration::from_millis(5)); } thread::sleep(Duration::from_millis(50));
        { let _g = pair.0.lock().unwrap(); if all { pair.1.notify_all(); } else { pair.1.notify_one(); } }
        for h in hs { h.join().unwrap(); } woke.load(SeqCst)
    }
    fn main() { println!("5 个线程在 wait:notify_one 唤醒了 {} 个;notify_all 唤醒了 {} 个", trial(false), trial(true)); }
''', quiet_src=True); R['one_all'] = r['out']
print()
print('== 五:用 Condvar 实现阻塞队列:生产者慢、消费者快,消费者在队列空时睡眠(用 CPU 时间验证没有忙等)')
r = tryit('u91e', '''
    use std::{sync::{Arc, Mutex, Condvar}, collections::VecDeque, thread, time::{Duration, Instant}};
    fn cpu_ms() -> f64 { let mut ts = unsafe { std::mem::zeroed::<libc_timespec>() }; unsafe { clock_gettime(12, &mut ts); } ts.tv_sec as f64 * 1e3 + ts.tv_nsec as f64 / 1e6 }
    #[repr(C)] struct libc_timespec { tv_sec: i64, tv_nsec: i64 }
    unsafe extern "C" { fn clock_gettime(clk: i32, ts: *mut libc_timespec) -> i32; }
    fn main() {
        let q = Arc::new((Mutex::new(VecDeque::new()), Condvar::new())); let q2 = q.clone();
        let c0 = cpu_ms(); let t0 = Instant::now();
        let prod = thread::spawn(move || { for i in 0..10 { thread::sleep(Duration::from_millis(50)); let (m, cv) = &*q2; m.lock().unwrap().push_back(i); cv.notify_one(); } });
        let mut got = vec![];
        let (m, cv) = &*q;
        while got.len() < 10 { let mut g = m.lock().unwrap(); while g.is_empty() { g = cv.wait(g).unwrap(); } got.push(g.pop_front().unwrap()); }
        prod.join().unwrap();
        println!("收到 {:?},墙钟时间约 {} ms,进程 CPU 时间约 {:.0} ms(消费者睡眠,没有忙等)", got, (t0.elapsed().as_millis() / 50) * 50, cpu_ms() - c0);
    }
''', quiet_src=True); R['queue'] = r['out']
save('u91', R)
