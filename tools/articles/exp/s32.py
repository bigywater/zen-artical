import sys, os, gzip; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s32'); reset_s()
def urlset(urls, alt=False):
    ns = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml"'
    body = ''.join(f'<url><loc>{u}</loc><lastmod>{lm}</lastmod>' + (f'<xhtml:link rel="alternate" hreflang="en" href="{u}?lang=en"/>' if alt else '') + '</url>' for u, lm in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset {ns}>{body}</urlset>'.encode()
class Site:
    def __init__(self): self.log = []; self.port = None
    def __call__(self, h):
        self.log.append(h.path); p = h.path.split('?')[0]; b = f'http://127.0.0.1:{h.server.srv.port}'
        if p == '/robots.txt': h.reply(200, f'User-agent: *\nAllow: /\nSitemap: /sitemap_index.xml\nsitemap: {b}/extra.html\n', {'Content-Type': 'text/plain'}); return
        if p == '/sitemap_index.xml':
            h.reply(200, f'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>{b}/sm/products.xml</loc></sitemap><sitemap><loc>{b}/sm/blog.xml.gz</loc></sitemap><sitemap><loc>{b}/sm/news.xml</loc></sitemap></sitemapindex>', {'Content-Type': 'application/xml'}); return
        if p == '/sm/products.xml': h.reply(200, urlset([(f'{b}/p/{i}', f'2025-0{i}-01') for i in (1, 2, 3)], alt=True), {'Content-Type': 'application/xml'}); return
        if p == '/sm/blog.xml.gz': h.reply(200, gzip.compress(urlset([(f'{b}/blog/a', '2024-01-01'), (f'{b}/blog/b', '2025-06-01')])), {'Content-Type': 'application/gzip'}); return
        if p == '/sm/news.xml': h.reply(200, gzip.compress(urlset([(f'{b}/news/1', '2025-09-01')])), {'Content-Type': 'application/xml', 'Content-Encoding': 'gzip'}); return
        if p == '/sm/plain-ct': h.reply(200, urlset([(f'{b}/x/1', '2025-01-01')]), {'Content-Type': 'text/plain'}); return
        if p == '/sitemap.php': h.reply(200, urlset([(f'{b}/y/1', '2025-01-01')]), {'Content-Type': 'text/xml'}); return
        if p == '/extra.html': h.reply(200, '<html>not a sitemap</html>', {'Content-Type': 'text/html'}); return
        h.reply(200, f'<html>{p}</html>', {'Content-Type': 'text/html'})
def go(spider_body, tag='s32', settings=None):
    d = sdir(tag); sv = Site()
    with Srv(sv) as s:
        code = f"""
import scrapy
from scrapy.spiders import SitemapSpider
class S(SitemapSpider):
    name = 's'
{spider_body.replace('@U@', s.url('').rstrip('/'))}
    def parse(self, response): EV(who='parse', url=response.url.split('{s.port}')[-1])
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 1, 'SCHEDULER_MEMORY_QUEUE': 'scrapy.squeues.FifoMemoryQueue'}, **(settings or {})))
    return sv, ev(d), out, stats(out)

print('== 一:sitemap_urls 指向 robots.txt:读取其中的 Sitemap: 行(相对路径按 robots.txt 的 URL 补全,行首大小写不敏感),递归进入索引(sitemapindex)里的各个子 sitemap,.xml.gz 自动解压,无效的 sitemap 只警告')
sv, E, out, st = go("    sitemap_urls = ['@U@/robots.txt']")
print(f'  服务器收到(按顺序):{sv.log}')
print(f'  parse 回调的页面:{sorted(x["url"] for x in E)}')
print('  警告:' + ' | '.join(l.strip()[:120] for l in out.split('\n') if 'Ignoring invalid sitemap' in l))

print('== 二:sitemap_rules:(正则, 回调) 列表,按顺序第一个匹配的生效;不匹配任何规则的 URL 直接丢掉(默认规则是 [("", "parse")] 匹配全部)')
sv, E, out, st = go("""    sitemap_urls = ['@U@/sitemap_index.xml']
    sitemap_rules = [('/p/', 'parse_product'), ('/blog/', 'parse_blog')]
    def parse_product(self, response): EV(who='product', url=response.url.split('/p/')[-1])
    def parse_blog(self, response): EV(who='blog', url=response.url.split('/blog/')[-1])
""")
print(f'  规则 [(/p/, parse_product), (/blog/, parse_blog)]:回调 {sorted((x["who"], x["url"]) for x in E)};服务器收到页面请求 {sorted(p for p in sv.log if p.startswith(("/p/", "/blog/", "/news/")))}(/news/1 没有规则匹配,没有请求)')

print('== 三:sitemap_follow:索引里的子 sitemap 只跟踪 URL 匹配的(默认 [""] 全部跟踪)')
sv, E, out, st = go("""    sitemap_urls = ['@U@/sitemap_index.xml']
    sitemap_follow = ['products', 'news']
""")
print(f'  sitemap_follow=["products","news"]:服务器收到 sitemap 请求 {[p for p in sv.log if "sm" in p or "index" in p]};parse 页面 {sorted(x["url"] for x in E)}(blog.xml.gz 没有被请求)')

print('== 四:sitemap_filter(entries):每个 entry 是一个字典(loc、lastmod 等);用它按 lastmod 过滤')
sv, E, out, st = go("""    sitemap_urls = ['@U@/sitemap_index.xml']
    def sitemap_filter(self, entries):
        for entry in entries:
            if 'lastmod' in entry:
                EV(who='entry', keys=sorted(entry), loc=entry['loc'].split('/', 3)[-1], lastmod=entry['lastmod'])
            if entry.get('lastmod', '9999') >= '2025-02':
                yield entry
""")
for x in E:
    if x['who'] == 'entry': print(f'  entry {x["loc"]:<10} lastmod={x["lastmod"]} 键={x["keys"]}')
print(f'  只保留 lastmod ≥ 2025-02 的:parse 页面 {sorted(x["url"] for x in E if x["who"] == "parse")}')

print('== 五:sitemap_alternate_links:带 <xhtml:link rel="alternate"> 的条目是否把备用链接也当成页面')
for tag, v in (('False(默认)', 'False'), ('True', 'True')):
    sv, E, out, st = go(f"""    sitemap_urls = ['@U@/sm/products.xml']
    sitemap_alternate_links = {v}
""")
    print(f'  {tag}:parse 页面 {sorted(x["url"] for x in E)}')

print('== 六:什么响应会被当成 sitemap:XmlResponse、gzip 魔数、或者 URL 以 .xml / .xml.gz 结尾;否则警告并忽略——哪怕内容就是合法的 sitemap')
for path in ('/sm/products.xml', '/sitemap.php', '/sm/plain-ct', '/sm/news.xml', '/sm/blog.xml.gz'):
    sv, E, out, st = go(f"    sitemap_urls = ['@U@{path}']")
    bad = [l for l in out.split('\n') if 'Ignoring invalid sitemap' in l]
    print(f'  {path:<20}→ parse 页面 {sorted(x["url"] for x in E)}' + ('  [警告:Ignoring invalid sitemap]' if bad else ''))
