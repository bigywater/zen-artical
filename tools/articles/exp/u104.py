import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u104'); R = {}
DEPS = 'tokio = { version = "1", features = ["rt", "rt-multi-thread", "time", "macros", "sync"] }'
def go(name, code, release=True, timeout=120):
    d = proj(name, {'src/main.rs': code}, deps=DEPS); rc, o = cargo(['build'] + (['--release'] if release else []) + ['--quiet'], d, timeout=900)
    if rc != 0: print('  编译失败:', o[:600]); return o
    rc, so, se, _ = run(TG / ('release' if release else 'debug') / name, timeout=timeout); out = so.rstrip() + (('\n' + se.rstrip()) if se.strip() else ''); print('\n'.join('  ' + l for l in out.splitlines())); return out
print('== 一:4 个工作线程的运行时:同时有 k 个任务在「阻塞」(thread::sleep 300 ms),主任务 sleep(10 ms),实际比预期晚了多久(定时器要靠工作线程驱动)')
R['k'] = go('u104a', '''
    use std::time::{Duration, Instant};
    #[tokio::main(flavor = "multi_thread", worker_threads = 4)]
    async fn main() {
        for k in [0usize, 1, 2, 3, 4, 6] {
            let blockers: Vec<_> = (0..k).map(|_| tokio::spawn(async { std::thread::sleep(Duration::from_millis(300)); })).collect();
            std::thread::sleep(Duration::from_millis(30));     // 让阻塞任务先占住线程(只阻塞主线程,它不是工作线程)
            let t = Instant::now(); tokio::time::sleep(Duration::from_millis(10)).await; let late = t.elapsed().as_secs_f64() * 1e3 - 10.0;
            for b in blockers { b.await.unwrap(); }
            println!("  {} 个阻塞任务 / 4 个工作线程:主任务 sleep(10 ms) 实际晚醒了约 {:>5.0} ms", k, late);
        }
    }
''')
print()
print('== 二:同样的阻塞工作改用 spawn_blocking:定时器不受影响(6 个阻塞任务,运行时仍然是 4 个工作线程)')
R['sb'] = go('u104b', '''
    use std::time::{Duration, Instant};
    #[tokio::main(flavor = "multi_thread", worker_threads = 4)]
    async fn main() {
        let blockers: Vec<_> = (0..6).map(|_| tokio::task::spawn_blocking(|| { std::thread::sleep(Duration::from_millis(300)); })).collect();
        std::thread::sleep(Duration::from_millis(30));
        let t = Instant::now(); tokio::time::sleep(Duration::from_millis(10)).await; let late = t.elapsed().as_secs_f64() * 1e3 - 10.0;
        for b in blockers { b.await.unwrap(); }
        println!("  6 个 spawn_blocking 任务同时在跑:主任务 sleep(10 ms) 晚醒了约 {:.0} ms", late);
    }
''')
print()
print('== 三:block_in_place:在多线程运行时里允许当前任务阻塞,其它任务不受影响;在 current_thread 里则 panic')
R['bip'] = go('u104c', '''
    use std::time::{Duration, Instant};
    #[tokio::main(flavor = "multi_thread", worker_threads = 2)]
    async fn main() {
        let blockers: Vec<_> = (0..2).map(|_| tokio::spawn(async { tokio::task::block_in_place(|| std::thread::sleep(Duration::from_millis(300))); })).collect();
        std::thread::sleep(Duration::from_millis(30));
        let t = Instant::now(); tokio::time::sleep(Duration::from_millis(10)).await; let late = t.elapsed().as_secs_f64() * 1e3 - 10.0;
        for b in blockers { b.await.unwrap(); }
        println!("  2 个 block_in_place 任务各阻塞 300 ms(运行时只配了 2 个工作线程):主任务 sleep(10 ms) 晚醒了约 {:.0} ms", late);
    }
''')
R['bip_ct'] = go('u104d', '''
    #[tokio::main(flavor = "current_thread")]
    async fn main() { tokio::task::block_in_place(|| {}); }
''', release=False)
print()
print('== 四:CPU 密集的纯计算是另一种「阻塞」:没有 await 的 200 ms 计算占住 4 个线程中的 4 个,小任务延迟')
R['cpu'] = go('u104e', '''
    use std::time::{Duration, Instant};
    #[tokio::main(flavor = "multi_thread", worker_threads = 4)]
    async fn main() {
        let hs: Vec<_> = (0..4).map(|_| tokio::spawn(async { let t = Instant::now(); let mut x = 0u64; while t.elapsed() < Duration::from_millis(200) { x = x.wrapping_add(1); } std::hint::black_box(x); })).collect();
        std::thread::sleep(Duration::from_millis(20));
        let t = Instant::now(); tokio::time::sleep(Duration::from_millis(10)).await;
        println!("  4 个 200 ms 的纯计算任务占满 4 个工作线程:主任务的 sleep(10 ms) 实际用了约 {:.0} ms", t.elapsed().as_secs_f64() * 1e3);
        for h in hs { h.await.unwrap(); }
    }
''')
save('u104', R)
