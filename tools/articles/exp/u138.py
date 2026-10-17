import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u138'); R = {}
HEAD = '''
    #![allow(unused)]
    use std::{net::{TcpListener, TcpStream}, io::{self, Read, Write}, thread, time::{Duration, Instant}, os::fd::AsRawFd};
    #[repr(C)] #[derive(Clone, Copy)] struct PollFd { fd: i32, events: i16, revents: i16 }
    unsafe extern "C" { fn poll(fds: *mut PollFd, n: u32, timeout_ms: i32) -> i32; fn clock_gettime(clk: i32, ts: *mut [i64; 2]) -> i32; }
    const POLLIN: i16 = 1;
    fn cpu_ms() -> f64 { let mut ts = [0i64; 2]; unsafe { clock_gettime(12, &mut ts); } ts[0] as f64 * 1e3 + ts[1] as f64 / 1e6 }
'''
print('== 一:set_nonblocking(true):accept / read 在没有数据时立刻返回 WouldBlock,而不是阻塞')
r = tryit('u138a', HEAD + '''
    fn main() {
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); let addr = l.local_addr().unwrap(); l.set_nonblocking(true).unwrap();
        let t = Instant::now(); let e = l.accept().unwrap_err(); println!("没有客户端时 accept:{:?},耗时 {} µs(立即返回)", e.kind(), t.elapsed().as_micros());
        let mut c = TcpStream::connect(addr).unwrap(); thread::sleep(Duration::from_millis(20));
        let (mut s, _) = l.accept().unwrap(); s.set_nonblocking(true).unwrap();
        let mut b = [0u8; 16]; let t = Instant::now(); let e = s.read(&mut b).unwrap_err(); println!("没有数据时 read:{:?},耗时 {} µs", e.kind(), t.elapsed().as_micros());
        c.write_all(b"hi").unwrap(); thread::sleep(Duration::from_millis(20)); println!("对端发 2 字节后 read: {:?}", s.read(&mut b).map(|n| n));
        drop(c); thread::sleep(Duration::from_millis(20)); println!("对端关闭后 read: {:?}(Ok(0) = EOF)", s.read(&mut b).map_err(|e| e.kind()));
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:忙等轮询的代价:非阻塞 + 空转循环等 300 ms 才到的数据 —— 数循环次数与进程 CPU 时间;对照阻塞式 read 与 poll(2)')
r = tryit('u138b', HEAD + '''
    fn main() {
        let which = std::env::args().nth(1).unwrap();
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); let addr = l.local_addr().unwrap();
        let sender = thread::spawn(move || { let mut c = TcpStream::connect(addr).unwrap(); thread::sleep(Duration::from_millis(300)); c.write_all(b"x").unwrap(); thread::sleep(Duration::from_millis(50)); });
        let (mut s, _) = l.accept().unwrap(); let c0 = cpu_ms(); let t = Instant::now(); let mut b = [0u8; 4]; let mut loops = 0u64;
        match which.as_str() {
            "busy" => { s.set_nonblocking(true).unwrap(); loop { loops += 1; match s.read(&mut b) { Ok(_) => break, Err(e) if e.kind() == io::ErrorKind::WouldBlock => continue, Err(e) => panic!("{}", e) } } }
            "blocking" => { loops = 1; s.read(&mut b).unwrap(); }
            _ => { s.set_nonblocking(true).unwrap(); let mut p = [PollFd { fd: s.as_raw_fd(), events: POLLIN, revents: 0 }]; loop { loops += 1; unsafe { poll(p.as_mut_ptr(), 1, -1); } match s.read(&mut b) { Ok(_) => break, Err(e) if e.kind() == io::ErrorKind::WouldBlock => continue, Err(e) => panic!("{}", e) } } }
        }
        println!("{:<9} 等到数据用了 {} ms,循环 {} 次,消耗 CPU 时间 {:.1} ms", which, t.elapsed().as_millis() / 10 * 10, loops, cpu_ms() - c0);
        sender.join().unwrap();
    }
''', quiet_src=True, release=True, show_run=False)
R['wait'] = {}
for w in ('busy', 'blocking', 'poll'):
    rc, so, se, _ = run(r['bin'], w); print('  ' + so.strip()); R['wait'][w] = so.strip()
print()
print('== 三:单线程同时服务多个连接:poll(2) 监视 3 个客户端 socket,谁就绪就读谁(一个线程,没有每连接一线程)')
r = tryit('u138c', HEAD + '''
    fn main() {
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); let addr = l.local_addr().unwrap();
        let mut clients: Vec<TcpStream> = (0..3).map(|_| TcpStream::connect(addr).unwrap()).collect();
        let mut conns: Vec<TcpStream> = (0..3).map(|_| { let (s, _) = l.accept().unwrap(); s.set_nonblocking(true).unwrap(); s }).collect();
        let starters: Vec<_> = clients.drain(..).enumerate().map(|(i, mut c)| thread::spawn(move || { thread::sleep(Duration::from_millis([120, 40, 80][i])); c.write_all(format!("client{}", i).as_bytes()).unwrap(); thread::sleep(Duration::from_millis(100)); })).collect();
        let t0 = Instant::now(); let me = thread::current().id(); let mut got = 0; let mut order = vec![];
        while got < 3 {
            let mut fds: Vec<PollFd> = conns.iter().map(|c| PollFd { fd: c.as_raw_fd(), events: POLLIN, revents: 0 }).collect();
            let n = unsafe { poll(fds.as_mut_ptr(), fds.len() as u32, 1000) };
            for (i, f) in fds.iter().enumerate() { if f.revents & POLLIN != 0 { let mut b = [0u8; 16]; if let Ok(k) = conns[i].read(&mut b) { if k > 0 { order.push((String::from_utf8_lossy(&b[..k]).to_string(), t0.elapsed().as_millis() / 20 * 20)); got += 1; } } } }
        }
        println!("一个线程({:?})按就绪顺序处理了 3 个连接:{:?}(客户端 0/1/2 分别在 120/40/80 ms 发数据)", me, order);
        for s in starters { s.join().unwrap(); }
    }
''', quiet_src=True); R['multi'] = r['out']
print()
print('== 四:set_nonblocking 作用在文件描述符上,所有克隆共享:try_clone 出来的两个 TcpStream 一个改成非阻塞,另一个也变了')
r = tryit('u138d', HEAD + '''
    fn main() {
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); let addr = l.local_addr().unwrap();
        let _c = TcpStream::connect(addr).unwrap(); let (a, _) = l.accept().unwrap(); let b = a.try_clone().unwrap();
        a.set_nonblocking(true).unwrap(); let mut buf = [0u8; 4]; let mut b = b;
        println!("只对 a 调用 set_nonblocking(true);用克隆 b 去 read:{:?}(立即返回 WouldBlock,没有阻塞 —— 非阻塞标志属于同一个打开的 socket)", b.read(&mut buf).map_err(|e| e.kind()));
    }
''', quiet_src=True); R['clone'] = r['out']
save('u138', R)
