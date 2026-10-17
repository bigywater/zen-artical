import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u141'); R = {}
DEPS = 'tokio = { version = "1", features = ["rt", "rt-multi-thread", "time", "macros", "net", "io-util", "sync"] }'
def go(name, code, release=True, timeout=180):
    d = proj(name, {'src/main.rs': code}, deps=DEPS); rc, o = cargo(['build'] + (['--release'] if release else []) + ['--quiet'], d, timeout=900)
    if rc != 0: print('  编译失败:', o[:600]); return ''
    rc, so, se, _ = run(TG / ('release' if release else 'debug') / name, timeout=timeout); out = so.rstrip() + (('\n' + se.rstrip()) if se.strip() else ''); print('\n'.join('  ' + l for l in out.splitlines())); return out
PROC = '''
    fn threads() -> usize { let o = std::process::Command::new("ps").args(["-M", "-p", &std::process::id().to_string()]).output().unwrap(); String::from_utf8_lossy(&o.stdout).lines().count().saturating_sub(1) }
    fn rss_mb() -> f64 { let o = std::process::Command::new("ps").args(["-o", "rss=", "-p", &std::process::id().to_string()]).output().unwrap(); String::from_utf8_lossy(&o.stdout).trim().parse::<f64>().unwrap() / 1024.0 }
'''
print('== 一:最小的 tokio 回显服务:accept 循环 + 每个连接 spawn 一个任务,用 tokio::io::copy 把读到的写回去')
R['echo'] = go('u141a', '''
    use tokio::{net::{TcpListener, TcpStream}, io::{self, AsyncReadExt, AsyncWriteExt}};
    #[tokio::main]
    async fn main() {
        let l = TcpListener::bind("127.0.0.1:0").await.unwrap(); let addr = l.local_addr().unwrap();
        tokio::spawn(async move { loop { let (mut s, peer) = l.accept().await.unwrap(); tokio::spawn(async move { let (mut r, mut w) = s.split(); let n = io::copy(&mut r, &mut w).await.unwrap(); println!("  服务端:一个连接结束,共回显 {} 字节(对端 IP {})", n, peer.ip()); }); } });
        for msg in ["hello", "tokio echo"] { let mut c = TcpStream::connect(addr).await.unwrap(); c.write_all(msg.as_bytes()).await.unwrap(); c.shutdown().await.unwrap(); let mut out = String::new(); c.read_to_string(&mut out).await.unwrap(); println!("客户端:发 {:?} 收 {:?}", msg, out); }
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;
    }
''')
print()
print('== 二:同时保持 3000 个空闲连接:tokio(任务)的线程数与内存')
R['tokio'] = go('u141b', PROC + '''
    use tokio::{net::{TcpListener, TcpStream}, io::{AsyncReadExt, AsyncWriteExt}};
    #[tokio::main(flavor = "multi_thread", worker_threads = 4)]
    async fn main() {
        let l = TcpListener::bind("127.0.0.1:0").await.unwrap(); let addr = l.local_addr().unwrap();
        let (t0, r0) = (threads(), rss_mb());
        tokio::spawn(async move { loop { let (mut s, _) = l.accept().await.unwrap(); tokio::spawn(async move { let mut b = [0u8; 64]; loop { let n = s.read(&mut b).await.unwrap_or(0); if n == 0 { break; } if s.write_all(&b[..n]).await.is_err() { break; } } }); } });
        let t = std::time::Instant::now(); let mut conns = Vec::new(); for _ in 0..3000 { conns.push(TcpStream::connect(addr).await.unwrap()); }
        let setup = t.elapsed().as_millis();
        let t = std::time::Instant::now(); for c in conns.iter_mut().take(1000) { c.write_all(b"ping").await.unwrap(); } let mut ok = 0; for c in conns.iter_mut().take(1000) { let mut b = [0u8; 4]; c.read_exact(&mut b).await.unwrap(); if &b == b"ping" { ok += 1; } }
        println!("  tokio:建立并保持 3000 个连接用时 {} ms;其中 1000 个各做一次回显往返用时 {} ms,{} 个正确", setup, t.elapsed().as_millis(), ok);
        println!("  线程数 {} → {}(tokio 工作线程 + 主线程等),RSS {:.0} MB → {:.0} MB", t0, threads(), r0, rss_mb());
    }
''')
print()
print('== 三:对照:每连接一个操作系统线程(256 KiB 栈)的阻塞式服务,尝试同样的 3000 个连接')
R['thread'] = go('u141c', PROC + '''
    use std::{net::{TcpListener, TcpStream}, io::{Read, Write}, thread};
    fn main() {
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); let addr = l.local_addr().unwrap();
        let (t0, r0) = (threads(), rss_mb());
        thread::spawn(move || { for s in l.incoming() { let mut s = match s { Ok(s) => s, Err(_) => continue }; if thread::Builder::new().stack_size(256 * 1024).spawn(move || { let mut b = [0u8; 64]; loop { let n = s.read(&mut b).unwrap_or(0); if n == 0 { break; } if s.write_all(&b[..n]).is_err() { break; } } }).is_err() { println!("  spawn 线程失败(到达线程数上限)"); break; } } });
        let t = std::time::Instant::now(); let mut conns = Vec::new(); let mut failed = None;
        for i in 0..3000 { match TcpStream::connect(addr) { Ok(c) => conns.push(c), Err(e) => { failed = Some((i, e.to_string())); break; } } }
        std::thread::sleep(std::time::Duration::from_millis(300));
        println!("  线程服务:建立 {} 个连接用时 {} ms{}", conns.len(), t.elapsed().as_millis(), failed.map(|(i, e)| format!(",第 {} 个失败:{}", i, e)).unwrap_or_default());
        println!("  线程数 {} → {},RSS {:.0} MB → {:.0} MB", t0, threads(), r0, rss_mb());
    }
''')
print()
print('== 四:回显的往返延迟:单个连接上发 4 字节等回显 20000 次(release):tokio 服务端对线程服务端')
R['lat'] = go('u141d', '''
    use tokio::{net::{TcpListener, TcpStream}, io::{AsyncReadExt, AsyncWriteExt}}; use std::time::Instant;
    #[tokio::main(flavor = "multi_thread", worker_threads = 2)]
    async fn main() {
        let l = TcpListener::bind("127.0.0.1:0").await.unwrap(); let a1 = l.local_addr().unwrap();
        tokio::spawn(async move { loop { let (mut s, _) = l.accept().await.unwrap(); s.set_nodelay(true).unwrap(); tokio::spawn(async move { let mut b = [0u8; 4]; while s.read_exact(&mut b).await.is_ok() { if s.write_all(&b).await.is_err() { break; } } }); } });
        let l2 = std::net::TcpListener::bind("127.0.0.1:0").unwrap(); let a2 = l2.local_addr().unwrap();
        std::thread::spawn(move || { use std::io::{Read, Write}; for s in l2.incoming() { let mut s = s.unwrap(); s.set_nodelay(true).unwrap(); std::thread::spawn(move || { let mut b = [0u8; 4]; while s.read_exact(&mut b).is_ok() { if s.write_all(&b).is_err() { break; } } }); } });
        for (name, addr) in [("tokio 服务端", a1), ("线程服务端", a2)] {
            let mut c = TcpStream::connect(addr).await.unwrap(); c.set_nodelay(true).unwrap(); let mut b = [0u8; 4]; let t = Instant::now();
            for i in 0..20000u32 { c.write_all(&i.to_le_bytes()).await.unwrap(); c.read_exact(&mut b).await.unwrap(); }
            println!("  {:<10} 平均往返 {:.1} µs", name, t.elapsed().as_secs_f64() * 1e6 / 20000.0);
        }
    }
''')
save('u141', R)
