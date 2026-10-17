"""分布式事务系列的实验辅助:自己起的 MySQL(Homebrew 26.7.0)、PostgreSQL(16.15)、Redis、Kafka、etcd 实例。
端口 9150–9199(不碰用户自己的 3306 / 5432 / 6379 / 8181 / 9101 / 9333);数据在 ttmp/<name>/,整体可删。
用 ttmp_venv 运行实验:ttmp_venv/bin/python exp/tN.py"""
import os, sys, subprocess, shutil, pathlib, time, socket, re, json, threading, signal, textwrap, statistics, random
HERE = pathlib.Path(__file__).parent
TT = HERE / 'ttmp'; TT.mkdir(exist_ok=True)
sys.path.insert(0, str(HERE))
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'): os.environ.pop(k, None)
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
from rl import tee, save
import pymysql, psycopg

MYSQL_BIN = '/opt/homebrew/opt/mysql/bin'
PG_BIN = '/opt/homebrew/opt/postgresql@16/bin'
FORBIDDEN = {3306, 5432, 6379, 8181, 9101, 9333, 27017}
_port = [9150]
_nodes = []


def free_port():
    while True:
        _port[0] += 1; p = _port[0]
        if p in FORBIDDEN: continue
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1', p)) != 0: return p


def tdir(name, clean=True):
    d = TT / name
    if clean: shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True); return d


def tidy(t):
    t = re.sub(r'/private/tmp/claude-501/[^\s"\':]*?/scratchpad', '<scratch>', t).replace(str(TT), '<ttmp>').replace(str(HERE), '<实验目录>')
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).lstrip('\n')


def reset():
    """杀掉所有本模块起过的 mysqld / postgres / 其它子进程。"""
    for n in list(_nodes):
        try: n.kill()
        except Exception: pass
    _nodes.clear()
    subprocess.run(f"pkill -f '{TT}/' 2>/dev/null; true", shell=True)
    time.sleep(0.5)


def wait_port(port, timeout=60, proc=None, logf=None):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError('进程退出:' + (pathlib.Path(logf).read_text()[-1500:] if logf else ''))
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1', port)) == 0: return
        time.sleep(0.2)
    raise TimeoutError(f'端口 {port} 没有起来')


class MySQL:
    """自己的 mysqld:--initialize-insecure,root 无密码,只监听 127.0.0.1。"""
    def __init__(self, name, port=None, opts=(), clean=True):
        self.name = name; self.d = tdir('my_' + name, clean); self.port = port or free_port(); self.opts = list(opts); self.p = None
        self.sock = f'/tmp/txmy{self.port}.sock'
        _nodes.append(self)

    def _base(self):
        return [f'{MYSQL_BIN}/mysqld', '--no-defaults', f'--basedir=/opt/homebrew/opt/mysql', f'--datadir={self.d}/data']

    def start(self, timeout=120):
        if not (self.d / 'data').exists():
            r = subprocess.run(self._base() + ['--initialize-insecure', f'--log-error={self.d}/init.log'], capture_output=True, text=True)
            if r.returncode: raise RuntimeError((self.d / 'init.log').read_text()[-2000:] + r.stderr)
        cmd = self._base() + [f'--port={self.port}', '--bind-address=127.0.0.1', f'--socket={self.sock}', '--mysqlx=OFF', f'--log-error={self.d}/err.log',
                              f'--pid-file={self.d}/mysqld.pid', '--innodb-buffer-pool-size=128M', '--innodb-flush-log-at-trx-commit=1', '--max-connections=200',
                              '--performance-schema=OFF', '--skip-name-resolve'] + self.opts
        self.p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        wait_port(self.port, timeout, self.p, self.d / 'err.log'); return self

    def conn(self, db=None, autocommit=True, **kw):
        return pymysql.connect(unix_socket=self.sock, user='root', password='', database=db, autocommit=autocommit, charset='utf8mb4', **kw)  # initialize-insecure 的 root 只允许 localhost,所以走 unix socket

    def q(self, sql, args=None, db=None):
        c = self.conn(db)
        try:
            with c.cursor() as cur:
                cur.execute(sql, args); return cur.fetchall()
        finally: c.close()

    def kill(self):
        if self.p and self.p.poll() is None:
            try: os.killpg(self.p.pid, signal.SIGKILL)
            except Exception: self.p.kill()
            self.p.wait()

    def stop(self):
        if self.p and self.p.poll() is None:
            try: os.killpg(self.p.pid, signal.SIGTERM)
            except Exception: pass
            try: self.p.wait(60)
            except Exception: self.kill()

    def errlog(self): return (self.d / 'err.log').read_text() if (self.d / 'err.log').exists() else ''


