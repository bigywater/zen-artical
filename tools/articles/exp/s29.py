import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s29'); reset_s()
d = sdir('s29')
def P(title, code):
    print(title)
    rc, out, t = py(d, 'import parsel, lxml.etree, time, statistics\nfrom parsel import Selector\nfrom scrapy.http import HtmlResponse\n' + code)
    print(out)
print('== 一:版本与底层:Selector 是 parsel 的类,解析用 lxml(libxml2);css 先翻译成 xpath 再交给 lxml')
P('', """
import cssselect, w3lib, sys
print(f'  parsel {parsel.__version__} / lxml {lxml.etree.LXML_VERSION} / libxml2 {".".join(map(str, lxml.etree.LIBXML_VERSION))} / cssselect {cssselect.__version__}')
from parsel import css2xpath
for c in ('div.item > a', 'ul li:nth-child(2)', 'a[href^="http"]', 'p::text', 'a::attr(href)', 'li:first-child', 'div#main p.x', 'a:not(.skip)', 'h1 + p', 'input[type=checkbox]:checked'):
    try: x = css2xpath(c)
    except Exception as e: x = f'报错 {type(e).__name__}: {e}'
    print(f'  {c:<30}→ {x}')
""")
print('== 二:同一个文档,css 和 xpath 查询的结果等价吗:::text 只取直接子文本节点,//text() 取所有后代文本,string(.) 把所有后代文本拼起来')
P('', """
html = '<div id=a>head <b>bold</b> tail <i>it</i></div>'
s = Selector(text=html)
print('  div::text            =', s.css('div::text').getall())
print('  div ::text           =', s.css('div ::text').getall())
print('  //div/text()         =', s.xpath('//div/text()').getall())
print('  //div//text()        =', s.xpath('//div//text()').getall())
print('  string(//div)        =', s.xpath('string(//div)').getall())
print('  div *::text          =', s.css('div *::text').getall())
print('  div.get()            =', s.css('div').get())
print('  div::attr(id)        =', s.css('div::attr(id)').get(), ' | @id:', s.xpath('//div/@id').get())
print('  不存在时 .get()       =', s.css('p').get(), '| .get(default="N/A") =', s.css('p').get(default='N/A'), '| .getall() =', s.css('p').getall())
print('  re / re_first        =', s.css('div').re(r'\\b(\\w+) <b>'), s.css('div').re_first(r'<i>(\\w+)</i>'), s.css('p').re_first(r'x', default='nodefault'))
""")
print('== 三:HTML 容错:libxml2 的 HTML 解析器怎么修坏标记;type="xml" 也不严格(recover 模式)')
P('', """
bad = '<p>one<p>two<table><tr><td>a<td>b</table><b><i>x</b></i>&unknown; &amp; <div'
s = Selector(text=bad)
print('  输入:', repr(bad))
print('  lxml 修复后的 HTML:', s.get())
print('  p 的个数:', len(s.css('p')), ';td 的个数:', len(s.css('td')))
try: sx = Selector(text=bad, type='xml'); print('  type="xml" 也不抛错(lxml 用 recover 模式),修复后:', sx.get())
except Exception as e: print('  type="xml" 解析:抛', type(e).__name__, str(e)[:70])
s2 = Selector(text='<a><b>1</b><b>2</b></a>', type='xml')
print('  type="xml" 合法文档:', s2.xpath('//b/text()').getall())
print('  空文档 Selector(text="") 的 root:', Selector(text='').root, ';get():', repr(Selector(text='').get()))
""")
print('== 四:XML 命名空间:默认命名空间下 //link 查不到,要用 remove_namespaces() 或带前缀的 xpath')
P('', """
atom = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A</title><link href="/a"/></entry><entry><title>B</title><link href="/b"/></entry></feed>'
s = Selector(text=atom, type='xml')
print('  //entry                         :', len(s.xpath('//entry')), '个')
print('  //a:entry (namespaces={"a": …}) :', len(s.xpath('//a:entry', namespaces={'a': 'http://www.w3.org/2005/Atom'})), '个')
s.remove_namespaces()
print('  remove_namespaces() 之后 //entry :', len(s.xpath('//entry')), '个;//link/@href =', s.xpath('//link/@href').getall())
""")
print('== 五:构造和查询的开销:约 1 MB 的 HTML(20,000 个 li)——解析一次,以及同一个 Selector 上 css / xpath 的耗时(各 20 次中位数,毫秒)')
P('', """
html = '<html><body><ul>' + ''.join(f'<li class="item"><a href="/p/{i}">item {i}</a></li>' for i in range(20000)) + '</ul></body></html>'
print(f'  文档大小 {len(html):,} 字节')
def med(f, n=20): 
    ts = []
    for _ in range(n): t0 = time.perf_counter(); f(); ts.append((time.perf_counter() - t0) * 1000)
    return statistics.median(ts)
print(f'  Selector(text=html) 解析:{med(lambda: Selector(text=html), 5):.1f} ms')
s = Selector(text=html)
print(f'  s.css("li.item a::attr(href)").getall():{med(lambda: s.css("li.item a::attr(href)").getall()):.1f} ms')
print(f'  s.xpath("//li[@class=\\'item\\']/a/@href").getall():{med(lambda: s.xpath("//li[@class=\\'item\\']/a/@href").getall()):.1f} ms')
print(f'  s.xpath("//a/@href").getall():{med(lambda: s.xpath("//a/@href").getall()):.1f} ms')
print(f'  s.css("li:nth-child(100)").get():{med(lambda: s.css("li:nth-child(100)").get()):.1f} ms')
print(f'  s.css("li")(只构造 Selector 列表,不取值):{med(lambda: s.css("li")):.1f} ms')
print(f'  s.re(r"/p/(\\\\d+)")(对整个文档做正则):{med(lambda: s.re(r"/p/(\\\\d+)"), 5):.1f} ms')
r = HtmlResponse('http://x/', body=html.encode())
print(f'  HtmlResponse.css 第一次(含解析):{med(lambda: HtmlResponse("http://x/", body=html.encode()).css("li").get(), 5):.1f} ms;同一个 response 第二次起:{med(lambda: r.css("li").get()):.2f} ms(response.selector 已缓存)')
""")
