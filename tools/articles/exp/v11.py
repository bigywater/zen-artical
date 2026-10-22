import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import rl, redis
from redis.retry import Retry
from redis.backoff import NoBackoff
tee('v11'); reset()
print('分布式限流:多个实例共用一个 Redis 里的令牌桶。Redis 8.10.2(本机自己起的实例,端口 ' + str(txl._port[0] + 1) + ' 附近),客户端 redis-py 8.1.0(每个线程一个连接)。桶的状态是一个 hash:tok(剩余令牌)和 ts(上次更新的毫秒时间)')
N = rl.Node(free_port(), 'v11'); N.start()
def rc(**kw): return redis.Redis(port=N.port, decode_responses=True, retry=Retry(NoBackoff(), 0), **kw)     # 关掉 redis-py 默认的重试与退避,否则超时会被它拖成好几秒
LUA = """
local rate=tonumber(ARGV[1]); local burst=tonumber(ARGV[2]); local now=tonumber(ARGV[3])
if now < 0 then local t=redis.call('TIME'); now=t[1]*1000+math.floor(t[2]/1000) end
local d=redis.call('HMGET',KEYS[1],'tok','ts'); local tok=tonumber(d[1]); local ts=tonumber(d[2])
if tok==nil then tok=burst; ts=now end
tok=math.min(burst, tok+math.max(0, now-ts)*rate/1000)
local ok=0
if tok>=1 then tok=tok-1; ok=1 end
redis.call('HSET',KEYS[1],'tok',tok,'ts',TSEXPR); redis.call('PEXPIRE',KEYS[1],60000)
return ok
"""
r0 = rc(); lua = r0.register_script(LUA.replace('TSEXPR', 'now')); lua_max = r0.register_script(LUA.replace('TSEXPR', 'math.max(ts, now)'))

# ============ 一 ============
print('== 一:原子性。桶里只有 1000 个令牌、不补充(速率 0);8 个线程各尝试 400 次取走一个令牌,共 3200 次尝试;理论上只能成功 1000 次。三种实现:(a) 客户端先 HMGET 读出来、算好、再 HSET 写回(读-改-写,不原子);(b) WATCH + MULTI/EXEC 乐观锁,冲突重试;(c) 一个 Lua 脚本(Redis 单线程执行,整体原子)。每种跑 3 轮')
def run1(kind):
    r0.delete('b1'); r0.hset('b1', mapping={'tok': 1000, 'ts': 0}); ok = [0] * 8; extra = [0] * 8
    def w(i):
        r = rc()
        for _ in range(400):
            if kind == 'rmw':
                tok = float(r.hget('b1', 'tok'))
                if tok >= 1: r.hset('b1', 'tok', tok - 1); ok[i] += 1
            elif kind == 'watch':
                while True:
                    with r.pipeline() as p:
                        try:
                            p.watch('b1'); tok = float(p.hget('b1', 'tok'))
                            if tok < 1: p.unwatch(); break
                            p.multi(); p.hset('b1', 'tok', tok - 1); p.execute(); ok[i] += 1; break
                        except redis.WatchError: extra[i] += 1
            else:
                ok[i] += lua(keys=['b1'], args=[0, 1000, 0], client=r)
    t0 = time.perf_counter(); ths = [threading.Thread(target=w, args=(i,)) for i in range(8)]; [t.start() for t in ths]; [t.join() for t in ths]; dt = time.perf_counter() - t0
    return sum(ok), sum(extra), dt, float(r0.hget('b1', 'tok'))
rows = []
for kind, name in (('rmw', '(a) 读-改-写(不原子)'), ('watch', '(b) WATCH + MULTI/EXEC'), ('lua', '(c) Lua 脚本')):
    R = [run1(kind) for _ in range(3)]
    rows.append((name, ' / '.join(str(r[0]) for r in R), ' / '.join(f'{r[3]:.0f}' for r in R), ' / '.join(str(r[1]) for r in R), f'{statistics.median([3200 / r[2] for r in R]):.0f}'))
table(rows, ['实现', '3 轮各放行多少(应为 1000)', '3 轮结束时桶里剩余令牌(应为 0)', '3 轮 WATCH 冲突重试次数', '尝试次数/秒(中位数)'])

# ============ 二 ============
print('== 二:速度。令牌桶 Lua 脚本,速率 100000/s、burst 100000(基本不拒绝),16 个线程各自连一个连接,各调用 5000 次;热点 = 所有线程同一个 key;分散 = 每个线程一个 key。再对照同一个令牌桶放在进程内(Python,一把锁)的速度')
def run2(spread):
    lat = [[] for _ in range(16)]
    def w(i):
        r = rc(); key = f'k{i}' if spread else 'hot'
        for _ in range(5000):
            t = time.perf_counter(); lua(keys=[key], args=[100000, 100000, -1], client=r); lat[i].append(time.perf_counter() - t)
    r0.flushdb(); t0 = time.perf_counter(); ths = [threading.Thread(target=w, args=(i,)) for i in range(16)]; [t.start() for t in ths]; [t.join() for t in ths]; dt = time.perf_counter() - t0
    allx = [x for l in lat for x in l]; return 80000 / dt, pct(allx, 50), pct(allx, 99)
rows = []
for spread, name in ((False, '热点:16 个线程共用 1 个 key'), (True, '分散:每个线程一个 key')):
    ops, p50, p99 = run2(spread); rows.append((name, f'{ops:.0f}/秒', f'{p50 * 1000:.2f} ms', f'{p99 * 1000:.2f} ms'))
