import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u108'); R = {}
LIB = '''
    #![allow(unused)]
    use std::{future::Future, pin::Pin, task::{Context, Poll, Waker, Wake}, sync::{Arc, Mutex, Condvar, atomic::{AtomicUsize, Ordering::SeqCst}}, thread, time::{Duration, Instant}};
    static POLLS: AtomicUsize = AtomicUsize::new(0);
    struct Notify(Mutex<bool>, Condvar);
    impl Wake for Notify { fn wake(self: Arc<Self>) { *self.0.lock().unwrap() = true; self.1.notify_one(); } }
    fn block_on<F: Future>(f: F) -> F::Output {
        let n = Arc::new(Notify(Mutex::new(false), Condvar::new())); let waker = Waker::from(n.clone()); let mut cx = Context::from_waker(&waker);
        let mut f = Box::pin(f);
        loop { POLLS.fetch_add(1, SeqCst); if let Poll::Ready(v) = f.as_mut().poll(&mut cx) { return v; } let mut g = n.0.lock().unwrap(); while !*g { g = n.1.wait(g).unwrap(); } *g = false; }
    }
    // ---- 自己写的定时器 Future:共享状态里存 done 标志与 waker,后台线程到点置位并唤醒 ----
    struct Shared { done: bool, waker: Option<Waker> }
    struct Timer { shared: Arc<Mutex<Shared>> }
    impl Timer {
        fn new(d: Duration) -> Timer {
            let shared = Arc::new(Mutex::new(Shared { done: false, waker: None })); let s2 = shared.clone();
            thread::spawn(move || { thread::sleep(d); let mut g = s2.lock().unwrap(); g.done = true; if let Some(w) = g.waker.take() { w.wake(); } });
            Timer { shared }
        }
    }
    impl Future for Timer {
        type Output = ();
        fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
            let mut g = self.shared.lock().unwrap();
            if g.done { Poll::Ready(()) } else { g.waker = Some(cx.waker().clone()); Poll::Pending }   // 每次 poll 都更新 waker(任务可能换了 waker)
        }
    }
    // ---- 自己写的 join:同时推进两个 Future,都完成才完成 ----
    struct Join2<A: Future, B: Future> { a: Pin<Box<A>>, b: Pin<Box<B>>, ra: Option<A::Output>, rb: Option<B::Output> }
    fn join2<A: Future, B: Future>(a: A, b: B) -> Join2<A, B> { Join2 { a: Box::pin(a), b: Box::pin(b), ra: None, rb: None } }
    impl<A: Future, B: Future> Future for Join2<A, B> where A::Output: Unpin, B::Output: Unpin {
        type Output = (A::Output, B::Output);
        fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
            let this = &mut *self;
            if this.ra.is_none() { if let Poll::Ready(v) = this.a.as_mut().poll(cx) { this.ra = Some(v); } }
            if this.rb.is_none() { if let Poll::Ready(v) = this.b.as_mut().poll(cx) { this.rb = Some(v); } }
            if this.ra.is_some() && this.rb.is_some() { Poll::Ready((this.ra.take().unwrap(), this.rb.take().unwrap())) } else { Poll::Pending }
        }
    }
'''
print('== 一:自己写的 Timer Future(共享状态 + 保存 waker + 后台线程唤醒):await 100 ms,统计 poll 次数')
r = tryit('u108a', LIB + '''
    fn main() {
        let t = Instant::now();
        block_on(async { Timer::new(Duration::from_millis(100)).await; });
        println!("等 100 ms 的 Timer:实际 {} ms,executor 总共 poll 了 {} 次(第一次 Pending,被 wake 后第二次 Ready)", t.elapsed().as_millis() / 10 * 10, POLLS.load(SeqCst));
    }
''', quiet_src=True); R['timer'] = r['out']
print()
print('== 二:顺序 await 两个定时器 vs 自己写的 join2:总耗时与 poll 次数')
r = tryit('u108b', LIB + '''
    fn main() {
        let t = Instant::now(); POLLS.store(0, SeqCst);
        block_on(async { Timer::new(Duration::from_millis(100)).await; Timer::new(Duration::from_millis(100)).await; });
        println!("顺序 await 两个 100 ms:总耗时约 {} ms,poll {} 次", t.elapsed().as_millis() / 10 * 10, POLLS.load(SeqCst));
        let t = Instant::now(); POLLS.store(0, SeqCst);
        let (a, b) = block_on(join2(async { Timer::new(Duration::from_millis(100)).await; "A" }, async { Timer::new(Duration::from_millis(100)).await; "B" }));
        println!("join2 同时等两个 100 ms:总耗时约 {} ms,poll {} 次,结果 ({}, {})", t.elapsed().as_millis() / 10 * 10, POLLS.load(SeqCst), a, b);
        let t = Instant::now(); POLLS.store(0, SeqCst);
        block_on(join2(Timer::new(Duration::from_millis(150)), Timer::new(Duration::from_millis(50))));
        println!("join2 的 150 ms 与 50 ms:总耗时约 {} ms(取最长的),poll {} 次(50 ms 的先完成、150 ms 的后完成)", t.elapsed().as_millis() / 10 * 10, POLLS.load(SeqCst));
    }
''', quiet_src=True); R['join'] = r['out']
print()
print('== 三:一个常见错误:Pending 之前没有保存 waker —— 即使条件之后满足,executor 也不会再 poll(对照 Timer 的正确版本)')
r = tryit('u108c', LIB.replace("g.waker = Some(cx.waker().clone()); Poll::Pending", "Poll::Pending") + '''
    fn main() {
        // 为了不让进程卡死,在另一个线程里 block_on,主线程等 600 ms
        let (tx, rx) = std::sync::mpsc::channel();
        thread::spawn(move || { block_on(Timer::new(Duration::from_millis(100))); tx.send(()).ok(); });
        match rx.recv_timeout(Duration::from_millis(600)) { Ok(_) => println!("完成了"), Err(_) => println!("600 ms 过去了,Timer 仍然没有完成:poll 时没保存 waker,到点后 wake 的是 None,executor 永远睡着") }
        std::process::exit(0);
    }
''', quiet_src=True); R['nowaker'] = r['out']
print()
print('== 四:poll 里的 waker 会变:同一个 Future 被移到别的任务/executor 后 waker 不同,所以每次 poll 都要重新保存')
r = tryit('u108d', LIB + '''
    fn main() {
        let timer = Timer::new(Duration::from_millis(80)); let mut f = Box::pin(timer);
        let n1 = Arc::new(Notify(Mutex::new(false), Condvar::new())); let n2 = Arc::new(Notify(Mutex::new(false), Condvar::new()));
        let (w1, w2) = (Waker::from(n1.clone()), Waker::from(n2.clone()));
        let _ = f.as_mut().poll(&mut Context::from_waker(&w1));     // 第一次 poll 用 waker1
        let _ = f.as_mut().poll(&mut Context::from_waker(&w2));     // 之后「搬家」,第二次 poll 用 waker2
        thread::sleep(Duration::from_millis(150));
        println!("80 ms 到点后:waker1 被唤醒了吗? {}  waker2 被唤醒了吗? {}(Timer 每次 poll 都覆盖了保存的 waker,所以只有最新的 waker2 被通知)", *n1.0.lock().unwrap(), *n2.0.lock().unwrap());
    }
''', quiet_src=True); R['rewake'] = r['out']
save('u108', R)
