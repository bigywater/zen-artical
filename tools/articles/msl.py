"""微服务系列的实验辅助:在本进程里起小 HTTP 服务(线程化),调用、计时、统计。
端口 9150 起(借用 txl 的端口分配);外部组件(nginx、etcd、Envoy……)的实例数据在 vtmp/<name>/,整体可删。
用 ttmp_venv 运行实验:ttmp_venv/bin/python exp/vN.py"""
import txl, pathlib
txl.TT = pathlib.Path(__file__).parent / 'vtmp'; txl.TT.mkdir(exist_ok=True)
from txl import *
import http.client, itertools, collections, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

TT = txl.TT


class Svc:
    """一个很小的 HTTP 服务:app(handler) 里自己 sleep / 调下游 / handler.reply(code, obj)。统计到达数与完成数。"""
    def __init__(self, app, name='svc', backlog=512, port=None):
        self.app, self.name, self.port = app, name, port or free_port(); self.arrived = 0; self.finished = 0; self.lock = threading.Lock()
        svc = self
        class H(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *a): pass
            def reply(self, code, obj=b'ok', headers=None):
                data = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
                try:
                    self.send_response(code); self.send_header('Content-Length', str(len(data)))
                    for k, v in (headers or {}).items(): self.send_header(k, str(v))
                    self.end_headers(); self.wfile.write(data)
                except Exception: pass
            def do_GET(self):
                with svc.lock: svc.arrived += 1
                try: svc.app(self)
                finally:
                    with svc.lock: svc.finished += 1
            do_POST = do_GET
        class S(ThreadingHTTPServer):
            daemon_threads = True; request_queue_size = backlog; allow_reuse_address = True
            def handle_error(self, request, client_address): pass     # client 先断开是实验里的常态,不要把堆栈打到输出里
        self.srv = S(('127.0.0.1', self.port), H); self.socks = set()
        orig = self.srv.process_request
        def pr(request, client_address, _o=orig, _s=self.socks):
            _s.add(request); return _o(request, client_address)
        self.srv.process_request = pr
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def stop(self):
        self.srv.shutdown(); self.srv.server_close()
        for c in list(self.socks):          # 把已建立的(keep-alive)连接也一并断开,否则对端还能继续用旧连接,服务看起来并没有“停”
            try: c.shutdown(socket.SHUT_RDWR)
            except Exception: pass
            try: c.close()
            except Exception: pass


_tl = threading.local()
ERRORS = collections.Counter()      # 连接类错误(不是超时)的次数:实验结束时应为 0,否则数字不可信


def rpc(port, path='/', timeout=5.0, headers=None, method='GET', keepalive=True):
    """返回 (状态码 或 'timeout' / 'error', 响应体 bytes, 耗时秒)。同一线程对同一端口复用一条 keep-alive 连接(否则几万次短连接会把本机的临时端口用光,
    出现大量连接错误);任何异常都丢掉这条连接。timeout 是每次 socket 操作的上限(服务一次性回包,近似总时长)。"""
    t0 = time.perf_counter(); pool = getattr(_tl, 'p', None)
    if pool is None: pool = _tl.p = {}
    c = pool.get(port) if keepalive else None
    if c is None: c = http.client.HTTPConnection('127.0.0.1', port, timeout=max(timeout, 0.001))
    else: c.timeout = max(timeout, 0.001); c.sock and c.sock.settimeout(c.timeout)
    hd = dict(headers or {})
    try:
        c.request(method, path, headers=hd); r = c.getresponse(); d = r.read()
        if keepalive and not r.will_close: pool[port] = c
        else: pool.pop(port, None); c.close()
        return r.status, d, time.perf_counter() - t0
    except (socket.timeout, TimeoutError):
        pool.pop(port, None); c.close(); return 'timeout', b'', time.perf_counter() - t0
    except Exception as e:
        pool.pop(port, None)
        try: c.close()
        except Exception: pass
        ERRORS['error'] += 1; ERRORS[type(e).__name__] += 1; return 'error', b'', time.perf_counter() - t0


def pct(xs, p):
    xs = sorted(xs)
    if not xs: return float('nan')
    k = (len(xs) - 1) * p / 100; f = int(k); c = min(f + 1, len(xs) - 1); return xs[f] + (xs[c] - xs[f]) * (k - f)


