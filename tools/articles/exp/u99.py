import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u99'); R = {}
DEPS = 'tokio = { version = "1", features = ["rt", "rt-multi-thread", "time", "macros", "sync"] }'
def build_run(name, code, args=(), release=True):
    d = proj(name, {'src/main.rs': code}, deps=DEPS)
    rc, o = cargo(['build'] + (['--release'] if release else []) + ['--quiet'], d, timeout=900)
    if rc != 0: return o
    rc, so, se, _ = run(TG / ('release' if release else 'debug') / name, *args); return so.rstrip() + (('\n' + se.rstrip()) if se.strip() else '')
print('== 一:多线程运行时:1000 个任务分布在哪些工作线程上(每个任务做一点 CPU 工作后 yield)')
o = build_run('u99a', '''
    use std::{collections::BTreeMap, sync::{Arc, Mutex}};
    #[tokio::main(flavor = "multi_thread", worker_threads = 4)]
    async fn main() {
        let seen = Arc::new(Mutex::new(BTreeMap::<String, u32>::new()));
        let hs: Vec<_> = (0..1000).map(|_| { let seen = seen.clone(); tokio::spawn(async move {
            for _ in 0..5 { let mut x = 0u64; for i in 0..20_000 { x = x.wrapping_add(i * i); } std::hint::black_box(x); tokio::task::yield_now().await; }
            *seen.lock().unwrap().entry(format!("{:?}", std::thread::current().id())).or_insert(0) += 1;
        }) }).collect();
        for h in hs { h.await.unwrap(); }
        for (k, v) in seen.lock().unwrap().iter() { println!("  线程 {:<12} 完成了 {} 个任务", k, v); }
        println!("共 {} 个工作线程参与", seen.lock().unwrap().len());
    }
''')
print('\n'.join('  ' + l for l in o.splitlines())); R['dist'] = o
print()
print('== 二:同一个任务反复 await 之后可能被不同线程接着执行(窃取/迁移):记录 20 个 yield 点上线程是否变化')
o = build_run('u99b', '''
    #[tokio::main(flavor = "multi_thread", worker_threads = 4)]
    async fn main() {
        let hs: Vec<_> = (0..16).map(|k| tokio::spawn(async move {
            let mut ids = vec![]; for _ in 0..20 { ids.push(format!("{:?}", std::thread::current().id())); let mut x = 0u64; for i in 0..50_000 { x = x.wrapping_add(i); } std::hint::black_box(x); tokio::task::yield_now().await; }
            let mut u = ids.clone(); u.sort(); u.dedup(); (k, u.len())
        })).collect();
        let mut moved = 0; for h in hs { let (_, n) = h.await.unwrap(); if n > 1 { moved += 1; } }
        println!("16 个任务里有 {} 个在运行过程中换过工作线程(同一个任务的多次 poll 不一定在同一线程)", moved);
    }
''')
print('  ' + o.replace('\n', '\n  ')); R['migrate'] = o
print()
print('== 三:current_thread 运行时:任务里有长时间不 await 的计算,会让其它任务无法被调度')
o = build_run('u99c', '''
    use std::time::{Duration, Instant};
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let t0 = Instant::now();
        let ticker = tokio::spawn(async move { for i in 0..5 { tokio::time::sleep(Duration::from_millis(20)).await; println!("  [{:>3} ms] ticker 第 {} 次(期望每 20 ms 一次)", t0.elapsed().as_millis() / 10 * 10, i + 1); } });
        tokio::time::sleep(Duration::from_millis(5)).await;
        println!("  [{:>3} ms] 开始 150 ms 的纯 CPU 计算(没有 await)", t0.elapsed().as_millis() / 10 * 10);
        let t = Instant::now(); let mut x = 0u64; while t.elapsed() < Duration::from_millis(150) { x = x.wrapping_add(1); } std::hint::black_box(x);
        println!("  [{:>3} ms] 计算结束", t0.elapsed().as_millis() / 10 * 10);
        ticker.await.unwrap();
    }
''')
print(o); R['starve'] = o
print()
print('== 四:同样的任务放到多线程运行时(2 个工作线程),ticker 不受影响')
o = build_run('u99d', '''
    use std::time::{Duration, Instant};
    #[tokio::main(flavor = "multi_thread", worker_threads = 2)]
    async fn main() {
        let t0 = Instant::now();
        let ticker = tokio::spawn(async move { for i in 0..5 { tokio::time::sleep(Duration::from_millis(20)).await; println!("  [{:>3} ms] ticker 第 {} 次", t0.elapsed().as_millis() / 10 * 10, i + 1); } });
        tokio::time::sleep(Duration::from_millis(5)).await;
        println!("  [{:>3} ms] 开始 150 ms 的纯 CPU 计算(没有 await)", t0.elapsed().as_millis() / 10 * 10);
        let t = Instant::now(); let mut x = 0u64; while t.elapsed() < Duration::from_millis(150) { x = x.wrapping_add(1); } std::hint::black_box(x);
        println!("  [{:>3} ms] 计算结束", t0.elapsed().as_millis() / 10 * 10);
        ticker.await.unwrap();
    }
''')
print(o); R['multi'] = o
print()
print('== 五:spawn_blocking:把阻塞/CPU 密集的工作放到专门的线程池,不占用工作线程')
o = build_run('u99e', '''
    use std::time::{Duration, Instant};
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let t0 = Instant::now();
        let ticker = tokio::spawn(async move { for i in 0..5 { tokio::time::sleep(Duration::from_millis(20)).await; println!("  [{:>3} ms] ticker 第 {} 次", t0.elapsed().as_millis() / 10 * 10, i + 1); } });
        let h = tokio::task::spawn_blocking(|| { std::thread::sleep(Duration::from_millis(150)); format!("{:?}", std::thread::current().id()) });
        let name = h.await.unwrap();
        println!("  [{:>3} ms] 阻塞任务在线程 {} 上完成(不是运行时线程 {:?}),ticker 全程正常", t0.elapsed().as_millis() / 10 * 10, name, std::thread::current().id());
        ticker.await.unwrap();
    }
''')
print(o); R['blocking'] = o
save('u99', R)
