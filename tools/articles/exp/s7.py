import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s7'); reset_s()
d = sdir('s7')
HEAD = """
import sys
from scrapy.http import HtmlResponse, TextResponse
TXT = '你好,世界:爬虫的编码'
def show(tag, body, ct=None, **kw):
    h = {'Content-Type': ct} if ct else {}
    r = HtmlResponse('http://x/', body=body, headers=h, **kw)
    ok = '与原文一致' if r.text.count('你好,世界:爬虫的编码') == 1 else (f'含 {r.text.count(chr(0xfffd))} 个替换字符' if chr(0xfffd) in r.text else '与原文不一致(乱码)')
    print(f'  {tag:<46}→ encoding={r.encoding:<10} 解码结果{ok}')
"""

print('== 一:response.encoding 的判断顺序:构造参数 > BOM > HTTP 头的 charset > HTML 里的 <meta> > 自动探测;冲突时谁赢(原文「你好,世界:爬虫的编码」)')
rc, out, t = py(d, HEAD + """
g = TXT.encode('gbk'); u = TXT.encode('utf-8')
M = lambda enc: ('<html><head><meta charset="%s"></head><body>' % enc).encode() + b'%s' + b'</body></html>'
mg = M('gbk') % g; mu = M('utf-8') % u
show('头 charset=gbk,正文 gbk', b'<body>' + g, 'text/html; charset=gbk')
show('没有头,<meta charset=gbk>,正文 gbk', mg, 'text/html')
show('头 charset=utf-8 + <meta charset=gbk>,正文 gbk', mg, 'text/html; charset=utf-8')
show('头 charset=gbk + <meta charset=utf-8>,正文 utf-8', mu, 'text/html; charset=gbk')
show('BOM(utf-8-sig)+ 头 charset=gbk,正文 utf-8', b'\\xef\\xbb\\xbf' + mu, 'text/html; charset=gbk')
show('构造参数 encoding=gbk,头 charset=utf-8,正文 gbk', mg, 'text/html; charset=utf-8', encoding='gbk')
show('没有头、没有 meta,正文 gbk(自动探测)', b'<body>' + g)
show('没有头、没有 meta,正文 utf-8(自动探测)', b'<body>' + u)
""")
print(out)

print('== 二:自动探测(没有头、没有 meta)对 GBK / Big5 / Shift_JIS / EUC-KR 的结果,文本越短越容易判错')
rc, out, t = py(d, HEAD + """
import random
random.seed(7)
from scrapy.http import HtmlResponse
base = {'gbk': '中华人民共和国是一个历史悠久的国家,爬虫工程师每天都要处理各种各样的网页编码问题,这是一段用来测试自动探测的文字。', 'big5': '中華人民共和國是一個歷史悠久的國家,爬蟲工程師每天都要處理各種各樣的網頁編碼問題,這是一段用來測試自動探測的文字。', 'shift_jis': 'スクレイピングは、ウェブページから情報を自動的に取り出す技術です。日本語の文章はエンコーディングの判定が難しいことがあります。', 'euc-kr': '웹 크롤링은 웹 페이지에서 정보를 자동으로 추출하는 기술입니다. 한국어 문장의 인코딩을 판별해 봅니다.'}
print(f'  {"真实编码":<12}' + ''.join(f'{n:>10}' for n in (3, 6, 12, 25, 50)) + '   (格子里是探测出的编码;★ 表示解码结果与原文不一致)')
for enc, s in base.items():
    row = []
    for n in (3, 6, 12, 25, 50):
        txt = s[:n]; r = HtmlResponse('http://x/', body=txt.encode(enc))
        row.append(r.encoding + ('' if r.text == txt else '★'))
    print(f'  {enc:<12}' + ''.join(f'{x:>10}' for x in row))
""")
print(out)

