import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f178'); R = {}
import pathlib
P = FT / 'f178proj'; shutil.rmtree(P, ignore_errors=True); P.mkdir(parents=True)
(P / 'app.py').write_text('print("app v1")\n'); (P / 'requirements.txt').write_text('flask==3.1.3\ngunicorn==26.2.0\n')
(P / 'venv' / 'lib').mkdir(parents=True); (P / 'venv' / 'lib' / 'junk.bin').write_bytes(os.urandom(40 * 1024 * 1024)); (P / '.git').mkdir(); (P / '.git' / 'pack.bin').write_bytes(os.urandom(10 * 1024 * 1024)); (P / '__pycache__').mkdir(); (P / '__pycache__' / 'x.pyc').write_bytes(b'x' * 1000)
def docker(*args, timeout=120):
    try: r = subprocess.run(['docker'] + list(args), cwd=P, capture_output=True, text=True, timeout=timeout, env={**os.environ, 'DOCKER_BUILDKIT': '1'}); return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired: return 124, 'TIMEOUT'
def build(df, tag, extra=()):
    rc, out = docker('build', '--progress=plain', '-f', df, '-t', tag, *extra, '.'); return rc, out
def ctx(out): 
    m = re.search(r'load build context\n#\d+ transferring context: ([\d.]+\s?[kMGB]+)', out); return m.group(1) if m else '?'
def cached_steps(out): return [l.strip() for l in out.splitlines() if re.search(r'#\d+ (CACHED|DONE)', l) or 'CACHED' in l][:0]
def steps(out):
    res = {}
    for m in re.finditer(r'#(\d+) \[[^\]]*\] (COPY|ADD|WORKDIR|ENV|LABEL|USER)[^\n]*\n(?:#\d+ [^\n]*\n)*?', out): pass
    L = []; cur = {}
    for l in out.splitlines():
        m = re.match(r'#(\d+) \[([^\]]*)\] (.*)', l)
        if m: cur[m.group(1)] = [m.group(2), m.group(3), 'built']
        m2 = re.match(r'#(\d+) CACHED', l)
        if m2 and m2.group(1) in cur: cur[m2.group(1)][2] = 'CACHED'
    return [(v[1][:50], v[2]) for k, v in sorted(cur.items(), key=lambda kv: int(kv[0])) if 'COPY' in v[1] or 'ADD' in v[1]]
print('== 一:.dockerignore 对构建上下文大小的影响(项目目录里有 40 MB 的 venv、10 MB 的 .git、__pycache__,基础镜像用 scratch,只做 COPY)')
DF1 = 'FROM scratch\nCOPY . /app\n'; (P / 'Dockerfile.one').write_text(DF1)
(P / '.dockerignore').unlink(missing_ok=True); rc, out = build('Dockerfile.one', 'f178:one'); c1 = ctx(out); print(f'  没有 .dockerignore:退出码 {rc},上下文 {c1}'); R['ctx_no_ignore'] = [rc, c1]
(P / '.dockerignore').write_text('venv\n.git\n__pycache__\n*.pyc\n'); rc, out = build('Dockerfile.one', 'f178:two'); c2 = ctx(out); print(f'  有 .dockerignore(venv、.git、__pycache__):退出码 {rc},上下文 {c2}'); R['ctx_ignore'] = [rc, c2]
rc, out = docker('image', 'inspect', 'f178:one', '--format', '{{.Size}}'); s1 = int(out.strip()) if out.strip().isdigit() else None; rc, out = docker('image', 'inspect', 'f178:two', '--format', '{{.Size}}'); s2 = int(out.strip()) if out.strip().isdigit() else None
print(f'  镜像大小:没有 .dockerignore {s1 / 1e6:.1f} MB,有 {s2 / 1e6:.3f} MB(COPY . 把 venv 与 .git 都装进了镜像)' if s1 and s2 else '  (没取到镜像大小)'); R['img_size'] = [s1, s2]
print()
print('== 二:层缓存顺序:先 COPY requirements.txt 再 COPY 源码,vs 一次 COPY . 。只改源码文件后重新构建,哪些步骤命中缓存')
DFa = 'FROM scratch\nCOPY . /app\nCOPY requirements.txt /app/requirements.txt\n'; DFb = 'FROM scratch\nCOPY requirements.txt /app/requirements.txt\nCOPY app.py /app/app.py\n'
(P / 'Dockerfile.a').write_text(DFa); (P / 'Dockerfile.b').write_text(DFb); R['cache'] = {}
for name, df in (('A:先 COPY .,再 COPY requirements.txt', 'Dockerfile.a'), ('B:先 COPY requirements.txt,再 COPY app.py', 'Dockerfile.b')):
    NONCE = str(time.time()); (P / 'requirements.txt').write_text(f'flask==3.1.3\ngunicorn==26.2.0\n# {NONCE}\n'); (P / 'app.py').write_text(f'print("app v1 {NONCE}")\n'); build(df, 'f178:' + df[-1]); (P / 'app.py').write_text(f'print("app v2 {NONCE}")\n'); rc, out = build(df, 'f178:' + df[-1]); st = steps(out)
    print(f'  [{name}] 只改了 app.py 之后的 COPY 步骤:'); [print(f'     {a:<50} {b}') for a, b in st]; R['cache'][name] = st
