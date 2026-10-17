import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import socket
tee('u142'); R = {}
SERVER = r'''
    use std::{net::{TcpListener, TcpStream}, io::{Read, Write, BufRead, BufReader}, thread, time::Duration, collections::HashMap, sync::{Arc, atomic::{AtomicUsize, Ordering::SeqCst}}};
    struct Req { method: String, path: String, version: String, headers: HashMap<String, String>, body: Vec<u8> }
    fn read_request(r: &mut BufReader<TcpStream>) -> Result<Option<Req>, (u16, &'static str)> {
        let mut line = String::new(); if r.read_line(&mut line).map_err(|_| (400, "read error"))? == 0 { return Ok(None); }
        let parts: Vec<&str> = line.trim_end().split(' ').collect(); if parts.len() != 3 { return Err((400, "bad request line")); }
        let mut headers = HashMap::new(); let mut total = line.len();
        loop { let mut h = String::new(); let n = r.read_line(&mut h).map_err(|_| (400, "read error"))?; total += n; if total > 8192 { return Err((431, "headers too large")); } if h == "\r\n" || n == 0 { break; } let (k, v) = h.trim_end().split_once(':').ok_or((400, "bad header"))?; headers.insert(k.trim().to_ascii_lowercase(), v.trim().to_string()); }
        let len: usize = headers.get("content-length").map(|v| v.parse().map_err(|_| (400, "bad content-length"))).transpose()?.unwrap_or(0);
        let mut body = vec![0u8; len]; r.read_exact(&mut body).map_err(|_| (400, "short body"))?;
        Ok(Some(Req { method: parts[0].into(), path: parts[1].into(), version: parts[2].into(), headers, body }))
    }
    fn respond(w: &mut TcpStream, code: u16, reason: &str, ctype: &str, body: &[u8], keep: bool, head_only: bool) {
        let head = format!("HTTP/1.1 {} {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nConnection: {}\r\n\r\n", code, reason, ctype, body.len(), if keep { "keep-alive" } else { "close" });
        let _ = w.write_all(head.as_bytes()); if !head_only { let _ = w.write_all(body); }
    }
    fn handle(stream: TcpStream, counter: Arc<AtomicUsize>) {
        stream.set_read_timeout(Some(Duration::from_secs(2))).ok();
        let mut w = stream.try_clone().unwrap(); let mut r = BufReader::new(stream);
        loop {
            match read_request(&mut r) {
                Ok(None) => break,
                Err((code, why)) => { respond(&mut w, code, why, "text/plain", why.as_bytes(), false, false); break; }
                Ok(Some(req)) => {
                    let n = counter.fetch_add(1, SeqCst) + 1;
                    let keep = req.version == "HTTP/1.1" && req.headers.get("connection").map(|v| !v.eq_ignore_ascii_case("close")).unwrap_or(true);
                    let head_only = req.method == "HEAD";
                    match (req.method.as_str(), req.path.as_str()) {
                        ("GET" | "HEAD", "/") => respond(&mut w, 200, "OK", "text/plain; charset=utf-8", format!("hello, request #{}\n", n).as_bytes(), keep, head_only),
                        ("POST", "/echo") => respond(&mut w, 200, "OK", "application/octet-stream", &req.body, keep, false),
                        ("GET", "/headers") => { let mut ks: Vec<_> = req.headers.iter().collect(); ks.sort(); respond(&mut w, 200, "OK", "text/plain", ks.iter().map(|(k, v)| format!("{}={}\n", k, v)).collect::<String>().as_bytes(), keep, false) }
                        ("GET" | "POST" | "HEAD", _) => respond(&mut w, 404, "Not Found", "text/plain", b"not found", keep, head_only),
                        _ => respond(&mut w, 405, "Method Not Allowed", "text/plain", b"method not allowed", keep, false),
                    }
                    if !keep { break; }
                }
            }
        }
    }
    fn main() {
        let l = TcpListener::bind("127.0.0.1:0").unwrap(); println!("{}", l.local_addr().unwrap().port()); std::io::stdout().flush().unwrap();
        let c = Arc::new(AtomicUsize::new(0));
        for s in l.incoming() { let c = c.clone(); let s = s.unwrap(); thread::spawn(move || handle(s, c)); }
    }
'''
ok, d, binp, _ = rustc('u142srv', SERVER, release=True); print('  服务端编译:', '成功' if ok else d[:300])
srv = subprocess.Popen([str(binp)], stdout=subprocess.PIPE, text=True); port = int(srv.stdout.readline().strip())
def curl(*a): r = subprocess.run(['curl', '-s', *a, f'http://127.0.0.1:{port}' + a[-1] if False else ''], capture_output=True, text=True); return r
def c(args, path): r = subprocess.run(['curl', '-s', '--http1.1', *args, f'http://127.0.0.1:{port}{path}'], capture_output=True, text=True); return (r.stdout + r.stderr).replace('\r', '')
def rawreq(data, wait=0.4):
    s = socket.create_connection(('127.0.0.1', port)); s.settimeout(2); s.sendall(data); time.sleep(wait); out = b''
    try:
        while True:
            b = s.recv(65536)
            if not b: break
            out += b
    except Exception: pass
    s.close(); return out.decode('utf-8', 'replace').replace('\r', '')
