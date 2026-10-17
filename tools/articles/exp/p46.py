import sys, os, re, subprocess, importlib.metadata as md; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p46')
d = pdir('p46')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--target', str(d / 'site'), 'cssselect'], capture_output=True, env={k: v for k, v in os.environ.items() if 'proxy' not in k.lower()})
sys.path.insert(0, str(d / 'site'))
import lxml.html, lxml.etree as ET, cssselect
from lxml.cssselect import CSSSelector
HTML = '''<html><body>
<div id="main" class="box wide">
  <h1 class="title">Shop</h1>
  <ul class="items">
    <li class="item sale" data-id="1"><a href="/p/1" class="link">One</a><span class="price">¥10</span></li>
    <li class="item" data-id="2"><a href="/p/2" class="link external">Two</a><span class="price">¥20</span></li>
    <li class="item sale hot" data-id="3"><a href="/p/3">Three</a><span class="price">¥30</span></li>
    <li class="itemized" data-id="4"><a href="https://other.test/x" class="link">Four</a><span class="price">¥40</span></li>
  </ul>
  <p class="note">Free shipping over ¥100</p>
  <p class="note small">Returns in 7 days</p>
</div>
<div class="box"><ul><li><a href="/q/1">q1</a></li><li><a href="/q/2">q2</a></li></ul></div>
</body></html>'''
doc = lxml.html.fromstring(HTML)
def cs(sel): return doc.cssselect(sel)
def xp(x): return doc.xpath(x)
def txt(els): return [e if isinstance(e, str) else (e.text_content().strip() or e.get('href') or '') for e in els]

print(f'== 一:同一个页面上的 16 个选取任务:CSS 选择器与 XPath 各怎么写(lxml {md.version("lxml")},cssselect {md.version("cssselect")}),结果条数是否一致')
TASKS = [
 ('所有商品 li', 'li.item', '//li[contains(concat(" ", normalize-space(@class), " "), " item ")]'),
 ('同时有 item 和 sale 两个 class', 'li.item.sale', '//li[contains(concat(" ", normalize-space(@class), " "), " item ") and contains(concat(" ", normalize-space(@class), " "), " sale ")]'),
 ('data-id 为 2 的 li', 'li[data-id="2"]', '//li[@data-id="2"]'),
 ('href 以 /p/ 开头的链接', 'a[href^="/p/"]', '//a[starts-with(@href, "/p/")]'),
 ('href 含 other.test 的链接', 'a[href*="other.test"]', '//a[contains(@href, "other.test")]'),
 ('li 的直接子元素 a', 'li > a', '//li/a'),
 ('a 的下一个兄弟 span', 'a + span', '//a/following-sibling::*[1][self::span]'),
 ('每个 ul 的第 2 个 li', 'ul > li:nth-child(2)', '//ul/li[2]'),
 ('不含 sale 的商品', 'li.item:not(.sale)', '//li[contains(concat(" ", normalize-space(@class), " "), " item ") and not(contains(concat(" ", normalize-space(@class), " "), " sale "))]'),
 ('价格文字(span.price 的文本)', 'span.price', '//span[@class="price"]/text()'),
 ('链接的 href 属性值', 'a[href]', '//a/@href'),
 ('文字是 "Two" 的链接', None, '//a[text()="Two"]'),
 ('包含 a 的 li 的父元素 ul', None, '//li[a]/parent::ul'),
 ('有 sale 商品的 div(向上找祖先)', None, '//li[contains(concat(" ", @class, " "), " sale ")]/ancestor::div[1]'),
 ('最后一个 li', 'li:last-child', '//li[last()]'),
 ('两种元素的并集 h1 和 p.note', 'h1, p.note', '//h1 | //p[contains(concat(" ", @class, " "), " note ")]'),
]
print(f'  {"任务":<28}{"CSS":<24}{"XPath":<8}{"结果条数 CSS / XPath"}')
for lab, c, x in TASKS:
    nc = len(cs(c)) if c else None; nx = len(xp(x))
    print(f'  {lab:<24}{(c or "(CSS 表达不了)")[:22]:<24}{"✓":<8}{(nc if nc is not None else "—")} / {nx}' + ('' if nc is None or nc == nx else '   ← 条数不同(CSS 选的是元素,XPath 选到了文本或属性节点)' if x.endswith(('text()', '/@href')) else '   ← 不一致!'))
