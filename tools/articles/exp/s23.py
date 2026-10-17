import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s23'); reset_s()
class Site:
    def __init__(self, robots=None, rstatus=200, rdelay=0.0): self.log = []; self.robots = robots; self.rstatus = rstatus; self.rdelay = rdelay
    def __call__(self, h):
        self.log.append((h.path, time.perf_counter()))
        if h.path == '/robots.txt':
            time.sleep(self.rdelay)
            if self.rstatus == 'garbage': h.reply(200, bytes(range(256)) * 4, {'Content-Type': 'application/octet-stream'}); return
            if self.rstatus != 200: h.reply(self.rstatus, 'x', {'Content-Type': 'text/plain'}); return
            h.reply(200, self.robots or '', {'Content-Type': 'text/plain'}); return
        h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
def go(sv, paths, settings=None, tag='s23', code_extra=''):
    d = sdir(tag)
    with Srv(sv) as s:
        code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        for p in {paths!r}: yield scrapy.Request('{s.url("")}' + p, callback=self.cb, errback=self.eb, dont_filter=True)
    def cb(self, response): EV(p=response.url.split('{s.port}')[-1], ok=True)
    def eb(self, failure): EV(p=failure.request.url.split('{s.port}')[-1], ok=False, err=type(failure.value).__name__ + ': ' + str(failure.value)[:40])
{code_extra}
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO', 'ROBOTSTXT_OBEY': 1, 'CONCURRENT_REQUESTS': 1}, **(settings or {})))
    return sv, ev(d), out, stats(out)
def rs(st): return {k.split('robotstxt/')[1]: v for k, v in sorted(st.items()) if k.startswith('robotstxt/')}

print('== 一:ROBOTSTXT_OBEY 的默认值,以及 scrapy startproject 生成的 settings.py 里怎么写')
r = subprocess.run([SPY, '-c', 'from scrapy.settings import default_settings as d; print(d.ROBOTSTXT_OBEY, d.ROBOTSTXT_PARSER, d.ROBOTSTXT_USER_AGENT)'], capture_output=True, text=True)
print('  默认值(ROBOTSTXT_OBEY、ROBOTSTXT_PARSER、ROBOTSTXT_USER_AGENT):' + r.stdout.strip())
d = sdir('s23a'); scrapy(d, 'startproject', 'proj', '.')
print('  项目模板 settings.py 里的相关行:' + ' | '.join(l.strip() for l in (d / 'proj' / 'settings.py').read_text().splitlines() if 'ROBOTSTXT' in l or l.startswith('USER_AGENT') or l.startswith('#USER_AGENT')))

print('== 二:被 robots.txt 禁止的请求:IgnoreRequest("Forbidden by robots.txt"),errback 能收到;服务器只收到一次 robots.txt(按 netloc 缓存),且它排在其它请求之前')
ROB = 'User-agent: *\nDisallow: /private\nAllow: /\n'
sv, E, out, st = go(Site(ROB), ['/a', '/private/x', '/b', '/private', '/privatefoo'])
for x in sorted(E, key=lambda x: x['p']): print(f'  {x["p"]:<14}{"通过" if x["ok"] else "被拒:" + x["err"]}')
print(f'  服务器收到的顺序:{[p for p, _ in sv.log]};robotstxt stats {rs(st)}')

print('== 三:匹配哪个 User-agent:默认 USER_AGENT 是 “Scrapy/2.19.0 (+https://scrapy.org)”;robots.txt 里写了 User-agent: Scrapy(Disallow /scrapy-only)和 User-agent: mybot(Disallow /mybot-only)和 *(Disallow /all)')
ROB3 = 'User-agent: Scrapy\nDisallow: /scrapy-only\n\nUser-agent: mybot\nDisallow: /mybot-only\n\nUser-agent: *\nDisallow: /all\n'
for tag, stt in (('默认 USER_AGENT', {}), ('ROBOTSTXT_USER_AGENT=mybot', {'ROBOTSTXT_USER_AGENT': 'mybot'}), ('USER_AGENT=mybot/1.0 (+http://x)', {'USER_AGENT': 'mybot/1.0 (+http://x)'})):
    sv, E, out, st = go(Site(ROB3), ['/scrapy-only', '/mybot-only', '/all', '/free'], stt)
    print(f'  {tag:<34}' + ' '.join(f'{x["p"]}:{"通过" if x["ok"] else "拒"}' for x in sorted(E, key=lambda x: x['p'])))

