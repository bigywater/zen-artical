"""Spring 实验辅助(第 x 系列):在 jtmp/<name>/ 下写真实的 Spring Boot 源码,javac 编译,java 运行。
依赖经 Maven 解析成 classpath(导入 spring-boot-dependencies 与 spring-cloud-dependencies 两个 BOM,所以坐标可以不写版本;代理 127.0.0.1:1087)。
Spring Boot 4.0.8 / Spring Cloud 2025.1.3 / JDK 21(必要时 17、27)。端口从 9600 起,绝不碰 6379、8181/9101/9333 与用户自己的数据库。"""
import os, sys, subprocess, shutil, pathlib, textwrap, time, json, re, socket, signal, threading, statistics, hashlib, http.client, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from jl import *
BOOT = '4.0.8'; CLOUD = '2025.1.3'
ENV_X = f'本机 macOS 27 arm64 / OpenJDK 21.0.12(Homebrew) / Spring Boot {BOOT}(对应 Spring Framework 7.0.x) / Spring Cloud {CLOUD};用 javac 编译、java 直接运行,依赖由 Maven 从 Maven Central 解析;数字每次运行会有小幅抖动'
def scp(*coords, jdk='21', boot=BOOT, cloud=CLOUD):
    """坐标 group:artifact[:version] → classpath(含传递依赖),结果缓存。没写版本的由 Boot / Cloud 的 BOM 决定。"""
    key = hashlib.md5(('|'.join(coords) + jdk + boot + cloud).encode()).hexdigest()[:10]; cf = JT / f'_scp_{key}.txt'
    if cf.exists(): return cf.read_text()
    deps = ''.join(f'<dependency><groupId>{c.split(":")[0]}</groupId><artifactId>{c.split(":")[1]}</artifactId>' + (f'<version>{c.split(":")[2]}</version>' if c.count(':') >= 2 else '') + '</dependency>' for c in coords)
    bom = lambda g, a, v: f'<dependency><groupId>{g}</groupId><artifactId>{a}</artifactId><version>{v}</version><type>pom</type><scope>import</scope></dependency>'
    pom = JT / f'_spom_{key}.xml'
    pom.write_text(f'<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>x</groupId><artifactId>x</artifactId><version>1</version>'
                   f'<dependencyManagement><dependencies>{bom("org.springframework.boot", "spring-boot-dependencies", boot)}{bom("org.springframework.cloud", "spring-cloud-dependencies", cloud)}</dependencies></dependencyManagement>'
                   f'<dependencies>{deps}</dependencies></project>')
    e = jenv(jdk, MAVEN_OPTS='-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=1087 -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=1087')
    r = subprocess.run(['mvn', '-q', '-f', str(pom), 'dependency:build-classpath', f'-Dmdep.outputFile={cf}'], env=e, capture_output=True, text=True, timeout=900)
    if r.returncode != 0: raise RuntimeError('mvn failed: ' + (r.stdout + r.stderr)[-1200:])
    return cf.read_text()
def sbuild(name, files, cp, jdk='21', clean=True, copts=(), timeout=300):
    """写文件并编译。.java 编译进 out/;其它文件(application.properties 等)原样复制到 out/ 的同一相对路径。返回 dict(dir, out, crc, cout)。"""
    d = jdir(name, clean); write(d, files); out = d / 'out'; out.mkdir(exist_ok=True)
    for p in files:
        if not p.endswith('.java'): (out / p).parent.mkdir(parents=True, exist_ok=True); shutil.copy(d / p, out / p)
    fs = [str(p) for p in d.rglob('*.java')]
    cr = subprocess.run(['javac', '-parameters', *copts, '-d', str(out), '-cp', cp, *fs], cwd=d, env=jenv(jdk), capture_output=True, text=True, timeout=timeout)
    return dict(dir=d, out=out, crc=cr.returncode, cout=tidy(cr.stdout + cr.stderr)[:1800], cp=cp, jdk=jdk)
NORM = re.compile(r'^\d{4}-\d\d-\d\dT[\d:.]+(?:[+-]\d\d:\d\d|Z)\s+(\w+)\s+\d+ --- (?:\[[^\]]*\]\s*)+(\S+)\s*: (.*)$')
def norm(text, loggers=True):
    """把 Spring Boot 的日志行 '2026-10-19T10:00:00.123+08:00  INFO 123 --- [app] [main] c.e.Foo : msg' 缩成 'INFO c.e.Foo: msg'。"""
    o = []
    for l in text.splitlines():
        m = NORM.match(l)
        o.append(f'{m.group(1)} {m.group(2)}: {m.group(3)}' if m else l)
    return '\n'.join(o)
