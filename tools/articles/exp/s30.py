import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s30'); reset_s()
d = sdir('s30')
HTML = '''<html><head><base href="http://site.test/docs/"><link href="/style.css" rel="stylesheet"></head><body>
<a href="intro.html">Intro</a>
<a href="/abs/path">Abs</a>
<a href="http://other.test/x">Other site</a>
<a href="intro.html">Intro again</a>
<a href="file.pdf">PDF file</a>
<a href="img.png">PNG</a>
<a href="page?b=2&a=1">query</a>
<a href="page?a=1&b=2">query2</a>
<a href="#frag">fragment only</a>
<a href="mailto:x@y.z">mail</a>
<a href="javascript:void(0)">js</a>
<a href="/nofollow" rel="nofollow">nf</a>
<a href=" /spaces ">with spaces</a>
<a href="/tel" onclick="go('/from-onclick')">onclick</a>
<area href="/area" alt="area">
<iframe src="/frame"></iframe>
<img src="/pic.jpg">
<div id="nav"><a href="/in-nav">in nav</a></div>
<div class="ad"><a href="/ad">ad link</a></div>
<a href="/x"><b>nested</b> text</a>
</body></html>'''
def P(title, code):
    print(title)
    rc, out, t = py(d, 'from scrapy.linkextractors import LinkExtractor, IGNORED_EXTENSIONS\nfrom scrapy.http import HtmlResponse\nHTML = ' + repr(HTML) + '\nr = HtmlResponse("http://site.test/docs/index.html", body=HTML.encode(), encoding="utf-8")\ndef show(tag, links):\n    print(f"  {tag}:{len(links)} 个")\n    for l in links: print(f"      {l.url:<40}text={l.text!r:<22}nofollow={l.nofollow}")\n' + code)
    print(out)
P('== 一:默认 LinkExtractor().extract_links(response):基准 URL 来自 <base href>;重复的去掉;pdf / png 被扩展名过滤;mailto、javascript 被丢弃;只看 <a> 和 <area> 的 href', """
show('默认', LinkExtractor().extract_links(r))
print('  没有出现在结果里的 href/src:img src=/pic.jpg、iframe src=/frame、link href=/style.css(tags 默认只有 a、area)')
""")
P('== 二:allow / deny(正则,匹配完整的绝对 URL)和 allow_domains / deny_domains', """
show('allow=r"/abs|/nofollow"', LinkExtractor(allow=r'/abs|/nofollow').extract_links(r))
show('deny=r"/(abs|ad|x)$"', LinkExtractor(deny=r'/(abs|ad|x)$').extract_links(r))
show('allow_domains="other.test"', LinkExtractor(allow_domains='other.test').extract_links(r))
show('deny_domains="other.test"(其余照常)', [l for l in LinkExtractor(deny_domains='other.test').extract_links(r)][:3] + [])
print('  deny_domains="other.test" 时总数:', len(LinkExtractor(deny_domains='other.test').extract_links(r)), '(默认是', len(LinkExtractor().extract_links(r)), ')')
""")
P('== 三:限定提取的区域和标签:restrict_css、restrict_xpaths、restrict_text、tags / attrs / deny_tags', """
show('restrict_css="#nav"', LinkExtractor(restrict_css='#nav').extract_links(r))
show('restrict_xpaths="//div[@class=\\'ad\\']"', LinkExtractor(restrict_xpaths="//div[@class='ad']").extract_links(r))
show('restrict_text=r"^nested|^Intro$"', LinkExtractor(restrict_text=r'^nested|^Intro$').extract_links(r))
show('tags=("a","area","iframe","link"), attrs=("href","src")(只看新增的几个)', [l for l in LinkExtractor(tags=('a', 'area', 'iframe', 'link'), attrs=('href', 'src')).extract_links(r) if l.url.endswith(('/frame', '.css', '/area'))])
show('tags="*", attrs="*"(所有标签所有属性)', [l for l in LinkExtractor(tags='*', attrs='*').extract_links(r) if l.url.endswith(('/pic.jpg', '/frame'))])
print('  tags="*", attrs="*" 总数:', len(LinkExtractor(tags='*', attrs='*').extract_links(r)))
show('tags="*", attrs="src", deny_extensions=[]', LinkExtractor(tags='*', attrs='src', deny_extensions=[]).extract_links(r))
show('tags="*", deny_tags="iframe", attrs="src", deny_extensions=[]', LinkExtractor(tags='*', deny_tags='iframe', attrs='src', deny_extensions=[]).extract_links(r))
""")
P('== 四:unique、canonicalize、process_value', """
print('  unique=True(默认):', len(LinkExtractor().extract_links(r)), '个;unique=False:', len(LinkExtractor(unique=False).extract_links(r)), '个')
show('query 两个链接(page?b=2&a=1 / page?a=1&b=2)默认 unique', [l for l in LinkExtractor().extract_links(r) if 'page' in l.url])
show('canonicalize=True', [l for l in LinkExtractor(canonicalize=True).extract_links(r) if 'page' in l.url])
import re
def pv(value):
    m = re.search(r"go\\('(.*?)'\\)", value)
    return m.group(1) if m else value
show('process_value 用于 attrs=("onclick",)', LinkExtractor(attrs=('onclick',), process_value=pv).extract_links(r))
""")
P('== 五:deny_extensions:默认 IGNORED_EXTENSIONS;传 [] 就都放行;只想过滤某几个扩展名', """
print('  IGNORED_EXTENSIONS 一共', len(IGNORED_EXTENSIONS), '个,前 12 个:', IGNORED_EXTENSIONS[:12])
show('deny_extensions=[](pdf、png 通过)', [l for l in LinkExtractor(deny_extensions=[]).extract_links(r) if l.url.endswith(('.pdf', '.png'))])
show('deny_extensions=["pdf"](只过滤 pdf)', [l for l in LinkExtractor(deny_extensions=['pdf']).extract_links(r) if l.url.endswith(('.pdf', '.png'))])
""")
P('== 六:rel="nofollow"、片段(#frag)和 <area>:提取器只记录,不过滤 nofollow;只有 # 的链接', """
ls = LinkExtractor().extract_links(r)
print('  /nofollow 的 nofollow =', [l.nofollow for l in ls if l.url.endswith('/nofollow')], '(链接仍被提取)')
print('  href="#frag" 的链接是否被提取:', any('frag' in l.url for l in ls), '| href 以 mailto: 开头:', any('mailto' in l.url for l in ls), '| javascript::', any('javascript' in l.url for l in ls))
print('  <area href="/area"> 是否被提取:', any(l.url.endswith('/area') for l in ls))
print('  嵌套文本 <a><b>nested</b> text</a> 的 text =', [l.text for l in ls if l.url == 'http://site.test/x'])
print('  Link 对象的字段:', ls[0].__dict__.keys() if hasattr(ls[0], '__dict__') else ls[0].__slots__)
""")
