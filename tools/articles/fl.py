"""Flask 实验辅助:在 fltmp/<name>/ 下生成真实的小应用,用 flenv 虚拟环境的 python 运行。
端口 9600+(绝不碰 6379、8181、9101、9333,以及用户自己的 mysql / postgres);需要数据库时用 dj.PG 另起的临时 PostgreSQL(端口 9450+)。"""
import os, sys, subprocess, shutil, pathlib, textwrap, time, json, re, socket, http.client, signal, threading, statistics
HERE = pathlib.Path(__file__).parent
PY = str(HERE.parent / 'flenv' / 'bin' / 'python'); BIN = HERE.parent / 'flenv' / 'bin'
FT = HERE / 'fltmp'; FT.mkdir(exist_ok=True)
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'): os.environ.pop(k, None)
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
sys.path.insert(0, str(HERE))
import rl
from rl import tee, save
FORBIDDEN = {5432, 6379, 8181, 9101, 9333, 3306}
_port = [9600]
def free_port():
    while True:
        _port[0] += 1; p = _port[0]
        if p in FORBIDDEN: continue
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1', p)) != 0: return p
def show(code): return textwrap.dedent(code).strip('\n')
def numbered(code): return '\n'.join(f'{i + 1:>3} | {l}' for i, l in enumerate(show(code).split('\n')))
def src(code, title='源码'): print(f'  {title}:'); print('\n'.join('    ' + l for l in numbered(code).split('\n')))
def app(name, files, clean=True):
    """新建(覆盖)fltmp/<name>/ 并写入文件({相对路径: 内容}),返回目录。"""
    d = FT / name
    if clean: shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    for rel, txt in files.items():
        p = d / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(textwrap.dedent(txt).lstrip('\n'))
    return d
def env(d, **extra):
    e = dict(os.environ); e['PYTHONPATH'] = str(d); e['PYTHONUNBUFFERED'] = '1'; e['PYTHONDONTWRITEBYTECODE'] = '1'; e.pop('FLASK_APP', None); e.update({k: str(v) for k, v in extra.items()}); return e
def clean(t): return rl.san(t) if hasattr(rl, 'san') else t.replace(str(HERE), '<实验目录>')
def py(d, code, timeout=120, **extra):
    """在 d 目录里运行一段 Python(用 flenv)。返回 (rc, stdout+stderr)"""
    r = subprocess.run([PY, '-c', textwrap.dedent(code)], cwd=d, env=env(d, **extra), capture_output=True, text=True, timeout=timeout); return r.returncode, tidy(r.stdout + r.stderr)
def pyfile(d, name, timeout=120, args=(), **extra):
    r = subprocess.run([PY, name, *args], cwd=d, env=env(d, **extra), capture_output=True, text=True, timeout=timeout); return r.returncode, tidy(r.stdout + r.stderr)
def tidy(t):
    t = re.sub(r'\x1b\[[0-9;]*m', '', t).replace(str(HERE), '<实验目录>').replace(str(HERE.parent), '<scratch>')
    t = re.sub(r'/private/tmp/claude-501/[^\s"\']*?/scratchpad', '<scratch>', t)
    t = re.sub(r'/opt/homebrew/Cellar/python@3\.14/[^\s"\']*/lib/python3\.14/', '<stdlib>/', t)
    t = re.sub(r'<scratch>/flenv/lib/python3\.14/site-packages/', '<site-packages>/', t)
    t = re.sub(r'Debugger PIN: \d{3}-\d{3}-\d{3}', 'Debugger PIN: ***-***-***', t)
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).lstrip('\n')
def pr(txt, n=30, ind='    ', w=170):
    L = txt.split('\n'); print('\n'.join(ind + l[:w] for l in L[:n]))
    if len(L) > n: print(f'{ind}…(共 {len(L)} 行)')
def ms(t0): return (time.perf_counter() - t0) * 1000
def median(xs): return statistics.median(xs)

def http(port, method='GET', path='/', headers=None, body=None, timeout=10, host='127.0.0.1'):
    """真实 HTTP 请求。返回 (status, headers_list, body_bytes, 耗时ms)"""
    c = http.client.HTTPConnection(host, port, timeout=timeout) if False else __import__('http.client').client.HTTPConnection(host, port, timeout=timeout)
    t0 = time.perf_counter(); c.request(method, path, body=body, headers=headers or {}); r = c.getresponse(); b = r.read(); dt = ms(t0); h = r.getheaders(); c.close(); return r.status, h, b, dt
class Server:
    """起一个真实服务进程(gunicorn / flask run / uvicorn / uwsgi 等),等端口可连,结束时整个进程组一起停。"""
    def __init__(self, d, cmd, port=None, wait=15, **extra):
        self.port = port or free_port(); self.d = d; self.log = d / f'server{self.port}.log'
        cmd = [c.replace('{port}', str(self.port)) for c in cmd]
        if cmd[0] in ('gunicorn', 'flask', 'uvicorn', 'uwsgi', 'python'): cmd[0] = str(BIN / cmd[0])
        self.f = open(self.log, 'w'); self.p = subprocess.Popen(cmd, cwd=d, env=env(d, **extra), stdout=self.f, stderr=subprocess.STDOUT, start_new_session=True)
        t0 = time.time()
        while time.time() - t0 < wait:
            if self.p.poll() is not None: raise RuntimeError('server exited: ' + tidy(self.log.read_text())[-800:])
            with socket.socket() as s:
                if s.connect_ex(('127.0.0.1', self.port)) == 0: break
            time.sleep(0.05)
        else: raise RuntimeError('server not ready: ' + tidy(self.log.read_text())[-800:])
        self.ready = time.time() - t0
    def get(self, path='/', **kw): return http(self.port, 'GET', path, **kw)
    def req(self, method, path, **kw): return http(self.port, method, path, **kw)
    def logtext(self): return tidy(self.log.read_text())
    def stop(self, sig=signal.SIGTERM):
        try: os.killpg(self.p.pid, sig)
        except ProcessLookupError: pass
        try: self.p.wait(10)
        except subprocess.TimeoutExpired: os.killpg(self.p.pid, signal.SIGKILL)
        self.f.close()
    def __enter__(self): return self
    def __exit__(self, *a): self.stop()
def hdrs(h, *names):
    """从 [(name,value)...] 里取出指定名字(不区分大小写)的头,保持顺序。"""
    ns = {n.lower() for n in names}; return [(k, v) for k, v in h if k.lower() in ns]
def fmt_h(h, *names): return '\n'.join(f'{k}: {v}' for k, v in (hdrs(h, *names) if names else h))
def show_resp(r, body=True, names=None, n=12, w=150):
    """打印 test_client 的 Response:状态行、(选定的)头、正文前 n 行。"""
    print(f'    {r.status}')
    for k, v in r.headers:
        if names is None or k.lower() in {x.lower() for x in names}: print(f'    {k}: {v}'[:w])
    if body:
        t = r.get_data(as_text=True)
        for l in t.split('\n')[:n]: print('    | ' + l[:w])
