import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u98'); R = {}
PRE = '''
    #![allow(unused)]
    use std::{future::Future, pin::Pin, task::{Context, Poll, Waker}, mem::size_of_val};
    struct YieldNow(bool);
    impl Future for YieldNow { type Output = (); fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> { if self.0 { Poll::Ready(()) } else { self.0 = true; cx.waker().wake_by_ref(); Poll::Pending } } }
    fn yield_now() -> YieldNow { YieldNow(false) }
'''
print('== 一:async fn 的 Future 就是一个状态机:大小取决于哪些局部变量要跨过 await 保存(看作用域,而不只是最后一次使用)')
r = tryit('u98a', PRE + '''
    async fn nothing() {}
    async fn no_live() { let buf = [0u8; 1000]; println!("{}", buf[0]); yield_now().await; }               // buf 在 await 之前就不再使用,但仍在作用域内
    async fn scoped() { { let buf = [0u8; 1000]; println!("{}", buf[0]); } yield_now().await; }            // buf 在内层块里,await 之前作用域已结束
    async fn live_across() { let buf = [0u8; 1000]; yield_now().await; println!("{}", buf[0]); }           // buf 跨 await 存活
    async fn two_live() { let a = [0u8; 1000]; let b = [0u8; 2000]; yield_now().await; println!("{} {}", a[0], b[0]); }
    async fn two_awaits() { yield_now().await; let a = [0u8; 1000]; yield_now().await; println!("{}", a[0]); }
    fn main() {
        println!("async fn nothing()     的 Future 大小: {:>5} 字节", size_of_val(&nothing()));
        println!("buf 在 await 前用完(仍在作用域内):      {:>5} 字节", size_of_val(&no_live()));
        println!("buf 放进内层 {{ }} 块,await 前作用域结束:  {:>5} 字节", size_of_val(&scoped()));
        println!("buf[1000] 跨 await 存活:                 {:>5} 字节", size_of_val(&live_across()));
        println!("a[1000] + b[2000] 跨 await 存活:         {:>5} 字节", size_of_val(&two_live()));
        println!("两个 await,只有一个 1000 字节数组跨第二个 await:{:>5} 字节", size_of_val(&two_awaits()));
        println!("YieldNow 自己:                           {:>5} 字节", size_of_val(&yield_now()));
    }
''', quiet_src=True); R['size'] = r['out']
print()
print('== 二:状态保存:局部变量在 Pending 之后仍然在,下次 poll 从上次停下的地方继续(用计数的 poll 看到每个 await 点只执行一次)')
r = tryit('u98b', PRE + '''
    async fn f() -> u32 {
        let mut sum = 0; println!("  [状态0] 开始");
        for i in 1..=3 { yield_now().await; sum += i; println!("  [await 之后] i = {} sum = {}", i, sum); }
        sum
    }
    fn main() {
        let mut fut = Box::pin(f()); let mut cx = Context::from_waker(Waker::noop()); let mut n = 0;
        loop { n += 1; println!("第 {} 次 poll:", n); if let Poll::Ready(v) = fut.as_mut().poll(&mut cx) { println!("Ready({}),共 poll {} 次", v, n); break; } }
    }
''', quiet_src=True); R['resume'] = r['out']
print()
print('== 三:poll 已经完成的 Future:再 poll 会 panic(async fn 的状态机只能走一遍)')
r = tryit('u98c', PRE + '''
    async fn f() -> i32 { 1 }
    fn main() {
        let mut fut = Box::pin(f()); let mut cx = Context::from_waker(Waker::noop());
        println!("第一次 poll: {:?}", fut.as_mut().poll(&mut cx));
        println!("第二次 poll(已完成):");
        let _ = fut.as_mut().poll(&mut cx);
    }
''', quiet_src=True); R['repoll'] = {'rc': r['rc'], 'err': [l for l in r['err'].splitlines() if l.strip() and 'note: run with' not in l][:3], 'out': r['out']}
print()
print('== 四:async fn 不能直接递归(状态机会无限大):E0733;用 Box::pin 打断')
r = tryit('u98d', '''
    async fn fib(n: u32) -> u32 { if n < 2 { n } else { fib(n - 1).await + fib(n - 2).await } }
    fn main() { let _ = fib(5); }
''', maxlines=30); R['e0733'] = r['diag']
r = tryit('u98e', PRE + '''
    fn fib(n: u32) -> Pin<Box<dyn Future<Output = u32>>> { Box::pin(async move { if n < 2 { n } else { fib(n - 1).await + fib(n - 2).await } }) }
    fn main() { let mut f = fib(10); let mut cx = Context::from_waker(Waker::noop()); println!("{:?}", f.as_mut().poll(&mut cx)); }
''', quiet_src=True); R['boxed'] = r['out']
print()
print('== 五:跨 await 持有引用的 Future 是自引用的,所以不能随便移动:要先 Pin(!Unpin)')
r = tryit('u98f', PRE + '''
    fn is_unpin<T: Unpin>(_: &T) {}
    async fn borrows() { let local = [1u8, 2, 3]; let r = &local; yield_now().await; println!("{}", r[0]); }
    fn main() { let f = borrows(); is_unpin(&f); is_unpin(&yield_now()); }
''', maxlines=30); R['unpin'] = r['diag']
save('u98', R)