def srun(b, main='Main', args=(), props=None, jopts=(), timeout=120, env=None, cwd=None, stdin=None):
    """一次性运行(跑完就退出)。返回 dict(rc, out, secs)。"""
    if b['crc'] != 0: return dict(rc=None, out='编译失败:\n' + b['cout'], secs=0)
    pr_ = [f'-D{k}={v}' for k, v in (props or {}).items()]; t = time.time()
    try:
        r = subprocess.run(['java', *jopts, *pr_, '-cp', str(b['out']) + ':' + b['cp'], main, *args], cwd=cwd or b['dir'], env=jenv(b['jdk'], **(env or {})), capture_output=True, text=True, timeout=timeout, input=stdin)
        return dict(rc=r.returncode, out=tidy(r.stdout + r.stderr), secs=time.time() - t)
    except subprocess.TimeoutExpired as ex:
        o = ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or '')
        return dict(rc=-9, out=tidy(o) + '\n(超时)', secs=time.time() - t)
class SApp:
    """起一个会一直运行的 Spring 应用(Web 服务等):start() 等到端口可连接,stop() 终止。日志在 d/app.log。"""
    def __init__(self, b, main='Main', props=None, args=(), jopts=(), env=None, port=None, name='app'):
        self.b, self.main, self.args, self.jopts, self.env = b, main, args, jopts, env or {}
        self.port = port or free_port(); self.props = dict(props or {}); self.props.setdefault('server.port', self.port); self.p = None
        self.logf = b['dir'] / f'{name}.log'; self.t_start = None; self.t_up = None
    def start(self, timeout=90, wait_port=True):
        if self.b['crc'] != 0: raise RuntimeError('编译失败:' + self.b['cout'][-800:])
        pr_ = [f'-D{k}={v}' for k, v in self.props.items()]; self.t_start = time.time()
        self.p = subprocess.Popen(['java', *self.jopts, *pr_, '-cp', str(self.b['out']) + ':' + self.b['cp'], self.main, *self.args], cwd=self.b['dir'], env=jenv(self.b['jdk'], **self.env), stdout=open(self.logf, 'w'), stderr=subprocess.STDOUT)
        if wait_port:
            while time.time() - self.t_start < timeout:
                if self.p.poll() is not None: raise RuntimeError('进程退出:' + tidy(self.logf.read_text())[-1500:])
                try: socket.create_connection(('127.0.0.1', int(self.props['server.port'])), 0.2).close(); self.t_up = time.time() - self.t_start; return self
                except OSError: time.sleep(0.05)
            raise RuntimeError('超时:' + tidy(self.logf.read_text())[-1500:])
        return self
    def log(self): return tidy(self.logf.read_text()) if self.logf.exists() else ''
    def get(self, path='/', headers=None, method='GET', body=None, timeout=10, port=None):
        c = http.client.HTTPConnection('127.0.0.1', port or int(self.props['server.port']), timeout=timeout)
        try:
            c.request(method, path, body=body, headers=headers or {}); r = c.getresponse(); d = r.read(); return r.status, d.decode('utf-8', 'replace'), dict(r.getheaders())
        finally: c.close()
    def rss_mb(self):
        r = subprocess.run(['ps', '-o', 'rss=', '-p', str(self.p.pid)], capture_output=True, text=True); return int(r.stdout.strip() or 0) / 1024
    def stop(self, sig=signal.SIGTERM, wait=15):
        if self.p and self.p.poll() is None:
            self.p.send_signal(sig)
            try: self.p.wait(wait)
            except subprocess.TimeoutExpired: self.p.kill(); self.p.wait()
        return self.p.returncode if self.p else None
def lines(text, *pats, maxn=60):
    """挑出包含任一子串/正则的行。"""
    return [l for l in text.splitlines() if any(re.search(p, l) for p in pats)][:maxn]
def show(text, n=40, w=170, ind='  '):
    for l in text.splitlines()[:n]: print(ind + (l if len(l) <= w else l[:w - 1] + '…'))
def res(r, pfx='RES '):
    """取出程序里 System.out.println("RES ...") 打的结果行(去掉前缀)。编译失败时把编译错误当作结果返回。"""
    if r.get('rc') is None and 'out' in r and r['out'].startswith('编译失败'): return r['out'].splitlines()
    return [l[len(pfx):] for l in r['out'].splitlines() if l.startswith(pfx)]
def build_run(name, files, cp, main='demo.Main', jdk='21', args=(), props=None, jopts=(), timeout=120, clean=True):
    """编译加运行一次;编译失败就打印错误并退出。返回 (build, run_result)。"""
    b = sbuild(name, files, cp, jdk=jdk, clean=clean)
    if b['crc'] != 0: print(b['cout'][:3000]); sys.exit(1)
    return b, srun(b, main, args=args, props=props, jopts=jopts, timeout=timeout)

# ---------- 数据库:自己起的 MySQL(txl.MySQL,端口 9150 起,root 无密码只走 unix socket;这里再建一个 TCP 可连的用户 app/app)----------
def mysql(name='xs', opts=()):
    import txl
    m = txl.MySQL(name, opts=opts).start(); m.q('CREATE DATABASE IF NOT EXISTS demo'); m.q("CREATE USER IF NOT EXISTS 'app'@'%' IDENTIFIED BY 'app'"); m.q("GRANT ALL ON *.* TO 'app'@'%'"); return m
def jdbc(m, extra=''):
    return f'jdbc:mysql://127.0.0.1:{m.port}/demo?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC{extra}'