class PG:
    """自己的 PostgreSQL:initdb 在 ttmp/pg_<name>/,pg_ctl 启动必须带 -o '-p PORT -k SOCK'(否则会落到默认的 5432,那是用户自己的库)。"""
    def __init__(self, name, port=None, conf=None, clean=True):
        self.name = name; self.d = tdir('pg_' + name, clean); self.port = port or free_port()
        self.sockdir = f'/tmp/txpg{self.port}'; self.conf = dict(max_prepared_transactions=20, fsync='on', max_connections=100, wal_level='logical',
                                                                  max_replication_slots=5, max_wal_senders=5); self.conf.update(conf or {})
        _nodes.append(self)

    def _pgctl(self, *a):
        return subprocess.run([f'{PG_BIN}/pg_ctl', '-D', str(self.d / 'data'), *a], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def start(self, timeout=60):
        os.makedirs(self.sockdir, exist_ok=True)
        if not (self.d / 'data').exists():
            r = subprocess.run([f'{PG_BIN}/initdb', '-D', str(self.d / 'data'), '-U', 'postgres', '--auth=trust', '-E', 'UTF8', '--locale=C'], capture_output=True, text=True)
            if r.returncode: raise RuntimeError(r.stdout + r.stderr)
        opts = f'-p {self.port} -k {self.sockdir} -c listen_addresses=127.0.0.1 ' + ' '.join(f'-c {k}={v}' for k, v in self.conf.items())
        subprocess.run([f'{PG_BIN}/pg_ctl', '-D', str(self.d / 'data'), '-o', opts, '-l', str(self.d / 'pg.log'), '-w', '-t', str(timeout), 'start'],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True); return self

    def dsn(self, db='postgres'): return f'host=127.0.0.1 port={self.port} user=postgres dbname={db}'

    def conn(self, db='postgres', autocommit=True, **kw):
        return psycopg.connect(self.dsn(db), autocommit=autocommit, **kw)

    def q(self, sql, args=None, db='postgres'):
        with self.conn(db) as c:
            cur = c.execute(sql, args)
            return cur.fetchall() if cur.description else None

    def kill(self):
        """kill -9 postmaster 和它的所有子进程(只杀 postmaster 的话,子进程还占着共享内存,重启会失败)。"""
        pid = self.d / 'data' / 'postmaster.pid'
        if pid.exists():
            pm = int(pid.read_text().splitlines()[0])
            kids = subprocess.run(['pgrep', '-P', str(pm)], capture_output=True, text=True).stdout.split()
            for k in kids + [str(pm)]:
                try: os.kill(int(k), signal.SIGKILL)
                except Exception: pass
            time.sleep(0.5)

    def stop(self): self._pgctl('-m', 'fast', 'stop')
    def log(self): return (self.d / 'pg.log').read_text() if (self.d / 'pg.log').exists() else ''


def ms(t): return f'{t * 1000:.1f} ms'
def sh(cmd, timeout=120):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout); return (r.stdout + r.stderr).rstrip()
def show(code): return textwrap.dedent(code).strip('\n')
def src(code, title='源码'):
    lines = show(code).split('\n'); print(f'  {title}:'); print('\n'.join(f'    {i + 1:>3} | {l}' for i, l in enumerate(lines)))
def table(rows, hdr=None):
    """简单的文本表格(对齐)。rows 是元组列表。"""
    rows = [tuple('NULL' if c is None else str(c) for c in r) for r in rows]
    if hdr: rows = [tuple(hdr)] + rows
    w = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for k, r in enumerate(rows):
        print('  ' + ' | '.join(c.ljust(w[i]) for i, c in enumerate(r)))
        if hdr and k == 0: print('  ' + '-+-'.join('-' * x for x in w))


# ---------- RocketMQ 5.5.1(官方 bin 包,ttmp/rocketmq-all-5.5.1-bin-release;实验结束后可整体删除)----------
RMQ_HOME = TT / 'rocketmq-all-5.5.1-bin-release'
JAVA17 = '/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home'


