"""爬虫实验辅助:所有请求只发给本机自己起的测试服务器(127.0.0.1,端口 9960+),不访问任何真实网站。
- Srv(fn):HTTP/1.1 线程服务器。fn(h) 里 h 是请求处理器:h.method / h.path / h.hdrs(原始头,按收到的顺序的 [(名, 值)]) / h.body;
  用 h.reply(status, body, headers) 回应;服务器记录每次请求(srv.log)和每条连接(srv.conns:来源端口 -> 该连接上的请求数)
- RawSrv(fn):纯套接字服务器,fn(conn, addr) 自己读写字节(测断连、半关闭、CONNECT 等)
- 清理:实验临时文件放在 ptmp/<name>/,用完 purge()(只删这个已知目录)"""
import os, sys, socket, threading, time, json, re, shutil, pathlib, statistics, gzip, zlib, socketserver, http.server
HERE = pathlib.Path(__file__).parent
PT = HERE / 'ptmp'; PT.mkdir(exist_ok=True)
sys.path.insert(0, str(HERE))
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
    os.environ.pop(k, None)
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
import rl
from rl import tee, save
from fl import pr, ms, median

FORBIDDEN = {5432, 3306, 6379, 8181, 9101, 9333}


def free_port(start=9960):
    for p in range(start, start + 400):
        if p in FORBIDDEN: continue
        with socket.socket() as s:  # 用 bind 探测(不要用 connect:探测连接会被已经在监听的服务器当成真实连接记进去)
            try: s.bind(('127.0.0.1', p)); return p
            except OSError: continue
    raise RuntimeError('no free port')


def tidy(t):
    t = re.sub(r'\x1b\[[0-9;]*m', '', t).replace(str(PT), '<ptmp>').replace(str(HERE), '<实验目录>')
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).strip('\n')


def pct(xs, p):
    xs = sorted(xs); k = (len(xs) - 1) * p / 100; f = int(k); c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def mean(xs): return sum(xs) / len(xs)


