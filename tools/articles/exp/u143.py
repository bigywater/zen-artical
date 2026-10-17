import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u143'); R = {}
HEAD = '''
    #![allow(unused)]
    use std::{os::unix::net::{UnixListener, UnixStream, UnixDatagram}, io::{Read, Write}, thread, time::{Duration, Instant}, fs, path::PathBuf, os::unix::fs::{FileTypeExt, PermissionsExt}};
    fn sock(name: &str) -> PathBuf { let d = std::env::temp_dir().join("u143"); fs::create_dir_all(&d).unwrap(); let p = d.join(name); let _ = fs::remove_file(&p); p }
'''
print('== 一:Unix 域套接字像 TCP,但地址是文件系统路径:bind 会创建一个类型为 socket 的文件;回显服务')
r = tryit('u143a', HEAD + '''
    fn main() {
        let p = sock("echo.sock"); let l = UnixListener::bind(&p).unwrap();
        let md = fs::metadata(&p).unwrap(); println!("bind 之后路径上出现了一个文件:is_socket = {},权限 {:o}", md.file_type().is_socket(), md.permissions().mode() & 0o777);
        let p2 = p.clone(); let h = thread::spawn(move || { let (mut s, addr) = l.accept().unwrap(); let mut b = [0u8; 64]; let n = s.read(&mut b).unwrap(); s.write_all(&b[..n]).unwrap(); println!("  服务端:对端地址 {:?}(客户端没有 bind,是未命名的)", addr.as_pathname()); });
        let mut c = UnixStream::connect(&p2).unwrap(); c.write_all("你好 uds".as_bytes()).unwrap(); let mut out = [0u8; 64]; let n = c.read(&mut out).unwrap(); println!("客户端:收到 {:?}", String::from_utf8_lossy(&out[..n])); h.join().unwrap();
        println!("listener 已经 drop,但套接字文件还在: {}(需要自己删除)", p.exists());
    }
''', quiet_src=True); R['echo'] = r['out']
print()
print('== 二:地址已被占用 / 残留的套接字文件:对已存在的路径 bind 失败(AddrInUse),要先删文件;没有人监听的路径 connect 得到 ConnectionRefused')
r = tryit('u143b', HEAD + '''
    fn main() {
        let p = sock("stale.sock"); { let _l = UnixListener::bind(&p).unwrap(); }
        println!("上一个 listener 已经退出,文件还在: {}", p.exists());
        println!("再 bind 同一个路径:{:?}", UnixListener::bind(&p).map(|_| ()).map_err(|e| (e.kind(), e.raw_os_error())));
        println!("connect 到这个没人监听的残留文件:{:?}", UnixStream::connect(&p).map(|_| ()).map_err(|e| (e.kind(), e.raw_os_error())));
        fs::remove_file(&p).unwrap(); println!("删除文件后 bind: {:?}", UnixListener::bind(&p).map(|_| "成功").map_err(|e| e.kind()));
        println!("connect 到不存在的路径:{:?}", UnixStream::connect(sock("nope.sock")).map(|_| ()).map_err(|e| (e.kind(), e.raw_os_error())));
    }
''', quiet_src=True); R['stale'] = r['out']
print()
print('== 三:路径长度有上限(sun_path):超过就 bind 失败')
r = tryit('u143c', HEAD + '''
    fn main() {
        let dir = std::env::temp_dir().join("u143"); fs::create_dir_all(&dir).unwrap();
        let (mut lo, mut hi) = (1usize, 400usize);
        while lo + 1 < hi { let mid = (lo + hi) / 2; let p = dir.join("x".repeat(mid)); let _ = fs::remove_file(&p); if UnixListener::bind(&p).is_ok() { lo = mid; let _ = fs::remove_file(&p); } else { hi = mid; } }
        let ok = dir.join("x".repeat(lo)); let bad = dir.join("x".repeat(hi));
        println!("目录部分 {} 字节;文件名最长 {} 字节时 bind 成功,总路径长度 {} 字节;文件名 {} 字节(总长 {})失败:{:?}", dir.as_os_str().len(), lo, ok.as_os_str().len(), hi, bad.as_os_str().len(), UnixListener::bind(&bad).map(|_| ()).map_err(|e| e.to_string()));
    }
''', quiet_src=True); R['len'] = r['out']
print()
print('== 四:socketpair:UnixStream::pair() 得到一对已连接的套接字,不需要路径(父子进程/线程间通信);UnixDatagram 保留消息边界')
r = tryit('u143d', HEAD + '''
    fn main() {
        let (mut a, mut b) = UnixStream::pair().unwrap(); a.write_all(b"ping").unwrap(); let mut buf = [0u8; 8]; let n = b.read(&mut buf).unwrap(); println!("UnixStream::pair:a 写 ping,b 读到 {:?};a 的地址 {:?}", String::from_utf8_lossy(&buf[..n]), a.local_addr().unwrap().as_pathname());
        let (x, y) = UnixDatagram::pair().unwrap(); x.send(b"abc").unwrap(); x.send(b"de").unwrap(); let mut b1 = [0u8; 16]; let n1 = y.recv(&mut b1).unwrap(); let n2 = y.recv(&mut b1).unwrap(); println!("UnixDatagram:发 3 字节与 2 字节,两次 recv 分别得到 {} 与 {} 字节(边界保留)", n1, n2);
    }
''', quiet_src=True); R['pair'] = r['out']
print()
print('== 五:速度:同一机器上的往返延迟(4 字节回显 50000 次)与吞吐(发 1 GiB):Unix 域套接字对 TCP 回环')
r = tryit('u143e', HEAD + '''
    use std::net::{TcpListener, TcpStream};
    fn pingpong<S: Read + Write>(mut c: S, n: u32) -> f64 { let mut b = [0u8; 4]; let t = Instant::now(); for i in 0..n { c.write_all(&i.to_le_bytes()).unwrap(); c.read_exact(&mut b).unwrap(); } t.elapsed().as_secs_f64() * 1e6 / n as f64 }
    fn thr<S: Read + Write + Send + 'static>(mut tx: S, mut rx: S) -> f64 { let total = 1usize << 30; let h = thread::spawn(move || { let buf = vec![1u8; 1 << 16]; let mut sent = 0; while sent < total { tx.write_all(&buf).unwrap(); sent += buf.len(); } }); let mut buf = vec![0u8; 1 << 16]; let mut got = 0; let t = Instant::now(); while got < total { got += rx.read(&mut buf).unwrap(); } let s = t.elapsed().as_secs_f64(); h.join().unwrap(); total as f64 / s / 1e9 }
    fn main() {
        let p = sock("bench.sock"); let l = UnixListener::bind(&p).unwrap(); thread::spawn(move || { let (mut s, _) = l.accept().unwrap(); let mut b = [0u8; 4]; while s.read_exact(&mut b).is_ok() { if s.write_all(&b).is_err() { break; } } });
        let tl = TcpListener::bind("127.0.0.1:0").unwrap(); let ta = tl.local_addr().unwrap(); thread::spawn(move || { let (mut s, _) = tl.accept().unwrap(); s.set_nodelay(true).unwrap(); let mut b = [0u8; 4]; while s.read_exact(&mut b).is_ok() { if s.write_all(&b).is_err() { break; } } });
        let u = UnixStream::connect(&p).unwrap(); let t = TcpStream::connect(ta).unwrap(); t.set_nodelay(true).unwrap();
        let mut best = [f64::MAX; 2]; for _ in 0..3 { best[0] = best[0].min(pingpong(&u, 50_000)); best[1] = best[1].min(pingpong(&t, 50_000)); }
        println!("往返延迟:Unix 域套接字 {:.1} µs,TCP 回环 {:.1} µs", best[0], best[1]);
        let (a, b) = UnixStream::pair().unwrap(); let g1 = thr(a, b);
        let tl = TcpListener::bind("127.0.0.1:0").unwrap(); let ta = tl.local_addr().unwrap(); let c = TcpStream::connect(ta).unwrap(); let (s, _) = tl.accept().unwrap(); let g2 = thr(c, s);
        println!("单向吞吐(64 KiB 块,1 GiB):Unix 域套接字 {:.2} GB/s,TCP 回环 {:.2} GB/s", g1, g2);
    }
''', quiet_src=True, release=True); R['bench'] = r['out']
save('u143', R)