print('== 三:声明的编码不对时:头里写 utf-8 但正文其实是 GBK——不会抛异常,.text 里满是替换字符 \\ufffd;.json() 呢')
rc, out, t = py(d, HEAD + """
import json
g = ('{"名字": "爬虫", "数量": 3}').encode('gbk')
r = TextResponse('http://x/', body=g, headers={'Content-Type': 'text/plain; charset=utf-8'})
print('  text/plain; charset=utf-8,正文 GBK 的 JSON:r.encoding =', r.encoding, ';r.text =', repr(r.text), ';替换字符', r.text.count('\\ufffd'), '个')
try: print('  r.json() =', r.json())
except Exception as e: print('  r.json() 抛', type(e).__name__, str(e)[:60])
r2 = TextResponse('http://x/', body=g, headers={'Content-Type': 'application/json'})
print('  application/json(没有 charset),正文 GBK:r2.encoding =', r2.encoding)
try: print('  r2.json() =', r2.json())
except Exception as e: print('  r2.json() 抛', type(e).__name__, str(e)[:60])
r3 = TextResponse('http://x/', body=g, headers={'Content-Type': 'application/json'}, encoding='gbk')
print('  同上,构造时 encoding=gbk:r3.json() =', r3.json())
""")
print(out)

print('== 四:编码名会被规范化:各种写法的 charset 经 w3lib.resolve_encoding 之后是什么')
rc, out, t = py(d, HEAD + """
for label in ('utf8', 'UTF-8', 'gb2312', 'GBK', 'gb18030', 'latin1', 'iso-8859-1', 'ascii', 'windows-1252', 'shift_jis', 'euc-kr', 'big5', 'x-unknown'):
    r = HtmlResponse('http://x/', body=b'abc', headers={'Content-Type': 'text/html; charset=' + label})
    print(f'  charset={label:<14}→ r.encoding = {r.encoding}')
""")
print(out)

print('== 五:Content-Type 决定响应的类型:只有文本类型才有 .text / .css / .xpath')
rc, out, t = py(d, HEAD + """
from scrapy.responsetypes import responsetypes
for ct in ('text/html', 'text/html; charset=utf-8', 'application/xhtml+xml', 'application/xml', 'text/xml', 'application/json', 'text/plain', 'application/javascript', 'image/png', 'application/octet-stream', 'application/pdf', ''):
    from scrapy.http import Headers
    hd = Headers({'Content-Type': ct} if ct else {})
    cls = responsetypes.from_args(headers=hd, url='http://x/a')
    r = cls('http://x/a', body=b'<a>1</a>', headers=hd)
    try: r.text; t = '有 .text'
    except AttributeError as e: t = '.text 抛 AttributeError: ' + str(e)[:40]
    print(f'  {ct or "(无 Content-Type)":<30}→ {cls.__name__:<14}{t}')
""")
print(out)

print('== 六:真实抓取:服务器分别发 GBK 正文 + 正确的头 / 没有 charset 的头 + meta / 错误地声明 utf-8,spider 里取 <title>')
def srv(h):
    g = '<html><head><meta charset="gbk"><title>爬虫入门</title></head><body>x</body></html>'.encode('gbk')
    g2 = '<html><head><title>爬虫入门</title></head><body>x</body></html>'.encode('gbk')
    if h.path == '/hdr': h.reply(200, g2, {'Content-Type': 'text/html; charset=gbk'})
    elif h.path == '/meta': h.reply(200, g, {'Content-Type': 'text/html'})
    elif h.path == '/wrong': h.reply(200, g, {'Content-Type': 'text/html; charset=utf-8'})
    elif h.path == '/none': h.reply(200, g2, {'Content-Type': 'text/html'})
with Srv(srv) as s:
    rc, out, t = runspider(d, f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        for p in ('hdr', 'meta', 'wrong', 'none'): yield scrapy.Request('{s.url("")}/' + p, dont_filter=True)
    def parse(self, response): EV(p=response.url.rsplit('/', 1)[-1], enc=response.encoding, title=response.css('title::text').get())
""", {'LOG_LEVEL': 'WARNING'})
tags = {'hdr': '头 charset=gbk', 'meta': '头无 charset,<meta charset=gbk>', 'wrong': '头 charset=utf-8(错的),<meta charset=gbk>', 'none': '头无 charset、无 meta(自动探测)'}
for x in sorted(ev(d), key=lambda x: list(tags).index(x['p'])): print(f'  {tags[x["p"]]:<44}→ encoding={x["enc"]:<8} <title> = {x["title"]!r}')
