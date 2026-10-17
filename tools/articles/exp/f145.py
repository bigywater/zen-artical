import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f145'); R = {}
import http.client as hc, redis as redis_lib, collections
RP = 9654
rdir = FT / 'f145_redis'; shutil.rmtree(rdir, ignore_errors=True); rdir.mkdir(parents=True)
rproc = subprocess.Popen(['/opt/homebrew/bin/redis-server', '--port', str(RP), '--bind', '127.0.0.1', '--save', '', '--appendonly', 'no', '--dir', str(rdir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try: redis_lib.Redis(port=RP).ping(); break
    except Exception: time.sleep(0.1)
APP = '''
import os, random, time
from flask import Flask, jsonify
import redis
app = Flask(__name__)
COUNT = {"n": 0}
STARTUP_TOKEN = random.randint(1000, 9999)          # 模块导入时算一次
CACHE = {}
r = redis.Redis(port=int(os.environ["RP"]), decode_responses=True)
@app.post("/inc")
def inc(): COUNT["n"] += 1; r.incr("shared"); return jsonify(pid=os.getpid())
@app.get("/count")
def count(): return jsonify(pid=os.getpid(), local=COUNT["n"], shared=int(r.get("shared") or 0), token=STARTUP_TOKEN)
@app.get("/cache/<k>")
def cache(k):
    first = k not in CACHE; CACHE.setdefault(k, os.getpid()); return jsonify(pid=os.getpid(), cached_by=CACHE[k], computed_now=first)
'''
d = mkapp('f145', {'app.py': APP})
def req(port, method, path):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=10); c.request(method, path); r = c.getresponse(); b = json.loads(r.read()); c.close(); return b
try:
    print('== 一:4 个 worker 进程,每个进程有自己的一份模块级全局变量:发 40 次 POST /inc,再读 20 次 /count')
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '4', 'app:app'], RP=RP) as s:
        time.sleep(1.0); redis_lib.Redis(port=RP).flushall()
        pids = collections.Counter(req(s.port, 'POST', '/inc')['pid'] for _ in range(40)); print('  40 次 /inc 落在各进程的次数:', sorted(pids.values()), f'(共 {len(pids)} 个进程)'); R['inc_dist'] = sorted(pids.values())
        reads = [req(s.port, 'GET', '/count') for _ in range(20)]; local = sorted({(x['pid'], x['local']) for x in reads}); print('  20 次读取看到的「全局计数」(进程号, 值):', [(p % 1000, v) for p, v in local]); print('  同一时刻读到的 local 值有', len({v for _, v in local}), '种,期望是 40 的只有 0 种;而 redis 里共享的计数始终是', {x['shared'] for x in reads}); R['local_values'] = sorted({v for _, v in local}); R['shared'] = sorted({x['shared'] for x in reads})
    print()
    print('== 二:模块导入时算一次的值(STARTUP_TOKEN):默认每个 worker 各自导入,--preload 则在 fork 之前导入一次')
    R['token'] = {}
    for label, extra in (('不加 --preload', []), ('--preload', ['--preload'])):
        with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '4'] + extra + ['app:app'], RP=RP) as s:
            time.sleep(1.0); toks = {}
            for _ in range(60): x = req(s.port, 'GET', '/count'); toks[x['pid']] = x['token']
            print(f'  {label:<12} 看到 {len(toks)} 个进程,STARTUP_TOKEN 有 {len(set(toks.values()))} 个不同的值'); R['token'][label] = [len(toks), len(set(toks.values()))]
    print()
    print('== 三:进程内缓存:同一个 key 被不同的进程各算一遍')
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '4', 'app:app'], RP=RP) as s:
        time.sleep(1.0); res = [req(s.port, 'GET', '/cache/k1') for _ in range(40)]; computed = sum(1 for x in res if x['computed_now']); print(f'  同一个 key 请求 40 次,「现算」了 {computed} 次(每个进程第一次各算一次,期望只算 1 次)'); R['cache'] = computed
    print()
    print('== 四:想要所有进程一致,要把状态放到进程外面:上面的 redis 计数始终等于 40')
    print('  (redis 的 INCR 是原子的,4 个进程各自 INCR,读到的是同一个总数)')
finally:
    rproc.terminate(); rproc.wait(5)
save('f145', R)
