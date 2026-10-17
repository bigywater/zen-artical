import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u96'); R = {}
PRE = '''
    use std::{future::Future, pin::Pin, task::{Context, Poll, Waker}};
    fn poll_once<F: Future>(f: &mut Pin<Box<F>>) -> Poll<F::Output> { let mut cx = Context::from_waker(Waker::noop()); f.as_mut().poll(&mut cx) }
'''
print('== 一:async fn 只是创建一个 Future,什么都不会执行;poll 才推进它')
r = tryit('u96a', PRE + '''
    async fn hello() -> i32 { println!("  hello() 的函数体开始执行"); 42 }
    fn main() {
        println!("调用 hello():");
        let fut = hello();
        println!("拿到了 Future({} 字节),函数体还没有运行", std::mem::size_of_val(&fut));
        let mut fut = Box::pin(fut);
        println!("第一次 poll:");
        let r = poll_once(&mut fut);
        println!("poll 返回 {:?}", r);
    }
''', quiet_src=True); R['lazy'] = r['out']
print()
print('== 二:手写 Future:Countdown 前 3 次 poll 返回 Pending(并通知 waker 再来),第 4 次 Ready')
r = tryit('u96b', PRE + '''
    struct Countdown { left: u32, polls: u32 }
    impl Future for Countdown {
        type Output = u32;
        fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<u32> {
            self.polls += 1;
            if self.left == 0 { println!("  第 {} 次 poll → Ready", self.polls); Poll::Ready(self.polls) }
            else { println!("  第 {} 次 poll → Pending(剩 {})", self.polls, self.left); self.left -= 1; cx.waker().wake_by_ref(); Poll::Pending }
        }
    }
    fn main() {
        let mut f = Box::pin(Countdown { left: 3, polls: 0 });
        loop { if let Poll::Ready(v) = poll_once(&mut f) { println!("最终得到 {}", v); break; } }
    }
''', quiet_src=True); R['countdown'] = r['out']
print()
print('== 三:async 块里的 await 把 Pending 向上传:外层 Future 每次 poll 都会重新 poll 内层,直到内层 Ready')
r = tryit('u96c', PRE + '''
    struct Wait(u32);
    impl Future for Wait { type Output = (); fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> { if self.0 == 0 { Poll::Ready(()) } else { self.0 -= 1; cx.waker().wake_by_ref(); Poll::Pending } } }
    async fn step(name: &str, n: u32) { println!("  {} 开始", name); Wait(n).await; println!("  {} 结束", name); }
    async fn job() -> &'static str { step("A", 2).await; step("B", 1).await; "全部完成" }
    fn main() {
        let mut f = Box::pin(job()); let mut k = 0;
        loop { k += 1; println!("外层第 {} 次 poll:", k); match poll_once(&mut f) { Poll::Ready(v) => { println!("→ Ready({:?})", v); break; } Poll::Pending => println!("→ Pending") } }
    }
''', quiet_src=True); R['nested'] = r['out']
print()
print('== 四:Future 被 drop 而没被 poll:函数体永远不会运行;已经 poll 过一半的 Future 被 drop:局部变量立即析构')
r = tryit('u96d', PRE + '''
    struct Noisy(&'static str); impl Drop for Noisy { fn drop(&mut self) { println!("  Noisy({}) 被 drop", self.0); } }
    struct Wait(u32);
    impl Future for Wait { type Output = (); fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> { if self.0 == 0 { Poll::Ready(()) } else { self.0 -= 1; cx.waker().wake_by_ref(); Poll::Pending } } }
    async fn work(tag: &'static str) { println!("  work({}) 开始", tag); let _n = Noisy(tag); Wait(5).await; println!("  work({}) 结束", tag); }
    fn main() {
        println!("创建后直接 drop(没 poll):"); drop(work("never"));
        println!("poll 一次后 drop:"); let mut f = Box::pin(work("half")); let _ = poll_once(&mut f); println!("  准备 drop Future"); drop(f);
    }
''', quiet_src=True); R['drop'] = r['out']
print()
print('== 五:忘记 .await:编译器警告 unused implementor of `Future`')
r = tryit('u96e', '''
    async fn f() -> i32 { 1 }
    async fn g() { f(); }
    fn main() { let _ = g(); }
''', maxlines=24); R['warn'] = r['diag']
save('u96', R)
