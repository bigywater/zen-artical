import sys, os, math, time, threading, collections, statistics, urllib.parse as up; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests
tee('p68')
class Fixed:
    name = '固定窗口'
    def __init__(s, limit=10, window=1.0): s.limit, s.window, s.wid, s.n = limit, window, None, 0
    def allow(s, now):
        w = math.floor(now / s.window)
        if w != s.wid: s.wid, s.n = w, 0
        if s.n < s.limit: s.n += 1; return True, 0
        return False, (w + 1) * s.window - now
class SlidingLog:
    name = '滑动窗口日志'
    def __init__(s, limit=10, window=1.0): s.limit, s.window, s.q = limit, window, collections.deque()
    def allow(s, now):
        while s.q and s.q[0] <= now - s.window: s.q.popleft()
        if len(s.q) < s.limit: s.q.append(now); return True, 0
        return False, s.q[0] + s.window - now
class SlidingCounter:
    name = '滑动窗口计数'
    def __init__(s, limit=10, window=1.0): s.limit, s.window, s.wid, s.cur, s.prev = limit, window, None, 0, 0
    def allow(s, now):
        w = math.floor(now / s.window)
        if s.wid is None: s.wid = w
        if w != s.wid: s.prev = s.cur if w == s.wid + 1 else 0; s.cur = 0; s.wid = w
        est = s.prev * (1 - (now - w * s.window) / s.window) + s.cur
        if est + 1 <= s.limit: s.cur += 1; return True, 0
        return False, max(0.01, (s.window - (now - w * s.window)) * (1 if s.prev == 0 else 0.5))
class TokenBucket:
    name = '令牌桶'
    def __init__(s, rate=10, burst=10): s.rate, s.burst, s.tok, s.t = rate, burst, burst, None
    def allow(s, now):
        if s.t is None: s.t = now
        s.tok = min(s.burst, s.tok + (now - s.t) * s.rate); s.t = now
        if s.tok >= 1: s.tok -= 1; return True, 0
        return False, (1 - s.tok) / s.rate
LIM = [Fixed, SlidingLog, SlidingCounter, TokenBucket]
class Site:
    def __init__(s, cls, **kw): s.cls = cls; s.kw = kw; s.lock = threading.Lock(); s.reset()
    def reset(s): s.lim = s.cls(**s.kw); s.ok = 0; s.rej = 0; s.times = []
    def __call__(s, h):
        with s.lock:
            now = time.time(); ok, ra = s.lim.allow(now)
            if ok: s.ok += 1
            else: s.rej += 1
            s.times.append((now, ok))
        if ok: return h.reply(200, b'ok')
        h.reply(429, b'slow down', headers={'Retry-After': str(max(1, math.ceil(ra))), 'X-Retry-After-Ms': str(int(ra * 1000) + 1)})
def client(base):
    s = requests.Session(); return s
def get(s, base, path='/x'):
    t = time.time(); r = s.get(base + path); return t, r.status_code, r.headers.get('Retry-After'), r.headers.get('X-Retry-After-Ms')
def sleep_until(t):
    d = t - time.time()
    if d > 0: time.sleep(d)

print('== 一:客户端 30 个请求/秒匀速发 3 秒(共 90 个),服务器限制 10 个/秒(令牌桶:速率 10/秒、桶容量 10;窗口类的窗口 1 秒)。看每一秒里被接受的个数')
for cls in LIM:
    site = Site(cls)
    with Srv(site) as sv:
        s = requests.Session(); t0 = time.time(); out = []
        for i in range(90):
            sleep_until(t0 + i / 30); out.append(get(s, sv.url('/x')))
        per = [sum(1 for t, st, _, _ in out if st == 200 and int(t - t0) == k) for k in range(3)]
        first = [round(t - t0, 2) for t, st, _, _ in out if st == 200][:12]
        print(f'  {cls.name}:被接受 {site.ok}/90,按客户端的每一秒 {per};前 12 个被接受的请求的时刻 {first}')
print('== 二:窗口边界的突发:对齐到墙上时钟整秒,在一秒的 0.90–0.95 处连发 10 个,下一秒的 0.05–0.10 处再连发 10 个,统计这 0.2 秒内被接受的个数(每种重复 5 次,限制 10 个/秒)')
for cls in LIM:
    res = []
    for rep in range(5):
        site = Site(cls)
        with Srv(site) as sv:
            s = requests.Session(); base = math.floor(time.time()) + 2
            sleep_until(base + 0.90); a = [get(s, sv.url('/x')) for _ in range(10)]
            sleep_until(base + 1.05); b = [get(s, sv.url('/x')) for _ in range(10)]
            res.append((sum(1 for x in a if x[1] == 200), sum(1 for x in b if x[1] == 200), round(b[-1][0] - a[0][0], 3)))
    print(f'  {cls.name}:每次(前 10 个被接受, 后 10 个被接受, 总跨度秒){res};两批合计被接受 {[a + b for a, b, _ in res]}')