print()
print('== 三:CMD 的写法写进镜像配置里是什么(docker inspect):shell 形式 与 exec 形式')
DFc = 'FROM scratch\nCMD gunicorn -b 0.0.0.0:8000 app:app\n'; DFd = 'FROM scratch\nCMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]\n'
R['cmd'] = {}
for name, df, tag in (('shell 形式 CMD gunicorn ...', DFc, 'f178:shellcmd'), ('exec 形式 CMD ["gunicorn", ...]', DFd, 'f178:execcmd')):
    (P / 'Dockerfile.cmd').write_text(df); build('Dockerfile.cmd', tag); rc, out = docker('image', 'inspect', tag, '--format', '{{json .Config.Cmd}}'); print(f'  {name:<32} 镜像里的 Cmd = {out.strip()}'); R['cmd'][name] = out.strip()
print()
print('== 四:docker build --check:对 Dockerfile 做静态检查(不需要拉镜像)')
(P / 'Dockerfile.lint').write_text('FROM scratch\nCOPY . .\nCMD python app.py\nMAINTAINER x\n'); rc, out = docker('build', '--check', '-f', 'Dockerfile.lint', '.', timeout=90); lines = [l.strip() for l in out.splitlines() if l.startswith('WARNING') or l.startswith('JSON') or l.startswith('Maintainer')][:6]; print(f'  退出码 {rc};提示:'); [print('    ' + l[:150]) for l in lines]; R['lint'] = [rc, lines]

print()
print('== 五:Dockerfile 里的安装步骤在本地原样做一遍:新建 venv,pip install --no-cache-dir -r requirements.txt(本机的 Flask,不需要镜像)')
L = FT / 'f178local'; shutil.rmtree(L, ignore_errors=True); L.mkdir(parents=True)
(L / 'requirements.txt').write_text('flask==3.1.3\ngunicorn==26.2.0\n')
pe = dict(os.environ, HTTPS_PROXY='http://127.0.0.1:1087', HTTP_PROXY='http://127.0.0.1:1087', PIP_DISABLE_PIP_VERSION_CHECK='1'); [pe.pop(k, None) for k in ('NO_PROXY',)]
def dsize(pth): return sum(f.stat().st_size for f in pathlib.Path(pth).rglob('*') if f.is_file())
R['pip'] = {}
for label, nocache in (('pip install(默认,有缓存)', False), ('pip install --no-cache-dir', True)):
    v = L / ('venv_' + ('nc' if nocache else 'c')); cache = L / ('cache_' + ('nc' if nocache else 'c')); subprocess.run(['python3', '-m', 'venv', str(v)], check=True)
    t0 = time.perf_counter(); r = subprocess.run([str(v / 'bin' / 'pip'), 'install', '-q', *(['--no-cache-dir'] if nocache else []), '-r', str(L / 'requirements.txt')], env=dict(pe, PIP_CACHE_DIR=str(cache)), capture_output=True, text=True); dt = time.perf_counter() - t0
    n = len([x for x in subprocess.run([str(v / 'bin' / 'pip'), 'list', '--format=freeze'], capture_output=True, text=True).stdout.splitlines() if '==' in x and not x.startswith(('pip=='))])
    cs = dsize(cache) if cache.exists() else 0
    print(f'  {label:<26}退出码 {r.returncode},用时 {dt:.1f} s,装了 {n} 个包,venv {dsize(v) / 1e6:.1f} MB,pip 缓存目录 {cs / 1e6:.1f} MB'); R['pip'][label] = [r.returncode, round(dt, 1), n, round(dsize(v) / 1e6, 1), round(cs / 1e6, 1)]
