"""ZooKeeper 实验辅助:自己起 ZooKeeper 3.9.6 进程(java -cp … QuorumPeerMain),端口 7300+/7400+/7500+,数据在 zkdata/。
绝不碰 2181、8080(用户的 weed)、/opt/homebrew/etc/zookeeper/zoo.cfg。"""
import os, sys, subprocess, socket, time, pathlib, shutil, signal, threading, re, textwrap
from dj import HERE
import rl
from rl import tee, save
ZH = pathlib.Path('/opt/homebrew/Cellar/zookeeper/3.9.6/libexec')
CP = ':'.join(sorted(str(p) for p in (ZH / 'lib').glob('*.jar')))
ZK384 = HERE.parent / 'zkdl' / 'apache-zookeeper-3.8.4-bin'
CP384 = ':'.join(sorted(str(p) for p in (ZK384 / 'lib').glob('*.jar'))) if ZK384.exists() else None
ZDATA = HERE / 'zkdata'
JAVA = '/usr/bin/java'
LOGBACK = """<configuration><appender name="F" class="ch.qos.logback.core.FileAppender"><file>%s</file><encoder><pattern>%%d{HH:mm:ss.SSS} [%%thread] %%-5level %%logger{12} - %%msg%%n</pattern></encoder></appender><root level="%s"><appender-ref ref="F"/></root></configuration>"""
CLI_LOGBACK = """<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><target>System.err</target><encoder><pattern>%msg%n</pattern></encoder></appender><root level="ERROR"><appender-ref ref="C"/></root></configuration>"""


def four(port, cmd, timeout=5):
    """发四字命令,返回文本(服务端关闭连接后读完)。"""
    s = socket.create_connection(('127.0.0.1', port), timeout=timeout); s.sendall(cmd.encode()); buf = b''
    try:
        while True:
            b = s.recv(65536)
            if not b: break
            buf += b
    except socket.timeout: pass
    s.close(); return buf.decode(errors='replace')


def kv(text):
    d = {}
    for l in text.splitlines():
        m = re.match(r'^([A-Za-z_ ]+?)[:=\s]\s*(.*)$', l)
        if m: d[m.group(1).strip().lower().replace(' ', '_')] = m.group(2).strip()
    return d


