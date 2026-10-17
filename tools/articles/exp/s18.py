import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s18'); reset_s()
class Lat:
    """服务器:第 n 个(按到达顺序,不含 /seed)请求的延迟由 fn(n) 决定,状态码由 st(n) 决定;记录并发峰值。"""
    def __init__(self, fn, st=lambda n: 200):
        self.fn = fn; self.st = st; self.n = 0; self.lock = threading.Lock(); self.cur = 0; self.peak = 0
    def __call__(self, h):
        if h.path == '/seed': h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'}); return
        with self.lock: self.n += 1; n = self.n; self.cur += 1; self.peak = max(self.peak, self.cur)
        time.sleep(self.fn(n))
        h.reply(self.st(n), '<html>x</html>', {'Content-Type': 'text/html'})
        with self.lock: self.cur -= 1
LINE = re.compile(r'slot: (\S+) \| conc:\s*(\d+) \| delay:\s*(\d+) ms \(([+-]\d+)\) \| latency:\s*(\d+) ms')
def crawl(lat, n, settings, meta='', tag='s18'):
    d = sdir(tag)
    with Srv(lat) as s:
        code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('{s.url("/seed")}')
    def parse(self, response):
        if response.url.endswith('seed'):
            for i in range({n}): yield scrapy.Request('{s.url("/p")}%d' % i, callback=self.sub{meta})
    def sub(self, response): pass
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO', 'AUTOTHROTTLE_ENABLED': 1, 'AUTOTHROTTLE_DEBUG': 1, 'CONCURRENT_REQUESTS': 100, 'CONCURRENT_REQUESTS_PER_DOMAIN': 100, 'SCHEDULER_MEMORY_QUEUE': 'scrapy.squeues.FifoMemoryQueue'}, **settings))
    rows = [tuple(int(x) if x.lstrip('+-').isdigit() else x for x in m) for m in LINE.findall(out)]
    return rows, stats(out), lat, out
def traj(rows): return [r[2] for r in rows]  # 每个响应处理之后槽的 delay(ms)

print('== 一:起步与收敛:延迟恒为 0.2 s 的服务器,40 个请求;AUTOTHROTTLE_START_DELAY=1.0;每个响应之后槽的 delay(ms,第一个值是 /seed 那个响应)。目标并发 TARGET_CONCURRENCY = 1 与 2')
for tc in (1, 2):
    rows, st, lat, out = crawl(Lat(lambda n: 0.2), 40, {'AUTOTHROTTLE_START_DELAY': 1.0, 'AUTOTHROTTLE_TARGET_CONCURRENCY': tc})
    print(f'  TARGET_CONCURRENCY={tc}:delay 轨迹(ms)= {traj(rows)[:14]} … {traj(rows)[-3:]};最终 {traj(rows)[-1]} ms(目标 latency/{tc} = {200 // tc} ms);服务器并发峰值 {lat.peak};总耗时 {st["elapsed_time_seconds"]:.1f} s')

print('== 二:服务器变慢又变快:前 15 个请求 0.1 s,中间 15 个 0.8 s,后 15 个 0.1 s;TARGET_CONCURRENCY=1,START_DELAY=0.1')
rows, st, lat, out = crawl(Lat(lambda n: 0.8 if 16 <= n <= 30 else 0.1), 45, {'AUTOTHROTTLE_START_DELAY': 0.1, 'AUTOTHROTTLE_TARGET_CONCURRENCY': 1})
tj = traj(rows)
print('  delay 轨迹(ms):')
for i in range(0, len(tj), 15): print('    ' + ' '.join(f'{x:>4}' for x in tj[i:i + 15]))
print(f'  变慢时(第 16~30 个)最高 {max(tj[15:30])} ms;变快后(第 31 个起)delay 每次约折半往下降:{tj[30:36]};服务器并发峰值 {lat.peak}')

print('== 三:非 200 响应不会让 delay 下降:前 10 个请求 0.5 s(200),后 20 个很快(0.02 s)但状态码 404 vs 200')
for tag, stf in (('后 20 个返回 200', lambda n: 200), ('后 20 个返回 404', lambda n: 200 if n <= 10 else 404)):
    rows, st, lat, out = crawl(Lat(lambda n: 0.5 if n <= 10 else 0.02, stf), 30, {'AUTOTHROTTLE_START_DELAY': 0.1, 'AUTOTHROTTLE_TARGET_CONCURRENCY': 1})
    tj = traj(rows)
    print(f'  {tag}:前 10 个之后 delay = {tj[9]} ms;最后 delay = {tj[-1]} ms;后 20 个的轨迹 {tj[10:16]} …')

print('== 四:上下限:DOWNLOAD_DELAY 当最小值、AUTOTHROTTLE_MAX_DELAY 当最大值——服务器延迟 2 s,目标并发 1(理想 delay 2000 ms)')
for tag, stt in (('MAX_DELAY=60(默认)', {}), ('MAX_DELAY=0.5', {'AUTOTHROTTLE_MAX_DELAY': 0.5})):
    rows, st, lat, out = crawl(Lat(lambda n: 2.0), 3, dict({'AUTOTHROTTLE_START_DELAY': 0.1}, **stt))
    print(f'  {tag}:delay 轨迹(ms)= {traj(rows)}')
rows, st, lat, out = crawl(Lat(lambda n: 0.05), 20, {'AUTOTHROTTLE_START_DELAY': 0.1, 'DOWNLOAD_DELAY': 0.3, 'DOWNLOAD_DELAY_JITTER': 0})
print(f'  服务器延迟 0.05 s、DOWNLOAD_DELAY=0.3(最小值):delay 轨迹(ms)= {traj(rows)[:6]} … {traj(rows)[-2:]}(理想值 50 ms 被抬到 300)')

print('== 五:AutoThrottle 只调延迟,不直接限制并发:服务器延迟 0.4 s,不同目标并发下,服务器端实际的同时处理峰值')
print(f'  {"TARGET_CONCURRENCY":>18}{"最终 delay ms":>14}{"服务器并发峰值":>14}{"总耗时 s":>10}')
for tc in (1, 2, 4):
    rows, st, lat, out = crawl(Lat(lambda n: 0.4), 40, {'AUTOTHROTTLE_START_DELAY': 0.4 / tc, 'AUTOTHROTTLE_TARGET_CONCURRENCY': tc})
    print(f'  {tc:>18}{traj(rows)[-1]:>14}{lat.peak:>14}{st["elapsed_time_seconds"]:>10.1f}')

print('== 六:meta["autothrottle_dont_adjust_delay"]=True 的请求不参与调整:前 10 个正常(0.1 s),后 10 个服务器 1.0 s 但请求带这个 meta')
rows, st, lat, out = crawl(Lat(lambda n: 0.1 if n <= 10 else 1.0), 20, {'AUTOTHROTTLE_START_DELAY': 0.1, 'AUTOTHROTTLE_TARGET_CONCURRENCY': 1}, meta=", meta={'autothrottle_dont_adjust_delay': True} if i >= 10 else {}")
print(f'  服务器收到 {lat.n} 个请求(后 10 个各耗时 1.0 s),总耗时 {st["elapsed_time_seconds"]:.1f} s;debug 行只有 {len(rows)} 条(seed + 前 10 个,带 meta 的不输出);delay 轨迹(ms)= {traj(rows)}')
