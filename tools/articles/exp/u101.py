import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u101'); R = {}
DEPS = 'tokio = { version = "1", features = ["rt", "time", "macros", "sync"] }'
def go(name, code, release=False):
    d = proj(name, {'src/main.rs': code}, deps=DEPS); rc, o = cargo(['build', '--quiet'], d, timeout=900)
    if rc != 0: print('  编译失败:', o[:600]); return o
    rc, so, se, _ = run(TG / 'debug' / name); out = so.rstrip() + (('\n' + se.rstrip()) if se.strip() else ''); print('\n'.join('  ' + l for l in out.splitlines())); return out
print('== 一:select! 同时等多个 Future,第一个完成的赢,其余的被 drop(取消)')
R['basic'] = go('u101a', '''
    use std::time::Duration; use tokio::time::sleep;
    struct Noisy(&'static str); impl Drop for Noisy { fn drop(&mut self) { println!("  {} 被 drop(取消)", self.0); } }
    async fn work(name: &'static str, ms: u64) -> &'static str { let _n = Noisy(name); sleep(Duration::from_millis(ms)).await; println!("  {} 跑完了", name); name }
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let w = tokio::select! { a = work("慢任务(100ms)", 100) => a, b = work("快任务(30ms)", 30) => b };
        println!("select! 的结果:{}", w);
        sleep(Duration::from_millis(150)).await;
        println!("又过了 150 ms:慢任务既没有跑完也没有再打印,它在 select! 结束时就被取消了");
    }
''')
print()
print('== 二:取消不安全的 Future:先读一条消息再等待的操作,被 select! 取消后,已经读到的消息就丢了')
R['unsafe'] = go('u101b', '''
    use std::time::Duration; use tokio::{sync::mpsc, time::sleep};
    // 先从通道取走一条,再做一件需要时间的事,最后返回:在「做事」时被取消,取走的那条就丢失
    async fn read_then_work(rx: &mut mpsc::Receiver<u32>) -> u32 { let v = rx.recv().await.unwrap(); sleep(Duration::from_millis(100)).await; v }
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let (tx, mut rx) = mpsc::channel(8);
        for i in 1..=3 { tx.send(i).await.unwrap(); }
        tokio::select! { v = read_then_work(&mut rx) => println!("读到 {}", v), _ = sleep(Duration::from_millis(20)) => println!("20 ms 超时,read_then_work 被取消") }
        let mut rest = vec![]; while let Ok(v) = rx.try_recv() { rest.push(v); }
        println!("通道里还剩 {:?}(消息 1 已经被 read_then_work 取走,取消时丢失了)", rest);
    }
''')
print()
print('== 三:取消安全的写法:rx.recv() 本身是取消安全的(没取走消息就被取消不会丢);把「取走」和「处理」分开')
R['safe'] = go('u101c', '''
    use std::time::Duration; use tokio::{sync::mpsc, time::sleep};
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let (tx, mut rx) = mpsc::channel(8);
        for i in 1..=3 { tx.send(i).await.unwrap(); }
        let mut handled = vec![];
        loop {
            tokio::select! {
                Some(v) = rx.recv() => { sleep(Duration::from_millis(10)).await; handled.push(v); }   // 取走后在分支体里处理:分支体不会被取消
                _ = sleep(Duration::from_millis(100)) => { println!("100 ms 没有新消息,退出循环"); break; }
            }
        }
        println!("处理了 {:?},一条都没丢", handled);
    }
''')
print()
print('== 四:公平性:两个分支同时就绪时,select! 默认随机选择;加 biased; 则总是选第一个')
R['fair'] = go('u101d', '''
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let n = 10_000; let (mut a, mut b, mut c, mut d) = (0, 0, 0, 0);
        for _ in 0..n { tokio::select! { _ = async {} => a += 1, _ = async {} => b += 1 } }
        for _ in 0..n { tokio::select! { biased; _ = async {} => c += 1, _ = async {} => d += 1 } }
        println!("默认(随机):分支1 {} 次,分支2 {} 次(共 {})", a, b, n);
        println!("biased;     :分支1 {} 次,分支2 {} 次", c, d);
    }
''')
print()
print('== 五:timeout:超时之后内部的 Future 被 drop,里面的局部变量一并析构')
R['timeout'] = go('u101e', '''
    use std::time::Duration; use tokio::time::{sleep, timeout};
    struct Noisy; impl Drop for Noisy { fn drop(&mut self) { println!("  内部 Future 的局部变量被 drop(超时取消了它)"); } }
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let r = timeout(Duration::from_millis(30), async { let _n = Noisy; sleep(Duration::from_millis(200)).await; "完成" }).await;
        println!("timeout 返回 {:?}", r.map_err(|e| e.to_string()));
        let r = timeout(Duration::from_millis(200), async { sleep(Duration::from_millis(10)).await; "完成" }).await;
        println!("未超时的 timeout 返回 {:?}", r.map_err(|e| e.to_string()));
    }
''')
save('u101', R)
