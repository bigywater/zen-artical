import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f172'); R = {}
APP = '''
import os
from flask import Flask, jsonify
def create_app(name="default"):
    app = Flask(__name__); app.config["NAME"] = name
    @app.get("/")
    def index(): return jsonify(name=app.config["NAME"], pid=os.getpid())
    return app
app = create_app("module-level")
'''
CONF = 'workers = 3\nbind = "127.0.0.1:%PORT%"\naccesslog = "-"\nraw_env = ["FROM_CONF=1"]\n'
d = mkapp('f172', {'app.py': APP, 'gunicorn.conf.py': CONF})
def start(cmd, **env_): 
    p = subprocess.Popen([str(BIN / 'gunicorn')] + cmd, cwd=d, env=env(d, **env_), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True); return p
def wait_port(port, t=8):
    t0 = time.time()
    while time.time() - t0 < t:
        with socket.socket() as s_:
            if s_.connect_ex(('127.0.0.1', port)) == 0: return True
        time.sleep(0.1)
    return False
import socket, http.client as hc
def get(port, path='/'):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=5); c.request('GET', path); r = c.getresponse(); b = r.read(); c.close(); return r.status, b.decode()
def stop(p):
    try: os.killpg(p.pid, signal.SIGTERM)
    except Exception: pass
    try: p.wait(8)
    except Exception: os.killpg(p.pid, signal.SIGKILL)
def kids(p): return sorted(int(x) for x in subprocess.run(['pgrep', '-P', str(p.pid)], capture_output=True, text=True).stdout.split())
print('== 一:入口写法:模块:变量、模块:工厂函数调用、写错时的报错')
R['entry'] = {}
for label, target in (('app:app(模块级的 app 变量)', 'app:app'), ('"app:create_app()"(调用工厂)', 'app:create_app()'), ("\"app:create_app('prod')\"(带参数的工厂)", "app:create_app('prod')")):
    port = free_port(); p = start(['-b', f'127.0.0.1:{port}', '-w', '1', target]); ok = wait_port(port); out = get(port)[1] if ok else p.stdout.read()[-200:]; stop(p); print(f'  {label:<34} → {out.strip()[:60]}'); R['entry'][label] = out.strip()[:60]
for label, target in (('模块不存在', 'nosuch:app'), ('变量不存在', 'app:nosuch')):
    port = free_port(); p = start(['-b', f'127.0.0.1:{port}', '-w', '1', target]); time.sleep(2.0); out = p.stdout.read() if p.poll() is not None else '(仍在运行)'; stop(p); line = [l.strip()[:100] for l in out.splitlines() if l.strip()][-2:] ; print(f'  {label:<34} → 退出,{line}'); R['entry'][label] = line
print()
print('== 二:配置来源的优先级:命令行 > 环境变量 GUNICORN_CMD_ARGS > 配置文件(gunicorn.conf.py 里写了 workers = 3)')
R['prio'] = {}
for label, cmd, env_ in (('只有配置文件', [], {}), ('GUNICORN_CMD_ARGS 里写 --workers 2', [], {'GUNICORN_CMD_ARGS': '--workers 2'}), ('命令行 -w 1(同时有上面两者)', ['-w', '1'], {'GUNICORN_CMD_ARGS': '--workers 2'})):
    port = free_port(); (d / 'gunicorn.conf.py').write_text(CONF.replace('%PORT%', str(port))); p = start(['-c', 'gunicorn.conf.py'] + cmd + ['app:app'], **env_); wait_port(port); time.sleep(0.8); n = len(kids(p)); stop(p); print(f'  {label:<34} → worker 进程数 {n}'); R['prio'][label] = n
print()
print('== 三:监听 unix socket(给 nginx 用),用 curl --unix-socket 访问')
sock = '/tmp/g172.sock'; (os.path.exists(sock) and os.unlink(sock)); p = start(['-b', f'unix:{sock}', '-w', '1', 'app:app']); time.sleep(1.2)
r = subprocess.run(['curl', '-s', '--unix-socket', sock, 'http://localhost/'], capture_output=True, text=True); print('  curl --unix-socket →', r.stdout.strip()[:60], '| socket 文件权限:', oct(os.stat(sock).st_mode & 0o777)); R['unix'] = [r.stdout.strip()[:60], oct(os.stat(sock).st_mode & 0o777)]; stop(p); os.path.exists(sock) and os.unlink(sock)
print()
print('== 四:运行时用信号管理:TTIN 加一个 worker、TTOU 减一个、HUP 重新加载(新 worker 取代旧的)')
port = free_port(); p = start(['-b', f'127.0.0.1:{port}', '-w', '2', 'app:app']); wait_port(port); time.sleep(0.8); w0 = kids(p); print('  启动:worker', len(w0), '个'); R['sig'] = {'start': len(w0)}
os.kill(p.pid, signal.SIGTTIN); time.sleep(1.2); w1 = kids(p); print('  发 SIGTTIN 后:', len(w1), '个'); R['sig']['ttin'] = len(w1)
os.kill(p.pid, signal.SIGTTOU); time.sleep(1.2); w2 = kids(p); print('  发 SIGTTOU 后:', len(w2), '个'); R['sig']['ttou'] = len(w2)
os.kill(p.pid, signal.SIGHUP); time.sleep(2.0); w3 = kids(p); print(f'  发 SIGHUP 后:{len(w3)} 个,其中与 HUP 之前相同的 pid {len(set(w3) & set(w2))} 个(旧 worker 被换掉了)'); R['sig']['hup'] = [len(w3), len(set(w3) & set(w2))]; stop(p)
print()
print('== 五:--check-config:只检查配置与应用能不能加载,不启动')
r = subprocess.run([str(BIN / 'gunicorn'), '--check-config', 'app:app'], cwd=d, capture_output=True, text=True, env=env(d)); print('  合法:退出码', r.returncode); r2 = subprocess.run([str(BIN / 'gunicorn'), '--check-config', 'app:nosuch'], cwd=d, capture_output=True, text=True, env=env(d)); print('  变量不存在:退出码', r2.returncode, '|', [l for l in (r2.stdout + r2.stderr).splitlines() if 'rror' in l][-1:]); R['check'] = [r.returncode, r2.returncode]
save('f172', R)