print('== 四:robots.txt 自己下载失败或内容异常时:/private 能不能抓(默认是“放行”)')
print(f'  {"robots.txt 的情形":<28}{"/private":<10}robotstxt stats / 说明')
for tag, sv0, stt in (('200 正常', Site(ROB), {}), ('404', Site(None, 404), {}), ('500(会被重试 2 次)', Site(None, 500), {}), ('超时(服务器睡 2 s,超时 0.5 s)', Site(ROB, 200, 2.0), {'DOWNLOAD_TIMEOUT': 0.5, 'RETRY_ENABLED': 0}), ('200 但是 1024 字节二进制垃圾', Site(None, 'garbage'), {})):
    sv, E, out, st = go(sv0, ['/private'], stt)
    x = E[0]
    print(f'  {tag:<28}{"通过" if x["ok"] else "被拒":<10}{rs(st)};服务器收到 robots.txt {len([1 for p, _ in sv.log if p == "/robots.txt"])} 次')

print('== 五:robots.txt 下载慢时,其它请求要等它:robots.txt 延迟 1.0 s,三个页面请求')
sv, E, out, st = go(Site(ROB, 200, 1.0), ['/a', '/b', '/c'])
t0 = sv.log[0][1]
print('  到达服务器的时刻(相对第一个请求,秒):' + ', '.join(f'{p}@{t - t0:.2f}' for p, t in sv.log) + f';总耗时 {st["elapsed_time_seconds"]:.2f} s')
print('  meta dont_obey_robotstxt=True 的请求既不下载 robots.txt 也不受它限制(/private/x 本来会被拒绝):', end='')
d = sdir('s23e')
sv2 = Site(ROB, 200, 1.0)
with Srv(sv2) as s:
    code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('{s.url("/private/x")}', meta={{'dont_obey_robotstxt': True}}, callback=self.cb)
    def cb(self, response): EV(ok=True)
"""
    rc, out, t = runspider(d, code, {'LOG_LEVEL': 'INFO', 'ROBOTSTXT_OBEY': 1})
print(f'服务器收到 {[p for p, _ in sv2.log]},总耗时 {stats(out)["elapsed_time_seconds"]:.2f} s(robots.txt 要 1.0 s 才返回,但没有被请求)')

print('== 六:robots.txt 的 Crawl-delay 被 Scrapy 忽略;不同端口(netloc)各自下载自己的 robots.txt')
ROB6 = 'User-agent: *\nCrawl-delay: 2\nAllow: /\n'
sv, E, out, st = go(Site(ROB6), ['/a', '/b', '/c', '/d'])
ts = [t for p, t in sv.log if p != '/robots.txt']; g = [(b - a) * 1000 for a, b in zip(ts, ts[1:])]
print(f'  Crawl-delay: 2 → 四个页面请求之间的间隔(ms):{[round(x) for x in g]}(没有等 2 秒);总耗时 {st["elapsed_time_seconds"]:.2f} s')
d = sdir('s23f'); a = Site(ROB); b = Site(ROB)
with Srv(a) as s1, Srv(b) as s2:
    code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('{s1.url("/x")}', callback=self.cb)
        yield scrapy.Request('{s2.url("/x")}', callback=self.cb)
    def cb(self, response): pass
"""
    rc, out, t = runspider(d, code, {'LOG_LEVEL': 'INFO', 'ROBOTSTXT_OBEY': 1})
print(f'  同一个主机 127.0.0.1 的两个端口:服务器 1 收到 {[p for p, _ in a.log]},服务器 2 收到 {[p for p, _ in b.log]};robotstxt/request_count = {stats(out).get("robotstxt/request_count")}')
