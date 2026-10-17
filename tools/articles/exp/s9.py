import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s9'); reset_s()
d = sdir('s9')
def ok(h): h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})

print('== 一:哪些 URL 会被当成同一个请求(RFPDupeFilter 用 SHA1(方法 + 规范化后的 URL + 请求体));每行比较一对 URL,GET')
rc, out, t = py(d, """
from scrapy import Request
from scrapy.utils.request import fingerprint
P = [
 ('查询参数顺序', 'http://a.com/p?a=1&b=2', 'http://a.com/p?b=2&a=1'),
 ('片段 #frag', 'http://a.com/p?a=1', 'http://a.com/p?a=1#top'),
 ('主机名大小写', 'http://A.COM/p', 'http://a.com/p'),
 ('默认端口 :80', 'http://a.com/p', 'http://a.com:80/p'),
 ('百分号编码的十六进制大小写', 'http://a.com/p?q=%e4%b8%ad', 'http://a.com/p?q=%E4%B8%AD'),
 ('中文原样 与 百分号编码', 'http://a.com/p?q=中', 'http://a.com/p?q=%E4%B8%AD'),
 ('空格 %20 与 +', 'http://a.com/p?q=a%20b', 'http://a.com/p?q=a+b'),
 ('末尾的 / (路径)', 'http://a.com/p', 'http://a.com/p/'),
 ('http 与 https', 'http://a.com/p', 'https://a.com/p'),
 ('空参数 ?a= 与没有 a', 'http://a.com/p?a=', 'http://a.com/p'),
 ('末尾的 ?', 'http://a.com/p?', 'http://a.com/p'),
 ('路径 /./ 和 /../', 'http://a.com/x/../p', 'http://a.com/p'),
 ('重复键的顺序 a=1&a=2', 'http://a.com/p?a=1&a=2', 'http://a.com/p?a=2&a=1'),
 ('www.a.com 与 a.com', 'http://www.a.com/p', 'http://a.com/p'),
]
print(f'  {"差异":<28}{"相同?":<7}{"URL 1":<34}URL 2')
for tag, u1, u2 in P:
    f1, f2 = fingerprint(Request(u1)), fingerprint(Request(u2))
    print(f'  {tag:<26}{"相同" if f1 == f2 else "不同":<7}{u1:<34}{u2}')
""")
print(out)

print('== 二:方法、请求体、请求头:请求头默认不参与;POST 的请求体逐字节比较;用自定义 fingerprinter 才能把头或 meta 算进去')
rc, out, t = py(d, """
from scrapy import Request
from scrapy.utils.request import fingerprint, RequestFingerprinter
import json
U = 'http://a.com/p'
def same(a, b, **kw): return '相同' if fingerprint(a, **kw) == fingerprint(b, **kw) else '不同'
print('  GET 与 POST(同 URL):', same(Request(U), Request(U, method='POST')))
print('  POST 体 {"a":1,"b":2} 与 {"b":2,"a":1}(同样的 JSON,键顺序不同):', same(Request(U, method='POST', body=json.dumps({'a': 1, 'b': 2})), Request(U, method='POST', body=json.dumps({'b': 2, 'a': 1}))))
print('  POST 体 "a=1&b=2" 与 "b=2&a=1":', same(Request(U, method='POST', body='a=1&b=2'), Request(U, method='POST', body='b=2&a=1')))
print('  POST 体 多一个空格:', same(Request(U, method='POST', body='a=1'), Request(U, method='POST', body='a=1 ')))
print('  Cookie 头不同:', same(Request(U, headers={'Cookie': 'sid=1'}), Request(U, headers={'Cookie': 'sid=2'})))
print('  Accept-Language 头不同(默认):', same(Request(U, headers={'Accept-Language': 'zh'}), Request(U, headers={'Accept-Language': 'en'})))
print('  Accept-Language 头不同,fingerprint(include_headers=[\\'Accept-Language\\']):', same(Request(U, headers={'Accept-Language': 'zh'}), Request(U, headers={'Accept-Language': 'en'}), include_headers=['Accept-Language']))
print('  meta 不同(默认):', same(Request(U, meta={'page': 1}), Request(U, meta={'page': 2})))
class MetaFP(RequestFingerprinter):
    def fingerprint(self, request):
        import hashlib
        return hashlib.sha1(super().fingerprint(request) + str(request.meta.get('page')).encode()).digest()
f = MetaFP()
print('  自定义 fingerprinter(把 meta[\\'page\\'] 算进去),meta 不同:', '相同' if f.fingerprint(Request(U, meta={'page': 1})) == f.fingerprint(Request(U, meta={'page': 2})) else '不同')
print('  fingerprint 的长度:', len(fingerprint(Request(U))), '字节(SHA1);十六进制:', fingerprint(Request(U)).hex()[:16] + '…')
""")
print(out)

