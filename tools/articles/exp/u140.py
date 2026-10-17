import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u140'); R = {}
srv = subprocess.Popen(['python3', str(RS / 'httpsrv' / 'srv.py')], stdout=subprocess.PIPE, text=True); port = int(srv.stdout.readline().strip())
HEAD = f'''
    #![allow(unused)]
    use std::{{net::TcpStream, io::{{Read, Write, BufRead, BufReader}}, time::Duration}};
    const PORT: u16 = {port};
    fn raw(req: &str) -> Vec<u8> {{ let mut s = TcpStream::connect(("127.0.0.1", PORT)).unwrap(); s.set_read_timeout(Some(Duration::from_secs(2))).unwrap(); s.write_all(req.as_bytes()).unwrap(); let mut out = Vec::new(); let _ = s.read_to_end(&mut out); out }}
'''
try:
    print('== 一:手写一个 HTTP/1.1 请求(就是几行文本),发给本机的 Python http.server(独立实现),看原始响应字节')
    r = tryit('u140a', HEAD + '''
        fn main() {
            let req = "GET /hello HTTP/1.1\\r\\nHost: 127.0.0.1\\r\\nConnection: close\\r\\n\\r\\n";
            println!("请求({} 字节):{:?}", req.len(), req);
            let resp = raw(req); let text = String::from_utf8_lossy(&resp);
            println!("响应共 {} 字节;按 \\\\r\\\\n 显示:", resp.len()); for line in text.split("\\r\\n") { println!("  | {}", line.replace('\\n', "⏎")); }
        }
    ''', quiet_src=True); R['raw'] = r['out']
    print()
    print('== 二:解析响应:状态行、头部(大小写不敏感、可重复)、空行分隔、正文长度由 Content-Length 决定')
    r = tryit('u140b', HEAD + '''
        fn main() {
            let resp = raw("GET /hello HTTP/1.1\\r\\nHost: x\\r\\nConnection: close\\r\\n\\r\\n");
            let split = resp.windows(4).position(|w| w == b"\\r\\n\\r\\n").unwrap(); let (head, body) = (std::str::from_utf8(&resp[..split]).unwrap(), &resp[split + 4..]);
            let mut lines = head.split("\\r\\n"); let status = lines.next().unwrap(); let parts: Vec<&str> = status.splitn(3, ' ').collect();
            println!("状态行 {:?} → 版本 {} 状态码 {} 原因短语 {:?}", status, parts[0], parts[1], parts[2]);
            let headers: Vec<(String, String)> = lines.map(|l| { let (k, v) = l.split_once(':').unwrap(); (k.trim().to_ascii_lowercase(), v.trim().to_string()) }).collect();
            println!("头部(键转小写)共 {} 个:{:?}", headers.len(), headers);
            let cl: usize = headers.iter().find(|(k, _)| k == "content-length").unwrap().1.parse().unwrap();
            println!("Content-Length = {},实际正文 {} 字节:{:?}(中文 \\"世界\\" 在 UTF-8 里每字 3 字节,所以 length 是字节数)", cl, body.len(), String::from_utf8_lossy(body));
            let xs: Vec<&String> = headers.iter().filter(|(k, _)| k == "x-demo").map(|(_, v)| v).collect(); println!("同名头 X-Demo 出现 {} 次:{:?}(头部可以重复)", xs.len(), xs);
        }
    ''', quiet_src=True); R['parse'] = r['out']
    print()
    print('== 三:没有 Content-Length 的响应:读到连接关闭为止(Connection: close);分块传输 Transfer-Encoding: chunked 的原始格式')
    r = tryit('u140c', HEAD + '''
        fn main() {
            let resp = raw("GET /close HTTP/1.1\\r\\nHost: x\\r\\nConnection: close\\r\\n\\r\\n"); let t = String::from_utf8_lossy(&resp);
            println!("/close 的响应头里有 Content-Length 吗: {};正文靠读到 EOF:{:?}", t.to_ascii_lowercase().contains("content-length"), t.split("\\r\\n\\r\\n").nth(1).unwrap());
            let resp = raw("GET /chunked HTTP/1.1\\r\\nHost: x\\r\\nConnection: close\\r\\n\\r\\n"); let split = resp.windows(4).position(|w| w == b"\\r\\n\\r\\n").unwrap(); let body = &resp[split + 4..];
            println!("/chunked 的原始正文:{:?}", String::from_utf8_lossy(body));
            let mut out = Vec::new(); let mut rest = body; loop { let eol = rest.windows(2).position(|w| w == b"\\r\\n").unwrap(); let size = usize::from_str_radix(std::str::from_utf8(&rest[..eol]).unwrap(), 16).unwrap(); if size == 0 { break; } out.extend_from_slice(&rest[eol + 2..eol + 2 + size]); rest = &rest[eol + 2 + size + 2..]; }
            println!("手写分块解码(十六进制长度 + 数据,0 结尾)得到:{:?}", String::from_utf8_lossy(&out));
        }
    ''', quiet_src=True); R['chunk'] = r['out']
    print()
    print('== 四:Keep-Alive:同一个 TCP 连接上连续发两个请求(HTTP/1.1 默认持久连接),第二个响应来自同一连接;对照每次新建连接')
    r = tryit('u140d', HEAD + '''
        use std::time::Instant;
        fn read_response(r: &mut BufReader<TcpStream>) -> (String, usize) {
            let mut status = String::new(); r.read_line(&mut status).unwrap(); let mut cl = 0; loop { let mut l = String::new(); r.read_line(&mut l).unwrap(); if l == "\\r\\n" { break; } if let Some(v) = l.to_ascii_lowercase().strip_prefix("content-length:") { cl = v.trim().parse().unwrap(); } }
            let mut body = vec![0u8; cl]; r.read_exact(&mut body).unwrap(); (status.trim().to_string(), body.len())
        }
        fn main() {
            let s = TcpStream::connect(("127.0.0.1", PORT)).unwrap(); let local = s.local_addr().unwrap(); let mut w = s.try_clone().unwrap(); let mut r = BufReader::new(s);
            for i in 0..2 { w.write_all(b"GET /hello HTTP/1.1\\r\\nHost: x\\r\\n\\r\\n").unwrap(); let (st, n) = read_response(&mut r); println!("同一连接上的第 {} 个请求:{:?},正文 {} 字节(本地端口没变: {})", i + 1, st, n, local.port() == w.local_addr().unwrap().port()); }
            let n = 500; let t = Instant::now(); let s = TcpStream::connect(("127.0.0.1", PORT)).unwrap(); let mut w = s.try_clone().unwrap(); let mut r = BufReader::new(s);
            for _ in 0..n { w.write_all(b"GET /hello HTTP/1.1\\r\\nHost: x\\r\\n\\r\\n").unwrap(); read_response(&mut r); } let keep = t.elapsed().as_secs_f64() * 1e6 / n as f64;
            let t = Instant::now(); for _ in 0..n { let s = TcpStream::connect(("127.0.0.1", PORT)).unwrap(); let mut w = s.try_clone().unwrap(); let mut r = BufReader::new(s); w.write_all(b"GET /hello HTTP/1.1\\r\\nHost: x\\r\\nConnection: close\\r\\n\\r\\n").unwrap(); read_response(&mut r); } let fresh = t.elapsed().as_secs_f64() * 1e6 / n as f64;
            println!("500 个请求,每个请求平均:复用连接 {:.0} µs,每次新建连接 {:.0} µs", keep, fresh);
        }
    ''', quiet_src=True, release=True); R['keep'] = r['out']
    print()
    print('== 五:与 curl 对照:同样的请求,curl -i 看到的响应和我们的原始字节一致;并看一次 302 重定向(curl -L 才会跟随)')
    rc, o, e = sh(['curl', '-s', '-i', '--http1.1', '-H', 'Connection: close', f'http://127.0.0.1:{port}/redirect']); print('  curl -i /redirect(不跟随):'); print('\n'.join('    ' + l for l in o.replace('\r', '').splitlines()[:5])); R['curl302'] = o.replace('\r', '').splitlines()[:5]
    rc, o, e = sh(['curl', '-s', '-L', f'http://127.0.0.1:{port}/redirect']); print(f'  curl -L /redirect(跟随)得到正文:{o.strip()!r}'); R['curlL'] = o.strip()
    rc, o, e = sh(['curl', '-s', '-H', 'X-Trace: 1', f'http://127.0.0.1:{port}/echo-headers']); print('  服务端看到的请求头(curl 默认会加这些):'); print('\n'.join('    ' + l for l in o.splitlines())); R['curlhdr'] = o.splitlines()
    r = tryit('u140e', HEAD + '''
        fn main() { let resp = raw("GET /echo-headers HTTP/1.1\\r\\nHost: 127.0.0.1\\r\\nConnection: close\\r\\n\\r\\n"); let t = String::from_utf8_lossy(&resp); println!("我们手写的最小请求,服务端看到的请求头:{:?}", t.split("\\r\\n\\r\\n").nth(1).unwrap().lines().collect::<Vec<_>>()); }
    ''', quiet_src=True); R['minhdr'] = r['out']
finally:
    srv.terminate()
save('u140', R)
