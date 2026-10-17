"""HBase 2.6.6 本机多进程助手:每个进程自己的 conf 目录,端口 7960+,ZooKeeper 用我的 7300。"""
import os, subprocess, time, signal, shutil, re
from zkl import ZDATA, HERE
HH = HERE.parent / 'hbase' / 'hbase-2.6.6'
JH = subprocess.run(['/usr/libexec/java_home'], capture_output=True, text=True).stdout.strip()
SITE = '''<?xml version="1.0"?><configuration>
<property><name>hbase.cluster.distributed</name><value>true</value></property>
<property><name>hbase.rootdir</name><value>file://{root}</value></property>
<property><name>hbase.unsafe.stream.capability.enforce</name><value>false</value></property>
<property><name>hbase.zookeeper.quorum</name><value>127.0.0.1</value></property>
<property><name>hbase.zookeeper.property.clientPort</name><value>{zport}</value></property>
<property><name>zookeeper.session.timeout</name><value>{sess}</value></property>
<property><name>hbase.master.port</name><value>{mport}</value></property>
<property><name>hbase.master.info.port</name><value>-1</value></property>
<property><name>hbase.regionserver.port</name><value>{rport}</value></property>
<property><name>hbase.regionserver.info.port</name><value>-1</value></property>
<property><name>hbase.master.hostname</name><value>127.0.0.1</value></property>
<property><name>hbase.regionserver.hostname</name><value>127.0.0.1</value></property>
<property><name>hbase.tmp.dir</name><value>{tmp}</value></property>
<property><name>hbase.wal.provider</name><value>filesystem</value></property>
</configuration>'''
ENV = '''export JAVA_HOME={jh}
export HBASE_MANAGES_ZK=false
export HBASE_HEAPSIZE=384m
export HBASE_LOG_DIR={log}
export HBASE_PID_DIR={log}
export HBASE_OPTS="-XX:+UseSerialGC"
'''
class HProc:
    def __init__(self, kind, name, port, root, zport=7300, sess=6000):
        self.kind, self.name, self.port = kind, name, port; self.dir = ZDATA / f'hbase-{name}'; self.root = root; self.zport = zport; self.sess = sess; self.p = None
    def start(self):
        shutil.rmtree(self.dir, ignore_errors=True); (self.dir / 'conf').mkdir(parents=True); (self.dir / 'log').mkdir(); (self.dir / 'tmp').mkdir()
        for f in os.listdir(HH / 'conf'):
            if f not in ('hbase-site.xml', 'hbase-env.sh'): shutil.copy(HH / 'conf' / f, self.dir / 'conf' / f)
        mp, rp = (self.port, 7990) if self.kind == 'master' else (7989, self.port)
        (self.dir / 'conf' / 'hbase-site.xml').write_text(SITE.format(root=self.root, zport=self.zport, sess=self.sess, mport=mp, rport=rp, tmp=self.dir / 'tmp'))
        (self.dir / 'conf' / 'hbase-env.sh').write_text(ENV.format(jh=JH, log=self.dir / 'log'))
        env = dict(os.environ, HBASE_CONF_DIR=str(self.dir / 'conf'), JAVA_HOME=JH, HBASE_HOME=str(HH))
        self.p = subprocess.Popen([str(HH / 'bin' / 'hbase'), self.kind, 'start'], stdout=open(self.dir / 'out.log', 'w'), stderr=subprocess.STDOUT, env=env, start_new_session=True)
        return self
    def alive(self): return self.p is not None and self.p.poll() is None
    def kill(self):
        if self.p is not None:
            try: os.killpg(self.p.pid, signal.SIGKILL)
            except Exception: pass
            try: self.p.wait(10)
            except Exception: pass
    def stop(self):
        if self.p is not None:
            try: os.killpg(self.p.pid, signal.SIGTERM)
            except Exception: pass
            try: self.p.wait(30)
            except Exception: self.kill()
    def log(self):
        t = ''
        for f in sorted((self.dir / 'log').glob('*.log')): t += f.read_text(errors='replace')
        return t + (self.dir / 'out.log').read_text(errors='replace')
def classpath(conf):
    env = dict(os.environ, HBASE_CONF_DIR=str(conf), JAVA_HOME=JH, HBASE_HOME=str(HH))
    return subprocess.run([str(HH / 'bin' / 'hbase'), 'classpath'], capture_output=True, text=True, env=env).stdout.strip()