print('== 三:收到 429 就按 Retry-After 等待再重试同一个请求,连续取 25 个页面;对比用标准的整秒 Retry-After 和精确的毫秒值(自定义头 X-Retry-After-Ms)')
for cls in LIM:
    row = []
    for mode in ('整秒 Retry-After', '精确毫秒'):
        site = Site(cls)
        with Srv(site) as sv:
            s = requests.Session(); t0 = time.time(); n429 = 0; sent = 0
            for i in range(25):
                while True:
                    t, st, ra, ms = get(s, sv.url('/x')); sent += 1
                    if st == 200: break
                    n429 += 1; time.sleep(int(ra) if mode.startswith('整') else int(ms) / 1000)
            el = time.time() - t0; row.append(f'{mode}:用时 {el:.2f} 秒,发出 {sent} 个请求,其中 429 有 {n429} 个,实际速率 {25 / el:.1f} 个/秒')
    print(f'  {cls.name}:' + ';'.join(row))
print('== 四:对令牌桶(速率 10/秒、桶容量 5)取 60 个页面,每个页面必须成功一次:三种客户端')
def strat(name, sv, site):
    s = requests.Session(); t0 = time.time(); sent = 0; n429 = 0
    for i in range(60):
        if name == '匀速 100 ms 一个': sleep_until(t0 + i * 0.1)
        while True:
            t, st, ra, ms = get(s, sv.url('/x')); sent += 1
            if st == 200: break
            n429 += 1
            if name == '429 后立刻重试': continue
            elif name == '429 后等 Retry-After(毫秒)': time.sleep(int(ms) / 1000)
            else: time.sleep(0.1)
    return time.time() - t0, sent, n429
for name in ('429 后立刻重试', '429 后等 Retry-After(毫秒)', '匀速 100 ms 一个'):
    site = Site(TokenBucket, rate=10, burst=5)
    with Srv(site) as sv: el, sent, n429 = strat(name, sv, site)
    print(f'  {name}:用时 {el:.2f} 秒,发出 {sent} 个请求(429 有 {n429} 个),服务器收到 {site.ok + site.rej} 个')
print('== 五:4 个线程共用一个限流 key(令牌桶 速率 10/秒、桶容量 10),各自不停地发请求,持续 3 秒(收到 429 立刻重试)')
site = Site(TokenBucket, rate=10, burst=10)
with Srv(site) as sv:
    cnt = [[0, 0] for _ in range(4)]; stop = time.time() + 3.0
    def worker(k):
        s = requests.Session()
        while time.time() < stop:
            t, st, ra, ms = get(s, sv.url('/x')); cnt[k][0 if st == 200 else 1] += 1
    ths = [threading.Thread(target=worker, args=(k,)) for k in range(4)]
    for t in ths: t.start()
    for t in ths: t.join()
print(f'  每个线程(被接受, 被拒绝):{[tuple(c) for c in cnt]};被接受合计 {sum(c[0] for c in cnt)}(3 秒内理论上最多 10 + 3×10 = 40),被拒绝合计 {sum(c[1] for c in cnt)}')
print('== 六:不知道服务器限多少时,客户端用 AIMD 调速(从 2 个/秒起,每 1 秒没遇到 429 就加 1 个/秒,遇到 429 就把速率减半),服务器限制 10 个/秒,跑 12 秒')
for cls in LIM:
    site = Site(cls)
    with Srv(site) as sv:
        s = requests.Session(); rate = 2.0; t0 = time.time(); nxt = t0; last_adj = t0; got429 = False; traj = []; sec_ok = collections.Counter()
        while time.time() - t0 < 12:
            sleep_until(nxt); t, st, ra, ms = get(s, sv.url('/x'))
            if st == 200: sec_ok[int(t - t0)] += 1
            else: got429 = True; rate = max(1.0, rate / 2)
            nxt += 1 / rate
            if time.time() - last_adj >= 1.0:
                if not got429: rate += 1
                traj.append(round(rate, 1)); got429 = False; last_adj = time.time()
        tot = site.ok + site.rej; last6 = sum(sec_ok[k] for k in range(6, 12)) / 6
        print(f'  {cls.name}:每秒调整后的速率 {traj};总共发出 {tot} 个,429 有 {site.rej} 个({site.rej * 100 / tot:.0f}%);后 6 秒平均每秒被接受 {last6:.1f} 个')
purge()
