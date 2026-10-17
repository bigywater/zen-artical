import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s4'); reset_s()
def ok(h): h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})

def project(name, settings_extra='', spider_extra='', mods=None, strip=True):
    d = sdir(name)
    rc, out, t = scrapy(d, 'startproject', 'proj', '.')
    assert rc == 0, out
    p = d / 'proj' / 'settings.py'; txt = p.read_text()
    if strip: txt = txt.replace('DOWNLOAD_DELAY = 1\n', '')
    p.write_text(txt + '\n' + textwrap.dedent(settings_extra))
    for fn, code in (mods or {}).items(): write(d, f'proj/{fn}', code)
    return d

SPIDER = lambda extra='', body='': f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
{extra}
    async def start(self):
        s = self.crawler.settings
        print('RESULT', {{k: (s.get(k), s.getpriority(k)) for k in KEYS}})
        return
        yield
KEYS = ['DOWNLOAD_DELAY']
"""

print('== 一:优先级数值:SETTINGS_PRIORITIES(scrapy/settings/__init__.py);同一个设置在多个地方出现时,优先级高的生效,相同优先级后设置的覆盖先设置的')
rc, out, t = py(sdir('s4a'), "from scrapy.settings import SETTINGS_PRIORITIES as P\nfor k, v in sorted(P.items(), key=lambda kv: kv[1]): print(f'  {k:<8}{v:>3}')")
print(out)

print('== 二:DOWNLOAD_DELAY 在不同地方设成不同的值,哪个生效、优先级是多少(每行是一次 scrapy crawl)')
ADDON = """
class DelayAddon:
    def update_settings(self, settings): settings.set('DOWNLOAD_DELAY', 4, 'addon')
