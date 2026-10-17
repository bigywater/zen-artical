"""Java 实验辅助:在 jtmp/<name>/ 下写真实的 .java 源码,用 javac 编译、java 运行(JDK 17 / 21 / 27 可选)。
需要第三方库时用 mcp() 经 Maven 解析 classpath(代理 127.0.0.1:1087)。绝不碰 6379、8181/9101/9333 与用户自己的数据库;自己起的服务用 9600+ 端口。"""
import os, sys, subprocess, shutil, pathlib, textwrap, time, json, re, socket, signal, threading, statistics, hashlib
HERE = pathlib.Path(__file__).parent
JT = HERE / 'jtmp'; JT.mkdir(exist_ok=True)
JDKS = {'17': '/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home', '21': '/opt/homebrew/opt/openjdk@21', '27': '/opt/homebrew/opt/openjdk', '25g': '/private/tmp/claude-501/-Users-w-Desktop-zen/ba230915-496f-4157-87cf-8cee4040b1b9/scratchpad/graal/graalvm-community-openjdk-25.0.2+10.1/Contents/Home'}
sys.path.insert(0, str(HERE))
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'): os.environ.pop(k, None)
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
import rl
from rl import tee, save
from fl import free_port, numbered, show, ms, median, pr
def tidy(t):
    t = re.sub(r'\x1b\[[0-9;]*m', '', t).replace(str(JT), '<jtmp>').replace(str(HERE.parent), '<scratch>').replace(str(HERE), '<实验目录>')
    t = re.sub(r'/private/tmp/claude-501/[^\s"\':]*?/scratchpad', '<scratch>', t); t = t.replace('/Users/w/.m2/repository', '<m2>')
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).lstrip('\n')
def jenv(jdk='21', **extra):
    e = dict(os.environ); e['JAVA_HOME'] = JDKS[jdk]; e['PATH'] = JDKS[jdk] + '/bin:' + e['PATH']; e.update({k: str(v) for k, v in extra.items()}); return e
def jdir(name, clean=True):
    d = JT / name
    if clean: shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True); return d
def write(d, files):
    for p, c in files.items():
        f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(textwrap.dedent(c).lstrip('\n'))
def mcp(*coords, jdk='21'):
    """Maven 坐标 group:artifact:version → classpath 字符串(含传递依赖),结果缓存。"""
    key = hashlib.md5(('|'.join(coords) + jdk).encode()).hexdigest()[:10]; cf = JT / f'_cp_{key}.txt'
    if cf.exists(): return cf.read_text()
    deps = ''.join(f'<dependency><groupId>{g}</groupId><artifactId>{a}</artifactId><version>{v}</version></dependency>' for g, a, v in (c.split(':')[:3] for c in coords))
    pom = JT / f'_pom_{key}.xml'; pom.write_text(f'<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>x</groupId><artifactId>x</artifactId><version>1</version><dependencies>{deps}</dependencies></project>')
    e = jenv(jdk, MAVEN_OPTS='-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=1087 -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=1087')
    r = subprocess.run(['mvn', '-q', '-f', str(pom), 'dependency:build-classpath', f'-Dmdep.outputFile={cf}'], env=e, capture_output=True, text=True, timeout=600)
    if r.returncode != 0: raise RuntimeError('mvn failed: ' + (r.stdout + r.stderr)[-800:])
    return cf.read_text()