def par(fn, items, workers):
    """用 workers 个线程对 items 逐个调 fn,保持顺序返回结果。"""
    res = [None] * len(items); q = iter(enumerate(items)); lk = threading.Lock()
    def w():
        while True:
            with lk:
                try: i, x = next(q)
                except StopIteration: return
            res[i] = fn(x)
    ts = [threading.Thread(target=w) for _ in range(workers)]
    [t.start() for t in ts]; [t.join() for t in ts]; return res


def openloop(fn, rate, duration, workers=400):
    """开环负载:按固定到达率 rate(个/秒)发请求,不管上一个有没有回来。返回 [(发出时刻, fn 的返回值)]。"""
    out = []; lk = threading.Lock(); t0 = time.perf_counter(); n = int(rate * duration); sem = threading.Semaphore(workers); ths = []
    def one(i, ts):
        try: r = fn(i)
        finally: sem.release()
        with lk: out.append((ts, r))
    for i in range(n):
        target = t0 + i / rate; d = target - time.perf_counter()
        if d > 0: time.sleep(d)
        sem.acquire(); t = threading.Thread(target=one, args=(i, target - t0)); t.start(); ths.append(t)
    for t in ths: t.join()
    return out


class Nginx:
    """自己起一个 nginx(Homebrew),配置里只写 http 块里的内容 body;{port} 是监听端口。数据在 vtmp/<name>/。"""
    def __init__(self, name, body, port=None, extra_main=''):
        self.d = txl.tdir(name); self.port = port or free_port(); self.name = name
        for s in ('cb', 'pt', 'fc', 'uw', 'sc'): (self.d / s).mkdir(exist_ok=True)
        self.write(body, extra_main)
        self.p = None
    def write(self, body, extra_main=''):
        d = self.d
        conf = f"""worker_processes 1; daemon off; pid {d}/nginx.pid; error_log {d}/err.log info; {extra_main}
events {{ worker_connections 1024; }}
http {{
  {'' if 'access_log' in body else 'access_log off;'} client_body_temp_path {d}/cb; proxy_temp_path {d}/pt; fastcgi_temp_path {d}/fc; uwsgi_temp_path {d}/uw; scgi_temp_path {d}/sc;
{body.replace('{port}', str(self.port)).replace('{d}', str(d))}
}}
"""
        (d / 'nginx.conf').write_text(conf)
    def start(self):
        self.p = subprocess.Popen(['nginx', '-c', str(self.d / 'nginx.conf'), '-p', str(self.d)], stdout=subprocess.DEVNULL, stderr=open(self.d / 'stderr.txt', 'w'))
        wait_port(self.port, 20, self.p, self.d / 'stderr.txt'); txl._nodes.append(self); return self
    def reload(self):
        subprocess.run(['nginx', '-c', str(self.d / 'nginx.conf'), '-p', str(self.d), '-s', 'reload'], capture_output=True)
    def kill(self): self.stop()
    def stop(self):
        if self.p and self.p.poll() is None:
            self.p.terminate()
            try: self.p.wait(5)
            except Exception: self.p.kill()


# ---- 熔断器(v5 里讲的那个手写版,后面几篇复用)----
class Open(Exception): pass
class TooMany(Exception): pass

class Breaker:
    """手写的熔断器:连续失败 trip 次 → 打开;打开 open_s 秒后第一个到来的请求使它进入半开;半开最多放行 max_half 个请求,max_half 个连续成功 → 关闭,任何一次失败 → 立刻重新打开。clock 可替换成虚拟时钟。"""
    def __init__(self, trip=5, open_s=1.0, max_half=3, clock=time.perf_counter, log=None):
        self.trip, self.open_s, self.max_half, self.clock, self.log = trip, open_s, max_half, clock, log
        self.state = 'closed'; self.cf = 0; self.cs = 0; self.admitted = 0; self.opened_at = 0.0; self.lk = threading.Lock(); self.t0 = clock(); self.trans = []
    def _set(self, new):
        if new == self.state: return
        self.trans.append(((self.clock() - self.t0), self.state, new)); self.state = new
        self.cf = 0; self.cs = 0; self.admitted = 0
        if new == 'open': self.opened_at = self.clock()
    def call(self, fn):
        with self.lk:
            if self.state == 'open':
                if self.clock() - self.opened_at >= self.open_s: self._set('half-open')
                else: raise Open()
            if self.state == 'half-open':
                if self.admitted >= self.max_half: raise TooMany()
                self.admitted += 1
            gen = (self.state, len(self.trans))
        try: r = fn(); ok = True
        except Exception: ok = False
        with self.lk:
            if (self.state, len(self.trans)) == gen:        # 状态没有被别人改过才计数
                if ok:
                    if self.state == 'closed': self.cf = 0
                    else:
                        self.cs += 1
                        if self.cs >= self.max_half: self._set('closed')
                else:
                    if self.state == 'closed':
                        self.cf += 1
                        if self.cf >= self.trip: self._set('open')
                    else: self._set('open')
        if not ok: raise RuntimeError('boom')
        return r



