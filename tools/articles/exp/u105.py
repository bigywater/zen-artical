import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u105'); R = {}
DEPS = 'tokio = { version = "1", features = ["rt", "rt-multi-thread", "time", "macros", "sync"] }'
def go(name, code, release=False, timeout=60):
    d = proj(name, {'src/main.rs': code}, deps=DEPS); rc, o = cargo(['build', '--quiet'], d, timeout=900)
    if rc != 0: L = [l for l in o.splitlines() if l.strip()][:14]; print('\n'.join('  ' + l for l in L)); return L
    rc, so, se, _ = run(TG / 'debug' / name, timeout=timeout); out = so.rstrip() + (('\n' + se.rstrip()) if se.strip() else ''); print('\n'.join('  ' + l for l in out.splitlines())); return out
print('== 一:drop 掉 JoinHandle 不会取消任务(任务继续在后台跑);abort() 才会取消')
R['detach'] = go('u105a', '''
    use std::time::Duration; use tokio::time::sleep;
    #[tokio::main(flavor = "multi_thread", worker_threads = 2)]
    async fn main() {
        let h = tokio::spawn(async { sleep(Duration::from_millis(50)).await; println!("  任务 A 跑完了(JoinHandle 早就被 drop 了)"); });
        drop(h);
        let h = tokio::spawn(async { sleep(Duration::from_millis(50)).await; println!("  任务 B 跑完了(不应该出现)"); });
        h.abort();
        let r = h.await; println!("  任务 B abort 之后 await:{:?}", r.map_err(|e| if e.is_cancelled() { "JoinError::Cancelled" } else { "其它" }));
        sleep(Duration::from_millis(100)).await;
    }
''')
print()
print('== 二:取消只发生在 await 点:abort 一个正在同步循环里的任务,它会先把循环跑完;只有到下一个 await 才被取消')
R['abort_sync'] = go('u105b', '''
    use std::time::{Duration, Instant}; use tokio::time::sleep;
    #[tokio::main(flavor = "multi_thread", worker_threads = 2)]
    async fn main() {
        let t0 = Instant::now();
        let h = tokio::spawn(async move {
            println!("  [{:>3} ms] 任务开始 200 ms 的同步循环(没有 await)", t0.elapsed().as_millis() / 10 * 10);
            let t = Instant::now(); while t.elapsed() < Duration::from_millis(200) {}
            println!("  [{:>3} ms] 同步循环结束,即将进入第一个 await", t0.elapsed().as_millis() / 10 * 10);
            sleep(Duration::from_millis(10)).await;
            println!("  任务继续执行(不应该出现)");
        });
        sleep(Duration::from_millis(50)).await;
        println!("  [{:>3} ms] 主任务调用 h.abort()", t0.elapsed().as_millis() / 10 * 10); h.abort();
        let r = h.await; println!("  [{:>3} ms] h.await 返回 {:?}", t0.elapsed().as_millis() / 10 * 10, r.map_err(|e| e.is_cancelled()));
    }
''')
print()
print('== 三:被取消时已经执行的副作用不会回滚:转账分两步(扣款 → await → 入账),在两步之间取消,钱就消失了')
R['partial'] = go('u105c', '''
    use std::{sync::{Arc, Mutex}, time::Duration}; use tokio::time::{sleep, timeout};
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let a = Arc::new(Mutex::new(100i64)); let b = Arc::new(Mutex::new(0i64));
        async fn transfer(a: Arc<Mutex<i64>>, b: Arc<Mutex<i64>>, n: i64) { *a.lock().unwrap() -= n; sleep(Duration::from_millis(100)).await; *b.lock().unwrap() += n; }
        let r = timeout(Duration::from_millis(30), transfer(a.clone(), b.clone(), 40)).await;
        let (va, vb) = (*a.lock().unwrap(), *b.lock().unwrap());
        println!("  transfer 被 timeout 取消:{}  账户 A = {},账户 B = {},合计 {}(转账前合计 100)", r.is_err(), va, vb, va + vb);
        async fn transfer_safe(a: Arc<Mutex<i64>>, b: Arc<Mutex<i64>>, n: i64) { sleep(Duration::from_millis(100)).await; let (mut x, mut y) = (a.lock().unwrap(), b.lock().unwrap()); *x -= n; *y += n; }
        let (a, b) = (Arc::new(Mutex::new(100i64)), Arc::new(Mutex::new(0i64)));
        let r = timeout(Duration::from_millis(30), transfer_safe(a.clone(), b.clone(), 40)).await;
        let (va, vb) = (*a.lock().unwrap(), *b.lock().unwrap());
        println!("  换新账户,先 await 后一次性改两个账户:被取消 {}  A = {},B = {},合计 {}(取消时什么都没改,没有损失)", r.is_err(), va, vb, va + vb);
    }
''')
print()
print('== 四:被取消时锁会正常释放(guard 随 Future 一起 drop),不会死锁')
R['lock'] = go('u105d', '''
    use std::{sync::Arc, time::Duration}; use tokio::{sync::Mutex, time::{sleep, timeout}};
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let m = Arc::new(Mutex::new(0)); let m2 = m.clone();
        let r = timeout(Duration::from_millis(30), async move { let mut g = m2.lock().await; *g += 1; sleep(Duration::from_millis(500)).await; }).await;
        println!("  持锁的任务被 timeout 取消:{}", r.is_err());
        println!("  之后立即 try_lock: {}(锁已随 Future 释放)", if m.try_lock().is_ok() { "成功" } else { "失败" });
    }
''')
print()
print('== 五:Drop 里不能 .await:想在取消时做异步清理不能直接写在 Drop 里')
R['e_drop'] = go('u105e', '''
    struct Conn;
    impl Drop for Conn { fn drop(&mut self) { tokio::time::sleep(std::time::Duration::from_millis(1)).await; } }
    fn main() {}
''')
save('u105', R)
