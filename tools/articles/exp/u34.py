import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u34'); R = {}
print('== 一:Mutex<T> 保护数据本身:只有拿到 MutexGuard 才能访问里面的值;guard 离开作用域自动解锁')
r = tryit('u34a', '''
    use std::sync::Mutex;
    fn main() {
        let m = Mutex::new(vec![1, 2, 3]);                 // m 不是 mut
        {
            let mut g = m.lock().unwrap();                 // 拿到 guard
            g.push(4);
            println!("持有 guard 时 try_lock() 失败:{}", m.try_lock().is_err());
        }                                                   // guard 在这里 drop,自动解锁
        let free = m.try_lock().is_ok();                  // 单独一条语句:临时的 Result<MutexGuard> 在语句结束时释放
        println!("guard 释放之后 try_lock() 成功:{},值 = {:?}", free, m.lock().unwrap());
        *m.lock().unwrap() = vec![9];                      // 临时 guard,语句结束就释放
        println!("{:?}", m.lock().unwrap());
    }
''', quiet_src=False)
print()
print('== 二:中毒(poisoning):持锁的线程 panic 了,锁被标记为中毒,之后的 lock() 返回 Err')
r = tryit('u34b', '''
    use std::sync::{Arc, Mutex};
    use std::thread;
    fn main() {
        let m = Arc::new(Mutex::new(5));
        let m2 = Arc::clone(&m);
        let h = thread::spawn(move || { let _g = m2.lock().unwrap(); panic!("持锁时 panic"); });
        println!("子线程的 join 结果是 Err:{}", h.join().is_err());
        println!("is_poisoned() = {}", m.is_poisoned());
        match m.lock() {
            Ok(g) => println!("拿到了 {}", *g),
            Err(e) => { println!("lock() 返回 Err(PoisonError);里面的数据仍然可以取出:{}", *e.into_inner()); }
        }
    }
''', quiet_src=False)
print()
print('== 三:死锁:同一个线程重复 lock()(Mutex 不可重入);以及一个更隐蔽的版本 —— 临时值的 guard 活到整条语句结束。程序会挂住,这里给每个程序 3 秒超时')
import subprocess
for name, code in (('u34c', '''
    use std::sync::Mutex;
    fn main() {
        let m = Mutex::new(0);
        let _a = m.lock().unwrap();
        println!("第一次 lock 成功,准备第二次 lock ...");
        let _b = m.lock().unwrap();
        println!("不会打印");
    }
'''), ('u34c2', '''
    use std::sync::Mutex;
    fn main() {
        let m = Mutex::new(0);
        // try_lock() 返回的 Result<MutexGuard> 是临时值,要到整条 println! 语句结束才 drop
        println!("{} {}", m.try_lock().is_ok(), m.lock().unwrap());
    }
''')):
    ok, diag, b, _ = rustc(name, code)
    print(f'  程序 {name}:')
    print('\n'.join('    ' + l for l in numbered(code).split('\n')))
    try:
        p = subprocess.run([str(b)], capture_output=True, text=True, timeout=3); print('    正常退出了?', p.returncode, p.stdout.strip())
    except subprocess.TimeoutExpired as e:
        out_ = (e.stdout or b'').decode() if isinstance(e.stdout, bytes) else (e.stdout or '')
        print('    3 秒后仍未结束(被超时杀掉);已有的输出:', repr(out_.strip())); R['deadlock_' + name] = True
print()
print('== 四:锁的粒度:在持锁期间做慢操作,其它线程被迫排队(4 个线程,每个持锁 50 ms 与只在锁内做 1 微秒的对比)')
r = tryit('u34d', '''
    use std::sync::{Arc, Mutex};
    use std::thread;
    use std::time::{Duration, Instant};
    fn run(hold: Duration) -> f64 {
        let m = Arc::new(Mutex::new(0u32));
        let t = Instant::now();
        let hs: Vec<_> = (0..4).map(|_| { let m = Arc::clone(&m); thread::spawn(move || { let mut g = m.lock().unwrap(); *g += 1; thread::sleep(hold); }) }).collect();
        for h in hs { h.join().unwrap(); }
        t.elapsed().as_secs_f64() * 1000.0
    }
    fn main() {
        println!("4 个线程各在锁内睡 50 ms:总耗时约 {:.0} ms(串行,≈ 4 × 50)", run(Duration::from_millis(50)));
        let m = Arc::new(Mutex::new(0u32));
        let t = Instant::now();
        let hs: Vec<_> = (0..4).map(|_| { let m = Arc::clone(&m); thread::spawn(move || { thread::sleep(Duration::from_millis(50)); *m.lock().unwrap() += 1; }) }).collect();
        for h in hs { h.join().unwrap(); }
        println!("4 个线程在锁外睡 50 ms、只在锁内加 1:总耗时约 {:.0} ms(并行,≈ 50)", t.elapsed().as_secs_f64() * 1000.0);
    }
''', quiet_src=True); R['gran'] = r['out']
print()
print('== 五:Mutex 的空间开销')
r = tryit('u34e', '''
    use std::mem::size_of;
    use std::sync::Mutex;
    fn main() { println!("u32 = {},Mutex<u32> = {}", size_of::<u32>(), size_of::<Mutex<u32>>()); }
''', quiet_src=True)
save('u34', R)
