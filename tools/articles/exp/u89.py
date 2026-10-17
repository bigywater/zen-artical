import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u89'); R = {}
print('== 一:多个生产者:tx.clone() 给每个线程一个发送端;每个生产者自己的消息保持发送顺序,不同生产者之间交错')
r = tryit('u89a', '''
    use std::{sync::mpsc, thread};
    fn main() {
        let (tx, rx) = mpsc::channel();
        let hs: Vec<_> = (0..3).map(|id| { let tx = tx.clone(); thread::spawn(move || { for seq in 0..4 { tx.send((id, seq)).unwrap(); } }) }).collect();
        drop(tx);
        let all: Vec<(i32, i32)> = rx.iter().collect();
        for h in hs { h.join().unwrap(); }
        println!("共收到 {} 条", all.len());
        for id in 0..3 { println!("生产者 {} 的序号按发送顺序到达: {}", id, all.iter().filter(|m| m.0 == id).map(|m| m.1).collect::<Vec<_>>() == vec![0, 1, 2, 3]); }
        println!("到达顺序(生产者编号): {}", all.iter().map(|m| m.0.to_string()).collect::<String>());
    }
''', quiet_src=True); R['multi'] = r['out']
print()
print('== 二:忘记 drop 原始 tx,接收端的迭代永远不会结束(用 recv_timeout 证明)')
r = tryit('u89b', '''
    use std::{sync::mpsc, thread, time::Duration};
    fn main() {
        let (tx, rx) = mpsc::channel();
        let tx2 = tx.clone();
        thread::spawn(move || { tx2.send(1).unwrap(); });
        println!("{:?}", rx.recv_timeout(Duration::from_millis(200)));
        println!("子线程已结束(它的 tx2 已 drop),但主线程手里的 tx 还活着:{:?}", rx.recv_timeout(Duration::from_millis(200)));
        drop(tx);
        println!("drop(tx) 之后:{:?}", rx.recv_timeout(Duration::from_millis(200)));
    }
''', quiet_src=True); R['leak'] = r['out']
print()
print('== 三:单消费者:Receiver 不能 clone;也不能共享给多个线程(!Sync)')
r = tryit('u89c', '''
    use std::sync::mpsc;
    fn main() { let (_tx, rx) = mpsc::channel::<i32>(); let _r2 = rx.clone(); }
''', maxlines=25); R['e_clone'] = r['diag']
r = tryit('u89d', '''
    use std::{sync::mpsc, thread};
    fn main() { let (_tx, rx) = mpsc::channel::<i32>(); thread::scope(|s| { s.spawn(|| { let _ = rx.recv(); }); s.spawn(|| { let _ = rx.recv(); }); }); }
''', maxlines=30); R['e_sync'] = r['diag']
print()
print('== 四:要多消费者就用 Arc<Mutex<Receiver>>:4 个工作线程抢 20 个任务(每个任务只被一个线程处理)')
r = tryit('u89e', '''
    use std::{sync::{mpsc, Arc, Mutex}, thread, time::Duration};
    fn main() {
        let (tx, rx) = mpsc::channel::<u32>(); let rx = Arc::new(Mutex::new(rx));
        let (rtx, rrx) = mpsc::channel();
        let hs: Vec<_> = (0..4).map(|w| { let rx = Arc::clone(&rx); let rtx = rtx.clone(); thread::spawn(move || loop {
            let job = rx.lock().unwrap().recv();
            match job { Ok(j) => { thread::sleep(Duration::from_millis(5)); rtx.send((w, j)).unwrap(); } Err(_) => break }
        }) }).collect();
        drop(rtx);
        for j in 0..20 { tx.send(j).unwrap(); } drop(tx);
        let done: Vec<(i32, u32)> = rrx.iter().collect(); for h in hs { h.join().unwrap(); }
        let mut jobs: Vec<u32> = done.iter().map(|d| d.1).collect(); jobs.sort();
        println!("处理了 {} 个任务,每个任务恰好一次: {}", done.len(), jobs == (0..20).collect::<Vec<_>>());
        let mut per = [0; 4]; for d in &done { per[d.0 as usize] += 1; } println!("4 个工作线程各处理的任务数: {:?}", per);
    }
''', quiet_src=True); R['pool'] = r['out']
print()
print('== 五:sync_channel(N):有界通道,满了 send 阻塞;容量 0 是会合(rendezvous)')
r = tryit('u89f', '''
    use std::{sync::mpsc, thread, time::{Duration, Instant}};
    fn main() {
        let (tx, rx) = mpsc::sync_channel::<i32>(2);
        tx.send(1).unwrap(); tx.send(2).unwrap();
        println!("容量 2:已发 2 个,try_send 第 3 个: {:?}", tx.try_send(3));
        let t = Instant::now();
        let h = { let tx = tx.clone(); thread::spawn(move || { tx.send(3).unwrap(); t.elapsed() }) };
        thread::sleep(Duration::from_millis(100)); println!("接收端睡了 100 ms 才取走一个:{:?}", rx.recv());
        let waited = h.join().unwrap(); println!("第 3 个 send 在通道满时被阻塞了约 {} 毫秒(取整到 50)", (waited.as_millis() / 50) * 50);
        let (t0, r0) = mpsc::sync_channel::<i32>(0);
        println!("容量 0(会合):没有接收者在等时 try_send = {:?}", t0.try_send(1));
        let h = thread::spawn(move || r0.recv().unwrap());
        t0.send(7).unwrap(); println!("接收者在等时 send 成功,对方收到 {}", h.join().unwrap());
    }
''', quiet_src=True); R['sync'] = r['out']
print()
print('== 六:吞吐量:无界 channel vs sync_channel(1) vs sync_channel(1024),1 个生产者 + 1 个消费者,发 100 万个 u32(release,各 3 次取最小)')
r = tryit('u89g', '''
    use std::{sync::mpsc, thread, time::Instant};
    fn run(kind: &str) -> f64 {
        let n = 1_000_000u32; let t = Instant::now();
        match kind {
            "unbounded" => { let (tx, rx) = mpsc::channel(); let h = thread::spawn(move || { for i in 0..n { tx.send(i).unwrap(); } }); let mut s = 0u64; for v in rx { s += v as u64; } h.join().unwrap(); std::hint::black_box(s); }
            k => { let cap = if k == "sync1" { 1 } else { 1024 }; let (tx, rx) = mpsc::sync_channel(cap); let h = thread::spawn(move || { for i in 0..n { tx.send(i).unwrap(); } }); let mut s = 0u64; for v in rx { s += v as u64; } h.join().unwrap(); std::hint::black_box(s); }
        }
        t.elapsed().as_secs_f64() * 1e3
    }
    fn main() { for k in ["unbounded", "sync1", "sync1024"] { let best = (0..3).map(|_| run(k)).fold(f64::MAX, f64::min); println!("{:<10} 100 万条 {:>8.1} ms(约 {:>6.0} ns/条)", k, best, best * 1e6 / 1e6); } }
''', quiet_src=True, release=True); R['bench'] = r['out']
save('u89', R)
