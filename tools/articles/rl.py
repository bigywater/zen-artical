"""redis 实验辅助:起独立实例(端口 7000+,数据目录在 rdata/),纯标准库 RESP2 客户端。
绝不碰 6379(用户自己的 redis)。所有实验都先 unset 代理。"""
import os, socket, subprocess, time, shutil, pathlib, json, sys, select

HERE = pathlib.Path(__file__).parent
RDATA = HERE / 'rdata'
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
    os.environ.pop(k, None)


class Err(Exception):
    pass


class C:
    """最小 RESP2 客户端。"""
    def __init__(self, port, host='127.0.0.1', timeout=10, password=None, user=None):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buf = bytearray()
        if password is not None:
            self.do(*(['AUTH'] + ([user] if user else []) + [password]))

    @staticmethod
    def enc(args):
        out = [b'*%d\r\n' % len(args)]
        for a in args:
            if not isinstance(a, bytes):
                a = str(a).encode()
            out.append(b'$%d\r\n%s\r\n' % (len(a), a))
        return b''.join(out)

    def send(self, *args):
        self.s.sendall(self.enc(args))

    def _fill(self):
        d = self.s.recv(65536)
        if not d:
            raise EOFError('closed')
        self.buf += d

    def _line(self):
        while True:
            i = self.buf.find(b'\r\n')
            if i >= 0:
                l = bytes(self.buf[:i + 2]); del self.buf[:i + 2]; return l
            self._fill()

    def _n(self, n):
        while len(self.buf) < n:
            self._fill()
        d = bytes(self.buf[:n]); del self.buf[:n]; return d

    def avail(self, timeout=0.0):
        """有可读数据(缓冲区里或套接字上)吗;不消费。"""
        if self.buf:
            return True
        r, _, _ = select.select([self.s], [], [], timeout)
        return bool(r)

    def read(self, raw=False):
        l = self._line()
        t, b = l[:1], l[1:-2]
        if t == b'+':
            return b.decode()
        if t == b'-':
            return Err(b.decode())
        if t == b':':
            return int(b)
        if t == b'$':
            n = int(b)
            if n < 0:
                return None
            d = self._n(n + 2)[:-2]
            return d if raw else d.decode('utf-8', 'replace')
        if t == b'*':
            n = int(b)
            if n < 0:
                return None
            return [self.read(raw) for _ in range(n)]
        raise ValueError(l)

    def do(self, *args, raw=False, raise_err=True):
        self.send(*args)
        r = self.read(raw)
        if isinstance(r, Err) and raise_err:
            raise r
        return r

    def pipeline(self, cmds):
        self.s.sendall(b''.join(self.enc(c) for c in cmds))
        return [self.read() for _ in cmds]

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def info(c, section=None):
    t = c.do('INFO', *([section] if section else []))
    d = {}
    for l in t.splitlines():
        if ':' in l and not l.startswith('#'):
            k, v = l.split(':', 1)
            d[k] = v
    return d


def kv(lst):
    return {lst[i]: lst[i + 1] for i in range(0, len(lst), 2)}


class Node:
    def __init__(self, port, name=None, conf=None, sentinel=False, args=()):
        assert port != 6379
        self.port, self.name = port, name or f'n{port}'
        self.dir = RDATA / self.name
        shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True)
        self.conf = dict(conf or {})
        self.sentinel = sentinel
        self.args = list(args)
        self.p = None

    def confpath(self):
        return self.dir / ('sentinel.conf' if self.sentinel else 'redis.conf')

    def write_conf(self):
        d = {'port': self.port, 'bind': '127.0.0.1', 'dir': str(self.dir), 'daemonize': 'no', 'save': '""',
             'appendonly': 'no', 'logfile': str(self.dir / 'redis.log'), 'protected-mode': 'no'}
        if self.sentinel:
            d.pop('save'); d.pop('appendonly')
        d.update(self.conf)
        lines = []
        for k, v in d.items():
            if isinstance(v, (list, tuple)):
                lines += [f'{k} {x}' for x in v]
            else:
                lines.append(f'{k} {v}')
        self.confpath().write_text('\n'.join(lines) + '\n')

    def start(self, wait=True, rewrite=True):
        try:
            socket.create_connection(('127.0.0.1', self.port), timeout=0.3).close()
            raise RuntimeError(f'port {self.port} already in use')
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            if isinstance(e, RuntimeError):
                raise
        if rewrite:
            self.write_conf()
        cmd = ['redis-server', str(self.confpath())] + (['--sentinel'] if self.sentinel else []) + self.args
        self.p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=self.dir)
        if wait:
            self.wait_up()
        return self

    def wait_up(self, timeout=30):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                c = C(self.port, timeout=2)
                c.do('PING', raise_err=False)
                c.close()
                return
            except Exception:
                time.sleep(0.05)
        raise RuntimeError(f'node {self.port} not up')

    def c(self, **kw):
        return C(self.port, **kw)

    def stop(self, sig=15):
        if self.p and self.p.poll() is None:
            self.p.send_signal(sig)
            try:
                self.p.wait(10)
            except Exception:
                self.p.kill()

    def kill9(self):
        self.stop(9)

    def log(self):
        p = self.dir / 'redis.log'
        return p.read_text() if p.exists() else ''


