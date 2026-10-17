"""Consul 2.0.4 本机集群助手:端口 7700+(HTTP)/ 7710+(server rpc)/ 7720+(serf lan),数据在 zkdata/consul-*/。"""
import os, json, time, subprocess, signal, shutil, http.client
from zkl import ZDATA, HERE
CB = HERE.parent / 'consul' / 'consul'
class CNode:
    def __init__(self, tag, i, n=3, mult=None):
        self.tag, self.i, self.n, self.mult = tag, i, n, mult; self.name = f'{tag}-{i}'; self.dir = ZDATA / f'consul-{self.name}'; self.http = 7701 + i; self.p = None
    def start(self, wipe=True):
        if wipe: shutil.rmtree(self.dir, ignore_errors=True)
        (self.dir / 'data').mkdir(parents=True, exist_ok=True)
        cfg = {'node_name': self.name, 'data_dir': str(self.dir / 'data'), 'server': True, 'bootstrap_expect': self.n, 'bind_addr': '127.0.0.1', 'client_addr': '127.0.0.1', 'advertise_addr': '127.0.0.1', 'disable_update_check': True, 'log_level': 'warn',
               'ports': {'http': self.http, 'https': -1, 'dns': -1, 'grpc': -1, 'grpc_tls': -1, 'server': 7711 + self.i, 'serf_lan': 7721 + self.i, 'serf_wan': -1},
               'retry_join': [f'127.0.0.1:{7721 + k}' for k in range(self.n) if k != self.i], 'performance': ({'raft_multiplier': self.mult} if self.mult else {})}
        (self.dir / 'cfg.json').write_text(json.dumps(cfg))
        self.p = subprocess.Popen([str(CB), 'agent', '-config-file', str(self.dir / 'cfg.json')], stdout=open(self.dir / 'out.log', 'w'), stderr=subprocess.STDOUT, start_new_session=True); return self
    def alive(self): return self.p is not None and self.p.poll() is None
    def kill(self):
        if self.alive():
            try: os.killpg(self.p.pid, signal.SIGKILL)
            except Exception: self.p.kill()
            self.p.wait()
    def stop(self):
        if self.alive():
            try: os.killpg(self.p.pid, signal.SIGTERM)
            except Exception: pass
            try: self.p.wait(15)
            except Exception: self.kill()
    def req(self, method, path, body=None, timeout=5):
        c = http.client.HTTPConnection('127.0.0.1', self.http, timeout=timeout); c.request(method, path, body if body is None or isinstance(body, (bytes, str)) else json.dumps(body)); r = c.getresponse(); d = r.read(); h = dict(r.getheaders()); c.close(); return r.status, d, h
class CCluster:
    def __init__(self, tag, n=3, mult=None): self.nodes = [CNode(tag, i, n, mult) for i in range(n)]
    def start(self, timeout=60):
        for nd in self.nodes: nd.start()
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.leader() is not None: return self
            time.sleep(0.3)
        raise TimeoutError('consul 没有选出 leader')
    def leader(self):
        for nd in self.nodes:
            if not nd.alive(): continue
            try:
                s, d, h = nd.req('GET', '/v1/status/leader', timeout=2)
                if s == 200 and d.strip() not in (b'""', b''): addr = json.loads(d); return next((x for x in self.nodes if f':{7711 + x.i}' in addr), None)
            except Exception: pass
        return None
    def stop(self):
        for nd in self.nodes: nd.stop()
