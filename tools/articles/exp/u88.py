import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u88'); R = {}
print('== 一:send 把值的所有权移进通道;recv 阻塞直到有值;发送之后原变量不能再用')
r = tryit('u88a', '''
    use std::{sync::mpsc, thread, time::{Duration, Instant}};
    fn main() {
        let (tx, rx) = mpsc::channel();
        let h = thread::spawn(move || { thread::sleep(Duration::from_millis(100)); tx.send(String::from("来自子线程")).unwrap(); });
        let t = Instant::now();
        let msg = rx.recv().unwrap();
        println!("recv 阻塞了 {} 毫秒(取整到 50),收到 {:?}", (t.elapsed().as_millis() / 50) * 50, msg);
        h.join().unwrap();
    }
''', quiet_src=True); R['block'] = r['out']
r = tryit('u88b', '''
    use std::sync::mpsc;
    fn main() { let (tx, rx) = mpsc::channel(); let s = String::from("x"); tx.send(s).unwrap(); println!("{}", s); let _ = rx; }
''', maxlines=30); R['e0382'] = r['diag']
print()
print('== 二:所有发送端 drop 之后,recv 返回 Err,迭代器结束')
r = tryit('u88c', '''
    use std::{sync::mpsc, thread};
    fn main() {
        let (tx, rx) = mpsc::channel();
        let h = thread::spawn(move || { for i in 1..=3 { tx.send(i).unwrap(); } println!("子线程结束,tx 随之 drop"); });
        let got: Vec<i32> = rx.iter().collect();
        println!("for / iter 收完后结束,共收到 {:?}", got);
        println!("再 recv: {:?}", rx.recv());
        h.join().unwrap();
    }
''', quiet_src=True); R['close'] = r['out']
print()
print('== 三:try_recv 不阻塞(Empty / Disconnected);recv_timeout 带超时')
r = tryit('u88d', '''
    use std::{sync::mpsc, time::Duration};
    fn main() {
        let (tx, rx) = mpsc::channel::<i32>();
        println!("空通道 try_recv: {:?}", rx.try_recv());
        println!("recv_timeout(50ms): {:?}", rx.recv_timeout(Duration::from_millis(50)));
        tx.send(1).unwrap(); println!("有值时 try_recv: {:?}", rx.try_recv());
        drop(tx);
        println!("发送端都 drop 后 try_recv: {:?}", rx.try_recv());
        println!("发送端都 drop 后 recv_timeout: {:?}", rx.recv_timeout(Duration::from_millis(50)));
    }
''', quiet_src=True); R['try'] = r['out']
print()
print('== 四:接收端 drop 之后 send 返回 Err,并把值还给你')
r = tryit('u88e', '''
    use std::sync::mpsc;
    fn main() {
        let (tx, rx) = mpsc::channel::<String>();
        drop(rx);
        let e = tx.send(String::from("没人收")).unwrap_err();
        println!("send 失败: {}  被退回的值: {:?}", e, e.0);
    }
''', quiet_src=True); R['senderr'] = r['out']
print()
print('== 五:通道里能传什么:只要 Send;Rc 不行')
r = tryit('u88f', '''
    use std::{sync::mpsc, rc::Rc, thread};
    fn main() { let (tx, rx) = mpsc::channel(); thread::spawn(move || { tx.send(Rc::new(1)).unwrap(); }); let _ = rx.recv(); }
''', maxlines=30); R['rc'] = r['diag']
print()
print('== 六:消息的所有权随 send 转移:接收方拿到的是同一块堆内存(地址不变),没有复制')
r = tryit('u88g', '''
    use std::{sync::mpsc, thread};
    fn main() {
        let (tx, rx) = mpsc::channel();
        let v: Vec<u64> = (0..1_000_000).collect(); let before = v.as_ptr() as usize;
        let h = thread::spawn(move || { tx.send(v).unwrap(); });
        let got = rx.recv().unwrap(); h.join().unwrap();
        println!("发送前缓冲区地址 == 接收后缓冲区地址: {}(100 万个 u64 没有被复制)", before == got.as_ptr() as usize);
    }
''', quiet_src=True); R['nocopy'] = r['out']
save('u88', R)