def cleanup(nodes):
    for n in nodes:
        try:
            n.stop()
        except Exception:
            pass


def save(name, obj):
    (HERE / 'out' / f'{name}.json').write_text(json.dumps(obj, ensure_ascii=False, indent=1))


class Tee:
    """把 stdout 同时写 out/NAME.txt,保证文章里贴的就是真输出。"""
    def __init__(self, name):
        self.f = open(HERE / 'out' / f'{name}.txt', 'w')
        self.o = sys.stdout

    def write(self, s):
        self.f.write(s); self.o.write(s); self.f.flush(); self.o.flush()

    def flush(self):
        self.f.flush(); self.o.flush()


def tee(name):
    sys.stdout = Tee(name)


# ---------- redis-cli 风格输出 ----------
def fmt(r, ind=0):
    pad = ' ' * ind
    if r is None:
        return '(nil)'
    if isinstance(r, Err):
        return f'(error) {r}'
    if isinstance(r, int):
        return f'(integer) {r}'
    if isinstance(r, str):
        return json.dumps(r, ensure_ascii=False)
    if isinstance(r, list):
        if not r:
            return '(empty array)'
        lines = []
        w = len(str(len(r)))
        for i, x in enumerate(r, 1):
            head = f'{i}) '.rjust(w + 2)
            s = fmt(x, ind + len(head))
            lines.append((pad if i > 1 else '') + head + s)
        return '\n'.join(lines)
    return str(r)


def sh(c, *args, show=True, cut=None):
    """执行并像 redis-cli 那样打印,返回原始结果。"""
    r = c.do(*args, raise_err=False)
    if show:
        cmd = ' '.join(str(a) if (' ' not in str(a) and str(a) != '') else json.dumps(str(a), ensure_ascii=False) for a in args)
        print(f'> {cmd}')
        s = fmt(r)
        if cut and len(s.splitlines()) > cut:
            L = s.splitlines()
            s = '\n'.join(L[:cut] + [f'... (共 {len(L)} 行)'])
        print(s)
    return r


def used_mem(c):
    return int(info(c, 'memory')['used_memory'])