print('== 三:verbatim_url 与 keep_fragments:要保留 URL 里 #fragment 或原样不规范化时')
rc, out, t = py(d, """
from scrapy import Request
from scrapy.utils.request import fingerprint
a, b = 'http://a.com/p?a=1&b=2#x', 'http://a.com/p?b=2&a=1#y'
print('  默认:', '相同' if fingerprint(Request(a)) == fingerprint(Request(b)) else '不同')
print('  keep_fragments=True:', '相同' if fingerprint(Request(a), keep_fragments=True) == fingerprint(Request(b), keep_fragments=True) else '不同')
print('  meta verbatim_url=True(不规范化):', '相同' if fingerprint(Request(a, meta={'verbatim_url': True})) == fingerprint(Request(b, meta={'verbatim_url': True})) else '不同')
print('  verbatim_url 下两个“只差参数顺序”的 URL:', '相同' if fingerprint(Request('http://a.com/p?a=1&b=2', meta={'verbatim_url': True})) == fingerprint(Request('http://a.com/p?b=2&a=1', meta={'verbatim_url': True})) else '不同')
""")
print(out)

print('== 四:在一次真实抓取里:同一个 URL yield 3 次;stats、日志;DUPEFILTER_DEBUG;dont_filter')
CODE = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/seed')
    def parse(self, response):
        if response.url.endswith('seed'):
            for u in ('/x?a=1&b=2', '/x?b=2&a=1', '/x?a=1&b=2#f', '/y'): yield response.follow(u, self.parse)
            yield scrapy.Request(response.urljoin('/x?a=1&b=2'), dont_filter=True)
"""
for tag, stt in (('默认', {}), ('DUPEFILTER_DEBUG=1', {'DUPEFILTER_DEBUG': 1})):
    dd = sdir('s9d')
    with Srv(ok) as s:
        rc, out, t = runspider(dd, CODE.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'DEBUG'}, **stt))
    st = stats(out)
    print(f'  {tag}:服务器收到 {[l["path"] for l in s.log]};dupefilter/filtered={st.get("dupefilter/filtered")};scheduler/enqueued={st.get("scheduler/enqueued")}')
    for l in out.split(chr(10)):
        if 'Filtered duplicate request' in l: print('      ' + l.strip()[:190])

print('== 五:JOBDIR 里的 requests.seen:每个指纹 2 字节长度 + 20 字节 SHA1 = 22 字节;再次运行时读回来,见过的 URL 全部被过滤')
dd = sdir('s9e'); jd = sdir('s9ejob')
CODE5 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/seed', dont_filter=@DF@)
    def parse(self, response):
        if response.url.endswith('seed'):
            for i in range(@N@): yield scrapy.Request('@U@/p%d' % i)
"""
with Srv(ok) as s:
    f = jd / 'requests.seen'
    for tag, n, df in (('第 1 次运行:seed(dont_filter=True)+ p0…p999', 1000, True), ('第 2 次运行,同一个 JOBDIR:seed(dont_filter=True)+ p0…p1499', 1500, True), ('第 3 次运行,同一个 JOBDIR:seed 没写 dont_filter(默认 False)', 1500, False)):
        s.reset()
        rc, out, t = runspider(dd, CODE5.replace('@U@', s.url('').rstrip('/')).replace('@N@', str(n)).replace('@DF@', str(df)), {'LOG_LEVEL': 'INFO', 'JOBDIR': str(jd)})
        st = stats(out)
        print(f'  {tag}:服务器收到 {len(s.log)} 个请求;dupefilter/filtered={st.get("dupefilter/filtered", 0)};requests.seen = {f.stat().st_size:,} 字节')
print(f'  22 字节/个 × (1 个 seed + 1500 个 p) = {22 * 1501:,} 字节(与文件大小一致)')

print('== 六:去重集合的开销:100 万个指纹的内存(tracemalloc)和计算指纹的耗时')
rc, out, t = py(d, """
import tracemalloc, time
from scrapy import Request
from scrapy.utils.request import fingerprint
N = 1_000_000
reqs = [Request('http://a.com/p?id=%d&x=%d' % (i, i * 7)) for i in range(20000)]
t0 = time.perf_counter()
fps = [fingerprint(r) for r in reqs]
dt = (time.perf_counter() - t0) / len(reqs) * 1e6
print(f'  计算 {len(reqs):,} 个指纹:平均 {dt:.1f} 微秒/个(含 URL 规范化 + SHA1,首次计算)')
import hashlib
tracemalloc.start()
s = set()
for i in range(N): s.add(hashlib.sha1(str(i).encode()).digest())
cur, peak = tracemalloc.get_traced_memory()
print(f'  {N:,} 个 20 字节指纹放进 set:tracemalloc 当前 {cur / 1e6:.1f} MB(平均 {cur / N:.0f} 字节/个,指纹本身 20 字节,bytes 对象 53 字节)')
""")
print(out)
