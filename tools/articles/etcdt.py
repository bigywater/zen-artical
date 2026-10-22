"""3 节点 etcd(3.7.2)实验辅助:自己起集群,每个节点的 peer 地址经过一层可调延迟的代理(默认 0),通过 etcd 自带的 HTTP/JSON 网关读写。
被连接的一方的代理决定那一方的 peer 流量的延迟(每个方向都延迟);要整体加网络延迟就给三个代理都设同一个值。"""
import os, sys, json, base64, http.client, subprocess, signal, shutil, socket, threading, time, random
from txl import TT, free_port
from rl import DelayProxy
b64 = lambda s: base64.b64encode(s.encode()).decode()


class Px(DelayProxy):
    """rl.DelayProxy 在目标节点被杀(连不上)时 accept 线程会直接退出;这里改成连不上就关掉这一条连接、继续接受新的。"""
    def _accept(self):
        while self.alive:
            try: a, _ = self.ls.accept()
            except Exception: return
            try: b = socket.create_connection(('127.0.0.1', self.tport), timeout=2); b.settimeout(None)   # 连上之后去掉超时:空闲的连接(比如复制链路)不能被代理悄悄断掉
            except Exception:
                try: a.close()
                except Exception: pass
                continue
            for x in (a, b): x.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            for x, y in ((a, b), (b, a)): threading.Thread(target=self._pump, args=(x, y), daemon=True).start()


class Etcd:
    def __init__(self, tag, n=3):
        self.tag = tag; self.n = n; self.CP = [free_port() for _ in range(n)]; self.PP = [free_port() for _ in range(n)]; self.QP = [free_port() for _ in range(n)]
        self.PX = [Px(self.QP[i], self.PP[i], 0) for i in range(n)]; self.procs = [None] * n

    def start_node(self, i):
        d = TT / f'etcd_{self.tag}_{i}'; d.mkdir(exist_ok=True); cl = ','.join(f'{self.tag}n{j}=http://127.0.0.1:{self.QP[j]}' for j in range(self.n))
        cmd = ['etcd', '--name', f'{self.tag}n{i}', '--data-dir', str(d / 'data'), '--listen-client-urls', f'http://127.0.0.1:{self.CP[i]}', '--advertise-client-urls', f'http://127.0.0.1:{self.CP[i]}',
               '--listen-peer-urls', f'http://127.0.0.1:{self.PP[i]}', '--initial-advertise-peer-urls', f'http://127.0.0.1:{self.QP[i]}', '--initial-cluster', cl, '--initial-cluster-token', self.tag, '--heartbeat-interval', '100', '--election-timeout', '1000']
        self.procs[i] = subprocess.Popen(cmd, stdout=open(d / 'etcd.log', 'a'), stderr=subprocess.STDOUT, start_new_session=True)

    def start(self):
        for i in range(self.n): self.start_node(i)
        l = self.wait_leader(); assert l is not None; time.sleep(0.8); return self

    def kill_node(self, i):
        if self.procs[i] and self.procs[i].poll() is None: os.killpg(self.procs[i].pid, signal.SIGKILL); self.procs[i].wait()

    def call(self, i, path, body, timeout=3):
        c = http.client.HTTPConnection('127.0.0.1', self.CP[i], timeout=timeout)
        try: c.request('POST', path, json.dumps(body), {'Content-Type': 'application/json'}); r = c.getresponse(); d = r.read(); return r.status, json.loads(d or b'{}')
        finally: c.close()

    def status(self, i):
        try: s, d = self.call(i, '/v3/maintenance/status', {}, 2); return d if s == 200 else None
        except Exception: return None

    def leader_idx(self):
        for i in range(self.n):
            d = self.status(i)
            if d and d.get('leader') and d['header']['member_id'] == d['leader']: return i
        return None

    def wait_leader(self, timeout=20):
        t0 = time.time()
        while time.time() - t0 < timeout:
            l = self.leader_idx()
            if l is not None: return l
            time.sleep(0.1)

    def conn(self, i, timeout=3): return http.client.HTTPConnection('127.0.0.1', self.CP[i], timeout=timeout)   # 长连接,测延迟时用,省掉每次建连接

    @staticmethod
    def req(c, path, body):
        c.request('POST', path, json.dumps(body), {'Content-Type': 'application/json'}); r = c.getresponse(); d = r.read(); return r.status, json.loads(d or b'{}')

    def put(self, i, k, v, c=None, timeout=3):
        if c: return self.req(c, '/v3/kv/put', {'key': b64(k), 'value': b64(v)})
        return self.call(i, '/v3/kv/put', {'key': b64(k), 'value': b64(v)}, timeout)

    def get(self, i, k, serializable=False, c=None, timeout=3):
        body = {'key': b64(k), 'serializable': serializable}
        s, d = self.req(c, '/v3/kv/range', body) if c else self.call(i, '/v3/kv/range', body, timeout)
        if s != 200: return None
        kvs = d.get('kvs') or []; return base64.b64decode(kvs[0]['value']).decode() if kvs else None

    def set_delay(self, ms, nodes=None):
        for i in (range(self.n) if nodes is None else nodes): self.PX[i].d = ms / 1000.0

    def stop(self):
        for i in range(self.n): self.kill_node(i)
        for p in self.PX: p.close()
        subprocess.run(f"pkill -f 'etcd --name {self.tag}' 2>/dev/null; true", shell=True)
        for i in range(self.n): shutil.rmtree(TT / f'etcd_{self.tag}_{i}', ignore_errors=True)