def wait_link(c, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        i = info(c, 'replication')
        if i.get('master_link_status') == 'up' and i.get('master_sync_in_progress', '0') == '0':
            return i
        time.sleep(0.05)
    raise RuntimeError('link not up: ' + str(info(c, 'replication')))


def repl_stats(c):
    s = info(c, 'stats')
    return {k: int(s[k]) for k in ('sync_full', 'sync_partial_ok', 'sync_partial_err')}


def logtail(node, pat, maxn=40):
    return [l for l in node.log().splitlines() if pat.lower() in l.lower()][-maxn:]


class Proxy:
    """TCP 转发:可以随时 cut()(关闭监听并断开所有连接,模拟网络中断)和 resume()。"""
    def __init__(self, lport, tport):
        self.lport, self.tport = lport, tport
        self.conns = []; self.ls = None; self.alive = False
        self.resume()

    def resume(self):
        self.ls = socket.socket(); self.ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ls.bind(('127.0.0.1', self.lport)); self.ls.listen(8); self.alive = True
        import threading
        threading.Thread(target=self._accept, args=(self.ls,), daemon=True).start()

    def _accept(self, ls):
        import threading
        while self.alive:
            try:
                a, _ = ls.accept()
            except Exception:
                return
            try:
                b = socket.create_connection(('127.0.0.1', self.tport))
            except Exception:
                a.close(); continue
            self.conns += [a, b]
            for x, y in ((a, b), (b, a)):
                threading.Thread(target=self._pump, args=(x, y), daemon=True).start()

    @staticmethod
    def _pump(x, y):
        try:
            while True:
                d = x.recv(65536)
                if not d:
                    break
                y.sendall(d)
        except Exception:
            pass
        for s in (x, y):
            try:
                s.close()
            except Exception:
                pass

    def cut(self):
        self.alive = False
        try:
            self.ls.close()
        except Exception:
            pass
        for s in self.conns:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass
        self.conns = []


def wait_loaded(node, timeout=120):
    """等实例加载完数据集(INFO loading:0);返回从调用起的耗时。"""
    t0 = time.time(); c = node.c()
    while time.time() - t0 < timeout:
        try:
            if info(c, 'persistence')['loading'] == '0':
                return time.time() - t0
        except Exception:
            pass
        time.sleep(0.01)
    raise RuntimeError('still loading')


# ---------- Redis Cluster ----------
def _crc16_table():
    t = []
    for i in range(256):
        c = i << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
        t.append(c)
    return t


_T16 = _crc16_table()


def crc16(data):
    if isinstance(data, str):
        data = data.encode()
    c = 0
    for b in data:
        c = ((c << 8) & 0xFFFF) ^ _T16[((c >> 8) ^ b) & 0xFF]
    return c


def keyslot(key):
    if isinstance(key, str):
        key = key.encode()
    s = key.find(b'{')
    if s >= 0:
        e = key.find(b'}', s + 1)
        if e > s + 1:
            key = key[s + 1:e]
    return crc16(key) % 16384


class Cluster:
    """本机 Redis Cluster:masters 个主库 + 每个主库 replicas 个从库,端口 base..base+N-1。"""
    def __init__(self, base=7300, masters=3, replicas=1, conf=None, name='cl'):
        self.base = base
        self.nodes = []
        total = masters * (1 + replicas)
        for i in range(total):
            cf = {'cluster-enabled': 'yes', 'cluster-config-file': 'nodes.conf', 'cluster-node-timeout': '3000', 'appendonly': 'no', 'repl-diskless-sync-delay': '0'}
            cf.update(conf or {})
            self.nodes.append(Node(base + i, name=f'{name}{base + i}', conf=cf))
        for n in self.nodes:
            n.start()
        cmd = ['redis-cli', '--cluster', 'create'] + [f'127.0.0.1:{n.port}' for n in self.nodes] + ['--cluster-replicas', str(replicas), '--cluster-yes']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        self.create_out = r.stdout
        self.wait_ok()
        self.wait_replicas()

    def wait_ok(self, timeout=60, nodes=None):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                ok = all(info(n.c(), 'cluster') is not None and n.c().do('CLUSTER', 'INFO').count('cluster_state:ok') for n in (nodes or self.nodes))
                if ok:
                    # 等到所有节点都看到全部槽位
                    if all('cluster_slots_assigned:16384' in n.c().do('CLUSTER', 'INFO') for n in (nodes or self.nodes)):
                        return time.time() - t0
            except Exception:
                pass
            time.sleep(0.2)
        raise RuntimeError('cluster not ok')

    def wait_replicas(self, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if all(info(n.c(), 'replication').get('master_link_status') == 'up' for n in self.nodes if info(n.c(), 'replication')['role'] == 'slave'):
                    return time.time() - t0
            except Exception:
                pass
            time.sleep(0.2)
        raise RuntimeError('replicas not up')

    def masters(self):
        return [n for n in self.nodes if 'master' in n.c().do('ROLE')[0]]

    def cleanup(self):
        cleanup(self.nodes)


def cluster_nodes(c):
    """解析 CLUSTER NODES → [dict]"""
    out = []
    for l in c.do('CLUSTER', 'NODES').splitlines():
        p = l.split()
        if len(p) < 8:
            continue
        addr = p[1].split('@')[0]
        out.append(dict(id=p[0], addr=addr, port=int(addr.split(':')[1]) if ':' in addr else 0, flags=p[2].split(','), master=p[3], ping=p[4], pong=p[5], epoch=int(p[6]), link=p[7], slots=p[8:]))
    return out


def slot_owner_map(c):
    m = {}
    for start, end, master, *rest in c.do('CLUSTER', 'SLOTS'):
        for s in range(start, end + 1):
            m[s] = int(master[1])
    return m


class CC:
    """极简集群客户端:缓存槽位表,处理 MOVED / ASK,统计重定向次数。"""
    def __init__(self, ports, refresh_on_moved=True, init_map=True, on_moved='slot'):
        self.on_moved = on_moved if refresh_on_moved else 'none'
        self.ports = list(ports)
        self.conns = {}
        self.slots = {}
        self.moved = 0
        self.ask = 0
        self.requests = 0
        self.refresh_on_moved = refresh_on_moved
        if init_map:
            self.refresh()

    def conn(self, port):
        if port not in self.conns:
            self.conns[port] = C(port, timeout=5)
        return self.conns[port]

    def refresh(self):
        for p in list(self.conns) + self.ports:
            try:
                self.slots = slot_owner_map(self.conn(p))
                return
            except Exception:
                self.conns.pop(p, None)
        raise RuntimeError('cannot refresh slots')

    def do(self, key, *args, hops=8):
        self.requests += 1
        slot = keyslot(key)
        port = self.slots.get(slot, self.ports[0])
        asking = False
        for _ in range(hops):
            try:
                c = self.conn(port)
                if asking:
                    c.do('ASKING')
                    asking = False
                r = c.do(*args, raise_err=False)
            except (EOFError, ConnectionError, OSError, socket.timeout):
                self.conns.pop(port, None)
                time.sleep(0.05)
                self.refresh()
                port = self.slots.get(slot, self.ports[0])
                continue
            if isinstance(r, Err):
                msg = str(r)
                if msg.startswith('MOVED'):
                    self.moved += 1
                    port = int(msg.split()[2].split(':')[1])
                    if self.on_moved == 'slot':
                        self.slots[slot] = port
                    elif self.on_moved == 'full':
                        self.refresh()
                    continue
                if msg.startswith('ASK'):
                    self.ask += 1
                    port = int(msg.split()[2].split(':')[1])
                    asking = True
                    continue
                if msg.startswith('TRYAGAIN') or msg.startswith('CLUSTERDOWN'):
                    time.sleep(0.05)
                    continue
                raise r
            return r
        raise RuntimeError('too many redirects')


# ---------- Sentinel ----------
class SentinelSet:
    """1 主 + n 从 + m 个 sentinel,全在本机。主库端口 base,从库 base+1…,sentinel 端口 sbase…"""
    def __init__(self, base=7600, replicas=2, sbase=7620, sentinels=3, quorum=2, down_after=3000, failover_timeout=10000, parallel=1, node_conf=None, name='st', sentinel_extra=None):
        self.base, self.sbase, self.quorum = base, sbase, quorum
        nc = {'repl-diskless-sync-delay': '0'}
        nc.update(node_conf or {})
        self.nodes = [Node(base, name=f'{name}{base}', conf=nc)]
        for i in range(replicas):
            c = dict(nc); c['replicaof'] = f'127.0.0.1 {base}'
            self.nodes.append(Node(base + 1 + i, name=f'{name}{base+1+i}', conf=c))
        self.sents = []
        for i in range(sentinels):
            conf = {'sentinel monitor': f'mymaster 127.0.0.1 {base} {quorum}', 'sentinel down-after-milliseconds': f'mymaster {down_after}',
                    'sentinel failover-timeout': f'mymaster {failover_timeout}', 'sentinel parallel-syncs': f'mymaster {parallel}'}
            conf.update(sentinel_extra or {})
            self.sents.append(Node(sbase + i, name=f'{name}s{sbase+i}', conf=conf, sentinel=True))
        for n in self.nodes:
            n.start()
        for n in self.nodes[1:]:
            wait_link(n.c())
        for s in self.sents:
            s.start()
        self.wait_ready()

    def wait_ready(self, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                ok = True
                for s in self.sents:
                    m = kv(s.c().do('SENTINEL', 'MASTER', 'mymaster'))
                    if int(m['num-slaves']) < len(self.nodes) - 1 or int(m['num-other-sentinels']) < len(self.sents) - 1:
                        ok = False
                if ok:
                    return time.time() - t0
            except Exception:
                pass
            time.sleep(0.2)
        raise RuntimeError('sentinels not ready')

    def addr(self, i=0):
        r = self.sents[i].c().do('SENTINEL', 'GET-MASTER-ADDR-BY-NAME', 'mymaster')
        return (r[0], int(r[1])) if r else None

    def cleanup(self):
        cleanup(self.sents + self.nodes)


def sentinel_master(c):
    return kv(c.do('SENTINEL', 'MASTER', 'mymaster'))


class DelayProxy:
    """给每个方向的转发加固定延迟(毫秒),模拟网络往返;delay_ms 是单向延迟。"""
    def __init__(self, lport, tport, delay_ms):
        self.lport, self.tport, self.d = lport, tport, delay_ms / 1000.0
        self.ls = socket.socket(); self.ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ls.bind(('127.0.0.1', lport)); self.ls.listen(16); self.alive = True
        import threading
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        import threading
        while self.alive:
            try:
                a, _ = self.ls.accept()
            except Exception:
                return
            b = socket.create_connection(('127.0.0.1', self.tport))
            for x in (a, b):
                x.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            for x, y in ((a, b), (b, a)):
                threading.Thread(target=self._pump, args=(x, y), daemon=True).start()

    def _pump(self, x, y):
        import queue, threading
        q = queue.Queue()

        def sender():
            while True:
                t, d = q.get()
                if d is None:
                    break
                w = t + self.d - time.perf_counter()
                if w > 0:
                    time.sleep(w)
                try:
                    y.sendall(d)
                except Exception:
                    break
        threading.Thread(target=sender, daemon=True).start()
        try:
            while True:
                d = x.recv(1 << 20)
                if not d:
                    break
                q.put((time.perf_counter(), d))
        except Exception:
            pass
        q.put((0, None))

    def close(self):
        self.alive = False
        try:
            self.ls.close()
        except Exception:
            pass