print(f'  CSS 能表达的 {sum(1 for _, c, _ in TASKS if c)} 个任务,CSS 表达不了的 {sum(1 for _, c, _ in TASKS if not c)} 个(按文字内容选、选父元素、选祖先)')

print('== 二:class 匹配陷阱(页面里 class 有 "item"、"item sale"、"itemized" 等)')
print(f'  CSS li.item                                      → {len(cs("li.item"))} 个(按空白分隔的"词"匹配,itemized 不算)')
print(f'  XPath //li[@class="item"]                         → {len(xp("//li[@class=\"item\"]"))} 个(整个属性值必须恰好等于 item,漏掉 "item sale")')
print(f'  XPath //li[contains(@class, "item")]              → {len(xp("//li[contains(@class, \"item\")]"))} 个(子串匹配,把 "itemized" 也选进来了)')
print(f'  XPath //li[contains(concat(" ", normalize-space(@class), " "), " item ")] → {len(xp("//li[contains(concat(\" \", normalize-space(@class), \" \"), \" item \")]"))} 个(和 CSS 一致,但写起来很长)')

print('== 三:位置的陷阱:XPath 的 //a[1] 与 (//a)[1];CSS 的 a:nth-of-type(1)')
print(f'  //a[1]    → {len(xp("//a[1]"))} 个(每个父元素下的第一个 a)')
print(f'  (//a)[1]  → {len(xp("(//a)[1]"))} 个(整个文档的第一个 a)')
print(f'  CSS a:nth-of-type(1) → {len(cs("a:nth-of-type(1)"))} 个(和 //a[1] 一样,每个父元素下的第一个 a)')
print(f'  XPath 的下标从 1 开始://li[1] 选出 {txt(xp("(//li[1])"))[:1]},//li[0] → {len(xp("//li[0]"))} 个')

print('== 四:cssselect 把 CSS 翻译成什么 XPath(lxml 内部就是这样做的)')
for sel in ('li.item', 'li.item.sale', 'a[href^="/p/"]', 'ul > li:nth-child(2)', 'li.item:not(.sale)', 'a + span', 'p.note'):
    print(f'  {sel:<22}→ {cssselect.HTMLTranslator().css_to_xpath(sel)}')

print('== 五:耗时(页面放大到 5000 个 li;每项重复若干次取平均)')
big = lxml.html.fromstring('<html><body><ul>' + ''.join(f'<li class="item{" sale" if i % 5 == 0 else ""}" data-id="{i}"><a href="/p/{i}" class="link">T{i}</a><span class="price">¥{i}</span></li>' for i in range(5000)) + '</ul></body></html>')
def per(fn, n):
    t0 = time.perf_counter()
    for _ in range(n): fn()
    return ms(t0) / n
XP_STR = '//li[contains(concat(" ", normalize-space(@class), " "), " sale ")]/a/@href'
XP_OBJ = ET.XPath(XP_STR); CSS_STR = 'li.sale > a'; CSS_OBJ = CSSSelector(CSS_STR); XP_SIMPLE = ET.XPath('//li[@data-id="2500"]'); CSS_SIMPLE = CSSSelector('li[data-id="2500"]')
assert len(XP_OBJ(big)) == 1000 and len(CSS_OBJ(big)) == 1000
rows = [('XPath 字符串 tree.xpath(…)(每次调用)', lambda: big.xpath(XP_STR)), ('XPath 预编译对象 etree.XPath(…)', lambda: XP_OBJ(big)), ('CSS 字符串 tree.cssselect(…)(每次调用)', lambda: big.cssselect(CSS_STR)), ('CSS 预编译对象 CSSSelector(…)', lambda: CSS_OBJ(big)),
        ('XPath 精确匹配一个属性(预编译)', lambda: XP_SIMPLE(big)), ('CSS 精确匹配一个属性(预编译)', lambda: CSS_SIMPLE(big))]
print(f'  {"方式":<40}{"每次耗时":>10}')
for lab, fn in rows: print(f'  {lab:<36}{per(fn, 100):>8.2f} ms')
print(f'  编译一个 CSSSelector 对象的耗时:{per(lambda: CSSSelector("li.sale > a"), 2000) * 1000:.0f} 微秒;编译一个 etree.XPath 对象:{per(lambda: ET.XPath(XP_STR), 2000) * 1000:.0f} 微秒')
purge()