class Node:
    def __init__(self, name, cport, myid=None, servers=None, conf=None, xmx=128, level='INFO', observer=False, jvm=(), ver='3.9.6'):
        assert cport not in (2181, 8080, 8181, 9101, 9333, 6379)
        self.name, self.cport, self.myid, self.servers, self.conf, self.xmx, self.level, self.observer, self.jvm = name, cport, myid, servers, conf or {}, xmx, level, observer, list(jvm)
        self.dir = ZDATA / name; self.p = None; self.ver = ver
    def cfg_text(self):
        c = {'tickTime': 2000, 'initLimit': 10, 'syncLimit': 5, 'dataDir': str(self.dir / 'data'), 'clientPort': self.cport, 'clientPortAddress': '127.0.0.1', 'admin.enableServer': 'false', '4lw.commands.whitelist': '*', 'maxClientCnxns': 60}
        if self.observer: c['peerType'] = 'observer'
        c.update(self.conf)
        lines = [f'{k}={v}' for k, v in c.items() if v is not None]
        if self.servers: lines += [f'server.{i}={h}:{q}:{e}' + (':observer' if obs else '') for i, h, q, e, obs in self.servers]
        return '\n'.join(lines) + '\n'
    def prepare(self, wipe=True):
        if wipe: shutil.rmtree(self.dir, ignore_errors=True)
        (self.dir / 'data').mkdir(parents=True, exist_ok=True)
        (self.dir / 'zoo.cfg').write_text(self.cfg_text())
        (self.dir / 'logback.xml').write_text(LOGBACK % (self.dir / 'zk.log', self.level))
        if self.myid is not None: (self.dir / 'data' / 'myid').write_text(str(self.myid))
    def start(self, wait=True, wipe=True, timeout=40):
        subprocess.run(['pkill', '-9', '-f', str(self.dir / 'zoo.cfg')], capture_output=True)
        for port in (self.cport,):
            r = subprocess.run(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN', '-t'], capture_output=True, text=True)
            for pid in r.stdout.split():
                cmd = subprocess.run(['ps', '-o', 'command=', '-p', pid], capture_output=True, text=True).stdout
                if 'QuorumPeerMain' in cmd and 'zkdata' in cmd: subprocess.run(['kill', '-9', pid])
        time.sleep(0.2)
        if wipe or not (self.dir / 'zoo.cfg').exists(): self.prepare(wipe)
        elif not getattr(self, 'keep_cfg', False): (self.dir / 'zoo.cfg').write_text(self.cfg_text()); (self.dir / 'logback.xml').write_text(LOGBACK % (self.dir / 'zk.log', self.level))
        cmd = [JAVA, f'-Xmx{self.xmx}m', '-Xms32m', f'-Dlogback.configurationFile={self.dir / "logback.xml"}', '-Dzookeeper.admin.enableServer=false', *self.jvm, '-cp', (CP384 if self.ver == '3.8.4' else CP), 'org.apache.zookeeper.server.quorum.QuorumPeerMain', str(self.dir / 'zoo.cfg')]
        self.p = subprocess.Popen(cmd, cwd=self.dir, stdout=open(self.dir / 'stdout.log', 'a'), stderr=subprocess.STDOUT)
        if wait: self.wait_ready(timeout)
        return self
    def wait_ready(self, timeout=40):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.mode() in ('standalone', 'leader', 'follower', 'observer'): return self
            except Exception: pass
            if self.p.poll() is not None: raise RuntimeError(f'{self.name} 进程退出: ' + (self.dir / 'stdout.log').read_text()[-400:])
            time.sleep(0.2)
        raise TimeoutError(f'{self.name} 没有在 {timeout}s 内就绪')
    def mode(self):
        try: return kv(four(self.cport, 'srvr', 2)).get('mode', '')
        except Exception: return ''
    def alive(self): return self.p is not None and self.p.poll() is None
    def stop(self, sig=signal.SIGTERM):
        if self.alive():
            self.p.send_signal(sig)
            try: self.p.wait(15)
            except Exception: self.p.kill(); self.p.wait()
    def kill(self): self.stop(signal.SIGKILL)
    def pause(self): self.p.send_signal(signal.SIGSTOP)
    def resume(self): self.p.send_signal(signal.SIGCONT)
    def log(self): return (self.dir / 'zk.log').read_text() if (self.dir / 'zk.log').exists() else ''
    def four(self, cmd): return four(self.cport, cmd)
    def srvr(self): return kv(self.four('srvr'))


class Ensemble:
    def __init__(self, name, n=3, base=7300, observers=0, conf=None, xmx=128, level='INFO'):
        self.name = name; self.nodes = []
        total = n + observers
        servers = [(i + 1, '127.0.0.1', base + 100 + i, base + 200 + i, i >= n) for i in range(total)]
        for i in range(total):
            self.nodes.append(Node(f'{name}-{i + 1}', base + i, myid=i + 1, servers=servers, conf=conf, xmx=xmx, level=level, observer=i >= n))
    def start(self, wait=True):
        for nd in self.nodes: nd.start(wait=False)
        if wait: self.wait_quorum()
        return self
    def wait_quorum(self, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if any(nd.alive() and nd.mode() == 'leader' for nd in self.nodes) and all(nd.mode() for nd in self.nodes if nd.alive()): return self
            time.sleep(0.3)
        raise TimeoutError('集群没有选出 leader')
    def leader(self):
        for nd in self.nodes:
            if nd.alive() and nd.mode() == 'leader': return nd
    def followers(self): return [nd for nd in self.nodes if nd.alive() and nd.mode() == 'follower']
    def stop(self):
        for nd in self.nodes: nd.stop()
    def hosts(self): return ','.join(f'127.0.0.1:{nd.cport}' for nd in self.nodes)


def client(hosts, timeout=10, start_timeout=15, **kw):
    import logging; logging.getLogger('kazoo').setLevel(logging.CRITICAL)
    from kazoo.client import KazooClient
    z = KazooClient(hosts=hosts, timeout=timeout, **kw); z.start(timeout=start_timeout); return z


def cli(port, *cmds, timeout=30, jvm=()):
    """用官方的 ZooKeeperMain 执行命令(每条命令一个 JVM),返回每条命令的标准输出。"""
    cb = ZDATA / 'cli-logback.xml'; ZDATA.mkdir(exist_ok=True); cb.write_text(CLI_LOGBACK); outs = []
    for c in cmds:
        r = subprocess.run([JAVA, '-Xmx64m', f'-Dlogback.configurationFile={cb}', *jvm, '-cp', CP, 'org.apache.zookeeper.ZooKeeperMain', '-server', f'127.0.0.1:{port}', *c.split()], capture_output=True, text=True, timeout=timeout)
        t = (r.stdout + r.stderr).strip().splitlines()
        t = [l for l in t if not (l.startswith('Connecting to') or l == 'WATCHER::' or l.startswith('WatchedEvent state:SyncConnected') or not l.strip())]
        outs.append('\n'.join(t))
    return outs


def cleanup(*things):
    for t in things:
        try: t.stop()
        except Exception: pass


class Proxy:
    """TCP 代理:客户端连代理,代理转给 ZooKeeper。drop_resp=True 时丢弃服务端返回的数据(请求仍会转发给服务端),close_all() 断开所有连接。"""
    def __init__(self, listen, target):
        self.listen, self.target = listen, target; self.drop_resp = False; self.blocked = False; self.blackhole = False; self.cap = bytearray(); self.conns = []; self.sock = None; self.stop_flag = False; self.bytes_up = 0; self.bytes_down = 0
    def start(self):
        s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('127.0.0.1', self.listen)); s.listen(50); self.sock = s
        threading.Thread(target=self._accept, daemon=True).start(); return self
    def _accept(self):
        while not self.stop_flag:
            try: c, _ = self.sock.accept()
            except Exception: return
            if self.blocked:
                c.close(); continue
            if self.blackhole:
                self.conns.append(c); continue
            try: u = socket.create_connection(('127.0.0.1', self.target), timeout=5)
            except Exception: c.close(); continue
            self.conns += [c, u]
            threading.Thread(target=self._pump, args=(c, u, False), daemon=True).start(); threading.Thread(target=self._pump, args=(u, c, True), daemon=True).start()
    def _pump(self, a, b, down):
        try:
            while True:
                d = a.recv(65536)
                if not d: break
                if len(self.cap) < 4_000_000: self.cap += d
                if self.blackhole: continue
                if down:
                    self.bytes_down += len(d)
                    if self.drop_resp: continue
                else: self.bytes_up += len(d)
                b.sendall(d)
        except Exception: pass
        for s in (a, b):
            try: s.close()
            except Exception: pass
    def block(self): self.blocked = True; self.close_all()
    def unblock(self): self.blocked = False
    def close_all(self):
        for s in self.conns:
            try: s.shutdown(socket.SHUT_RDWR)
            except Exception: pass
            try: s.close()
            except Exception: pass
        self.conns = []
    def stop(self):
        self.stop_flag = True; self.close_all()
        try: self.sock.close()
        except Exception: pass


def threads(node):
    """用 jstack 列出节点 JVM 里的线程名(去掉 GC / JIT 的内部线程)。"""
    r = subprocess.run(['/usr/bin/jstack', str(node.p.pid)], capture_output=True, text=True).stdout
    names = sorted(set(re.findall(r'^"([^"]+)"', r, re.M)))
    skip = ('GC ', 'G1 ', 'C1 ', 'C2 ', 'VM ', 'Signal', 'Service', 'Finalizer', 'Reference', 'Common-Cleaner', 'Monitor', 'Notification', 'Attach', 'Sweeper', 'main')
    return [x for x in names if not x.startswith(skip)]


def cli_session(port, jvm=()):
    """交互式 ZooKeeperMain(从 stdin 读命令),返回 Popen;watch 事件会打印在它的 stdout。"""
    cb = ZDATA / 'cli-logback.xml'; ZDATA.mkdir(exist_ok=True); cb.write_text(CLI_LOGBACK)
    return subprocess.Popen([JAVA, '-Xmx64m', f'-Dlogback.configurationFile={cb}', *jvm, '-cp', CP, 'org.apache.zookeeper.ZooKeeperMain', '-server', f'127.0.0.1:{port}'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def can_write(hosts, timeout=6, start_timeout=4):
    """能否通过 hosts 完成一次写(临时节点创建 + 删除)。"""
    z = None
    try:
        z = client(hosts, timeout=timeout, start_timeout=start_timeout); p = z.create('/probe-', b'', ephemeral=True, sequence=True); z.delete(p); return True
    except Exception: return False
    finally:
        if z is not None:
            try: z.stop(); z.close()
            except Exception: pass


def log_lines(node, pats, strip=True):
    """从节点日志里取包含任一子串的行,去掉线程与 logger 前缀,保留时间戳。"""
    out = []
    for l in node.log().splitlines():
        if any(p in l for p in pats):
            out.append(re.sub(r'^(\S+) \[.*?\] \w+\s+\S+ - ', r'\1 ', l) if strip else l)
    return out


def tsec(line):
    m = re.match(r'(\d+):(\d+):(\d+\.\d+)', line)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None


class NetEnsemble(Ensemble):
    """每对节点之间的 quorum / 选举连接都经过自己的 TCP 代理,可以制造网络分区:partition([1], [2, 3]) 切断 1 号与 2、3 号之间的所有节点间通信(客户端端口不经过代理)。"""
    def __init__(self, name, n=3, base=7300, conf=None, xmx=128, level='INFO'):
        self.name = name; self.nodes = []; self.proxies = {}; self.n = n
        for i in range(1, n + 1):
            for j in range(1, n + 1):
                if i != j: self.proxies[(i, j)] = (Proxy(base + 500 + 10 * i + j, base + 100 + (j - 1)), Proxy(base + 600 + 10 * i + j, base + 200 + (j - 1)))
        for i in range(1, n + 1):
            servers = []
            for j in range(1, n + 1):
                if i == j: servers.append((j, '127.0.0.1', base + 100 + (j - 1), base + 200 + (j - 1), False))
                else: servers.append((j, '127.0.0.1', base + 500 + 10 * i + j, base + 600 + 10 * i + j, False))
            self.nodes.append(Node(f'{name}-{i}', base + i - 1, myid=i, servers=servers, conf=conf, xmx=xmx, level=level))
    def start(self, wait=True):
        for pq in self.proxies.values():
            for p in pq: p.start()
        return Ensemble.start(self, wait)
    def partition(self, a, b, mode='drop'):
        """mode='drop':悄悄丢包(连接不断,和真实的网络分区一样);mode='close':立刻断开连接。"""
        for i in a:
            for j in b:
                for key in ((i, j), (j, i)):
                    for p in self.proxies[key]:
                        if mode == 'close': p.block()
                        else: p.blackhole = True
    def heal(self):
        for pq in self.proxies.values():
            for p in pq: p.blackhole = False; p.blocked = False; p.close_all()
    def stop(self):
        Ensemble.stop(self)
        for pq in self.proxies.values():
            for p in pq: p.stop()


class DNode(Node):
    """使用动态配置文件的节点(支持 reconfig)。dyn: [(id, qport, eport, role, cport)]。"""
    def __init__(self, name, myid, dyn, **kw):
        conf = {'clientPort': None, 'clientPortAddress': None, 'standaloneEnabled': 'false', 'reconfigEnabled': 'true', 'dynamicConfigFile': None}; conf.update(kw.pop('conf', {}))
        kw.setdefault('jvm', ['-Dzookeeper.skipACL=yes'])
        Node.__init__(self, name, myid[1] if isinstance(myid, tuple) else myid, **dict(kw, conf=conf)); self.dyn = dyn; self.myid = myid; self.cport = [x for x in dyn if x[0] == myid][0][4]
        self.conf['dynamicConfigFile'] = str(self.dir / 'zoo.cfg.dynamic')
    def prepare(self, wipe=True):
        Node.prepare(self, wipe)
        (self.dir / 'zoo.cfg.dynamic').write_text('\n'.join(f'server.{i}=127.0.0.1:{q}:{e}:{role};127.0.0.1:{c}' for i, q, e, role, c in self.dyn) + '\n')


class DEnsemble:
    def __init__(self, name, n=3, base=7300, conf=None, xmx=128):
        self.name = name; self.base = base; self.conf = conf or {}; self.xmx = xmx; self.dyn = [(i + 1, base + 100 + i, base + 200 + i, 'participant', base + i) for i in range(n)]
        self.nodes = [self.mk(i + 1, self.dyn) for i in range(n)]
    def mk(self, i, dyn): return DNode(f'{self.name}-{i}', i, dyn, conf=dict(self.conf), xmx=self.xmx)
    def start(self, wait=True):
        for nd in self.nodes: nd.start(wait=False)
        if wait: Ensemble.wait_quorum(self)
        return self
    def leader(self): return Ensemble.leader(self)
    def followers(self): return Ensemble.followers(self)
    def new_node(self, i, role='participant'):
        ent = (i, self.base + 100 + i - 1, self.base + 200 + i - 1, role, self.base + i - 1)
        nd = self.mk(i, [x for x in self.dyn if x[0] != i] + [ent]); self.nodes.append(nd); return nd
    def hosts(self, only_alive=True): return ','.join(f'127.0.0.1:{nd.cport}' for nd in self.nodes if nd.alive() or not only_alive)
    def stop(self):
        for nd in self.nodes: nd.stop()


def pki(force=False):
    """生成实验用的 CA、服务端证书(SAN=localhost,127.0.0.1)、两个客户端证书、一个主机名不匹配的服务端证书;PKCS12 密钥库口令 changeit。只用于本机实验。"""
    d = ZDATA / 'pki'
    if d.exists() and not force: return d
    shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    def sh(*a, **k): r = subprocess.run(a, cwd=d, capture_output=True, text=True, **k); assert r.returncode == 0, (a, r.stderr); return r
    sh('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.crt', '-days', '30', '-subj', '/CN=zk-test-ca')
    def issue(name, subj, san=None):
        sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', f'{name}.key', '-out', f'{name}.csr', '-subj', subj)
        ext = f'subjectAltName={san}' if san else None
        args = ['openssl', 'x509', '-req', '-in', f'{name}.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key', '-CAcreateserial', '-out', f'{name}.crt', '-days', '30']
        if ext: (d / f'{name}.ext').write_text(ext + '\n'); args += ['-extfile', f'{name}.ext']
        sh(*args)
        sh('openssl', 'pkcs12', '-export', '-in', f'{name}.crt', '-inkey', f'{name}.key', '-certfile', 'ca.crt', '-out', f'{name}.p12', '-name', name, '-passout', 'pass:changeit')
    issue('server', '/CN=localhost', 'DNS:localhost,IP:127.0.0.1'); issue('client1', '/CN=client1'); issue('client2', '/CN=client2'); issue('wronghost', '/CN=wrong.example.com')
    sh('keytool', '-importcert', '-alias', 'ca', '-file', 'ca.crt', '-keystore', 'truststore.p12', '-storetype', 'PKCS12', '-storepass', 'changeit', '-noprompt')
    return d


def tls_conf(d, port, client_auth='none', plain=True, keystore='server.p12'):
    c = {'secureClientPort': port, 'serverCnxnFactory': 'org.apache.zookeeper.server.NettyServerCnxnFactory', 'ssl.keyStore.location': str(d / keystore), 'ssl.keyStore.password': 'changeit', 'ssl.keyStore.type': 'PKCS12', 'ssl.trustStore.location': str(d / 'truststore.p12'), 'ssl.trustStore.password': 'changeit', 'ssl.trustStore.type': 'PKCS12', 'ssl.clientAuth': client_auth}
    if not plain: c['clientPort'] = None; c['clientPortAddress'] = None
    return c


def tls_cli_jvm(d, client=None, trust=True, hostver=True):
    j = ['-Dzookeeper.client.secure=true', '-Dzookeeper.clientCnxnSocket=org.apache.zookeeper.ClientCnxnSocketNetty']
    if trust: j += [f'-Dzookeeper.ssl.trustStore.location={d / "truststore.p12"}', '-Dzookeeper.ssl.trustStore.password=changeit', '-Dzookeeper.ssl.trustStore.type=PKCS12']
    if client: j += [f'-Dzookeeper.ssl.keyStore.location={d / (client + ".p12")}', '-Dzookeeper.ssl.keyStore.password=changeit', '-Dzookeeper.ssl.keyStore.type=PKCS12']
    if not hostver: j += ['-Dzookeeper.ssl.hostnameVerification=false']
    return j
