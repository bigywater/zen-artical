import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u102'); R = {}
DEPS = 'tokio = { version = "1", features = ["rt", "time", "macros", "sync"] }'
def go(name, code):
    d = proj(name, {'src/main.rs': code}, deps=DEPS); rc, o = cargo(['build', '--quiet'], d, timeout=900)
    if rc != 0: print('  编译失败:', o[:700]); return o
    rc, so, se, _ = run(TG / 'debug' / name); out = so.rstrip() + (('\n' + se.rstrip()) if se.strip() else ''); print('\n'.join('  ' + l for l in out.splitlines())); return out
print('== 一:有界 mpsc(容量 2):通道满时 send().await 会等待 —— 背压:生产者的速度被消费者拖住')
R['bounded'] = go('u102a', '''
    use std::time::{Duration, Instant}; use tokio::{sync::mpsc, time::sleep};
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let (tx, mut rx) = mpsc::channel::<u32>(2); let t0 = Instant::now();
        let prod = tokio::spawn(async move { for i in 1..=6 { tx.send(i).await.unwrap(); println!("  [{:>3} ms] 生产者 send({}) 返回", t0.elapsed().as_millis() / 10 * 10, i); } });
        sleep(Duration::from_millis(5)).await;
        while let Some(v) = rx.recv().await { println!("  [{:>3} ms] 消费者 收到 {}(处理 50 ms)", t0.elapsed().as_millis() / 10 * 10, v); sleep(Duration::from_millis(50)).await; }
        prod.await.unwrap();
    }
''')
print()
print('== 二:无界 mpsc:send 永不等待,生产者一口气发完,积压在队列里(内存增长没有上限)')
R['unbounded'] = go('u102b', '''
    use std::time::{Duration, Instant}; use tokio::{sync::mpsc, time::sleep};
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let (tx, mut rx) = mpsc::unbounded_channel::<u32>(); let t0 = Instant::now();
        for i in 1..=100_000 { tx.send(i).unwrap(); }
        println!("  生产者发完 10 万条用时 {} ms(同步 send,不 await);此时队列里积压了 {} 条", t0.elapsed().as_millis(), rx.len());
        let mut n = 0; while let Ok(_) = rx.try_recv() { n += 1; } println!("  消费者取走 {} 条", n);
        drop(tx); let _ = sleep(Duration::from_millis(1)).await;
    }
''')
print()
print('== 三:oneshot:只发一个值;发送端 drop 而没发值,接收端得到 Err(RecvError)')
R['oneshot'] = go('u102c', '''
    use tokio::sync::oneshot;
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let (tx, rx) = oneshot::channel(); tokio::spawn(async move { tx.send("结果").unwrap(); });
        println!("  收到 {:?}", rx.await);
        let (tx, rx) = oneshot::channel::<i32>(); drop(tx);
        println!("  发送端 drop 后接收: {:?}", rx.await);
        let (tx, rx) = oneshot::channel::<i32>(); drop(rx);
        println!("  接收端 drop 后发送: {:?}(值被退回)", tx.send(5));
    }
''')
print()
print('== 四:broadcast:每个接收者都收到每条消息;接收者太慢、超过容量时,最旧的被覆盖,接收者得到 Lagged(n)')
R['broadcast'] = go('u102d', '''
    use tokio::sync::broadcast;
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let (tx, mut r1) = broadcast::channel::<u32>(4); let mut r2 = tx.subscribe();
        for i in 1..=3 { tx.send(i).unwrap(); }
        println!("  两个接收者都收到 1..=3: r1 = {:?} {:?} {:?}  r2 = {:?} {:?} {:?}", r1.recv().await, r1.recv().await, r1.recv().await, r2.recv().await, r2.recv().await, r2.recv().await);
        let mut slow = tx.subscribe();
        for i in 10..=17 { tx.send(i).unwrap(); }   // 容量 4,发了 8 条,最旧的 4 条被覆盖
        println!("  慢接收者 recv: {:?}", slow.recv().await);
        println!("  之后继续 recv: {:?} {:?} {:?} {:?}", slow.recv().await, slow.recv().await, slow.recv().await, slow.recv().await);
    }
''')
print()
print('== 五:watch:只保留最新值;接收者只关心「当前状态」,中间值可以被跳过')
R['watch'] = go('u102e', '''
    use tokio::sync::watch;
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let (tx, mut rx) = watch::channel("v0");
        tx.send("v1").unwrap(); tx.send("v2").unwrap(); tx.send("v3").unwrap();
        println!("  连发 v1 v2 v3 之后,接收者看到的当前值: {}(中间的 v1 v2 被跳过)", *rx.borrow());
        println!("  changed() 返回: {:?};再次 changed 之前没有新值", rx.changed().await.map(|_| *rx.borrow_and_update()));
        let r = tokio::time::timeout(std::time::Duration::from_millis(30), rx.changed()).await; println!("  没有新值时 changed() 等待 30 ms: {}", if r.is_err() { "超时(一直在等新值)" } else { "返回了" });
    }
''')
save('u102', R)