# ---- 原始 TCP 服务(各种坏上游)----
class Raw:
    """原始 TCP 服务:每个连接交给 handler(conn)。"""
    def __init__(s, handler, backlog=128, rcvbuf=None):
        s.sock = socket.socket(); s.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if rcvbuf: s.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
        s.port = free_port(); s.sock.bind(('127.0.0.1', s.port)); s.sock.listen(backlog); s.handler = handler; s.stop = False; s.conns = []
        threading.Thread(target=s.loop, daemon=True).start()
    def loop(s):
        while not s.stop:
            try: c, _ = s.sock.accept()
            except Exception: return
            s.conns.append(c); threading.Thread(target=s.safe, args=(c,), daemon=True).start()
    def safe(s, c):
        try: s.handler(c)
        except Exception: pass
    def close(s):
        s.stop = True
        for c in s.conns:
            try: c.close()
            except Exception: pass
        try: s.sock.close()
        except Exception: pass
def read_req(c):
    d = b''
    while b'\r\n\r\n' not in d:
        x = c.recv(65536)
        if not x: return None
        d += x
    return d


class Envoy:
    """自己起一个 Envoy(Homebrew),静态配置 YAML 由调用者给(用 {port} 占位监听端口)。数据在 vtmp/<name>/。"""
    def __init__(self, name, yaml_text, port=None):
        self.d = txl.tdir(name); self.port = port or free_port(); self.p = None; self.name = name
        (self.d / 'envoy.yaml').write_text(yaml_text.replace('{port}', str(self.port)))
    def start(self, extra=()):
        self.p = subprocess.Popen(['envoy', '-c', str(self.d / 'envoy.yaml'), '--concurrency', '1', '--disable-hot-restart', '-l', 'warning', '--base-id', str(random.randrange(1, 10**6))] + list(extra), stdout=open(self.d / 'out.log', 'w'), stderr=subprocess.STDOUT)
        wait_port(self.port, 30, self.p, self.d / 'out.log'); txl._nodes.append(self); return self
    def kill(self): self.stop()
    def stop(self):
        if self.p and self.p.poll() is None:
            self.p.terminate()
            try: self.p.wait(5)
            except Exception: self.p.kill()


def envoy_http_conf(routes, clusters, extra_hcm='', pre_filters=''):
    """routes: 已缩进好的 routes 列表文本;clusters: {名字: [端口,...]}"""
    cl = ''
    for n, ports in clusters.items():
        eps = ''.join(f'\n        - endpoint: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {p}}}}}}}' for p in ports)
        cl += f'''
  - name: {n}
    type: STATIC
    connect_timeout: 1s
    load_assignment:
      cluster_name: {n}
      endpoints:
      - lb_endpoints:{eps}'''
    return f'''static_resources:
  listeners:
  - name: l
    address: {{socket_address: {{address: 127.0.0.1, port_value: {{port}}}}}}
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress
          {extra_hcm}
          route_config:
            virtual_hosts:
            - name: all
              domains: ["*"]
              routes:
{routes}
          http_filters:
{pre_filters}
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
  clusters:{cl}
'''


