import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f170'); R = {}
import http.client as hc, threading
APP = '''
import os, sqlite3, threading, time, random
from flask import Flask, jsonify, request
app = Flask(__name__)
COUNT = {"n": 0}; SAFE = {"n": 0}; LOCK = threading.Lock()
SHARED = {str(i): i for i in range(300000)}
CONN = sqlite3.connect(":memory:", check_same_thread=False); CONN.execute("create table t (id integer, v integer)"); CONN.executemany("insert into t values (?, ?)", [(i, i) for i in range(100)])
@app.post("/inc")
def inc():
    w = float(request.args.get("w", "0")); v = COUNT["n"]
    if w: time.sleep(w)                       # 读和写之间的窗口(比如中间调了一次数据库或外部接口)
    COUNT["n"] = v + 1; return "ok"
@app.post("/inc-safe")
def inc_safe():
    with LOCK: v = SAFE["n"]; time.sleep(0); SAFE["n"] = v + 1
    return "ok"
@app.get("/sum")
def total():
    s = 0
    for k, v in SHARED.items(): s += v          # 遍历全局字典
    return jsonify(s=s)
@app.post("/mutate")
def mutate():
    k = str(random.randrange(10000)); SHARED[k] = 1; SHARED.pop(k, None); return "ok"
@app.get("/shared-conn")
def shared_conn():
    cur = CONN.execute("select id, v from t where id = ?", (random.randrange(100),)); time.sleep(0); return jsonify(row=cur.fetchone())
@app.get("/own-conn")
def own_conn():
    c = sqlite3.connect(":memory:"); c.execute("select 1"); c.close(); return "ok"
@app.get("/count")
def count(): return jsonify(unsafe=COUNT["n"], safe=SAFE["n"])
'''
d = mkapp('f170', {'app.py': APP})
def ab(port, path, n, c, post=False):
    cmd = ['ab', '-n', str(n), '-c', str(c)] + (['-p', '/dev/null'] if post else []) + [f'http://127.0.0.1:{port}{path}']
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout
    non2 = re.search(r'Non-2xx responses:\s+(\d+)', out); fail = re.search(r'Failed requests:\s+(\d+)', out); rps = re.search(r'Requests per second:\s+([\d.]+)', out)
    return int(non2.group(1)) if non2 else 0, int(fail.group(1)) if fail else 0, float(rps.group(1))
def counts(port): c = hc.HTTPConnection('127.0.0.1', port); c.request('GET', '/count'); return json.loads(c.getresponse().read())
print('== 一:读-改-写的计数器:读和写之间的窗口大小,决定压测能不能「碰到」竞争(ab 2000 个 POST,32 并发,gunicorn gthread 1 个 worker × 32 线程)')
R['lost'] = {}
for label, w in (('窗口 0(中间没有任何让出)', 0), ('窗口 0.0001 秒', 0.0001), ('窗口 0.001 秒', 0.001)):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '32', 'app:app']) as s:
        time.sleep(1.0); ab(s.port, f'/inc?w={w}', 2000, 32, True); c = counts(s.port)
    lost = 2000 - c['unsafe']; print(f'  {label:<24} 计数 {c["unsafe"]} / 2000(丢了 {lost} 次,{lost / 2000 * 100:.1f}%)'); R['lost'][label] = [c['unsafe'], lost]
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '32', 'app:app']) as s:
    time.sleep(1.0); ab(s.port, '/inc-safe', 2000, 32, True); c = counts(s.port)
print(f'  加锁(窗口 0.001 秒的写法)  计数 {c["safe"]} / 2000'); R['safe'] = c['safe']
print()
print('== 二:遍历全局字典时另一个请求在修改它:有多少请求因此返回 500')
R['dict'] = {}
for conc in (1, 32):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '32', 'app:app']) as s:
        time.sleep(1.0)
        th = threading.Thread(target=lambda: ab(s.port, '/mutate', 4000, 8, True)); th.start(); non2, fail, rps = ab(s.port, '/sum', 3000, conc); th.join(); log = s.logtext(); n_err = log.count('dictionary changed size during iteration')
    print(f'  /sum 并发 {conc:>2}(同时有 /mutate 在改字典):3000 个请求里非 2xx {non2} 个;日志里「dictionary changed size during iteration」{n_err} 次'); R['dict'][conc] = [non2, n_err]
print()
print('== 三:被所有线程共用的数据库连接(sqlite3 的 check_same_thread=False 只是关掉了检查):并发查询')
R['conn'] = {}
for label, path in (('共用一个连接', '/shared-conn'), ('每个请求自己的连接', '/own-conn')):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '32', 'app:app']) as s:
        time.sleep(1.0); non2, fail, rps = ab(s.port, path, 3000, 32); log = s.logtext(); kinds = sorted({l.strip().split(':')[0] for l in log.splitlines() if l.strip().startswith(('sqlite3.', 'TypeError', 'ProgrammingError'))})
    print(f'  {label:<14} 3000 个请求(32 并发):非 2xx {non2} 个 | 日志里的异常类型 {kinds[:3]}'); R['conn'][label] = [non2, kinds[:3]]
save('f170', R)