def jrun(name, files, main='Main', jdk='21', jopts=(), args=(), cp='', preview=False, timeout=120, copts=(), clean=True, show_compile=True, env=None):
    """写源码 → javac → java。返回 dict(crc, cout, rc, out)。"""
    d = jdir(name, clean); write(d, files); out = d / 'out'; out.mkdir(exist_ok=True)
    e = jenv(jdk, **(env or {})); fs = [str(p) for p in d.rglob('*.java')]
    pv = ['--enable-preview', '--release', jdk] if preview else []
    cr = subprocess.run(['javac', *pv, *copts, '-d', str(out), *(['-cp', cp] if cp else []), *fs], cwd=d, env=e, capture_output=True, text=True, timeout=timeout)
    res = dict(crc=cr.returncode, cout=tidy(cr.stdout + cr.stderr), rc=None, out='')
    if cr.returncode != 0: return res
    try:
        r = subprocess.run(['java', *(['--enable-preview'] if preview else []), *jopts, '-cp', str(out) + (':' + cp if cp else ''), main, *args], cwd=d, env=e, capture_output=True, text=True, timeout=timeout)
        res.update(rc=r.returncode, out=tidy(r.stdout + r.stderr))
    except subprocess.TimeoutExpired as ex: res.update(rc=-9, out=tidy((ex.stdout or b'').decode() if isinstance(ex.stdout, bytes) else (ex.stdout or '')) + '\n(超时)')
    return res
def jshow(r, n=40, w=170):
    if r['crc'] != 0: print('  编译失败:'); pr(r['cout'], n, '    ', w); return
    pr(r['out'], n, '    ', w)
def jsrc(files, title=None):
    for p, c in files.items():
        print(f'  {title or p}:'); print('\n'.join('    ' + l for l in numbered(c).split('\n')))

def jmhrun(name, files, args=('-wi', '3', '-i', '5', '-w', '1', '-r', '1', '-f', '1'), jdk='21', jvmargs=(), timeout=900, regex='.*', sysprops=()):
    """用 JMH 1.37 编译并运行(注解处理器生成基准代码);返回 dict(rows=[(benchmark, mode, score, err, unit)], out, crc, cout)。"""
    cp = mcp('org.openjdk.jmh:jmh-core:1.37', 'org.openjdk.jmh:jmh-generator-annprocess:1.37', jdk=jdk)
    d = jdir(name); write(d, files); out = d / 'out'; out.mkdir(exist_ok=True); e = jenv(jdk)
    fs = [str(p) for p in d.rglob('*.java')]
    cr = subprocess.run(['javac', '-proc:full', '-cp', cp, '-processorpath', cp, '-d', str(out), *fs], cwd=d, env=e, capture_output=True, text=True, timeout=timeout)
    if cr.returncode != 0: return dict(rows=[], out='', crc=cr.returncode, cout=tidy(cr.stdout + cr.stderr))
    jv = ['-jvmArgs', ' '.join(jvmargs)] if jvmargs else []
    r = subprocess.run(['java', *sysprops, '-cp', f'{out}:{cp}', 'org.openjdk.jmh.Main', regex, *args, *jv], cwd=d, env=e, capture_output=True, text=True, timeout=timeout)
    o = r.stdout + r.stderr
    rows = [(m.group(1), m.group(2), float(m.group(4)), float(m.group(5)) if m.group(5) else None, m.group(6)) for m in re.finditer(r'^(\S+)\s+(avgt|thrpt|sample|ss)\s+(\d+)\s+([\d.]+)(?:\s+±\s+([\d.]+|NaN))?\s+(\S+)\s*$', o, re.M)]
    return dict(rows=rows, out=o, crc=0, cout='')

