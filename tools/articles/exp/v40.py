import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import heapq
tee('v40'); reset()
print('一个最小的注册中心(我写的 Python 类,约 40 行):register(服务名, 实例 id, 地址, ttl)登记并开始一个租约;heartbeat(实例 id)续约(把到期时间推到“现在 + ttl”);deregister 主动注销;lookup(服务名)返回当前没过期的实例。过期有两种实现:(1) 惰性——查询时才检查到期时间;(2) 后台线程每隔 reap_interval 扫描一遍并删除过期的。下面的数字大多是真实时间下测出来的')
class Registry:
    def __init__(s, reap_interval=None, clock=time.perf_counter, use_heap=False):
        s.clock, s.items, s.lk, s.use_heap, s.heap = clock, {}, threading.Lock(), use_heap, []
        s.reap_interval = reap_interval
        if reap_interval:
            s.stop = False; threading.Thread(target=s._reaper, daemon=True).start()
    def register(s, svc, iid, addr, ttl):
        with s.lk:
            s.items[(svc, iid)] = {'addr': addr, 'ttl': ttl, 'exp': s.clock() + ttl}
            if s.use_heap: heapq.heappush(s.heap, (s.items[(svc, iid)]['exp'], (svc, iid)))
    def heartbeat(s, svc, iid):
        with s.lk:
            it = s.items.get((svc, iid))
            if not it: return False                      # 已经过期被删了:客户端必须重新 register
            it['exp'] = s.clock() + it['ttl']
            if s.use_heap: heapq.heappush(s.heap, (it['exp'], (svc, iid)))
            return True
    def deregister(s, svc, iid):
        with s.lk: s.items.pop((svc, iid), None)
    def lookup(s, svc):
        now = s.clock()
        with s.lk: return sorted(i for (sv, i), it in s.items.items() if sv == svc and (s.reap_interval is not None or it['exp'] > now))
    def _reaper(s):
        while not s.stop:
            time.sleep(s.reap_interval); s.reap()
    def reap(s):
        now = s.clock()
        with s.lk:
            if s.use_heap:
                n = 0
                while s.heap and s.heap[0][0] <= now:
                    exp, k = heapq.heappop(s.heap); it = s.items.get(k)
                    if it and it['exp'] <= now: del s.items[k]; n += 1
                return n
            dead = [k for k, it in s.items.items() if it['exp'] <= now]
            for k in dead: del s.items[k]
            return len(dead)

# ============ 一 ============
print('== 一:一个实例崩溃后,多久从注册中心消失。实例 i1 注册(ttl = 2 s)并每 0.5 s 续约一次;崩溃 = 突然不再续约(不注销)。另一个实例 i2 在崩溃前主动 deregister 作对照。每种过期实现重复 20 次:惰性检查 / 后台线程每 1 s 扫一次 / 后台线程每 0.2 s 扫一次。“消失用了多久”= 从最后一次续约到 lookup 不再返回它')
rows = []
for name, ri in (('惰性(查询时检查)', None), ('后台每 1 s 扫描', 1.0), ('后台每 0.2 s 扫描', 0.2)):
    ds = []
    for trial in range(20):
        R = Registry(ri)
        if ri: time.sleep(random.uniform(0, ri))          # 让后台扫描线程的相位和实例的注册时刻无关
        R.register('svc', 'i1', 'a:1', 2.0); last = time.perf_counter()
        for _ in range(3): time.sleep(0.5 + random.uniform(0, 0.05)); R.heartbeat('svc', 'i1'); last = time.perf_counter()
        t0 = last
        while 'i1' in R.lookup('svc'): time.sleep(0.01)
        ds.append(time.perf_counter() - t0)
        if R.reap_interval: R.stop = True
        if trial == 0:
            R2 = Registry(); R2.register('svc', 'i2', 'a:2', 2.0); t1 = time.perf_counter(); R2.deregister('svc', 'i2'); dereg = time.perf_counter() - t1
    rows.append((name, f'{min(ds):.2f} s', f'{statistics.median(ds):.2f} s', f'{max(ds):.2f} s'))