"""
CASES = [
 ('新建项目的 settings.py 原样(模板里写着 DOWNLOAD_DELAY = 1)', '', '', [], False),
 ('模板的那一行删掉,什么都不设', '', '', [], True),
 ('settings.py 里 =1', 'DOWNLOAD_DELAY = 1', '', [], True),
 ('settings.py =1 + spider.custom_settings =2', 'DOWNLOAD_DELAY = 1', '    custom_settings = {"DOWNLOAD_DELAY": 2}', [], True),
 ('settings.py =1 + custom_settings =2 + 命令行 -s =3', 'DOWNLOAD_DELAY = 1', '    custom_settings = {"DOWNLOAD_DELAY": 2}', ['-s', 'DOWNLOAD_DELAY=3'], True),
 ('settings.py =1 + addon =4(addon 优先级 15 < project 20)', 'DOWNLOAD_DELAY = 1\nADDONS = {"proj.addon.DelayAddon": 100}', '', [], True),
 ('只有 addon =4', 'ADDONS = {"proj.addon.DelayAddon": 100}', '', [], True),
 ('-s =3,spider.update_settings 里 set(…, 5, "cmdline")', '', '    @classmethod\n    def update_settings(cls, settings):\n        super().update_settings(settings); settings.set("DOWNLOAD_DELAY", 5, "cmdline")', ['-s', 'DOWNLOAD_DELAY=3'], True),
 ('-s =3,spider.update_settings 里 set(…, 5, 41)', '', '    @classmethod\n    def update_settings(cls, settings):\n        super().update_settings(settings); settings.set("DOWNLOAD_DELAY", 5, 41)', ['-s', 'DOWNLOAD_DELAY=3'], True),
 ('settings.py =1 + 旧写法 spider 属性 download_delay = 2', 'DOWNLOAD_DELAY = 1', '    download_delay = 2', [], True),
]
print(f'  {"设置来源":<68}{"生效值":>8}{"优先级":>8}')
for tag, st, sp, args, strip in CASES:
    d = project('s4b', st, mods={'addon.py': ADDON}, strip=strip)
    write(d, 'proj/spiders/s.py', SPIDER(sp))
    rc, out, t = scrapy(d, 'crawl', 's', '-s', 'LOG_LEVEL=WARNING', '-s', 'TELNETCONSOLE_ENABLED=0', '-s', 'REMOTE_CONTROL_ENABLED=0', *args)
    m = re.search(r"RESULT \{'DOWNLOAD_DELAY': \(([^,]+), (\d+)\)\}", out)
    warn = [l.strip() for l in out.split('\n') if 'Deprecation' in l]
    print(f'  {tag:<64}{(m.group(1) if m else "?"):>8}{(m.group(2) if m else "?"):>8}' + (f'   警告:{warn[0].split("ScrapyDeprecationWarning: ")[-1][:120]}' if warn else ''))

print('== 三:字典型设置(DOWNLOADER_MIDDLEWARES)在不同优先级之间是整个替换还是逐键合并;值写 None 会怎样')
MW = "class A:\n    pass\nclass B:\n    pass\n"
MWS = lambda extra: f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
{extra}
    async def start(self):
        s = self.crawler.settings
        print('RESULT_USER', dict(s.getdict('DOWNLOADER_MIDDLEWARES')))
        print('RESULT_MERGED_HAS', {{k.rsplit('.', 1)[-1]: v for k, v in s.getwithbase('DOWNLOADER_MIDDLEWARES').items() if k.rsplit('.', 1)[-1] in ('A', 'B', 'RetryMiddleware')}})
        return
        yield
"""
for tag, st, sp in (('settings.py 里 {A: 543},spider 里没有', 'DOWNLOADER_MIDDLEWARES = {"proj.mw.A": 543}', ''),
                    ('settings.py 里 {A: 543},custom_settings 里 {B: 544}', 'DOWNLOADER_MIDDLEWARES = {"proj.mw.A": 543}', '    custom_settings = {"DOWNLOADER_MIDDLEWARES": {"proj.mw.B": 544}}'),
                    ('settings.py 里 {A: 543},custom_settings 里 {RetryMiddleware: None}', 'DOWNLOADER_MIDDLEWARES = {"proj.mw.A": 543}', '    custom_settings = {"DOWNLOADER_MIDDLEWARES": {"scrapy.downloadermiddlewares.retry.RetryMiddleware": None}}')):
    d = project('s4c', st, mods={'mw.py': MW})
    write(d, 'proj/spiders/s.py', MWS(sp))
    rc, out, t = scrapy(d, 'crawl', 's', '-s', 'LOG_LEVEL=WARNING', '-s', 'TELNETCONSOLE_ENABLED=0', '-s', 'REMOTE_CONTROL_ENABLED=0')
    print(f'  {tag}')
    for l in out.split('\n'):
        if l.startswith('RESULT'): print('      ' + l.replace('RESULT_USER', '用户层(getdict)   ').replace('RESULT_MERGED_HAS', '与 BASE 合并后(只列 A/B/Retry)'))

print('== 四:命令行 -s 传进来的都是字符串;getbool / getint / getlist / getdict 怎么转换,直接用 settings["X"] 会踩什么坑')
VALS = ['False', '0', '', 'true', '1', 'no']
d = project('s4d')
write(d, 'proj/spiders/s.py', """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        s = self.crawler.settings
        r = s['MYFLAG']
        try: gb = s.getbool('MYFLAG')
        except Exception as e: gb = type(e).__name__ + ': ' + str(e)[:50]
        try: gi = s.getint('MYFLAG')
        except Exception as e: gi = type(e).__name__
        print('RESULT', repr(r), 'truthy=' + str(bool(r)), 'getbool=' + str(gb), 'getint=' + str(gi))
        return
        yield
""")
print(f'  {"-s MYFLAG=…":<14}  settings["MYFLAG"] 原值 / 当 if 用 / getbool / getint')
for v in VALS:
    rc, out, t = scrapy(d, 'crawl', 's', '-s', 'LOG_LEVEL=WARNING', '-s', 'TELNETCONSOLE_ENABLED=0', '-s', 'REMOTE_CONTROL_ENABLED=0', '-s', f'MYFLAG={v}')
    print(f'  {repr(v):<14}  ' + ([l for l in out.split("\n") if l.startswith("RESULT")] or [out[-200:]])[0].replace('RESULT ', ''))
