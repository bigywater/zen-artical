import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f174'); R = {}
import textwrap, collections, threading, http.client as hc
APP = '''
import os, time
from flask import Flask, request, jsonify
app = Flask(__name__)
NAME = os.environ["NAME"]
@app.get("/who")
def who(): return jsonify(name=NAME)
@app.route("/work", methods=["GET", "POST"])
def work():
    s = float(request.args.get("s", "0"))
    if os.environ.get("HANG") == "1": s = 5
    time.sleep(s); return jsonify(name=NAME, method=request.method)
'''
d = mkapp('f174', {'app.py': APP})
W = FT / 'f174nginx'; shutil.rmtree(W, ignore_errors=True); (W / 'logs').mkdir(parents=True); (W / 'tmp').mkdir()
def conf(ports, listen, weights=None, extra_loc='', upstream_extra='', server_extra=''):
    servers = '\n'.join(f'      server 127.0.0.1:{p}{" weight=" + str(weights[i]) if weights else ""}{server_extra};' for i, p in enumerate(ports))
    return textwrap.dedent(f'''
    worker_processes 1; daemon off; pid {W}/nginx.pid; error_log {W}/logs/error.log;
    events {{ worker_connections 64; }}
    http {{
      access_log {W}/logs/access.log; client_body_temp_path {W}/tmp/b; proxy_temp_path {W}/tmp/p; fastcgi_temp_path {W}/tmp/f; uwsgi_temp_path {W}/tmp/u; scgi_temp_path {W}/tmp/s;
      upstream app {{
{servers}
{upstream_extra}
      }}
      server {{ listen 127.0.0.1:{listen}; location / {{ proxy_pass http://app; proxy_set_header Host $http_host; {extra_loc} }} }}
    }}''')
class Nginx:
    def __init__(self, text): (W / 'nginx.conf').write_text(text); self.p = subprocess.Popen(['/opt/homebrew/bin/nginx', '-p', str(W), '-c', str(W / 'nginx.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True); time.sleep(0.8)
    def __enter__(self): return self
    def __exit__(self, *a):
        try: os.killpg(self.p.pid, signal.SIGTERM)
        except Exception: pass
        try: self.p.wait(5)
        except Exception: pass
def call(port, method, path, timeout=15):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=timeout); t0 = time.perf_counter()
    try: c.request(method, path); r = c.getresponse(); b = r.read(); return r.status, ms(t0), b
    except Exception as e: return type(e).__name__, ms(t0), b''
    finally: c.close()
def backends(names, **extra):
    L = []
    for n in names: L.append(Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '8', 'app:app'], NAME=n, **extra))
    return L
print('== 一:round-robin 负载均衡:两个 gunicorn 后端,40 个请求')
bs = backends(['A', 'B']); time.sleep(1.0); lp = free_port()
with Nginx(conf([b.port for b in bs], lp)):
    cnt = collections.Counter(json.loads(call(lp, 'GET', '/who')[2])['name'] for _ in range(40)); print('  分布:', dict(cnt)); R['rr'] = dict(cnt)
with Nginx(conf([b.port for b in bs], lp, weights=[3, 1])):
    cnt = collections.Counter(json.loads(call(lp, 'GET', '/who')[2])['name'] for _ in range(40)); print('  weight=3 比 1:', dict(cnt)); R['weight'] = dict(cnt)
print()
print('== 二:一个后端挂了(进程停掉):默认配置下 nginx 把失败的请求换到另一个后端重试')
lp = free_port()
with Nginx(conf([b.port for b in bs], lp)):
    bs[1].stop(); time.sleep(0.5); res = [call(lp, 'GET', '/who') for _ in range(40)]; ok = sum(1 for r in res if r[0] == 200); names = collections.Counter(json.loads(r[2])['name'] for r in res if r[0] == 200)
    print(f'  B 停掉后 40 个请求:成功 {ok},失败 {40 - ok};落在 {dict(names)}'); R['failover'] = [ok, dict(names)]
    err = (W / 'logs' / 'error.log').read_text(); print('  nginx 的 error.log 里记录了连接被拒:', 'Connection refused' in err, '(出现次数', err.count('Connection refused'), ')'); R['refused'] = err.count('Connection refused')
lp = free_port()
with Nginx(conf([b.port for b in bs], lp, extra_loc='proxy_next_upstream off;')):
    res = [call(lp, 'GET', '/who') for _ in range(40)]; ok = sum(1 for r in res if r[0] == 200); print(f'  proxy_next_upstream off 时 40 个请求:成功 {ok},失败 {40 - ok}(落到挂掉后端的请求直接 502)'); R['no_retry'] = [ok, collections.Counter(r[0] for r in res)]
for b in bs: b.stop()
print()
print('== 三:一个后端卡住(请求要 5 秒):proxy_read_timeout 1 秒,max_fails=0(不把它标记为不可用,每个请求都会被分到它);GET 与 POST 各 6 个')
a = backends(['A'])[0]; h = backends(['HANG'], HANG='1')[0]; time.sleep(1.0); lp = free_port()
with Nginx(conf([h.port, a.port], lp, extra_loc='proxy_read_timeout 1s;', server_extra=' max_fails=0')):
    R['hang'] = {}
    for method in ('GET', 'POST'):
        res = [call(lp, method, '/work?s=0') for _ in range(6)]; sts = collections.Counter(r[0] for r in res); mx = max(r[1] for r in res); names = collections.Counter(json.loads(r[2])['name'] for r in res if r[0] == 200)
        print(f'  {method:<5} 6 个请求:状态 {dict(sts)},最慢 {mx:.0f} ms,成功的落在 {dict(names)}'); R['hang'][method] = [dict(sts), mx, dict(names)]
a.stop(); h.stop()
save('f174', R)