class ConsulCluster:
    """n 个 server 的 Consul 集群(Homebrew 的 consul),全部在 127.0.0.1,各用一组端口。数据在 vtmp/<name>_<i>/。"""
    def __init__(self, name, n=3):
        self.name, self.n = name, n; self.ports = [dict(http=free_port(), grpc=free_port(), grpc_tls=free_port(), dns=free_port(), lan=free_port(), wan=free_port(), srv=free_port()) for _ in range(n)]; self.procs = [None] * n
    def start_node(self, i):
        d = txl.tdir(f'{self.name}_{i}', clean=False); p = self.ports[i]
        cmd = ['consul', 'agent', '-server', f'-bootstrap-expect={self.n}', f'-node={self.name}n{i}', '-bind=127.0.0.1', '-client=127.0.0.1', f'-http-port={p["http"]}', f'-grpc-port={p["grpc"]}', f'-grpc-tls-port={p["grpc_tls"]}', f'-dns-port={p["dns"]}', f'-serf-lan-port={p["lan"]}', f'-serf-wan-port={p["wan"]}', f'-server-port={p["srv"]}', f'-data-dir={d}/data', '-log-level=warn', '-disable-host-node-id']
        if i > 0: cmd.append(f'-retry-join=127.0.0.1:{self.ports[0]["lan"]}')
        self.procs[i] = subprocess.Popen(cmd, stdout=open(d / 'consul.log', 'a'), stderr=subprocess.STDOUT, start_new_session=True)
    def start(self):
        for i in range(self.n): self.start_node(i)
        self.wait_leader(60); time.sleep(1.0); return self
    def kill_node(self, i):
        if self.procs[i] and self.procs[i].poll() is None: os.killpg(self.procs[i].pid, signal.SIGKILL); self.procs[i].wait()
    def http(self, i, method, path, body=None, timeout=3.0, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.ports[i]['http'], timeout=timeout)
        try:
            c.request(method, path, body=(body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()), headers=headers or {}); r = c.getresponse(); d = r.read(); return r.status, d
        finally: c.close()
    def leader(self, i=None):
        for k in ([i] if i is not None else range(self.n)):
            if self.procs[k] is None or self.procs[k].poll() is not None: continue
            try:
                s, d = self.http(k, 'GET', '/v1/status/leader', timeout=1.0)
                if s == 200 and d.strip() not in (b'""', b''): return json.loads(d)
            except Exception: pass
        return None
    def wait_leader(self, timeout=30):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.leader(): return True
            time.sleep(0.2)
        return False
    def stop_all(self):
        for i in range(self.n): self.kill_node(i)


class ConsulAgent:
    """Consul 的 client 模式 agent(不是 server,不参与 Raft):通过 gossip 加入 cluster,服务和健康检查登记在它本地,再同步给 server。"""
    def __init__(self, name, cluster):
        self.name, self.cl = name, cluster; self.p = dict(http=free_port(), grpc=free_port(), grpc_tls=free_port(), dns=free_port(), lan=free_port()); self.proc = None
        self.node = name
    def start(self, wait=True):
        d = txl.tdir(f'{self.name}', clean=False); p = self.p
        cmd = ['consul', 'agent', f'-node={self.node}', '-bind=127.0.0.1', '-client=127.0.0.1', f'-http-port={p["http"]}', f'-grpc-port={p["grpc"]}', f'-grpc-tls-port={p["grpc_tls"]}', f'-dns-port={p["dns"]}', f'-serf-lan-port={p["lan"]}', f'-data-dir={d}/data', '-log-level=warn', '-disable-host-node-id'] + [f'-retry-join=127.0.0.1:{q["lan"]}' for q in self.cl.ports]
        self.proc = subprocess.Popen(cmd, stdout=open(d / 'consul.log', 'a'), stderr=subprocess.STDOUT, start_new_session=True)
        if wait:
            t0 = time.time()
            while time.time() - t0 < 30:
                try:
                    s, b = self.http('GET', '/v1/agent/self', timeout=1.0)
                    if s == 200: return self
                except Exception: pass
                time.sleep(0.1)
        return self
    def kill(self):
        if self.proc and self.proc.poll() is None: os.killpg(self.proc.pid, signal.SIGKILL); self.proc.wait()
    def http(self, method, path, body=None, timeout=3.0, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.p['http'], timeout=timeout)
        try:
            c.request(method, path, body=(body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()), headers=headers or {}); r = c.getresponse(); d = r.read(); return r.status, d
        finally: c.close()