class RocketMQ:
    """NameServer + 单 Broker(都是 java -cp lib/* 直接起,自己指定堆大小和端口;broker 的 listenPort-2、+1 也要空闲)。"""
    def __init__(self, name, base=None, broker_conf=None, clean=True):
        self.name = name; self.d = tdir('rmq_' + name, clean)
        b = base
        if b is None:
            while True:
                b = free_port()
                if all(socket.socket().connect_ex(('127.0.0.1', b + k)) != 0 for k in (-2, 0, 1, 2, 3)): break
        self.ns_port = b + 3; self.port = b; self.conf = dict(broker_conf or {}); self.ps = []
        _nodes.append(self)

    def _env(self): return dict(os.environ, JAVA_HOME=JAVA17, ROCKETMQ_HOME=str(RMQ_HOME), PATH=JAVA17 + '/bin:' + os.environ['PATH'])

    def start(self, timeout=90):
        cp = str(RMQ_HOME / 'lib' / '*')
        (self.d / 'namesrv.conf').write_text(f'listenPort={self.ns_port}\nkvConfigPath={self.d}/kvConfig.json\nconfigStorePath={self.d}/namesrv.properties\n')
        self.ps.append(subprocess.Popen([f'{JAVA17}/bin/java', '-Xms128m', '-Xmx256m', '-cp', cp, 'org.apache.rocketmq.namesrv.NamesrvStartup', '-c', str(self.d / 'namesrv.conf')],
                                        stdout=open(self.d / 'ns.out', 'w'), stderr=subprocess.STDOUT, env=self._env(), start_new_session=True))
        wait_port(self.ns_port, timeout, self.ps[0], self.d / 'ns.out')
        conf = dict(brokerClusterName='DefaultCluster', brokerName='broker-a', brokerId=0, namesrvAddr=f'127.0.0.1:{self.ns_port}', listenPort=self.port,
                    brokerIP1='127.0.0.1', storePathRootDir=str(self.d / 'store'), storePathCommitLog=str(self.d / 'store' / 'commitlog'),
                    autoCreateTopicEnable='true', deleteWhen='04', fileReservedTime=48, flushDiskType='ASYNC_FLUSH',
                    transactionCheckInterval=3000, transactionTimeOut=3000, transactionCheckMax=15, enableControllerMode='false',
                    mappedFileSizeCommitLog=64 * 1024 * 1024, mappedFileSizeConsumeQueue=300000 * 20, diskMaxUsedSpaceRatio=99)
        conf.update(self.conf)
        (self.d / 'broker.conf').write_text('\n'.join(f'{k}={v}' for k, v in conf.items()) + '\n')
        self.ps.append(subprocess.Popen([f'{JAVA17}/bin/java', '-Xms256m', '-Xmx512m', '-XX:MaxDirectMemorySize=512m', '-cp', cp, 'org.apache.rocketmq.broker.BrokerStartup', '-c', str(self.d / 'broker.conf')],
                                        stdout=open(self.d / 'broker.out', 'w'), stderr=subprocess.STDOUT, env=self._env(), start_new_session=True))
        wait_port(self.port, timeout, self.ps[1], self.d / 'broker.out')
        # 等 broker 注册到 NameServer
        t0 = time.time()
        while time.time() - t0 < timeout:
            r = self.admin('clusterList')
            if 'broker-a' in r: break
            time.sleep(1)
        return self

    def admin(self, *a, timeout=60):
        r = subprocess.run([f'{JAVA17}/bin/java', '-Xmx128m', '-cp', str(RMQ_HOME / 'lib' / '*'), 'org.apache.rocketmq.tools.command.MQAdminStartup', *a, '-n', f'127.0.0.1:{self.ns_port}'] if a[0] != 'x' else [],
                           capture_output=True, text=True, env=self._env(), timeout=timeout)
        return (r.stdout + r.stderr)

    def kill(self):
        for p in self.ps:
            if p.poll() is None:
                try: os.killpg(p.pid, signal.SIGKILL)
                except Exception: p.kill()
                p.wait()

    stop = kill
    def log(self, which='broker'):
        f = self.d / f'{which}.out'; return f.read_text() if f.exists() else ''


def java_run(name, files, main, classpath='', args=(), timeout=180, env=None, javac_opts=()):
    """在 ttmp/<name>/ 写 .java 源码,javac(JDK 17)编译,java 运行;返回 (rc, stdout+stderr)。"""
    d = tdir('j_' + name)
    for p, c in files.items():
        f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(textwrap.dedent(c).lstrip('\n'))
    cp = classpath or str(RMQ_HOME / 'lib' / '*')
    e = dict(os.environ, JAVA_HOME=JAVA17, PATH=JAVA17 + '/bin:' + os.environ['PATH']); e.update(env or {})
    r = subprocess.run([f'{JAVA17}/bin/javac', '-nowarn', '-encoding', 'UTF-8', '-cp', cp, '-d', str(d / 'cls'), *javac_opts, *[str(d / p) for p in files if p.endswith('.java')]],
                       capture_output=True, text=True, env=e)
    if r.returncode: return r.returncode, r.stdout + r.stderr
    r = subprocess.run([f'{JAVA17}/bin/java', '-Xmx256m', '-cp', f'{d}/cls:{cp}', main, *args], capture_output=True, text=True, env=e, timeout=timeout)
    return r.returncode, r.stdout + r.stderr
