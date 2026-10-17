import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f111'); R = {}
import threading, redis as redis_lib, math
from flask import Flask, request, jsonify, g
from werkzeug.middleware.proxy_fix import ProxyFix
RP = 9653
rdir = FT / 'f111_redis'; shutil.rmtree(rdir, ignore_errors=True); rdir.mkdir(parents=True)
rproc = subprocess.Popen(['/opt/homebrew/bin/redis-server', '--port', str(RP), '--bind', '127.0.0.1', '--save', '', '--appendonly', 'no', '--dir', str(rdir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try: redis_lib.Redis(port=RP).ping(); break
    except Exception: time.sleep(0.1)
rc_ = redis_lib.Redis(port=RP, decode_responses=True)
LUA = """
local key = KEYS[1]; local cap = tonumber(ARGV[1]); local rate = tonumber(ARGV[2]); local now = tonumber(ARGV[3])
local d = redis.call('HMGET', key, 'tokens', 'ts'); local tokens = tonumber(d[1]); local ts = tonumber(d[2])
if tokens == nil then tokens = cap; ts = now end
tokens = math.min(cap, tokens + (now - ts) * rate)
local ok = 0; local retry = 0
if tokens >= 1 then tokens = tokens - 1; ok = 1 else retry = (1 - tokens) / rate end
redis.call('HSET', key, 'tokens', tokens, 'ts', now); redis.call('EXPIRE', key, math.ceil(cap / rate) + 1)
return {ok, tostring(tokens), tostring(retry)}
"""
bucket = rc_.register_script(LUA)
def take(key, cap, rate): ok, tokens, retry = bucket(keys=[key], args=[cap, rate, time.time()]); return bool(ok), float(tokens), float(retry)
def naive(key, cap):
    n = int(rc_.get(key) or 0)
    if n >= cap: return False
    time.sleep(0.002); rc_.set(key, n + 1, ex=60); return True
try:
    print('== 一:令牌桶(容量 5,每秒补 2 个):突发 5 个通过,第 6 个被拒;之后按补充速度放行')
    rc_.flushall(); seq = []; t0 = time.time()
    for i in range(7): ok, tk, retry = take('b1', 5, 2); seq.append((i + 1, ok, round(retry, 2)))
    print('  连发 7 次(序号,是否放行,需要等待秒数):', seq); R['burst'] = seq
    time.sleep(1.1); ok, tk, retry = take('b1', 5, 2); ok2, _, _ = take('b1', 5, 2); ok3, _, retry3 = take('b1', 5, 2); print(f'  等 1.1 秒(补了约 2.2 个令牌)后连发 3 次:{ok}, {ok2}, {ok3}(第 3 次需要再等 {retry3:.2f} 秒)'); R['refill'] = [ok, ok2, ok3]
    print()
    print('== 二:Redis 里「先读后写」与 Lua 脚本:20 个线程同时抢 10 个名额')
    for label, fn in (('先 GET 再 SET(非原子)', lambda: naive('race1', 10)), ('Lua 令牌桶(原子,容量 10,不补充)', lambda: take('race2', 10, 0.000001)[0])):
        rc_.flushall(); res = []; bar = threading.Barrier(20)
        def w():
            bar.wait(); res.append(fn())
        ths = [threading.Thread(target=w) for _ in range(20)]; [t.start() for t in ths]; [t.join() for t in ths]; print(f'  {label:<32} 放行 {sum(res)} 个(上限 10)'); R.setdefault('race', {})[label] = sum(res)
    print()
    print('== 三:429 响应带上 Retry-After 与 RateLimit 头')
    app = Flask('rl'); app.logger.disabled = True
    @app.get('/api')
    def api():
        key = f'u:{request.headers.get("X-User", request.remote_addr)}'; ok, tokens, retry = take(key, 3, 1)
        h = {'RateLimit-Limit': '3', 'RateLimit-Remaining': str(int(tokens))}
        if not ok: h['Retry-After'] = str(math.ceil(retry)); return jsonify(error='too many requests'), 429, h
        return jsonify(ok=True), 200, h
    rc_.flushall(); c = app.test_client(); R['hdr'] = []
    for i in range(5): r = c.get('/api', headers={'X-User': 'ann'}); hh = {k: v for k, v in r.headers if k.lower().startswith(('ratelimit', 'retry'))}; print(f'  第 {i + 1} 次 → {r.status_code} {hh}'); R['hdr'].append([r.status_code, hh])
    print()
    print('== 四:限流的 key 从哪来:信任 X-Forwarded-For 而前面没有代理时,攻击者可以随便伪造来绕过')
    for label, wrap in (('不信任代理头(用 remote_addr)', False), ('ProxyFix(x_for=1) 信任 X-Forwarded-For', True)):
        a2 = Flask('rl2'); a2.logger.disabled = True
        if wrap: a2.wsgi_app = ProxyFix(a2.wsgi_app, x_for=1)
        @a2.get('/api')
        def api2(): ok, tokens, retry = take(f'ip:{request.remote_addr}', 3, 0.0001); return ('ok', 200) if ok else ('limited', 429)
        rc_.flushall(); c2 = a2.test_client(); codes = [c2.get('/api', headers={'X-Forwarded-For': f'203.0.113.{i}'}).status_code for i in range(8)]
        print(f'  {label:<38} 8 个请求(每个伪造不同的 X-Forwarded-For)→ {codes}'); R.setdefault('spoof', {})[label] = codes
    print()
    print('== 五:按用户限流还是按 IP 限流:同一个 IP 后面有多个用户(比如公司出口)')
    a3 = Flask('rl3'); a3.logger.disabled = True
    @a3.get('/api')
    def api3():
        k = f'user:{request.headers["X-User"]}' if request.headers.get('X-User') else f'ip:{request.remote_addr}'; ok, tokens, retry = take(k, 3, 0.0001); return ('ok', 200) if ok else ('limited', 429)
    for label, hdrs in (('按 IP(未登录,3 个用户共用 1 个 IP)', [{}, {}, {}]), ('按用户', [{'X-User': 'a'}, {'X-User': 'b'}, {'X-User': 'c'}])):
        rc_.flushall(); c3 = a3.test_client(); codes = [c3.get('/api', headers=hdrs[i % 3]).status_code for i in range(9)]; print(f'  {label:<34} 9 个请求(三人轮流)→ {codes.count(200)} 个放行,{codes.count(429)} 个 429'); R.setdefault('keyby', {})[label] = [codes.count(200), codes.count(429)]
finally:
    rproc.terminate(); rproc.wait(5)
save('f111', R)