table(rows, ['过期实现', '最短', '中位数', '最长(崩溃后消失用了多久,20 次)'])
print(f'  对照:主动 deregister 在调用返回时就已经消失({dereg * 1e6:.0f} µs)。崩溃的实例要靠租约到期:消失时间 = ttl(2 s)再加上一个 0 到扫描间隔之间的延迟(最短和最长之差就是这个延迟的范围);惰性检查没有扫描延迟,但 lookup 之外别的地方(例如统计实例数、通知订阅者)仍然看到旧状态')

# ============ 二 ============
print('== 二:心跳间隔和 ttl 的关系——误摘除。1000 个实例都活着,每 1 s 续约一次,但每次续约消息有 10% 的概率丢失(独立丢失)。用虚拟时钟模拟 5 分钟,惰性过期。ttl 分别是 1.5 / 2 / 3 / 5 s(即允许连续丢 0 / 1 / 2 / 4 次心跳)。统计 5 分钟内“活着的实例被错误摘除”的次数,以及理论值:一次摘除需要连续丢够 ⌈ttl / 间隔⌉ 个心跳')
def sim_flaps(ttl, loss, n=1000, dur=300, interval=1.0, seed=3):
    rng = random.Random(seed); clk = [0.0]; R = Registry(None, clock=lambda: clk[0]); flaps = 0
    for i in range(n): R.register('svc', f'i{i}', 'a', ttl)
    present = {f'i{i}': True for i in range(n)}
    t = 0.0
    while t < dur:
        t += interval; clk[0] = t
        for i in range(n):
            iid = f'i{i}'
            if rng.random() >= loss:
                if not R.heartbeat('svc', iid): R.register('svc', iid, 'a', ttl)          # 过期后的第一次心跳失败,实例重新注册
            if (('svc', iid) in R.items and R.items[('svc', iid)]['exp'] > t) != present[iid]:
                present[iid] = not present[iid]
                if not present[iid]: flaps += 1
    return flaps
import math
rows = []
for ttl in (1.5, 2.0, 3.0, 5.0):
    k = math.ceil(ttl / 1.0); flaps = sim_flaps(ttl, 0.10); theory = 1000 * 300 * (0.1 ** k) * (0.9)
    rows.append((f'{ttl} s', k, flaps, f'{theory:.1f}'))
table(rows, ['ttl', '需要连续丢几个心跳才会过期', '5 分钟内误摘除次数(1000 个实例)', '理论期望(1000 × 300 × 丢包率^k × 0.9)'])
print('  理论期望是近似值(每个时刻“刚好连续丢了 k 个心跳”的概率)。ttl 是心跳间隔的 1.5 倍和 2 倍时,都只能容忍一次丢包(连续丢两次就过期),每个实例 5 分钟里平均被误摘几次;每多容忍一次连续丢包,误摘除大约降到十分之一(丢包率 10%)')

# ============ 三 ============
print('== 三:过期扫描的代价。注册 N 个实例(ttl 10 s),其中恰好有 100 个已经到期,扫描一次需要多久。两种实现:(a) 扫描全部实例;(b) 最小堆按到期时间排序,只弹出到期的。N = 1 万 / 10 万 / 100 万')
rows = []
for n in (10_000, 100_000, 1_000_000):
    out = []
    for use_heap in (False, True):
        clk = [0.0]; R = Registry(None, clock=lambda: clk[0], use_heap=use_heap)
        for i in range(n): R.register('svc', f'i{i}', 'a', 10.0 if i >= 100 else 1.0)
        clk[0] = 5.0; t0 = time.perf_counter(); dead = R.reap(); out.append((time.perf_counter() - t0, dead))
    rows.append((f'{n:,}', f'{out[0][0] * 1000:.2f} ms', f'{out[1][0] * 1000:.3f} ms', out[0][1], out[1][1]))
table(rows, ['实例数 N', '扫描全部', '最小堆', '删掉的(扫描)', '删掉的(堆)'])
print('  扫描的代价随 N 线性增长,实例多了就不能每秒全扫一遍;最小堆只处理到期的那几个,代价取决于到期的数量。续约会往堆里推新的条目,旧条目留在堆里直到弹出时被发现已经过期失效(惰性删除),所以堆会比实例数大一些')
