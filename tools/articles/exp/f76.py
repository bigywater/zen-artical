import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f76'); R = {}
import redis as redis_lib, json
RP = 9651
rdir = FT / 'f76_redis'; shutil.rmtree(rdir, ignore_errors=True); rdir.mkdir(parents=True)
rproc = subprocess.Popen(['/opt/homebrew/bin/redis-server', '--port', str(RP), '--bind', '127.0.0.1', '--save', '', '--appendonly', 'no', '--dir', str(rdir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try: redis_lib.Redis(port=RP).ping(); break
    except Exception: time.sleep(0.1)
rc_ = redis_lib.Redis(port=RP)
APP = '''
import os
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
app = Flask(__name__)
storage = os.environ.get("STORAGE", "memory://")
strategy = os.environ.get("STRATEGY", "fixed-window")
def key_func():
    return request.headers.get("X-Client", get_remote_address())
limiter = Limiter(key_func, app=app, storage_uri=storage, strategy=strategy, default_limits=[os.environ.get("DEFAULT", "1000 per minute")], headers_enabled=True, storage_options={})
@app.get("/ping")
def ping(): return "pong"
@app.get("/five")
@limiter.limit("5 per minute")
def five(): return "ok"
@app.get("/multi")
@limiter.limit("3 per 10 seconds; 100 per hour")
def multi(): return "ok"
@app.get("/exempt")
@limiter.exempt
def exempt(): return "exempt"
shared = limiter.shared_limit("4 per minute", scope="shared-scope")
@app.get("/s1")
@shared
def s1(): return "s1"
@app.get("/s2")
@shared
def s2(): return "s2"
@app.get("/cost")
@limiter.limit("10 per minute", cost=5)
def cost(): return "ok"
@app.errorhandler(429)
def too_many(e): return jsonify(error="rate limited", detail=str(e.description)), 429
'''
d = mkapp('f76', {'app.py': APP})
def Srv(workers=1, **extra): return Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--workers', str(workers), 'app:app'], **extra)
def burst(s, path, n, client='c1'):
    out = []
    for i in range(n): st, h, b, dt = s.get(path, headers={'X-Client': client}); out.append((st, {k.lower(): v for k, v in h}))
    return out
try:
    print('== 一:固定窗口 "5 per minute":前 5 个 200,第 6 个起 429;看响应头')
    with Srv() as s:
        res = burst(s, '/five', 7); print('  7 次请求的状态码:', [r[0] for r in res]); R['codes'] = [r[0] for r in res]
        hh = {k: v for k, v in res[0][1].items() if k.startswith(('x-ratelimit', 'retry-after'))}; print('  第 1 次响应的限流头:', hh); R['h200'] = hh
        h429 = {k: v for k, v in res[-1][1].items() if k.startswith(('x-ratelimit', 'retry-after'))}; print('  第 7 次(429)响应的头:', h429); R['h429'] = h429
        st, h, b, dt = s.get('/five', headers={'X-Client': 'c1'}); print('  429 的正文(自定义 errorhandler):', b.decode()); R['body429'] = b.decode()
        print('  别的客户端(X-Client: c2)不受影响:', [r[0] for r in burst(s, '/five', 3, 'c2')]); R['other'] = [r[0] for r in burst(s, '/five', 1, 'c3')]
    print()
    print('== 二:一个路由多个限制;共享限制(多个路由共用一个桶);cost;exempt')
    with Srv() as s:
        print('  "3 per 10 seconds; 100 per hour" 连发 5 次:', [r[0] for r in burst(s, '/multi', 5)]); R['multi'] = [r[0] for r in burst(s, '/multi', 1, 'c9')]
        print('  共享桶 "4 per minute":交替请求 /s1 与 /s2 共 6 次:', [burst(s, p, 1)[0][0] for p in ('/s1', '/s2', '/s1', '/s2', '/s1', '/s2')]); R['shared'] = [burst(s, p, 1, 'cc')[0][0] for p in ('/s1', '/s2', '/s1', '/s2', '/s1', '/s2')]
        print('  cost=5 的 "10 per minute":连发 3 次:', [r[0] for r in burst(s, '/cost', 3)]); R['cost'] = [r[0] for r in burst(s, '/cost', 3, 'cd')]
        print('  @limiter.exempt 的路由连发 30 次是否都 200:', all(r[0] == 200 for r in burst(s, '/exempt', 30))); R['exempt'] = all(r[0] == 200 for r in burst(s, '/exempt', 30))
        r = burst(s, '/ping', 2)[1][1]; print('  只有默认限制的 /ping,头里:', {k: v for k, v in r.items() if k.startswith('x-ratelimit')}); R['default_hdr'] = {k: v for k, v in r.items() if k.startswith('x-ratelimit')}
    print()
    print('== 三:策略:fixed-window 在窗口边界可以「突发 2 倍」;moving-window 更平滑(用 "3 per 2 seconds" 演示)')
    R['strat'] = {}
    for strat in ('fixed-window', 'moving-window'):
        d2 = mkapp(f'f76s', {'app.py': APP.replace('"5 per minute"', '"3 per 2 seconds"')})
        with Server(d2, ['gunicorn', '-b', '127.0.0.1:{port}', '--workers', '1', 'app:app'], STRATEGY=strat) as s:
            c = f'x{strat}'; seq = []; t0 = time.time()
            seq.append(burst(s, '/five', 1, c)[0][0])
            time.sleep(1.5 - (time.time() - t0))
            for _ in range(3): seq.append(burst(s, '/five', 1, c)[0][0])
            time.sleep(2.2 - (time.time() - t0))
            for _ in range(3): seq.append(burst(s, '/five', 1, c)[0][0])
        R['strat'][strat] = seq; print(f'  {strat:<14} t=0 发 1 次,t=1.5 s 连发 3 次,t=2.2 s 再连发 3 次:{seq}(限制 "3 per 2 seconds")')
    print()
    print('== 四:存储:memory:// 是进程内的——多个 worker 各记各的,实际限额 = 限额 × worker 数;redis 存储共享')
    for label, st_ in (('memory://(3 个 worker)', 'memory://'), (f'redis://127.0.0.1:{RP}(3 个 worker)', f'redis://127.0.0.1:{RP}')):
        rc_.flushall()
        with Srv(workers=3, STORAGE=st_) as s:
            time.sleep(0.5); codes = [burst(s, '/five', 1, 'w')[0][0] for _ in range(30)]
        ok = codes.count(200); R.setdefault('workers', {})[label] = ok; print(f'  {label:<34} 同一个客户端连发 30 次,限制 "5 per minute":放行 {ok} 次')
    rc_.flushall()
    with Srv(workers=1, STORAGE=f'redis://127.0.0.1:{RP}') as s:
        burst(s, '/five', 2, 'rk'); ks = [k.decode() for k in rc_.keys('*')]; print('  redis 里的键:', ks[:4]); R['redis_keys'] = ks[:4]
        k = [k for k in rc_.keys('*') if b'five' in k][0]; print('  某个限流键的值 =', rc_.get(k), '| TTL =', rc_.ttl(k)); R['rkey'] = [rc_.get(k).decode(), rc_.ttl(k)]
    print()
    print('== 五:key_func 决定「按谁限流」:按 IP、按用户、按 API key;代理后面直接用 get_remote_address 会把所有人当成同一个(代理的 IP)')
    with Srv() as s:
        r = [s.get('/five', headers={'X-Forwarded-For': f'203.0.113.{i}'})[0] for i in range(7)]; print('  不同 X-Forwarded-For 的 7 个请求(本篇的 key_func 回退到 get_remote_address)状态码:', r); R['xff'] = r
    print('  (没有配置 ProxyFix 时 remote_addr 是直连方,所以上面全算同一个客户端——见第 135 篇)')
    print()
    print('== 六:限流的开销:memory 存储下命中限制检查的每请求耗时(test client,3000 次)')
    import timeit
    from flask import Flask
    from flask_limiter import Limiter
    a = Flask('t'); lim = Limiter(lambda: 'k', app=a, storage_uri='memory://', default_limits=['1000000 per minute']); a.add_url_rule('/p', 'p', lambda: 'ok'); b = Flask('t2'); b.add_url_rule('/p', 'p', lambda: 'ok')
    ca, cb = a.test_client(), b.test_client(); ca.get('/p'); cb.get('/p')
    ta = min(timeit.timeit(lambda: ca.get('/p'), number=3000) / 3000 * 1e6 for _ in range(3)); tb = min(timeit.timeit(lambda: cb.get('/p'), number=3000) / 3000 * 1e6 for _ in range(3)); print(f'  无限流 {tb:.0f} µs/请求;有限流(memory)  {ta:.0f} µs/请求;多出 {ta - tb:.0f} µs'); R['cost_us'] = [tb, ta]
finally:
    rproc.terminate(); rproc.wait(5)
save('f76', R)