class TB:
    def __init__(s, rate, burst): s.rate, s.burst, s.tok, s.last, s.lk = rate, burst, burst, time.perf_counter(), threading.Lock()
    def allow(s):
        with s.lk:
            t = time.perf_counter(); s.tok = min(s.burst, s.tok + (t - s.last) * s.rate); s.last = t
            if s.tok >= 1: s.tok -= 1; return True
            return False
tb = TB(100000, 100000); t0 = time.perf_counter()
def w2():
    for _ in range(5000): tb.allow()
ths = [threading.Thread(target=w2) for _ in range(16)]; [t.start() for t in ths]; [t.join() for t in ths]; dt = time.perf_counter() - t0
rows.append(('对照:进程内的令牌桶(一把锁)', f'{80000 / dt:.0f}/秒', '-', '-'))
table(rows, ['场景', '吞吐', '延迟中位数', 'p99'])

# ============ 三 ============
print('== 三:时间从哪里来。限额 100 个/秒、burst 10,3 个客户端各以 100 个/秒(共 300/s)发 5 秒,它们的本地时钟分别偏差 0、+300 ms、−300 ms(模拟没有对时的机器)。Lua 脚本里的“现在”:(a) 用 Redis 服务器的 TIME;(b) 用客户端传进来的时间戳,记下的 ts 就是传入的时间;(c) 同样用客户端时间戳,但记下的 ts 只增不减(取 max)。放行数应约为 100 × 5 + 10 = 510')
def run3(use_server_time, script=None):
    r0.flushdb(); allowed = [0] * 3; offs = [0, 300, -300]; T0 = time.time()
    def w(i):
        r = rc(); n = 0
        for k in range(500):
            tgt = T0 + k / 100.0
            d = tgt - time.time()
            if d > 0: time.sleep(d)
            now = -1 if use_server_time else int(time.time() * 1000) + offs[i]
            allowed[i] += (script or lua)(keys=['b3'], args=[100, 10, now], client=r)
    ths = [threading.Thread(target=w, args=(i,)) for i in range(3)]; [t.start() for t in ths]; [t.join() for t in ths]; return allowed
rows = []
for use, name, sc in ((True, '(a) Redis 的 TIME', None), (False, '(b) 客户端时间戳(偏差 0 / +300 / −300 ms),ts 直接记成传入的时间', None), (False, '(c) 客户端时间戳(同样的偏差),ts 只增不减(math.max)', lua_max)):
    a = run3(use, sc); rows.append((name, sum(a), a))
table(rows, ['“现在”的来源', '5 秒内放行总数', '三个客户端各放行'])

# ============ 四 ============
print('== 四:Redis 不可用时怎么办。限额 100 个/秒;8 个线程共发约 200 个/秒的请求,共 8 秒,第 2 秒到第 5 秒 Redis 被 SIGSTOP 暂停(连接不断但不回话,模拟 Redis 卡住);客户端的 socket 超时 50 ms。三种策略:fail-open(Redis 出错就放行)、fail-closed(出错就拒绝)、退回本地(出错就用本进程里的令牌桶,限额 100/8 个/秒/线程)。每秒放行数与每次判断的平均耗时')
def run4(policy):
    r0.flushdb(); stop = threading.Event(); errs = collections.Counter(); per = collections.Counter(); durs = collections.defaultdict(list); lk = threading.Lock(); T0 = time.time()
    def w(i):
        r = rc(socket_timeout=0.05, socket_connect_timeout=0.05); loc = TB(100 / 8, 100 / 8)
        for k in range(200):
            tgt = T0 + k * 0.04
            d = tgt - time.time()
            if d > 0: time.sleep(d)
            t1 = time.perf_counter()
            try: ok = bool(lua(keys=['b4'], args=[100, 10, -1], client=r))
            except (redis.TimeoutError, redis.ConnectionError) as e:
                with lk: errs[(int(time.time() - T0) >= 3, type(e).__name__ + ':' + str(e)[:40])] += 1
                ok = True if policy == 'open' else False if policy == 'closed' else loc.allow()
            sec = int(time.time() - T0)
            with lk: per[sec] += ok; durs[sec].append(time.perf_counter() - t1)
    ths = [threading.Thread(target=w, args=(i,)) for i in range(8)]; [t.start() for t in ths]
    time.sleep(2.0); os.kill(N.p.pid, signal.SIGSTOP); time.sleep(3.0); os.kill(N.p.pid, signal.SIGCONT); [t.join() for t in ths]
    return [per[s] for s in range(8)], [statistics.mean(durs[s]) * 1000 if durs[s] else 0 for s in range(8)], errs
rows = []; allerrs = None
for pol, name in (('open', 'fail-open'), ('closed', 'fail-closed'), ('local', '退回本地令牌桶')):
    a, d, errs = run4(pol); rows.append((name, '放行/秒') + tuple(a)); rows.append(('', '平均耗时 ms') + tuple(f'{x:.0f}' for x in d)); allerrs = errs if pol == 'open' else allerrs
table(rows, ['策略', '', '第 0 秒', '1', '2', '3', '4', '5', '6', '7'])
print('  fail-open 这一轮里客户端遇到的错误(第 2 秒起;键 = (是否已过第 3 秒, 错误类型与信息前 40 个字符)):', dict(allerrs))
print('  Redis 暂停的第 2 到第 5 秒:fail-open 把请求几乎全放行(接近 200 个/秒,限额形同虚设),fail-closed 几乎全部拒绝,退回本地令牌桶则按各线程的本地额度放行(8 个线程的额度加起来约 100;切换那一秒因为本地桶是满的,会多放行一些);只有切换那一秒每次判断平均慢几十毫秒(等 socket 超时),之后很快就报连接错误')
N.stop()
