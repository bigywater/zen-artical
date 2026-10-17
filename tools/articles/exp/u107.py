import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u107'); R = {}
CNT = '''
    #![allow(unused)]
    use std::{future::Future, pin::Pin, task::{Context, Poll, RawWaker, RawWakerVTable, Waker}, sync::atomic::{AtomicUsize, Ordering::SeqCst}, mem::size_of};
    static CLONE: AtomicUsize = AtomicUsize::new(0); static WAKE: AtomicUsize = AtomicUsize::new(0); static WAKE_REF: AtomicUsize = AtomicUsize::new(0); static DROP: AtomicUsize = AtomicUsize::new(0);
    unsafe fn v_clone(p: *const ()) -> RawWaker { CLONE.fetch_add(1, SeqCst); RawWaker::new(p, &VTABLE) }
    unsafe fn v_wake(_: *const ()) { WAKE.fetch_add(1, SeqCst); }
    unsafe fn v_wake_ref(_: *const ()) { WAKE_REF.fetch_add(1, SeqCst); }
    unsafe fn v_drop(_: *const ()) { DROP.fetch_add(1, SeqCst); }
    static VTABLE: RawWakerVTable = RawWakerVTable::new(v_clone, v_wake, v_wake_ref, v_drop);
    fn counting_waker() -> Waker { unsafe { Waker::from_raw(RawWaker::new(std::ptr::null(), &VTABLE)) } }
    fn counts() -> String { format!("clone {} / wake {} / wake_by_ref {} / drop {}", CLONE.load(SeqCst), WAKE.load(SeqCst), WAKE_REF.load(SeqCst), DROP.load(SeqCst)) }
    fn reset() { for c in [&CLONE, &WAKE, &WAKE_REF, &DROP] { c.store(0, SeqCst); } }
'''
print('== 一:Waker 就是「数据指针 + 一张 4 个函数的表」(clone / wake / wake_by_ref / drop):用计数的 vtable 观察每个操作调用了哪个函数')
r = tryit('u107a', CNT + '''
    fn main() {
        println!("size_of::<Waker>() = {} 字节(两个指针:数据指针 + vtable 指针)", size_of::<Waker>());
        let w = counting_waker(); println!("创建后:       {}", counts());
        let w2 = w.clone(); println!("w.clone():     {}", counts());
        w2.wake_by_ref(); println!("w2.wake_by_ref(): {}(不消耗 w2)", counts());
        w2.wake(); println!("w2.wake():     {}(wake 消耗 w2,所以没有 drop 调用:由 wake 的实现负责释放)", counts());
        drop(w); println!("drop(w):       {}", counts());
    }
''', quiet_src=True); R['vtable'] = r['out']
print()
print('== 二:一次 poll 里通过 Context 拿到的 waker 是借来的引用(&Waker);想在以后唤醒就得 clone 一份保存')
r = tryit('u107b', CNT + '''
    struct Saver { saved: Option<Waker>, polls: u32 }
    impl Future for Saver {
        type Output = u32;
        fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<u32> {
            self.polls += 1;
            if self.polls < 3 { self.saved = Some(cx.waker().clone()); println!("  poll #{}:Pending,保存了 waker({})", self.polls, counts()); Poll::Pending } else { println!("  poll #{}:Ready", self.polls); Poll::Ready(self.polls) }
        }
    }
    fn main() {
        let w = counting_waker(); let mut cx = Context::from_waker(&w);
        let mut f = Box::pin(Saver { saved: None, polls: 0 });
        while let Poll::Pending = f.as_mut().poll(&mut cx) { f.saved.take().unwrap().wake(); println!("  (外部事件调用 saved.wake())"); }
        println!("结束:{}", counts());
    }
''', quiet_src=True); R['clone'] = r['out']
print()
print('== 三:will_wake:两个 waker 是否会唤醒同一个任务;同一任务重复 poll 时,Future 应该只在 waker 变了的时候才更新保存的 waker')
r = tryit('u107c', CNT + '''
    fn main() {
        let a = counting_waker(); let b = a.clone(); let c = counting_waker();
        println!("a.will_wake(&b)(b 是 a 的克隆): {}", a.will_wake(&b));
        println!("a.will_wake(&c)(同一个数据指针 + 同一张 vtable,另一个实例): {}", a.will_wake(&c));
        println!("Waker::noop().will_wake(&Waker::noop()): {}", Waker::noop().will_wake(Waker::noop()));
        println!("a.will_wake(Waker::noop()): {}", a.will_wake(Waker::noop()));
    }
''', quiet_src=True); R['will'] = r['out']
print()
print('== 四:忘记注册 waker:poll 返回 Pending 却没有任何人会唤醒它 —— 任务永远不会被再次 poll(用一个「到点才就绪」的 Future + 执行器模拟,并设超时)')
r = tryit('u107d', '''
    use std::{future::Future, pin::Pin, task::{Context, Poll, Waker}, sync::{Arc, Mutex, Condvar}, thread, time::{Duration, Instant}};
    struct Flag { ready: Arc<Mutex<bool>>, register: bool }
    impl Future for Flag {
        type Output = &'static str;
        fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<&'static str> {
            if *self.ready.lock().unwrap() { return Poll::Ready("就绪"); }
            if self.register { let w = cx.waker().clone(); let r = self.ready.clone(); thread::spawn(move || { thread::sleep(Duration::from_millis(50)); *r.lock().unwrap() = true; w.wake(); }); }
            else { let r = self.ready.clone(); thread::spawn(move || { thread::sleep(Duration::from_millis(50)); *r.lock().unwrap() = true; /* 忘了 wake */ }); }
            Poll::Pending
        }
    }
    struct Notify(Mutex<bool>, Condvar);
    impl std::task::Wake for Notify { fn wake(self: Arc<Self>) { *self.0.lock().unwrap() = true; self.1.notify_one(); } }
    fn block_on_timeout<F: Future>(f: F, limit: Duration) -> Option<(F::Output, u32)> {
        let n = Arc::new(Notify(Mutex::new(false), Condvar::new())); let waker = Waker::from(n.clone()); let mut cx = Context::from_waker(&waker);
        let mut f = Box::pin(f); let t = Instant::now(); let mut polls = 0;
        loop {
            polls += 1; if let Poll::Ready(v) = f.as_mut().poll(&mut cx) { return Some((v, polls)); }
            let mut g = n.0.lock().unwrap(); while !*g { let left = limit.checked_sub(t.elapsed())?; let (ng, to) = n.1.wait_timeout(g, left).unwrap(); g = ng; if to.timed_out() { return None; } } *g = false;
        }
    }
    fn main() {
        let ok = block_on_timeout(Flag { ready: Arc::new(Mutex::new(false)), register: true }, Duration::from_millis(500));
        println!("注册并调用了 waker:{:?}", ok);
        let bad = block_on_timeout(Flag { ready: Arc::new(Mutex::new(false)), register: false }, Duration::from_millis(500));
        println!("条件满足了但没调用 waker:{:?}(500 ms 后放弃:任务永远睡下去)", bad);
    }
''', quiet_src=True); R['lost'] = r['out']
save('u107', R)
