"""Kafka 3.9.2 的本机启动助手:自己的端口 7900+,数据在 zkdata/kafka-*,通过 ZooKeeper(我的 7300)或 KRaft 运行。"""
import os, sys, time, subprocess, signal, shutil, pathlib, re
from zkl import ZDATA, HERE
KHOME = HERE.parent / 'kafka' / 'kafka_2.13-3.9.2'
def kcmd(tool, *args, timeout=120, check=False):
    env = dict(os.environ, KAFKA_HEAP_OPTS='-Xmx256m -Xms64m', LOG_DIR=str(ZDATA / 'kafka-tools-logs'))
    r = subprocess.run([str(KHOME / 'bin' / tool), *args], capture_output=True, text=True, timeout=timeout, env=env)
    return (r.stdout + r.stderr).strip() if not check else r
class KNode:
    def __init__(self, nid, port, props, name=None):
        self.id, self.port = nid, port; self.name = name or f'kafka-{nid}'; self.dir = ZDATA / self.name; self.props = dict(props); self.p = None
    def write(self, props=None):
        self.dir.mkdir(parents=True, exist_ok=True); (self.dir / 'data').mkdir(exist_ok=True)
        pr = dict(self.props); pr.update(props or {}); pr.setdefault('log.dirs', str(self.dir / 'data'))
        (self.dir / 'server.properties').write_text('\n'.join(f'{k}={v}' for k, v in pr.items()) + '\n')
    def start(self, props=None, wait_log='started (kafka.server.KafkaServer)|Kafka Server started', timeout=90):
        self.write(props); logf = self.dir / 'kafka.log'
        env = dict(os.environ, KAFKA_HEAP_OPTS='-Xmx256m -Xms64m', LOG_DIR=str(self.dir / 'logs'))
        self.p = subprocess.Popen([str(KHOME / 'bin' / 'kafka-server-start.sh'), str(self.dir / 'server.properties')], stdout=open(logf, 'w'), stderr=subprocess.STDOUT, env=env, start_new_session=True)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.p.poll() is not None: raise RuntimeError(f'{self.name} 退出:' + logf.read_text()[-1500:])
            if re.search(wait_log, logf.read_text()): return self
            time.sleep(0.3)
        raise TimeoutError(self.name + ' 没有启动\n' + logf.read_text()[-1500:])
    def alive(self): return self.p is not None and self.p.poll() is None
    def kill(self):
        if self.alive():
            try: os.killpg(self.p.pid, signal.SIGKILL)
            except Exception: self.p.kill()
            self.p.wait()
    def stop(self):
        if self.alive():
            try: os.killpg(self.p.pid, signal.SIGTERM)
            except Exception: self.p.terminate()
            try: self.p.wait(30)
            except Exception: self.kill()
    def log(self): return (self.dir / 'kafka.log').read_text() if (self.dir / 'kafka.log').exists() else ''