write(d, 'proj/spiders/s.py', """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        s = self.crawler.settings
        print('RESULT getlist', s.getlist('MYLIST'), '| getdict', s.getdict('MYDICT'), '| getfloat', s.getfloat('MYF'), '| getint(\\'12\\')', s.getint('MYI'))
        return
        yield
""")
rc, out, t = scrapy(d, 'crawl', 's', '-s', 'LOG_LEVEL=WARNING', '-s', 'TELNETCONSOLE_ENABLED=0', '-s', 'REMOTE_CONTROL_ENABLED=0', '-s', 'MYLIST=a,b,c', '-s', 'MYDICT={"x": 1, "y": [2]}', '-s', 'MYF=0.5', '-s', 'MYI=12')
print('  -s MYLIST=a,b,c -s \'MYDICT={"x": 1, "y": [2]}\' -s MYF=0.5 -s MYI=12 →')
print('      ' + [l for l in out.split('\n') if l.startswith('RESULT')][0])

print('== 五:设置什么时候冻结:from_crawler 里还能改,start() 里就改不了了')
d = project('s4e')
write(d, 'proj/spiders/s.py', """
import scrapy
class S(scrapy.Spider):
    name = 's'
    @classmethod
    def from_crawler(cls, crawler, *a, **kw):
        print('RESULT from_crawler: frozen =', crawler.settings.frozen, end='; ')
        try: crawler.settings.set('DOWNLOAD_DELAY', 7, 'spider'); print('set 成功,读到', crawler.settings.get('DOWNLOAD_DELAY'))
        except Exception as e: print('set 失败:', type(e).__name__, e)
        return super().from_crawler(crawler, *a, **kw)
    async def start(self):
        s = self.crawler.settings
        print('RESULT start(): frozen =', s.frozen, end='; ')
        try: s.set('DOWNLOAD_DELAY', 9, 'spider'); print('set 成功')
        except Exception as e: print('set 失败:', type(e).__name__, e)
        print('RESULT start() 读到 DOWNLOAD_DELAY =', s.get('DOWNLOAD_DELAY'), '(from_crawler 里设的 7 保留着)')
        return
        yield
""")
rc, out, t = scrapy(d, 'crawl', 's', '-s', 'LOG_LEVEL=WARNING', '-s', 'TELNETCONSOLE_ENABLED=0', '-s', 'REMOTE_CONTROL_ENABLED=0')
for l in out.split('\n'):
    if l.startswith('RESULT'): print('  ' + l.replace('RESULT ', ''))

print('== 六:Scrapy 怎么找到项目设置:scrapy.cfg、子目录、SCRAPY_SETTINGS_MODULE 环境变量(命令:scrapy settings --get BOT_NAME)')
d = project('s4f', 'BOT_NAME = "mybot"')
write(d, 'other_settings.py', 'BOT_NAME = "otherbot"\n')
(d / 'proj' / 'spiders').mkdir(exist_ok=True)
print('  $ cat scrapy.cfg'); print('    ' + '\n    '.join((d / 'scrapy.cfg').read_text().strip().split('\n')))
for tag, cwd, env in (('项目根目录', d, None), ('项目的子目录 proj/spiders/', d / 'proj' / 'spiders', None), ('项目外的空目录', sdir('s4f_empty'), None), ('项目根目录 + SCRAPY_SETTINGS_MODULE=other_settings', d, {'SCRAPY_SETTINGS_MODULE': 'other_settings', 'PYTHONPATH': str(d)})):
    e = dict(os.environ); e.update(env or {}); e.pop('SCRAPY_SETTINGS_MODULE', None) if not env else None
    r = subprocess.run([SPY, '-m', 'scrapy', 'settings', '--get', 'BOT_NAME'], cwd=cwd, capture_output=True, text=True, env=e)
    print(f'  {tag:<46}→ {r.stdout.strip() or r.stderr.strip()[-80:]}')