try:
    print('== 一:用标准库写的一个小 HTTP/1.1 服务端(解析请求行与头部、按 Content-Length 读正文、路由、写响应、keep-alive),用 curl 访问各个路由')
    for label, args, path in [('GET /', ['-i'], '/'), ('GET /nope', ['-i'], '/nope'), ('HEAD /(只有头)', ['-I'], '/'), ('POST /echo -d "payload"', ['-i', '-d', 'payload'], '/echo'), ('DELETE /', ['-i', '-X', 'DELETE'], '/')]:
        out = c(args, path); first = out.splitlines()[0] if out else ''; body = out.split('\n\n', 1)[1] if '\n\n' in out else ''
        print(f'  curl {label:<28} → {first!r}  正文 {body.strip()!r}'); R.setdefault('routes', {})[label] = [first, body.strip()]
    print()
    print('== 二:服务端看到的请求头(curl 发的):头部键被我们转小写保存')
    out = c([], '/headers'); print('\n'.join('    ' + l for l in out.splitlines())); R['headers'] = out.splitlines()
    print()
    print('== 三:keep-alive:curl 一次命令访问同一个服务端两次 —— 看 curl 的详细输出里是否复用了连接,服务端的计数器')
    r = subprocess.run(['curl', '-sv', '--http1.1', f'http://127.0.0.1:{port}/', f'http://127.0.0.1:{port}/'], capture_output=True, text=True)
    lines = [l.replace('\r', '') for l in r.stderr.splitlines() if 'Connected to' in l or 'Re-using' in l or 'Connection #0' in l or 'left intact' in l]
    print('\n'.join('    ' + l for l in lines)); print('  两次响应的正文:', [l for l in r.stdout.replace('\r', '').splitlines() if 'request' in l]); R['keepalive'] = [lines, [l for l in r.stdout.splitlines() if 'request' in l]]
    print()
    print('== 四:不合法的请求:服务端要给出 4xx 而不是崩溃')
    for label, data in [('请求行只有两段', b'GET /\r\nHost: x\r\n\r\n'), ('头部没有冒号', b'GET / HTTP/1.1\r\nBadHeader\r\n\r\n'), ('Content-Length 不是数字', b'POST /echo HTTP/1.1\r\nContent-Length: abc\r\n\r\n'), ('头部超过 8 KiB', b'GET / HTTP/1.1\r\nX: ' + b'a' * 9000 + b'\r\n\r\n'), ('Content-Length 声明 100 却只发 5 字节(服务端等 2 秒读超时后关闭)', b'POST /echo HTTP/1.1\r\nContent-Length: 100\r\n\r\nhello')]:
        out = rawreq(data, wait=2.5 if '2 秒' in label else 0.4); first = out.splitlines()[0] if out else '(没有响应,连接被关闭)'; print(f'  {label:<40} → {first}'); R.setdefault('bad', {})[label] = first
    print()
    print('== 五:并发:20 个 curl 同时请求,服务端每个连接一个线程;计数器没有丢更新(用原子计数)')
    ps = [subprocess.Popen(['curl', '-s', '--http1.1', '-H', 'Connection: close', f'http://127.0.0.1:{port}/'], stdout=subprocess.PIPE, text=True) for _ in range(20)]
    outs = [p.communicate()[0].strip() for p in ps]; nums = sorted(int(o.split('#')[1]) for o in outs if '#' in o)
    print(f'  20 个并发请求得到的请求序号:{nums}(没有重复、没有缺失:{len(set(nums)) == 20}),累计服务器已处理 {max(nums)} 个'); R['conc'] = [len(set(nums)), max(nums)]
finally:
    srv.terminate()
save('u142', R)
