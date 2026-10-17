import sys, os, socket, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s35'); reset_s()
class Site:
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(h.path); p = h.path
        if p == '/': h.reply(200, '<html><a href="/a">a</a><a href="/b">b</a><a href="/missing">m</a><a href="/redir">r</a></html>', {'Content-Type': 'text/html'})
        elif p == '/missing': h.reply(404, 'nf', {'Content-Type': 'text/plain'})
        elif p == '/redir': h.reply(302, b'', {'Location': '/a'})
        else: h.reply(200, '<html>page ' + p + '</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s35'):
    d = sdir(tag); sv = Site()
    with Srv(sv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO'}, **(settings or {})))
    return sv, ev(d), out, stats(out)

CODE = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/')
    def parse(self, response):
        if response.url.endswith('/'):
            for u in response.css('a::attr(href)').getall(): yield response.follow(u, errback=self.eb)
        else: yield {'url': response.url}
    def eb(self, failure): pass
    def closed(self, reason): EV(closed_stats=len(self.crawler.stats.get_stats()))
"""
print('== 一:一次最普通的抓取(起始页 + a、b、一个 404、一个 302 → a)结束时 Scrapy 打印的 stats,逐项看:')
sv, E, out, st = go(CODE)
skip = ('start_time', 'finish_time')
for k in sorted(st):
    v = st[k]
    if k in skip: v = '<datetime>'
    elif isinstance(v, float): v = round(v, 3)
    print(f'  {k:<46}{v}')

print('== 二:downloader/request_bytes、response_bytes 到底数的是什么:用原始套接字服务器对照真实收到/发出的字节')
class Raw:
    def __init__(self, body=b'<html>ok</html>'):
        self.req = []; self.sent = []
        def fn(conn, addr):
            data = read_request(conn)
            if not data: return
            self.req.append(len(data))
            resp = b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: ' + str(len(body)).encode() + b'\r\nServer: raw\r\n\r\n' + body
            self.sent.append((len(resp), len(resp) - len(body))); conn.sendall(resp)
        self.srv = RawSrv(fn)
    def __enter__(self): self.srv.__enter__(); return self
    def __exit__(self, *a): self.srv.__exit__()
for tag, body in (('小页面(15 字节)', b'<html>ok</html>'), ('大页面(20,000 字节)', b'<p>' + b'x' * 19990 + b'</p>')):
    d = sdir('s35b')
    with Raw(body) as r:
        code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('http://127.0.0.1:{r.srv.port}/p')
    def parse(self, response): pass
"""
        rc, out, t = runspider(d, code, {'LOG_LEVEL': 'INFO'})
    st = stats(out)
    print(f'  {tag}:服务器实际收到请求 {r.req[0]} 字节;stats downloader/request_bytes = {st["downloader/request_bytes"]}')
    print(f'      服务器实际发出响应 {r.sent[0][0]} 字节(头 {r.sent[0][1]} + 体 {len(body)});stats downloader/response_bytes = {st["downloader/response_bytes"]}')

print('== 三:自定义统计:crawler.stats 的 inc_value / set_value / max_value / min_value / get_value / get_stats')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/')
    def parse(self, response):
        s = self.crawler.stats
        s.inc_value('mine/pages'); s.inc_value('mine/bytes', len(response.body), start=1000)
        s.set_value('mine/last_url', response.url.rsplit('/', 1)[-1] or '/')
        s.max_value('mine/max_len', len(response.body)); s.min_value('mine/min_len', len(response.body))
        EV(get=s.get_value('mine/pages'), missing=s.get_value('mine/none', 'DEFAULT'), n=len(s.get_stats()))
        if response.url.endswith('/'):
            for u in ('/a', '/b'): yield response.follow(u)
""")
print('  stats 里 mine/* 的键:' + ', '.join(f'{k}={v}' for k, v in sorted(st.items()) if k.startswith('mine/')))
print(f'  回调里 get_value 读到的(最后一次):{E[-1]}')

print('== 四:STATS_CLASS:DummyStatsCollector 什么都不记(stats 为空);STATS_DUMP=0 不在结束时打印(但仍可从 crawler.stats 读)')
for tag, stt in (('默认 MemoryStatsCollector', {}), ('DummyStatsCollector', {'STATS_CLASS': 'scrapy.statscollectors.DummyStatsCollector'}), ('STATS_DUMP=0', {'STATS_DUMP': 0})):
    sv, E, out, st = go(CODE, stt)
    cs = [x for x in E if 'closed_stats' in x]
    print(f'  {tag}:日志里有 “Dumping Scrapy stats”:{"是" if "Dumping Scrapy stats" in out else "否"};日志里打出的键数 {len(st)};spider.closed() 里 crawler.stats.get_stats() 的键数 {cs[0]["closed_stats"] if cs else "?"}')

print('== 五:memusage/* 和 log_count/*:MemoryUsage 扩展记录启动和最大 RSS;日志每个级别的条数')
sv, E, out, st = go(CODE, {'LOG_LEVEL': 'DEBUG'})
print('  DEBUG 级别的运行:' + ', '.join(f'{k}={v}' for k, v in sorted(st.items()) if k.startswith(('log_count', 'memusage'))))
print('  elapsed_time_seconds 与 finish_time − start_time:' + f'{st["elapsed_time_seconds"]:.4f} s  /  {(st["finish_time"] - st["start_time"]).total_seconds():.4f} s')
