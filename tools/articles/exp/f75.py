import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f75'); R = {}
import threading, redis as redis_lib, json
RP = 9650
rdir = FT / 'f75_redis'; shutil.rmtree(rdir, ignore_errors=True); rdir.mkdir(parents=True)
rproc = subprocess.Popen(['/opt/homebrew/bin/redis-server', '--port', str(RP), '--bind', '127.0.0.1', '--save', '', '--appendonly', 'no', '--dir', str(rdir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try: redis_lib.Redis(port=RP).ping(); break
    except Exception: time.sleep(0.1)
rc_ = redis_lib.Redis(port=RP, decode_responses=False)
APP = '''
import os, time
from flask import Flask, request, jsonify
from flask_caching import Cache
app = Flask(__name__)
ctype = os.environ.get("CACHE_TYPE", "SimpleCache")
cfg = {"CACHE_TYPE": ctype, "CACHE_DEFAULT_TIMEOUT": 60}
if ctype == "RedisCache": cfg.update(CACHE_REDIS_HOST="127.0.0.1", CACHE_REDIS_PORT=int(os.environ["REDIS_PORT"]), CACHE_KEY_PREFIX=os.environ.get("PREFIX", "lab_"))
if ctype == "FileSystemCache": cfg.update(CACHE_DIR=os.environ["CACHE_DIR"])
app.config.from_mapping(cfg)
cache = Cache(app)
CALLS = {"n": 0}
def slow(tag):
    CALLS["n"] += 1; time.sleep(float(os.environ.get("SLOW", "0.05"))); return f"{tag}:call#{CALLS['n']}:pid{os.getpid()}"
@app.get("/plain")
def plain(): return slow("plain")
@app.get("/cached")
@cache.cached(timeout=2)
def cached(): return slow("cached")
@app.get("/qs-ignored")
@cache.cached(timeout=30)
def qs_ignored(): return slow("qs:" + request.args.get("a", ""))
@app.get("/qs-keyed")
@cache.cached(timeout=30, query_string=True)
def qs_keyed(): return slow("qs:" + request.args.get("a", ""))
@cache.memoize(timeout=30)
def compute(x, y=1): return slow(f"memo({x},{y})")
@app.get("/memo/<int:x>")
def memo(x): return compute(x, y=int(request.args.get("y", 1)))
@app.post("/memo-clear/<int:x>")
def memo_clear(x): cache.delete_memoized(compute, x, y=int(request.args.get("y", 1))); return "cleared"
@app.get("/calls")
def calls(): return str(CALLS["n"])
@app.get("/clear")
def clear(): cache.clear(); return "all cleared"
'''
d = mkapp('f75', {'app.py': APP})
def Srv(ctype, workers=1, threads=1, **extra): return Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--workers', str(workers), '--threads', str(threads), 'app:app'], CACHE_TYPE=ctype, REDIS_PORT=RP, CACHE_DIR=str(d / 'fscache'), **extra)
try:
    print('== 一:@cache.cached(timeout=2):第一次计算,之后命中;过期后重新计算(SimpleCache,单 worker)')
    with Srv('SimpleCache') as s:
        out = []
        for i in range(3): t0 = time.perf_counter(); b = s.get('/cached')[2].decode(); out.append((b, round((time.perf_counter() - t0) * 1000)))
        print('  连续 3 次:', out); R['hits'] = out
        time.sleep(2.2); t0 = time.perf_counter(); b = s.get('/cached')[2].decode(); print(f'  过期后(2.2 秒后):{b}({(time.perf_counter() - t0) * 1000:.0f} ms)'); R['after_expire'] = b
        print('  不缓存的 /plain 连续 2 次:', [s.get('/plain')[2].decode() for _ in range(2)]); R['plain'] = [s.get('/plain')[2].decode() for _ in range(2)]
    print()
    print('== 二:查询参数默认不参与缓存键:/qs-ignored?a=1 与 ?a=2 返回同一份;query_string=True 才区分')
    with Srv('SimpleCache') as s:
        a = [s.get(f'/qs-ignored?a={i}')[2].decode() for i in (1, 2)]; b = [s.get(f'/qs-keyed?a={i}')[2].decode() for i in (1, 2)]
        print('  默认(query_string=False):', a); print('  query_string=True      :', b); R['qs'] = [a, b]
    print()
    print('== 三:memoize:参数不同分别缓存;delete_memoized 精确清除')
    with Srv('SimpleCache') as s:
        r1 = [s.get('/memo/1')[2].decode(), s.get('/memo/1')[2].decode(), s.get('/memo/2')[2].decode(), s.get('/memo/1?y=5')[2].decode()]; print('  memo(1)、memo(1)、memo(2)、memo(1, y=5):', r1); R['memo'] = r1
        s.req('POST', '/memo-clear/1'); r2 = s.get('/memo/1')[2].decode(); print('  delete_memoized(compute, 1) 后 memo(1):', r2, '| 另一个参数组合 memo(1, y=5) 仍命中:', s.get('/memo/1?y=5')[2].decode()); R['memo_clear'] = [r2, s.get('/memo/1?y=5')[2].decode()]
    print()
    print('== 四:后端不同,存储位置不同:RedisCache 在 redis 里(键、TTL、值的格式);FileSystemCache 在目录里')
    rc_.flushall()
    with Srv('RedisCache', PREFIX='lab_') as s:
        s.get('/cached'); s.get('/memo/3')
        ks = sorted(k.decode() for k in rc_.keys('*')); print('  redis 里的键:', ks); R['redis_keys'] = ks
        k0 = [k for k in rc_.keys('*') if b'cached' in k or b'view' in k][0]; print('  视图缓存键', k0.decode(), '| TTL =', rc_.ttl(k0), '秒 | 值的前几个字节:', rc_.get(k0)[:20]); R['ttl'] = rc_.ttl(k0); R['value_head'] = repr(rc_.get(k0)[:20])
    shutil.rmtree(d / 'fscache', ignore_errors=True)
    with Srv('FileSystemCache') as s:
        s.get('/cached'); fs = sorted(os.listdir(d / 'fscache')); print('  FileSystemCache 目录里的文件:', [f[:12] + '…' for f in fs]); R['fs_files'] = len(fs)
    print()
    print('== 五:多个 worker 进程:SimpleCache 是进程内的,每个 worker 各算一次;RedisCache 是共享的')
    for ctype in ('SimpleCache', 'RedisCache'):
        rc_.flushall()
        with Srv(ctype, workers=3, PREFIX=f'w_{ctype}_') as s:
            time.sleep(0.5); res = [s.get('/qs-keyed?a=same')[2].decode() for _ in range(12)]; pids = sorted({r.split(':pid')[1] for r in res}); computed = sorted({r.split(':')[2] for r in res}); R.setdefault('workers', {})[ctype] = [len(set(res)), len(pids)]
            print(f'  {ctype:<12} 3 个 worker、12 个相同请求:不同的响应内容 {len(set(res))} 种(= 被计算了几次);响应来自 {len(pids)} 个不同进程')
    print()
    print('== 六:缓存击穿:缓存刚过期时,8 个并发请求同时到达——没有锁时每个都重新计算(0.3 秒的慢计算)')
    rc_.flushall()
    with Srv('RedisCache', threads=8, PREFIX='st_', SLOW='0.3') as s:
        s.get('/cached'); time.sleep(2.3); before = int(s.get('/calls')[2]); res = []
        ths = [threading.Thread(target=lambda: res.append(s.get('/cached')[2].decode())) for _ in range(8)]; t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; dt = time.perf_counter() - t0; after = int(s.get('/calls')[2])
        print(f'  缓存过期后 8 个并发请求:慢计算被执行了 {after - before} 次(总耗时 {dt:.2f} 秒);8 个响应里不同的 call 编号 {len({r.split(":")[1] for r in res})} 个'); R['stampede'] = [after - before, round(dt, 2)]
    print()
    print('== 七:命中与未命中的耗时(慢计算 50 ms)')
    with Srv('SimpleCache') as s:
        miss = []; hit = []
        s.get('/clear')
        for i in range(5): s.get('/clear'); t0 = time.perf_counter(); s.get('/qs-keyed?a=1'); miss.append((time.perf_counter() - t0) * 1000)
        s.get('/qs-keyed?a=1')
        for i in range(20): t0 = time.perf_counter(); s.get('/qs-keyed?a=1'); hit.append((time.perf_counter() - t0) * 1000)
        print(f'  未命中(计算 50 ms)中位数 {median(miss):.1f} ms;命中中位数 {median(hit):.2f} ms'); R['lat'] = [median(miss), median(hit)]
finally:
    rproc.terminate(); rproc.wait(5)
save('f75', R)