class Nacos:
    """Nacos(3.x,vtmp/nacos 里解压的发行版)单机或多节点。每个实例有自己的 home(conf 拷贝、logs、data),共享同一个 jar。
    端口:main(HTTP)、console、main+1000(gRPC 客户端)、main+1001(gRPC 集群)。JVM 用 Temurin 17。"""
    DIST = pathlib.Path(__file__).parent / 'vtmp/nacos/nacos'
    JAVA = '/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home/bin/java'
    def __init__(self, name, main_port, console_port=None, members=None, mem='-Xms256m -Xmx512m'):
        for p_ in (main_port, main_port + 1, main_port + 1000, main_port + 1001):     # Nacos 的 gRPC 端口是主端口 + 1000 / + 1001;本机上别的程序(例如企业微信占着 9884)占了就会连不上,事先检查
            s_ = socket.socket(); s_.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)     # 刚关掉的连接处于 TIME_WAIT 时不算占用
            try: s_.bind(('127.0.0.1', p_))
            except OSError: raise RuntimeError(f'Nacos 需要的端口 {p_} 已被占用,换一个主端口')
            finally: s_.close()
        self.name, self.main, self.mem = name, main_port, mem; self.console = console_port or (main_port + 1)
        self.home = txl.tdir(f'nacos_{name}'); self.p = None; self.members = members
        for sub in ('plugins', ):
            os.symlink(self.DIST / sub, self.home / sub)
        shutil.copytree(self.DIST / 'conf', self.home / 'conf'); (self.home / 'logs').mkdir(); (self.home / 'data').mkdir()
        props = (self.home / 'conf/application.properties').read_text()
        props += f'\nnacos.server.main.port={main_port}\nnacos.console.port={self.console}\nnacos.core.auth.enabled=false\nnacos.core.auth.admin.enabled=false\nnacos.core.auth.console.enabled=false\n'
        (self.home / 'conf/application.properties').write_text(props)
        if members: (self.home / 'conf/cluster.conf').write_text('\n'.join(f'127.0.0.1:{m}' for m in members) + '\n')
    def start(self, wait=True):
        standalone = self.members is None
        cmd = [self.JAVA] + self.mem.split() + ['-server', '-Duser.home=' + str(self.home), f'-Dnacos.standalone={"true" if standalone else "false"}', '-DembeddedStorage=true', f'-Dnacos.home={self.home}',
               f'-Dloader.path={self.home}/plugins,{self.home}/plugins/health,{self.home}/plugins/cmdb,{self.home}/plugins/selector', '--add-opens=java.base/java.lang=ALL-UNNAMED', '--add-opens=java.base/java.lang.reflect=ALL-UNNAMED', '--add-opens=java.base/java.util=ALL-UNNAMED',
               '-Dnacos.deployment.type=merged', '-jar', str(self.DIST / 'target/nacos-server.jar'), f'--spring.config.additional-location=file:{self.home}/conf/', f'--logging.config={self.home}/conf/nacos-logback.xml', '--server.max-http-request-header-size=524288']
        self.p = subprocess.Popen(cmd, stdout=open(self.home / 'logs/stdout.log', 'w'), stderr=subprocess.STDOUT, start_new_session=True, env={**os.environ, 'JAVA_HOME': '/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home'})
        txl._nodes.append(self)
        if wait: wait_port(self.main, 120, self.p, self.home / 'logs/stdout.log')
        return self
    def kill(self):
        if self.p and self.p.poll() is None:
            try: os.killpg(self.p.pid, signal.SIGKILL)
            except Exception: pass
            self.p.wait()
    stop = kill
    def http(self, method, path, params=None, body=None, timeout=5.0, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.main, timeout=timeout)
        try:
            q = ('?' + '&'.join(f'{k}={v}' for k, v in (params or {}).items())) if params else ''
            data = None
            if body is not None: data = body if isinstance(body, bytes) else '&'.join(f'{k}={v}' for k, v in body.items()).encode(); headers = {**(headers or {}), 'Content-Type': 'application/x-www-form-urlencoded'}
            c.request(method, path + q, body=data, headers=headers or {}); r = c.getresponse(); d = r.read(); return r.status, d
        finally: c.close()


def _clean_env():
    return {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}


