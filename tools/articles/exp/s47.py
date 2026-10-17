import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s47'); reset_s()
class Site:
    def __init__(self): self.log = []
    def __call__(self, h): self.log.append(h.path); h.reply(200, f'<html>{h.path}</html>', {'Content-Type': 'text/html'})
def run(spider_code, args=(), settings=None, tag='s47', sv=None):
    d = sdir(tag); sv = sv or Site()
    with Srv(sv) as s:
        write(d, 'spider.py', PRE_ + spider_code.replace('@U@', s.url('').rstrip('/')))
        a = ['runspider', 'spider.py', '-s', 'LOG_LEVEL=INFO', '-s', 'TELNETCONSOLE_ENABLED=0', '-s', 'REMOTE_CONTROL_ENABLED=0']
        for k, v in (settings or {}).items(): a += ['-s', f'{k}={v}']
        for x in args: a += [y.replace('@U@', s.url('').rstrip('/')) for y in (x if isinstance(x, (list, tuple)) else [x])]
        rc, out, t = scrapy(d, *a)
    return rc, out, ev(d), sv
PRE_ = PRE

print('== 一:-a NAME=VALUE:传给 spider 的 __init__(默认的 Spider.__init__ 把所有关键字参数写成实例属性);值总是字符串')
rc, out, E, sv = run("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    category = 'default-cat'
    async def start(self):
        EV(category=self.category, page=self.page, page_type=type(self.page).__name__, extra=getattr(self, 'extra', '(没有)'), n_ok=True)
        return
        yield
""", [['-a', 'category=books', '-a', 'page=3']])
print(f'  -a category=books -a page=3:{[{k: v for k, v in x.items() if k not in ("t", "n_ok")} for x in E]}(class 属性 category 被覆盖;page 是字符串 “3”)')
rc, out, E, sv = run("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        EV(url=self.url, eq=self.eq)
        return
        yield
""", [['-a', 'url=http://x/?a=1&b=2', '-a', 'eq=a=b=c']])
print(f'  值里带 =:{[{k: v for k, v in x.items() if k != "t"} for x in E]}(按第一个 = 拆分)')

print('== 二:__init__ 自己写时必须接收 **kwargs,否则传了没声明的参数会 TypeError;推荐写法')
rc, out, E, sv = run("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    def __init__(self, category=None, **kwargs):
        super().__init__(**kwargs)
        self.category = category
    async def start(self):
        EV(category=self.category, other=getattr(self, 'other', '(没有)'))
        return
        yield
""", [['-a', 'category=books', '-a', 'other=1']])
print(f'  推荐写法 __init__(self, category=None, **kwargs) + super().__init__(**kwargs):{[{k: v for k, v in x.items() if k != "t"} for x in E]}')
rc, out, E, sv = run("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    def __init__(self, category=None):
        self.category = category
    async def start(self):
        EV(category=self.category)
        return
        yield
""", [['-a', 'category=books', '-a', 'other=1']])
print(f'  漏了 **kwargs:退出码 {rc};{[l for l in out.split(chr(10)) if l.startswith("TypeError")][:1]}')

print('== 三:几个坑:start_urls 通过 -a 传(字符串而不是列表);-a 没有 =;spider 属性与 -a 同名')
rc, out, E, sv = run("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    def parse(self, response): EV(url=response.url)
""", [['-a', 'start_urls=@U@/only']])
print(f'  -a start_urls=http://…/only:退出码 {rc};服务器收到 {sv.log};回调 {[x.get("url") for x in E]};日志里的错误:{[l.strip()[:110] for l in out.split(chr(10)) if "Missing scheme" in l or "ERROR" in l][:2]}')
rc, out, E, sv = run("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    start_urls = ['@U@/default']
    def parse(self, response): EV(url=response.url)
""", [['-a', 'start_urls=["@U@/from-arg"]']])
print(f'  -a start_urls=[…](JSON 风格的字符串):服务器收到 {sv.log}')
rc, out, E, sv = run("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): return
        yield
""", [['-a', 'novalue']])
print(f'  -a novalue(没有 =):退出码 {rc};{[l.strip()[:110] for l in out.split(chr(10)) if "Invalid" in l or "usage" in l.lower()][:2]}')

print('== 四:正确传 URL 列表的办法:-a 传逗号分隔的字符串,在 __init__ 里自己拆成 start_urls')
rc, out, E, sv = run("""
import scrapy, json
class S(scrapy.Spider):
    name = 's'
    def __init__(self, urls='', **kw):
        super().__init__(**kw)
        self.start_urls = [u for u in urls.split(',') if u]
    def parse(self, response): EV(url=response.url.rsplit('/', 1)[-1])
""", [['-a', 'urls=@U@/a,@U@/b']])
print(f'  -a urls=a,b 由 __init__ 拆成 start_urls:服务器收到 {sv.log}')

print('== 五:程序里启动(CrawlerProcess.crawl(S, 关键字参数))可以传任意类型,不限于字符串;-s 是设置、-a 是参数,不能混用')
d = sdir('s47e'); sv = Site()
with Srv(sv) as s:
    code = f"""
import scrapy
from scrapy.crawler import CrawlerProcess
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        EV(page=self.page, page_type=type(self.page).__name__, opts=self.opts, opts_type=type(self.opts).__name__, setting_same_name=self.settings.get('PAGE'))
        return
        yield
p = CrawlerProcess({{'LOG_LEVEL': 'ERROR', 'PAGE': 'from-settings', 'TELNETCONSOLE_ENABLED': False, 'REMOTE_CONTROL_ENABLED': False}})
p.crawl(S, page=3, opts={{'k': [1, 2]}})
p.start()
"""
    rc, out, t = py(d, PRE + code)
print(f'  p.crawl(S, page=3, opts={{…}}):{[{k: v for k, v in x.items() if k != "t"} for x in ev(d)]}(类型保留;同名的设置 PAGE 是另一回事)')
