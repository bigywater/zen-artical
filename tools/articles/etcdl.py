"""etcd 实验辅助:自己起 etcd 3.7.2 集群,端口 7600+(客户端)/ 7610+(peer),数据在 zkdata/etcd-*/。通过 HTTP JSON 网关读写。"""
import subprocess, time, json, base64, http.client, shutil, signal, pathlib, os
from dj import HERE
ZD = HERE / 'zkdata'
b64 = lambda s: base64.b64encode(s.encode() if isinstance(s, str) else s).decode()
class EtcdNode:
    def __init__(self, name, idx, n, base=7600, extra=()):
        self.name, self.idx, self.cport, self.pport = name, idx, base + idx, base + 10 + idx; self.dir = ZD / f'etcd-{name}'; self.p = None; self.n = n; self.base = base; self.extra = list(extra)
    def start(self, wipe=True, state='new'):
        if wipe: shutil.rmtree(self.dir, ignore_errors=True)
        cl = ','.join(f'{self.name.rsplit("-", 1)[0]}-{i}=http://127.0.0.1:{self.base + 10 + i}' for i in range(self.n))
        cmd = ['etcd', '--name', self.name, '--data-dir', str(self.dir), '--listen-client-urls', f'http://127.0.0.1:{self.cport}', '--advertise-client-urls', f'http://127.0.0.1:{self.cport}', '--listen-peer-urls', f'http://127.0.0.1:{self.pport}', '--initial-advertise-peer-urls', f'http://127.0.0.1:{self.pport}', '--initial-cluster', cl, '--initial-cluster-state', state, '--initial-cluster-token', 'zkbook', '--log-level', 'error', *self.extra]
        self.dir.parent.mkdir(exist_ok=True); self.p = subprocess.Popen(cmd, stdout=open(self.dir.parent / f'etcd-{self.name}.log', 'w'), stderr=subprocess.STDOUT); return self
    def alive(self): return self.p is not None and self.p.poll() is None
    def kill(self):
        if self.alive(): self.p.kill(); self.p.wait()
    def stop(self):
        if self.alive():
            self.p.terminate()
            try: self.p.wait(10)
            except Exception: self.p.kill()
    def call(self, path, body, timeout=3):
        c = http.client.HTTPConnection('127.0.0.1', self.cport, timeout=timeout); c.request('POST', path, json.dumps(body), {'Content-Type': 'application/json'}); r = c.getresponse(); d = r.read(); c.close()
        return r.status, json.loads(d or b'{}')
    def put(self, k, v, timeout=3): return self.call('/v3/kv/put', {'key': b64(k), 'value': b64(v)}, timeout)
    def get(self, k, serializable=False, timeout=3):
        s, d = self.call('/v3/kv/range', {'key': b64(k), 'serializable': serializable}, timeout)
        kvs = d.get('kvs') or []; return base64.b64decode(kvs[0]['value']).decode() if kvs else None
    def status(self):
        s, d = self.call('/v3/maintenance/status', {}, 2); return d
class EtcdCluster:
    def __init__(self, tag, n=3, base=7600, extra=()):
        self.nodes = [EtcdNode(f'{tag}-{i}', i, n, base, extra) for i in range(n)]
    def start(self, timeout=30):
        for nd in self.nodes: nd.start()
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.leader() is not None: return self
            except Exception: pass
            time.sleep(0.2)
        raise TimeoutError('etcd 没有选出 leader')
    def leader(self):
        for nd in self.nodes:
            if not nd.alive(): continue
            try:
                d = nd.status()
                if d.get('leader') and d.get('header', {}).get('member_id') == d.get('leader'): return nd
            except Exception: pass
        return None
    def stop(self):
        for nd in self.nodes: nd.stop()