class Prom:
    """Prometheus(vtmp/dl 里解压的发行版):cfg 是 prometheus.yml 全文;数据在 vtmp/<name>/data。可以 start / reload / query / query_range / stop。"""
    DIST = pathlib.Path(__file__).parent / 'vtmp/dl/prom/prometheus-3.15.0.darwin-arm64'
    def __init__(self, name, cfg, port=None, flags=()):
        self.d = txl.tdir(name); self.port = port or free_port(); self.flags = list(flags); (self.d / 'prometheus.yml').write_text(cfg); self.p = None; self.name = name
    def start(self):
        cmd = [str(self.DIST / 'prometheus'), f'--config.file={self.d}/prometheus.yml', f'--storage.tsdb.path={self.d}/data', f'--web.listen-address=127.0.0.1:{self.port}', '--log.level=warn', '--web.enable-lifecycle'] + self.flags
        self.p = subprocess.Popen(cmd, stdout=open(self.d / 'out.log', 'w'), stderr=subprocess.STDOUT, env=_clean_env(), start_new_session=True)
        wait_port(self.port, 30, self.p, self.d / 'out.log'); txl._nodes.append(self); return self
    def _get(self, path, params, timeout=10.0):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=timeout)
        try:
            c.request('GET', path + '?' + urllib.parse.urlencode(params)); r = c.getresponse(); d = r.read(); return r.status, json.loads(d)
        finally: c.close()
    def query(self, q, t=None):
        p = {'query': q}
        if t is not None: p['time'] = t
        s, j = self._get('/api/v1/query', p); return j['data']['result'] if j.get('status') == 'success' else j
    def query_range(self, q, start, end, step):
        s, j = self._get('/api/v1/query_range', {'query': q, 'start': start, 'end': end, 'step': step}); return j['data']['result'] if j.get('status') == 'success' else j
    def reload(self):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10); c.request('POST', '/-/reload'); r = c.getresponse(); r.read(); c.close(); return r.status
    def write_cfg(self, cfg): (self.d / 'prometheus.yml').write_text(cfg)
    def kill(self): self.stop()
    def stop(self):
        if self.p and self.p.poll() is None:
            try: os.killpg(self.p.pid, signal.SIGTERM)
            except Exception: pass
            try: self.p.wait(8)
            except Exception: os.killpg(self.p.pid, signal.SIGKILL)


class Alertmgr:
    """Alertmanager(vtmp/dl)。cfg 是 alertmanager.yml 全文。"""
    DIST = pathlib.Path(__file__).parent / 'vtmp/dl/am/alertmanager-0.34.1.darwin-arm64'
    def __init__(self, name, cfg, port=None):
        self.d = txl.tdir(name); self.port = port or free_port(); self.cport = free_port(); (self.d / 'alertmanager.yml').write_text(cfg); self.p = None
    def start(self):
        cmd = [str(self.DIST / 'alertmanager'), f'--config.file={self.d}/alertmanager.yml', f'--storage.path={self.d}/data', f'--web.listen-address=127.0.0.1:{self.port}', f'--cluster.listen-address=127.0.0.1:{self.cport}', '--log.level=warn']
        self.p = subprocess.Popen(cmd, stdout=open(self.d / 'out.log', 'w'), stderr=subprocess.STDOUT, env=_clean_env(), start_new_session=True)
        wait_port(self.port, 30, self.p, self.d / 'out.log'); txl._nodes.append(self); return self
    def get(self, path):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        try: c.request('GET', path); r = c.getresponse(); return r.status, json.loads(r.read() or b'null')
        finally: c.close()
    def kill(self): self.stop()
    def stop(self):
        if self.p and self.p.poll() is None:
            try: os.killpg(self.p.pid, signal.SIGTERM)
            except Exception: pass
            try: self.p.wait(8)
            except Exception: os.killpg(self.p.pid, signal.SIGKILL)


class Otelcol:
    """OpenTelemetry Collector contrib(vtmp/dl/otel)。cfg 是配置全文;wait_port 是用来判断启动完成的端口(某个 receiver 的端口)。"""
    BIN = pathlib.Path(__file__).parent / 'vtmp/dl/otel/otelcol-contrib'
    def __init__(self, name, cfg, wait_port_=None):
        self.d = txl.tdir(name); (self.d / 'otel.yaml').write_text(cfg); self.p = None; self.wp = wait_port_
    def start(self):
        self.p = subprocess.Popen([str(self.BIN), f'--config={self.d}/otel.yaml'], stdout=open(self.d / 'out.log', 'w'), stderr=subprocess.STDOUT, env=_clean_env(), start_new_session=True)
        if self.wp: wait_port(self.wp, 30, self.p, self.d / 'out.log')
        txl._nodes.append(self); return self
    def log(self): return (self.d / 'out.log').read_text(errors='replace')
    def kill(self): self.stop()
    def stop(self):
        if self.p and self.p.poll() is None:
            try: os.killpg(self.p.pid, signal.SIGTERM)
            except Exception: pass
            try: self.p.wait(8)
            except Exception: os.killpg(self.p.pid, signal.SIGKILL)