class _H(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'plab'
    sys_version = ''

    def setup(self):
        super().setup()
        self.server.srv._conn_open(self.client_address[1])

    def log_message(self, *a): pass

    def _go(self):
        n = int(self.headers.get('Content-Length') or 0)
        self.body = self.rfile.read(n) if n else b''
        if 'chunked' in (self.headers.get('Transfer-Encoding') or '').lower():
            b = b''
            while True:
                size = int(self.rfile.readline().strip() or b'0', 16)
                if size == 0: self.rfile.readline(); break
                b += self.rfile.read(size); self.rfile.read(2)
            self.body = b
        self.hdrs = [(k, v) for k, v in self.headers.items()]
        self.t_in = time.perf_counter()
        sv = self.server.srv; sv._record(self)
        with sv.lock:
            sv.inflight += 1; sv.peak = max(sv.peak, sv.inflight)
        try: sv.fn(self)
        finally:
            with sv.lock: sv.inflight -= 1  # close_connection 由 parse_request 按请求头设置(Connection: close 会让服务器在回应后关掉连接)

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_OPTIONS = do_PATCH = _go

    def reply(self, status=200, body=b'', headers=None, close=False, length=True, reason=None):
        if isinstance(body, str): body = body.encode()
        self.send_response(status, reason)
        hs = dict(headers or {})
        for k, v in hs.items(): self.send_header(k, v)
        if length and 'Content-Length' not in hs and 'Transfer-Encoding' not in hs: self.send_header('Content-Length', str(len(body)))
        if close: self.send_header('Connection', 'close'); self.close_connection = True
        self.end_headers()
        if self.command != 'HEAD': self.wfile.write(body)
        try: self.wfile.flush()
        except Exception: pass

    def send_chunks(self, chunks, status=200, headers=None, delay=0.0):
        self.send_response(status)
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.send_header('Transfer-Encoding', 'chunked'); self.end_headers()
        for c in chunks:
            if isinstance(c, str): c = c.encode()
            self.wfile.write(b'%x\r\n%s\r\n' % (len(c), c)); self.wfile.flush()
            if delay: time.sleep(delay)
        self.wfile.write(b'0\r\n\r\n'); self.wfile.flush()


class _S(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    request_queue_size = 512
    allow_reuse_address = True
    ctx = None

    def handle_error(self, request, client_address):
        pass  # 客户端提前断开、RST 等不打印回溯(实验里这是常态)

    def get_request(self):
        sock, addr = super().get_request()
        if self.ctx is not None: sock = self.ctx.wrap_socket(sock, server_side=True, do_handshake_on_connect=False)  # 握手放到连接线程里做
        return sock, addr


class Srv:
    """with Srv(fn) as s: s.url('/x')"""
    def __init__(self, fn=None, port=None, tls=None, idle=None):
        """tls=(certfile, keyfile) 时用 HTTPS(自签名证书,见 make_cert)。"""
        self.fn = fn or (lambda h: h.reply(200, b'ok'))
        self.port = port or free_port()
        self.log = []; self.conns = {}; self.lock = threading.Lock(); self.n_conn = 0; self.inflight = 0; self.peak = 0
        H = type('H', (_H,), {'timeout': idle}) if idle else _H  # idle 秒内连接上没有新请求,服务器就关掉它
        self.httpd = _S(('127.0.0.1', self.port), H); self.httpd.srv = self
        self.tls = bool(tls)
        if tls:
            import ssl
            c = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); c.load_cert_chain(*tls); self.httpd.ctx = c
        self.th = threading.Thread(target=self.httpd.serve_forever, kwargs=dict(poll_interval=0.05), daemon=True)

    def _conn_open(self, cport):
        with self.lock: self.n_conn += 1; self.conns[cport] = 0

    def _record(self, h):
        with self.lock:
            self.conns[h.client_address[1]] = self.conns.get(h.client_address[1], 0) + 1
            self.log.append(dict(t=time.perf_counter(), method=h.command, path=h.path, hdrs=h.hdrs, body=h.body, cport=h.client_address[1], http=h.request_version,
                                 reused=getattr(h.connection, 'session_reused', None), tls=(h.connection.version() if hasattr(h.connection, 'version') else None)))

    def url(self, path='/'): return f'{"https" if self.tls else "http"}://127.0.0.1:{self.port}{path}'
    def __enter__(self): self.th.start(); return self
    def __exit__(self, *a): self.stop()
    def stop(self):
        self.httpd.shutdown(); self.httpd.server_close()
    def reset(self):
        with self.lock: self.log = []; self.conns = {}; self.n_conn = 0; self.peak = 0


class RawSrv:
    """fn(conn, addr) 在每条连接的线程里运行,自己读写字节。"""
    def __init__(self, fn, port=None):
        self.port = port or free_port(); self.fn = fn
        self.sock = socket.socket(); self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', self.port)); self.sock.listen(256); self.sock.settimeout(0.2)
        self.stop_ev = threading.Event(); self.n_conn = 0; self.lock = threading.Lock()
        self.th = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self.stop_ev.is_set():
            try: c, a = self.sock.accept()
            except socket.timeout: continue
            except OSError: break
            with self.lock: self.n_conn += 1
            threading.Thread(target=self._run, args=(c, a), daemon=True).start()

    def _run(self, c, a):
        try: self.fn(c, a)
        except Exception: pass
        finally:
            try: c.close()
            except Exception: pass

    def url(self, path='/'): return f'http://127.0.0.1:{self.port}{path}'
    def __enter__(self): self.th.start(); return self
    def __exit__(self, *a): self.stop()
    def stop(self):
        self.stop_ev.set()
        try: self.sock.close()
        except Exception: pass


def read_request(conn, limit=65536):
    """从套接字读到一个完整的请求头(到 \\r\\n\\r\\n),返回原始字节。"""
    buf = b''
    conn.settimeout(5)
    while b'\r\n\r\n' not in buf and len(buf) < limit:
        d = conn.recv(4096)
        if not d: break
        buf += d
    return buf


def make_cert(d, cn='127.0.0.1', san='IP:127.0.0.1,DNS:localhost', alg='ec256'):
    """用 openssl 生成自签名证书(EC P-256,有效期 2 天,SAN 含 127.0.0.1 与 localhost),返回 (cert, key)。"""
    import subprocess
    suffix = '' if alg == 'ec256' else '_' + alg
    c, k = str(d / f'cert{suffix}.pem'), str(d / f'key{suffix}.pem')
    spec = {'ec256': ['ec', '-pkeyopt', 'ec_paramgen_curve:prime256v1'], 'ec384': ['ec', '-pkeyopt', 'ec_paramgen_curve:secp384r1'],
            'rsa2048': ['rsa:2048'], 'rsa4096': ['rsa:4096']}[alg]
    if not os.path.exists(c):
        subprocess.run(['openssl', 'req', '-x509', '-newkey', *spec, '-nodes', '-keyout', k, '-out', c,
                        '-days', '2', '-subj', f'/CN={cn}', '-addext', f'subjectAltName={san}'], check=True, capture_output=True)
    return c, k


def gz(b): return gzip.compress(b, 6, mtime=0)
def pdir(name, clean=True):
    d = PT / name
    if clean: shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True); return d


