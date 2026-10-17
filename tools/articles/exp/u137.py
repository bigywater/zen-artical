import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u137'); R = {}
HEAD = '''
    #![allow(unused)]
    use std::{net::{TcpListener, TcpStream, Shutdown, SocketAddr}, io::{Read, Write, BufRead, BufReader}, thread, time::{Duration, Instant}};
'''
print('== 一:服务端 bind(\"127.0.0.1:0\") 让系统分配端口;accept 得到每个连接的 TcpStream 与对端地址;一个最小的回显服务')
r = tryit('u137a', HEAD + '''
    fn main() {
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); let addr = l.local_addr().unwrap();
        println!("监听地址 {}(端口由系统分配:{})", "127.0.0.1:<端口>", addr.port() > 1024);
        let h = thread::spawn(move || { for _ in 0..2 { let (mut s, peer) = l.accept().unwrap(); let mut buf = [0u8; 64]; let n = s.read(&mut buf).unwrap(); s.write_all(&buf[..n]).unwrap(); println!("  服务端:来自 {} 的 {} 字节已回显(对端 IP {},是回环地址: {})", "<客户端地址>", n, peer.ip(), peer.ip().is_loopback()); } });
        for msg in ["hello", "世界"] { let mut c = TcpStream::connect(addr).unwrap(); c.write_all(msg.as_bytes()).unwrap(); let mut out = vec![0u8; 64]; let n = c.read(&mut out).unwrap(); println!("客户端:发 {:?},收到 {:?}", msg, String::from_utf8_lossy(&out[..n])); }
        h.join().unwrap();
    }
''', quiet_src=True); R['echo'] = r['out']
print()
print('== 二:错误:连接被拒绝(没人监听)、地址已被占用、读超时')
r = tryit('u137b', HEAD + '''
    fn main() {
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); let addr = l.local_addr().unwrap(); drop(l);
        let e = TcpStream::connect(addr).unwrap_err(); println!("连接一个没人监听的端口:kind = {:?},os_error = {:?}", e.kind(), e.raw_os_error());
        let l1 = TcpListener::bind("127.0.0.1:0").unwrap(); let a1 = l1.local_addr().unwrap();
        let e = TcpListener::bind(a1).unwrap_err(); println!("同一个地址 bind 第二次:kind = {:?},os_error = {:?}", e.kind(), e.raw_os_error());
        let t = thread::spawn(move || TcpStream::connect(a1).unwrap()); let (mut s, _peer) = l1.accept().unwrap(); let _client = t.join().unwrap();   // 客户端连接保持打开,但不发数据
        s.set_read_timeout(Some(Duration::from_millis(100))).unwrap(); let t = Instant::now(); let mut b = [0u8; 8];
        let e = s.read(&mut b).unwrap_err(); println!("读超时 100 ms:kind = {:?}(实际等了约 {} ms)", e.kind(), (t.elapsed().as_millis() / 50) * 50);
    }
''', quiet_src=True); R['err'] = r['out']
print()
print('== 三:TCP 是字节流,不是消息:连续两次 write 对端可能一次 read 读到;用读到 EOF 或长度前缀分帧')
r = tryit('u137c', HEAD + '''
    fn main() {
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); let addr = l.local_addr().unwrap();
        let w = thread::spawn(move || { let mut c = TcpStream::connect(addr).unwrap(); c.set_nodelay(true).unwrap(); c.write_all(b"AAAA").unwrap(); c.write_all(b"BBBB").unwrap(); c.write_all(b"CCCC").unwrap(); });
        let (mut s, _) = l.accept().unwrap(); w.join().unwrap(); thread::sleep(Duration::from_millis(50));
        let mut b = [0u8; 64]; let n = s.read(&mut b).unwrap(); println!("发送端分 3 次 write 各 4 字节,接收端一次 read 读到 {} 字节:{:?}(消息边界没有保留)", n, String::from_utf8_lossy(&b[..n]));
        let n2 = s.read(&mut b).unwrap(); println!("再 read:{} 字节(0 = 对端已关闭,读到 EOF)", n2);
    }
''', quiet_src=True); R['stream'] = r['out']
print()
print('== 四:半关闭 shutdown(Write):客户端发完请求后关闭写端,服务端 read_to_end 才能读到 EOF 而结束;不关闭就一直等')
r = tryit('u137d', HEAD + '''
    fn main() {
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); let addr = l.local_addr().unwrap();
        let srv = thread::spawn(move || { let (mut s, _) = l.accept().unwrap(); s.set_read_timeout(Some(Duration::from_millis(400))).unwrap(); let mut data = Vec::new(); let r = s.read_to_end(&mut data); let kind = r.as_ref().err().map(|e| e.kind()); if r.is_ok() { s.write_all(format!("收到 {} 字节", data.len()).as_bytes()).unwrap(); } (data.len(), kind) });
        let mut c = TcpStream::connect(addr).unwrap(); c.write_all(b"request body").unwrap();
        c.shutdown(Shutdown::Write).unwrap(); let mut resp = String::new(); c.read_to_string(&mut resp).unwrap(); println!("客户端 shutdown(Write) 之后,服务端 read_to_end 返回,回复 {:?}", resp); println!("服务端结果 {:?}", srv.join().unwrap());
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); let addr = l.local_addr().unwrap();
        let srv = thread::spawn(move || { let (mut s, _) = l.accept().unwrap(); s.set_read_timeout(Some(Duration::from_millis(400))).unwrap(); let mut data = Vec::new(); let r = s.read_to_end(&mut data); (data.len(), r.err().map(|e| e.kind())) });
        let mut c = TcpStream::connect(addr).unwrap(); c.write_all(b"request body").unwrap(); thread::sleep(Duration::from_millis(600));
        println!("客户端不关闭写端:服务端 read_to_end 在 400 ms 超时后失败,返回 {:?}(已经读到的 12 字节仍留在 Vec 里)", srv.join().unwrap());
    }
''', quiet_src=True); R['half'] = r['out']
print()
print('== 五:TCP_NODELAY 与小包延迟:同一连接上交替发送小请求并等回复 2000 次,默认 vs set_nodelay(true)')
r = tryit('u137e', HEAD + '''
    fn run(nodelay: bool) -> f64 {
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); let addr = l.local_addr().unwrap();
        let srv = thread::spawn(move || { let (mut s, _) = l.accept().unwrap(); s.set_nodelay(true).unwrap(); let mut b = [0u8; 4]; loop { if s.read_exact(&mut b).is_err() { break; } s.write_all(&b).unwrap(); } });
        let mut c = TcpStream::connect(addr).unwrap(); c.set_nodelay(nodelay).unwrap(); let t = Instant::now(); let mut b = [0u8; 4];
        for i in 0..2000u32 { c.write_all(&i.to_le_bytes()[..2]).unwrap(); c.write_all(&i.to_le_bytes()[2..]).unwrap(); c.read_exact(&mut b).unwrap(); }
        let per = t.elapsed().as_secs_f64() * 1e6 / 2000.0; drop(c); srv.join().unwrap(); per
    }
    fn main() { let a = run(false); let b = run(true); println!("请求分两次 write(2 字节 + 2 字节)再等回复,每轮往返:默认 {:.0} µs,set_nodelay(true) {:.0} µs", a, b); }
''', quiet_src=True, release=True); R['nodelay'] = r['out']
save('u137', R)