class MiniDNS:
    """很小的权威 DNS 服务(dnspython 解析与构造报文):UDP 和 TCP,区域可以随时修改。zone[(名字, 类型)] = [(ttl, rdata 文本), ...];neg_ttl 是 NXDOMAIN 的 SOA minimum(负缓存时间)。统计收到的查询数。"""
    def __init__(self, neg_ttl=30):
        import dns.message, dns.rrset, dns.rdatatype, dns.rcode, dns.flags, dns.name, dns.rdataclass
        self.d = dict(msg=dns.message, rrset=dns.rrset, rt=dns.rdatatype, rc=dns.rcode, fl=dns.flags, nm=dns.name, rcl=dns.rdataclass)
        self.zone = {}; self.neg_ttl = neg_ttl; self.queries = 0; self.udp_queries = 0; self.tcp_queries = 0; self.lk = threading.Lock(); self.port = free_port(); self.stop_ = False
        self.us = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); self.us.bind(('127.0.0.1', self.port))
        self.ts = socket.socket(); self.ts.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); self.ts.bind(('127.0.0.1', self.port)); self.ts.listen(32)
        threading.Thread(target=self._udp, daemon=True).start(); threading.Thread(target=self._tcp, daemon=True).start()
    def set(self, name, rdtype, recs):
        with self.lk: self.zone[(name.lower().rstrip('.') + '.', rdtype)] = list(recs)
    def delete(self, name, rdtype):
        with self.lk: self.zone.pop((name.lower().rstrip('.') + '.', rdtype), None)
    def answer(self, data, limit):
        d = self.d; q = d['msg'].from_wire(data); r = d['msg'].make_response(q); qn = q.question[0].name.to_text().lower(); qt = d['rt'].to_text(q.question[0].rdtype)
        with self.lk:
            recs = self.zone.get((qn, qt)); names = {k[0] for k in self.zone}
            r.flags |= d['fl'].AA
            if recs:
                for ttl, txt in recs: r.answer.append(d['rrset'].from_text(qn, ttl, 'IN', qt, txt))
            elif qn in names: pass
            else:
                r.set_rcode(d['rc'].NXDOMAIN); r.authority.append(d['rrset'].from_text('svc.local.', self.neg_ttl, 'IN', 'SOA', f'ns.svc.local. admin.svc.local. 1 3600 600 86400 {self.neg_ttl}'))
        if q.edns >= 0: r.use_edns(0, 0, 4096)
        wire = r.to_wire()
        if len(wire) > limit:
            r.flags |= d['fl'].TC; r.answer = []; wire = r.to_wire()
        return wire
    def _udp(self):
        while not self.stop_:
            try: data, a = self.us.recvfrom(65535)
            except Exception: return
            self.queries += 1; self.udp_queries += 1
            try:
                q = self.d['msg'].from_wire(data); limit = 4096 if q.edns >= 0 else 512; self.us.sendto(self.answer(data, limit), a)
            except Exception: pass
    def _tcp(self):
        while not self.stop_:
            try: c, _ = self.ts.accept()
            except Exception: return
            threading.Thread(target=self._tcp_conn, args=(c,), daemon=True).start()
    def _tcp_conn(self, c):
        try:
            while True:
                h = c.recv(2)
                if len(h) < 2: return
                n = int.from_bytes(h, 'big'); data = b''
                while len(data) < n: data += c.recv(n - len(data))
                self.queries += 1; self.tcp_queries += 1; w = self.answer(data, 65535); c.sendall(len(w).to_bytes(2, 'big') + w)
        except Exception: pass
        finally: c.close()
    def close(self):
        self.stop_ = True
        for s in (self.us, self.ts):
            try: s.close()
            except Exception: pass