def purge():
    shutil.rmtree(PT, ignore_errors=True); PT.mkdir(exist_ok=True)


def row(*cols, w=(0,)):
    return '  ' + ' | '.join(str(c) for c in cols)


if __name__ == '__main__':
    purge(); print('清理完成')


class Nginx:
    """起一个只监听 127.0.0.1 的 nginx(独立 prefix 在 ptmp/ 下),HTTPS + HTTP/2,反向代理到本机的后端 Srv。
    访问日志格式:连接序号 该连接上第几个请求 协议 TLS版本 URI 状态码。"""
    def __init__(self, name, backend_port, cert, key, streams=128, extra=''):
        import subprocess
        self.dir = pdir('nx_' + name); self.port = free_port(); self.backend = backend_port
        for sub in ('body', 'proxy', 'fcgi', 'uwsgi', 'scgi'): (self.dir / sub).mkdir()
        self.log = self.dir / 'access.log'
        conf = f"""worker_processes 1; daemon off; pid {self.dir}/nginx.pid; error_log {self.dir}/err.log warn;
events {{ worker_connections 1024; }}
http {{
  log_format f '$connection $connection_requests $server_protocol $ssl_protocol $request_uri $status'; access_log {self.log} f;
  client_body_temp_path {self.dir}/body; proxy_temp_path {self.dir}/proxy; fastcgi_temp_path {self.dir}/fcgi; uwsgi_temp_path {self.dir}/uwsgi; scgi_temp_path {self.dir}/scgi;
  keepalive_requests 100000;
  upstream be {{ server 127.0.0.1:{backend_port}; keepalive 256; }}
  server {{
    listen 127.0.0.1:{self.port} ssl; http2 on; http2_max_concurrent_streams {streams};
    ssl_certificate {cert}; ssl_certificate_key {key};
    {extra}
    location / {{ proxy_pass http://be; proxy_http_version 1.1; proxy_set_header Connection ""; }}
  }}
}}
"""
        (self.dir / 'nginx.conf').write_text(conf)
        self.p = subprocess.Popen(['nginx', '-p', str(self.dir), '-c', str(self.dir / 'nginx.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(100):
            with socket.socket() as s:
                if s.connect_ex(('127.0.0.1', self.port)) == 0: break
            time.sleep(0.05)
        else: raise RuntimeError('nginx 没起来:' + ((self.dir / 'err.log').read_text()[-300:] if (self.dir / 'err.log').exists() else '') + str(self.p.poll()))

    def url(self, path='/'): return f'https://127.0.0.1:{self.port}{path}'
    def entries(self):
        return [l.split() for l in self.log.read_text().splitlines() if l.strip()] if self.log.exists() else []
    def clear(self): open(self.log, 'w').close()
    def __enter__(self): return self
    def __exit__(self, *a): self.stop()
    def stop(self):
        self.p.terminate()
        try: self.p.wait(5)
        except Exception: self.p.kill()
