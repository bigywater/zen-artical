import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s16'); reset_s()
def crawl(hosts, per_host, settings, delay=0.0, tag='s16', warn=False):
    d = sdir(tag); tr = Track(delay)
    with Srv(tr) as s:
        urls = [f'http://{h}:{s.port}/p{i}' for h in hosts for i in range(per_host)]
        code = f"""
import scrapy
URLS = {urls!r}
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('http://{hosts[0]}:{s.port}/seed')
    def parse(self, response):
        if response.url.endswith('seed'):
            for u in URLS: yield scrapy.Request(u, callback=self.sub)
    def sub(self, response): pass
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 100, 'CONCURRENT_REQUESTS_PER_DOMAIN': 100}, **settings))
    ts = sorted(tr.t)[1:]  # 去掉 /seed
    gaps = [(b - a) * 1000 for a, b in zip(ts, ts[1:])]
    return tr, stats(out), gaps, out
def pct(xs, p): xs = sorted(xs); return xs[min(len(xs) - 1, int(len(xs) * p / 100))]
def summ(gaps): return f'间隔 ms:最小 {min(gaps):.0f}、P10 {pct(gaps, 10):.0f}、中位数 {pct(gaps, 50):.0f}、P90 {pct(gaps, 90):.0f}、最大 {max(gaps):.0f}、平均 {sum(gaps) / len(gaps):.0f}'

print('== 一:DOWNLOAD_DELAY=0.2 时,相邻两个请求“到达服务器”的间隔分布(单域名 100 个请求,服务器不延迟);2.19 的抖动由 DOWNLOAD_DELAY_JITTER 控制(默认 0.5 = ±50%)')
for jit in (None, 0, 0.5, 1.0):
    st = {'DOWNLOAD_DELAY': 0.2}
    if jit is not None: st['DOWNLOAD_DELAY_JITTER'] = jit
    tr, s_, gaps, out = crawl(['127.0.0.1'], 100, st)
    print(f'  DOWNLOAD_DELAY_JITTER={"(默认)" if jit is None else jit:<6}{summ(gaps)};总耗时 {s_["elapsed_time_seconds"]:.1f} s')

print('== 二:旧设置 RANDOMIZE_DOWNLOAD_DELAY:2.19 里已弃用——设成 False 还能关掉抖动吗,有什么警告')
for v in ('False', 'True'):
    tr, s_, gaps, out = crawl(['127.0.0.1'], 60, {'DOWNLOAD_DELAY': 0.2, 'RANDOMIZE_DOWNLOAD_DELAY': v})
    w = [l.split('ScrapyDeprecationWarning: ')[-1].strip() for l in out.split('\n') if 'RANDOMIZE_DOWNLOAD_DELAY setting is deprecated' in l]
    print(f'  RANDOMIZE_DOWNLOAD_DELAY={v:<6}{summ(gaps)}')
    print('      警告:' + (w[0][:150] if w else '(无)'))

print('== 三:延迟是“两次请求发出之间”的间隔,不是“上一个响应回来之后”:服务器每个请求耗时 0.6 s,DOWNLOAD_DELAY=0.1,无抖动(24 个请求)')
tr, s_, gaps, out = crawl(['127.0.0.1'], 24, {'DOWNLOAD_DELAY': 0.1, 'DOWNLOAD_DELAY_JITTER': 0}, delay=0.6)
print(f'  {summ(gaps)};服务器同时处理的峰值 {tr.peak["127.0.0.1"]}(≈ 0.6 ÷ 0.1 = 6);总耗时 {s_["elapsed_time_seconds"]:.1f} s(24×0.1 + 0.6 ≈ 3.0)')

print('== 四:每个域名各有自己的延迟计时:两个主机名(127.0.0.1 与 localhost)各 20 个请求,DOWNLOAD_DELAY=0.2 无抖动,总耗时与一个域名 20 个差不多')
t1 = crawl(['127.0.0.1'], 20, {'DOWNLOAD_DELAY': 0.2, 'DOWNLOAD_DELAY_JITTER': 0})
t2 = crawl(['127.0.0.1', 'localhost'], 20, {'DOWNLOAD_DELAY': 0.2, 'DOWNLOAD_DELAY_JITTER': 0})
print(f'  一个域名 20 个请求:总耗时 {t1[1]["elapsed_time_seconds"]:.1f} s;两个域名各 20 个(共 40 个):总耗时 {t2[1]["elapsed_time_seconds"]:.1f} s;理想值 20×0.2 = 4.0 s')
hosts = [h[0] for h in t2[0].paths][1:]
print(f'  两个域名的请求到达顺序(1=127.0.0.1,l=localhost):{"".join("1" if h == "127.0.0.1" else "l" for h in hosts)}')

print('== 五:DOWNLOAD_SLOTS 给单个域名设自己的 delay:127.0.0.1 用 0.05,localhost 用 0.3(各 20 个请求,无抖动)')
tr, s_, gaps, out = crawl(['127.0.0.1', 'localhost'], 20, {'DOWNLOAD_DELAY': 0.2, 'DOWNLOAD_DELAY_JITTER': 0, 'DOWNLOAD_SLOTS': '{"127.0.0.1": {"delay": 0.05}, "localhost": {"delay": 0.3}}'})
hs = [(h, t) for (h, p), t in zip(tr.paths, tr.t)][1:]
for host in ('127.0.0.1', 'localhost'):
    ts = [t for h, t in hs if h == host]
    g = [(b - a) * 1000 for a, b in zip(ts, ts[1:])]
    print(f'  {host:<10}{summ(g)}')
print(f'  总耗时 {s_["elapsed_time_seconds"]:.1f} s(localhost 慢的那个决定:20×0.3 = 6.0)')

print('== 六:旧写法 spider 属性 download_delay 与设置:优先级(spider 30 > project 20)')
d = sdir('s16f'); tr = Track(0.0)
with Srv(tr) as s:
    code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    download_delay = 0.3
    async def start(self):
        for i in range(8): yield scrapy.Request('http://127.0.0.1:{s.port}/p%d' % i)
    def parse(self, response): pass
"""
    rc, out, t = runspider(d, code, {'LOG_LEVEL': 'INFO', 'DOWNLOAD_DELAY_JITTER': 0})
ts = sorted(tr.t); g = [(b - a) * 1000 for a, b in zip(ts, ts[1:])]
print(f'  只有 spider.download_delay = 0.3:{summ(g)}')
print('  警告:' + ' | '.join(l.split('ScrapyDeprecationWarning: ')[-1].strip()[:120] for l in out.split('\n') if "'download_delay'" in l))
