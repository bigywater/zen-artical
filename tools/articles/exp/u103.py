import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u103'); R = {}
DEPS = 'tokio = { version = "1", features = ["rt", "rt-multi-thread", "time", "macros", "sync"] }'
def build(name, code, release=False):
    d = proj(name, {'src/main.rs': code}, deps=DEPS); rc, o = cargo(['build'] + (['--release'] if release else []) + ['--quiet'], d, timeout=900); return rc, o
def runb(name, release=False, timeout=60):
    try: rc, so, se, _ = run(TG / ('release' if release else 'debug') / name, timeout=timeout)
    except subprocess.TimeoutExpired: return None
    return so.rstrip()
print('== 一:std::sync::MutexGuard 跨 await 持有:tokio::spawn 要求 Future 是 Send,编译器拒绝')
rc, o = build('u103a', '''
    use std::sync::Mutex; use std::sync::Arc;
    #[tokio::main]
    async fn main() {
        let m = Arc::new(Mutex::new(0));
        tokio::spawn(async move { let mut g = m.lock().unwrap(); *g += 1; tokio::time::sleep(std::time::Duration::from_millis(1)).await; }).await.unwrap();
    }
''')
L = [l for l in o.splitlines() if l.strip()][:14]; print('\n'.join('  ' + l for l in L)); R['e_send'] = L
print()
print('== 二:换成 tokio::sync::Mutex 就可以跨 await 持有;它的 lock() 是 async 的')
rc, o = build('u103b', '''
    use std::sync::Arc; use tokio::sync::Mutex;
    #[tokio::main(flavor = "multi_thread", worker_threads = 2)]
    async fn main() {
        let m = Arc::new(Mutex::new(0u32));
        let hs: Vec<_> = (0..4).map(|i| { let m = m.clone(); tokio::spawn(async move { let mut g = m.lock().await; let before = *g; tokio::time::sleep(std::time::Duration::from_millis(20)).await; *g = before + 1; i }) }).collect();
        for h in hs { h.await.unwrap(); }
        println!("4 个任务各自 持锁 → sleep 20 ms(跨 await)→ +1,最终值 {}(没有丢更新)", *m.lock().await);
    }
''')
print('  编译退出码', rc); out = runb('u103b'); print('  ' + out); R['tokio_mutex'] = out
print()
print('== 三:std Mutex 的 guard 如果不跨 await(用块限制作用域)是完全可以的,而且是推荐写法')
rc, o = build('u103c', '''
    use std::sync::{Arc, Mutex};
    #[tokio::main(flavor = "multi_thread", worker_threads = 2)]
    async fn main() {
        let m = Arc::new(Mutex::new(Vec::new()));
        let hs: Vec<_> = (0..4).map(|i| { let m = m.clone(); tokio::spawn(async move {
            tokio::time::sleep(std::time::Duration::from_millis(10 * (4 - i))).await;
            { m.lock().unwrap().push(i); }            // guard 在块结束时释放,没有跨 await
            tokio::time::sleep(std::time::Duration::from_millis(1)).await;
        }) }).collect();
        for h in hs { h.await.unwrap(); }
        println!("std Mutex 只在块内持有,任务可以 spawn:{:?}", m.lock().unwrap());
    }
''')
print('  编译退出码', rc); out = runb('u103c'); print('  ' + out); R['std_ok'] = out
print()
print('== 四:单线程运行时里,std Mutex 跨 await 持有会死锁:任务 A 持锁 await 让出线程,任务 B 在同一线程上 lock() 阻塞,A 永远没有机会运行')
rc, o = build('u103d', '''
    use std::sync::{Arc, Mutex}; use std::time::Duration;
    struct SendFut<F>(F); unsafe impl<F> Send for SendFut<F> {}
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let m = Arc::new(Mutex::new(0));
        let local = tokio::task::LocalSet::new();
        let (m1, m2) = (m.clone(), m.clone());
        local.spawn_local(async move { let _g = m1.lock().unwrap(); println!("  A 拿到锁,然后 await sleep(50 ms)"); tokio::time::sleep(Duration::from_millis(50)).await; println!("  A 醒来,释放锁"); });
        local.spawn_local(async move { tokio::time::sleep(Duration::from_millis(10)).await; println!("  B 尝试 lock()(同一线程,会阻塞)"); let _g = m2.lock().unwrap(); println!("  B 拿到锁"); });
        let r = tokio::time::timeout(Duration::from_millis(500), local).await;
        println!("  结果:{:?}", r.map(|_| "完成"));
    }
''')
print('  编译退出码', rc, [l for l in o.splitlines() if 'error' in l][:2])
out = runb('u103d', timeout=6)
if out is None: print('  6 秒内程序没有退出:B 阻塞了唯一的线程,连 500 ms 的 timeout 也没有机会触发 → 死锁'); R['deadlock'] = 'timeout6s'
else: print('  ' + out.replace('\n', '\n  ')); R['deadlock'] = out
print()
print('== 五:没有 await 的短临界区,std Mutex 与 tokio Mutex 的开销(4 个任务各锁 100 万次 +1,multi_thread 4 线程,release)')
rc, o = build('u103e', '''
    use std::{sync::Arc, time::Instant};
    #[tokio::main(flavor = "multi_thread", worker_threads = 4)]
    async fn main() {
        let n = 1_000_000u64;
        let sm = Arc::new(std::sync::Mutex::new(0u64)); let tm = Arc::new(tokio::sync::Mutex::new(0u64));
        let mut best = (f64::MAX, f64::MAX);
        for _ in 0..3 {
            let t = Instant::now(); let hs: Vec<_> = (0..4).map(|_| { let m = sm.clone(); tokio::spawn(async move { for _ in 0..n { *m.lock().unwrap() += 1; } }) }).collect(); for h in hs { h.await.unwrap(); } best.0 = best.0.min(t.elapsed().as_secs_f64() * 1e3);
            let t = Instant::now(); let hs: Vec<_> = (0..4).map(|_| { let m = tm.clone(); tokio::spawn(async move { for _ in 0..n { *m.lock().await += 1; } }) }).collect(); for h in hs { h.await.unwrap(); } best.1 = best.1.min(t.elapsed().as_secs_f64() * 1e3);
        }
        println!("std::sync::Mutex   4 任务 × 100 万次:{:>8.1} ms", best.0);
        println!("tokio::sync::Mutex 4 任务 × 100 万次:{:>8.1} ms", best.1);
    }
''', release=True)
print('  编译退出码', rc); out = runb('u103e', release=True); print('  ' + out.replace('\n', '\n  ')); R['bench'] = out
save('u103', R)