# ---------- JDBC 实验用的临时数据库实例(端口 9500+/9600+,数据目录在 jtmp/dbdata/,绝不碰用户自己的 postgres(5432)/mysqld(3306)) ----------
PGBIN = '/opt/homebrew/bin'
class PGI:
    def __init__(self, port=9501, conf=None):
        assert port not in (5432, 3306, 6379, 8181, 9101, 9333)
        self.port = port; self.dir = JT / 'dbdata' / f'pg{port}'; self.sock = f'/tmp/pgj{port}'; self.conf = conf or {}
    def start(self):
        if self.dir.exists(): subprocess.run([f'{PGBIN}/pg_ctl', '-D', str(self.dir), '-m', 'immediate', 'stop'], capture_output=True)
        shutil.rmtree(self.dir, ignore_errors=True); shutil.rmtree(self.sock, ignore_errors=True); os.makedirs(self.sock); self.dir.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([f'{PGBIN}/initdb', '-D', str(self.dir), '-U', 'lab', '--auth=trust', '-E', 'UTF8', '--locale=C'], capture_output=True, text=True); assert r.returncode == 0, r.stderr
        opts = f'-p {self.port} -k {self.sock} -c listen_addresses=127.0.0.1 -c max_connections=200' + ''.join(f' -c {k}={v}' for k, v in self.conf.items())
        r = subprocess.run([f'{PGBIN}/pg_ctl', '-D', str(self.dir), '-o', opts, '-l', str(self.dir / 'pg.log'), '-w', 'start'], capture_output=True, text=True); assert r.returncode == 0, r.stderr + (self.dir / 'pg.log').read_text()[-500:]
        r = subprocess.run([f'{PGBIN}/createdb', '-h', '127.0.0.1', '-p', str(self.port), '-U', 'lab', 'lab'], capture_output=True, text=True); assert r.returncode == 0, r.stderr
        return self
    def stop(self):
        subprocess.run([f'{PGBIN}/pg_ctl', '-D', str(self.dir), '-m', 'fast', '-w', 'stop'], capture_output=True, text=True); shutil.rmtree(self.sock, ignore_errors=True)
    def psql(self, sql):
        r = subprocess.run([f'{PGBIN}/psql', '-h', '127.0.0.1', '-p', str(self.port), '-U', 'lab', '-d', 'lab', '-At', '-c', sql], capture_output=True, text=True); return r.stdout.strip() + r.stderr.strip()
    url = property(lambda s: f'jdbc:postgresql://127.0.0.1:{s.port}/lab?user=lab')

class MYI:
    def __init__(self, port=9601, conf=None):
        assert port not in (5432, 3306, 33060, 6379, 8181, 9101, 9333)
        self.port = port; self.dir = JT / 'dbdata' / f'my{port}'; self.sock = f'/tmp/myj{port}.sock'; self.conf = conf or {}; self.p = None
    def start(self):
        self.stop(); shutil.rmtree(self.dir, ignore_errors=True); self.dir.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(['/opt/homebrew/bin/mysqld', '--no-defaults', '--initialize-insecure', f'--datadir={self.dir}', '--user=' + os.environ.get('USER', 'w')], capture_output=True, text=True); assert r.returncode == 0, r.stderr[-600:]
        args = ['/opt/homebrew/bin/mysqld', '--no-defaults', f'--datadir={self.dir}', f'--port={self.port}', f'--socket={self.sock}', '--mysqlx=OFF', '--bind-address=127.0.0.1', f'--pid-file={self.dir}/my.pid', '--max_connections=200', '--innodb_buffer_pool_size=256M', f'--log-error={self.dir}/err.log'] + [f'--{k}={v}' for k, v in self.conf.items()]
        self.p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        for _ in range(120):
            if os.path.exists(self.sock) and subprocess.run(['/opt/homebrew/bin/mysqladmin', '--no-defaults', f'--socket={self.sock}', '-uroot', 'ping'], capture_output=True).returncode == 0: break
            time.sleep(0.5)
        else: raise RuntimeError('mysqld 没有起来:' + (self.dir / 'err.log').read_text()[-500:])
        self.sql('CREATE DATABASE IF NOT EXISTS lab'); return self
    def sql(self, q):
        r = subprocess.run(['/opt/homebrew/bin/mysql', '--no-defaults', f'--socket={self.sock}', '-uroot', '-N', '-B', '-e', q], capture_output=True, text=True); return (r.stdout + r.stderr).strip()
    def stop(self):
        if os.path.exists(self.sock): subprocess.run(['/opt/homebrew/bin/mysqladmin', '--no-defaults', f'--socket={self.sock}', '-uroot', 'shutdown'], capture_output=True, text=True)
        if self.p:
            try: self.p.wait(timeout=30)
            except Exception: self.p.kill()
    url = property(lambda s: f'jdbc:mysql://127.0.0.1:{s.port}/lab?user=root&allowPublicKeyRetrieval=true&useSSL=false')
