import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s31'); reset_s()
class Site:
    """/ → /list/1、/list/2、/item/1、/about;/list/N → /item/N0、/item/N1、/list/(N+1)(到 3 为止);/item/* → 返回 /about 和一个到 /list/1 的回链。"""
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(h.path); p = h.path.split('?')[0]
        links = []
        if p == '/': links = ['/list/1', '/list/2', '/item/1', '/about', '/feed.xml']
        elif p.startswith('/list/'):
            n = int(p.split('/')[-1]); links = [f'/item/{n}0', f'/item/{n}1'] + ([f'/list/{n + 1}'] if n < 3 else [])
        elif p.startswith('/item/'): links = ['/about', '/list/1']
        if p == '/feed.xml': h.reply(200, '<feed><a href="/hidden">x</a></feed>', {'Content-Type': 'application/xml'}); return
        h.reply(200, '<html>' + ''.join(f'<a href="{l}">{l}</a>' for l in links) + '</html>', {'Content-Type': 'text/html'})
def go(rules_code, extra='', tag='s31', settings=None):
    d = sdir(tag); sv = Site()
    with Srv(sv) as s:
        code = f"""
import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
class S(CrawlSpider):
    name = 's'
    start_urls = ['{s.url("/")}']
    rules = ({rules_code},)
    def item(self, response, **kw): EV(who='item', url=response.url.split('{s.port}')[-1], rule=response.meta.get('rule'), link_text=response.meta.get('link_text'), kw=kw)
    def other(self, response): EV(who='other', url=response.url.split('{s.port}')[-1])
{extra}
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 1}, **(settings or {})))
    return sv, ev(d), out, stats(out)
def summary(sv, E): return f'服务器收到 {len(sv.log)} 个请求;回调 {len(E)} 次'

print('== 一:follow 的默认值:没有 callback 的规则 follow=True(只跟踪,不回调);有 callback 的规则 follow=False(回调,但不继续往下跟链接);显式 follow=True 才两样都做')
for tag, rules in (('Rule(LinkExtractor(allow="/list/|/item/"))(无 callback)', 'Rule(LinkExtractor(allow=r"/list/|/item/"))'),
                   ('Rule(LinkExtractor(allow="/list/|/item/"), callback="item")', 'Rule(LinkExtractor(allow=r"/list/|/item/"), callback="item")'),
                   ('同上,再加 follow=True', 'Rule(LinkExtractor(allow=r"/list/|/item/"), callback="item", follow=True)')):
    sv, E, out, st = go(rules)
    print(f'  {tag}:服务器收到 {len(sv.log)} 个请求;回调 {len(E)} 次;抓到的路径 {sorted(set(sv.log))}')

print('== 二:一个链接被多条规则命中时,只归第一条规则(规则的顺序决定谁处理):/item/1、/item/10、/item/11 同时匹配规则 0(allow="/item/1")和规则 1(allow="/item/")')
sv, E, out, st = go('Rule(LinkExtractor(allow=r"/list/")), Rule(LinkExtractor(allow=r"/item/1"), callback="other"), Rule(LinkExtractor(allow=r"/item/"), callback="item")')
print('  规则 1: /item/1 → other;规则 2: /item/ → item')
for x in sorted(E, key=lambda x: x['url']): print(f'    {x["url"]:<10}→ {x["who"]}')
sv, E, out, st = go('Rule(LinkExtractor(allow=r"/list/")), Rule(LinkExtractor(allow=r"/item/"), callback="item"), Rule(LinkExtractor(allow=r"/item/1"), callback="other")')
print('  调换规则 1、2 的顺序后,全部归 item:' + str(sorted({x["who"] for x in E})))

print('== 三:每个规则产生的请求 meta 里有 rule(规则序号)和 link_text(链接文字);cb_kwargs 通过规则传给回调')
sv, E, out, st = go('Rule(LinkExtractor(allow=r"/list/1$"), follow=False), Rule(LinkExtractor(allow=r"/item/1$"), callback="item", cb_kwargs={"tag": "from-rule"})')
for x in E: print(f'  回调 {x["url"]}:meta rule={x["rule"]}, link_text={x["link_text"]!r}, cb_kwargs={x["kw"]}')

print('== 四:process_links(在规则里过滤/改写 Link 对象列表)和 process_request(对每个请求改写或返回 None 丢弃)')
sv, E, out, st = go('Rule(LinkExtractor(allow=r"/list/")), Rule(LinkExtractor(allow=r"/item/"), callback="item", process_links="drop_odd", process_request="tag_request")', extra="""
    def drop_odd(self, links): return [l for l in links if not l.url.endswith('1')]
    def tag_request(self, request, response):
        if request.url.endswith('/item/10'): return None
        request.meta['seen_from'] = response.url.split('/')[-2] + '/' + response.url.split('/')[-1]
        return request
    def item(self, response, **kw): EV(who='item', url=response.url.split('/item')[-1], seen_from=response.meta.get('seen_from'))
""")
print(f'  规则:/list/ 跟踪;/item/ 回调 + process_links 丢掉以 1 结尾的 + process_request 丢掉 /item/10 并给其余请求加 meta seen_from')
print(f'  服务器收到的 /item 请求:{sorted(p for p in sv.log if p.startswith("/item"))};回调 {[(x["url"], x["seen_from"]) for x in E]}')

print('== 五:起始页面的响应也走规则;parse_start_url 钩子处理起始页本身;2.19 里覆盖 parse 不会影响规则(起始请求的默认回调是 _parse,它调用 parse_with_rules)')
sv, E, out, st = go('Rule(LinkExtractor(allow=r"/about"), callback="other")', extra="""
    def parse_start_url(self, response):
        EV(who='parse_start_url', url=response.url.split(':')[-1].split('/', 1)[-1] or '/')
        return []
""")
print(f'  起始页响应:{[x for x in E if x["who"] == "parse_start_url"]};/about 回调 {[x["url"] for x in E if x["who"] == "other"]}')
sv, E, out, st = go('Rule(LinkExtractor(allow=r"/about"), callback="other")', extra="""
    def parse(self, response): EV(who='my parse', url=response.url)
""")
print(f'  CrawlSpider 子类里定义了自己的 parse 以后:回调事件 {[x["who"] for x in E]}(没有 my parse);服务器收到 {sv.log}(规则照常触发,自己的 parse 没有被调用)')

print('== 六:只对 HTML 响应应用规则:XML 响应(Content-Type: application/xml)里的 <a> 不会被跟踪')
sv, E, out, st = go('Rule(LinkExtractor(), callback="other")', settings={})
print(f'  / 页面有一个指向 /feed.xml 的链接,/feed.xml 里有 <a href="/hidden">:服务器收到 {sorted(set(sv.log))}(没有 /hidden)')