v = L / 'venv_nc'; fr = subprocess.run([str(v / 'bin' / 'pip'), 'list', '--format=freeze'], capture_output=True, text=True).stdout.split(); print('  装好的包:', ', '.join(x for x in fr if not x.startswith('pip==')))
print()
print('== 六:CMD ["gunicorn", "-b", ...] 的绑定地址:0.0.0.0 vs 127.0.0.1,从本机回环地址与本机局域网地址(en0)分别访问')
(L / 'app.py').write_text('from flask import Flask\napp = Flask(__name__)\n@app.get("/")\ndef i(): return "ok"\n')
lan = subprocess.run(['ipconfig', 'getifaddr', 'en0'], capture_output=True, text=True).stdout.strip(); R['bind'] = {}
def try_get(host, port):
    try: c = hc.HTTPConnection(host, port, timeout=2); c.request('GET', '/'); r = c.getresponse(); b = r.read().decode(); return f'{r.status} {b}'
    except Exception as e: return type(e).__name__
import http.client as hc
for bind in ('0.0.0.0', '127.0.0.1'):
    port = free_port(); p = subprocess.Popen([str(v / 'bin' / 'gunicorn'), '-b', f'{bind}:{port}', 'app:app'], cwd=L, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True); time.sleep(1.5)
    a = try_get('127.0.0.1', port); b = try_get(lan, port) if lan else '(没有 en0 地址)'
    os.killpg(p.pid, signal.SIGKILL); p.wait(); print(f'  -b {bind}:PORT  →  经 127.0.0.1 访问:{a};经局域网地址访问:{b}'); R['bind'][bind] = [a, b]
print('  (容器里「外部」访问走的是容器自己的网卡地址,不是容器内的 127.0.0.1;这里的局域网地址是同样的道理,没有用到 Docker 网络)')
print()
print('== 七:PYTHONUNBUFFERED:stdout 不是终端(被管道/文件接走,Docker 收日志就是这样)时,视图里 print 的那行什么时候出现')
(L / 'pr.py').write_text('from flask import Flask\napp = Flask(__name__)\n@app.get("/")\ndef i():\n    print("hello from view")\n    return "ok"\n')
R['unbuf'] = {}
for label, ex in (('默认', {}), ('PYTHONUNBUFFERED=1', {'PYTHONUNBUFFERED': '1'})):
    port = free_port(); lf = L / f'out_{len(R["unbuf"])}.log'; fh = open(lf, 'w')
    p = subprocess.Popen([str(v / 'bin' / 'gunicorn'), '-b', f'127.0.0.1:{port}', 'pr:app'], cwd=L, env=dict(os.environ, **ex), stdout=fh, stderr=subprocess.STDOUT, start_new_session=True); time.sleep(1.5)
    try_get('127.0.0.1', port); time.sleep(1.5); seen = 'hello from view' in lf.read_text()
    os.killpg(p.pid, signal.SIGTERM); time.sleep(1.0); after = 'hello from view' in lf.read_text(); os.killpg(p.pid, signal.SIGKILL) if p.poll() is None else None; p.wait(); fh.close()
    print(f'  {label:<20}请求后 1.5 秒日志里有那行:{seen};进程被 SIGTERM 退出之后有:{after}'); R['unbuf'][label] = [seen, after]
print()
print('== 八:代码目录不可写(用 chmod -R a-w 模拟「用非 root 用户运行,而文件属于 root」):视图往应用目录里写文件')
(L / 'wr.py').write_text('from flask import Flask\napp = Flask(__name__)\n@app.get("/")\ndef i():\n    open("data.txt", "w").write("x")\n    return "written"\n@app.errorhandler(500)\ndef e(x): return type(x.original_exception).__name__, 500\n')
R['perm'] = {}
for label, ro in (('目录可写', False), ('目录只读(a-w)', True)):
    subprocess.run(['chmod', '-R', 'a-w' if ro else 'u+w', str(L)]) if ro else subprocess.run(['chmod', '-R', 'u+w', str(L)])
    (L / 'data.txt').unlink(missing_ok=True) if not ro else None
    if ro: subprocess.run(['chmod', 'a-w', str(L)])
    port = free_port(); p = subprocess.Popen([str(v / 'bin' / 'gunicorn'), '-b', f'127.0.0.1:{port}', 'wr:app'], cwd=L, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True); time.sleep(1.5)
    out = try_get('127.0.0.1', port); os.killpg(p.pid, signal.SIGKILL); p.wait(); print(f'  {label:<16}→ {out}'); R['perm'][label] = out
subprocess.run(['chmod', '-R', 'u+w', str(L)])
print('  (这是用权限位模拟,不是真的换了一个用户;root 不受权限位限制,所以容器里用 root 时这个问题看不到)')

for t in ('f178:one', 'f178:two', 'f178:a', 'f178:b', 'f178:shellcmd', 'f178:execcmd'): docker('rmi', '-f', t)
save('f178', R)
