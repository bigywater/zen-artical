import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u97'); R = {}
EXEC = '''
    #![allow(unused)]
    use std::{future::Future, pin::Pin, sync::{Arc, Mutex, mpsc::{self, Sender, Receiver}}, task::{Context, Poll, Wake, Waker}, thread, time::{Duration, Instant}, collections::BinaryHeap, cmp::Reverse, sync::atomic::{AtomicUsize, Ordering::SeqCst}};
    static POLLS: AtomicUsize = AtomicUsize::new(0);
    // ---- 一个最小的单线程执行器:任务队列 + waker = 把任务重新放回队列 ----
    struct Task { fut: Mutex<Option<Pin<Box<dyn Future<Output = ()> + Send>>>>, tx: Sender<Arc<Task>>, id: usize }
    impl Wake for Task { fn wake(self: Arc<Self>) { let t = self.clone(); self.tx.send(t).unwrap(); } }
    struct Executor { rx: Receiver<Arc<Task>>, tx: Sender<Arc<Task>>, next: usize }
    impl Executor {
        fn new() -> Self { let (tx, rx) = mpsc::channel(); Executor { rx, tx, next: 0 } }
        fn spawn(&mut self, f: impl Future<Output = ()> + Send + 'static) { let id = self.next; self.next += 1; let t = Arc::new(Task { fut: Mutex::new(Some(Box::pin(f))), tx: self.tx.clone(), id }); self.tx.send(t).unwrap(); }
        fn run(self) {
            drop(self.tx);   // 只剩任务自己持有的 tx;全部任务结束后 rx 关闭
            while let Ok(task) = self.rx.recv() {
                let mut slot = task.fut.lock().unwrap();
                if let Some(mut f) = slot.take() {
                    let waker = Waker::from(task.clone()); let mut cx = Context::from_waker(&waker);
                    POLLS.fetch_add(1, SeqCst);
                    if f.as_mut().poll(&mut cx).is_pending() { *slot = Some(f); }
                }
            }
        }
    }
    // ---- 一个用后台线程实现的定时器:到点调用 waker ----
    struct Sleep { deadline: Instant, started: bool }
    fn sleep(ms: u64) -> Sleep { Sleep { deadline: Instant::now() + Duration::from_millis(ms), started: false } }
    impl Future for Sleep {
        type Output = ();
        fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
            if Instant::now() >= self.deadline { return Poll::Ready(()); }
            if !self.started { self.started = true; let (w, d) = (cx.waker().clone(), self.deadline); thread::spawn(move || { let now = Instant::now(); if d > now { thread::sleep(d - now); } w.wake(); }); }
            Poll::Pending
        }
    }
'''
print('== 一:一个 60 行的执行器:3 个任务各自 sleep 不同时间并打印;全部在同一个线程上交错运行')
r = tryit('u97a', EXEC + '''
    fn main() {
        let main_thread = thread::current().id();
        let t0 = Instant::now(); let mut ex = Executor::new();
        for (name, ms) in [("A", 150u64), ("B", 50), ("C", 100)] {
            ex.spawn(async move {
                println!("[{:>3} ms] 任务 {} 开始(同一线程: {})", t0.elapsed().as_millis() / 10 * 10, name, thread::current().id() == main_thread);
                sleep(ms).await;
                println!("[{:>3} ms] 任务 {} 睡了 {} ms,醒来结束", t0.elapsed().as_millis() / 10 * 10, name, ms);
            });
        }
        ex.run();
        println!("总耗时约 {} ms(最长的任务 150 ms,而不是 150 + 50 + 100 = 300 ms);executor 一共 poll 了 {} 次", t0.elapsed().as_millis() / 10 * 10, POLLS.load(SeqCst));
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:唤醒的路径:Pending → 定时线程调用 wake() → 任务被重新放进队列 → executor 再 poll;用日志标出每一步')
r = tryit('u97b', EXEC + '''
    struct Logged(&'static str);
    impl Future for Logged { type Output = (); fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> { println!("  poll {} → Pending,注册 waker(来自 {:?})", self.0, thread::current().name().unwrap_or("主线程")); let w = cx.waker().clone(); thread::Builder::new().name("定时器线程".into()).spawn(move || { thread::sleep(Duration::from_millis(30)); println!("  定时器线程 wake()"); w.wake(); }).unwrap(); Poll::Pending } }
    fn main() {
        let mut ex = Executor::new();
        ex.spawn(async { println!("  任务开始"); let mut once = Some(Logged("x")); std::future::poll_fn(move |cx| { match once.take() { Some(mut l) => { let _ = Pin::new(&mut l).poll(cx); Poll::Pending } None => Poll::Ready(()) } }).await; println!("  任务被再次 poll,继续执行并结束"); });
        ex.run(); println!("executor 退出,共 poll {} 次", POLLS.load(SeqCst));
    }
''', quiet_src=True); R['wake'] = r['out']
print()
print('== 三:任务里的阻塞调用会卡住整个单线程执行器:同样 3 个任务,其中一个用 thread::sleep(阻塞)代替 sleep().await')
r = tryit('u97c', EXEC + '''
    fn main() {
        let t0 = Instant::now(); let mut ex = Executor::new();
        ex.spawn(async move { println!("[{:>3} ms] 阻塞任务开始 thread::sleep(200)", t0.elapsed().as_millis() / 10 * 10); thread::sleep(Duration::from_millis(200)); println!("[{:>3} ms] 阻塞任务结束", t0.elapsed().as_millis() / 10 * 10); });
        ex.spawn(async move { println!("[{:>3} ms] 异步任务开始 sleep(20).await(期望 20 ms 后醒来)", t0.elapsed().as_millis() / 10 * 10); sleep(20).await; println!("[{:>3} ms] 异步任务醒来", t0.elapsed().as_millis() / 10 * 10); });
        ex.run();
    }
''', quiet_src=True); R['block'] = r['out']
print()
print('== 四:对照:同样的 3 个 async 任务,用标准库 + 手写 executor 与 tokio(单线程 current_thread)各跑一遍,总耗时与 poll 次数')
d = proj('u97d', {'src/main.rs': '''
    use std::time::{Duration, Instant};
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let t0 = Instant::now();
        let hs: Vec<_> = [150u64, 50, 100].into_iter().map(|ms| tokio::spawn(async move { tokio::time::sleep(Duration::from_millis(ms)).await; ms })).collect();
        let mut done = vec![]; for h in hs { done.push(h.await.unwrap()); }
        println!("tokio current_thread:{:?} 总耗时约 {} ms", done, t0.elapsed().as_millis() / 10 * 10);
    }
'''}, deps='tokio = { version = "1", features = ["rt", "time", "macros"] }')
rc, o = cargo(['build', '--release', '--quiet'], d, timeout=900); rc2, so, se, _ = run(TG / 'release' / 'u97d'); print('  ', so.strip() if rc == 0 else o[:500]); R['tokio'] = so.strip()
save('u97', R)
