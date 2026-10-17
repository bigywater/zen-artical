import sys, os, re, time, html as H; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import lxml.html
tee('p51')
print('== 一:同一个目标"取出所有商品链接的 href 和文字",正则与解析器在 12 种写法略有不同的 HTML 上的结果')
TARGET = ('/p/1', 'One')
CASES = [
 ('标准写法', '<a class="item" href="/p/1">One</a>'),
 ('属性顺序不同', '<a href="/p/1" class="item">One</a>'),
 ('单引号和多余空白', "<a  class='item'   href = '/p/1' >One</a>"),
 ('没有引号的属性', '<a class=item href=/p/1>One</a>'),
 ('大小写混用', '<A CLASS="item" HREF="/p/1">One</A>'),
 ('文字里有嵌套标签', '<a class="item" href="/p/1"><b>On</b>e</a>'),
 ('文字里有换行', '<a class="item" href="/p/1">\n  One\n</a>'),
 ('属性值里有 > 符号', '<a class="item" title="a>b" href="/p/1">One</a>'),
 ('HTML 实体', '<a class="item" href="/p/1?a=1&amp;b=2">One &amp; Two</a>'),
 ('注释里的同样内容', '<!-- <a class="item" href="/p/9">Old</a> --><a class="item" href="/p/1">One</a>'),
 ('<script> 里的字符串', '<script>var s = \'<a class="item" href="/p/9">Fake</a>\';</script><a class="item" href="/p/1">One</a>'),
 ('属性值里有 <a 字样', '<div title="see <a href=/x>"><a class="item" href="/p/1">One</a></div>'),
]
RX = re.compile(r'<a\s+class="item"\s+href="([^"]+)"\s*>(.*?)</a>', re.S)
RX2 = re.compile(r'<a[^>]*href=["\']?([^"\'\s>]+)["\']?[^>]*>(.*?)</a>', re.S | re.I)
def by_regex(rx, h): return [(m.group(1), m.group(2).strip()) for m in rx.finditer(h)]
def by_lxml(h):
    doc = lxml.html.fromstring(f'<html><body>{h}</body></html>'); return [(a.get('href'), a.text_content().strip()) for a in doc.xpath('//a[contains(concat(" ", normalize-space(@class), " "), " item ")]')]
print(f'  正则一(最直接的写法):{RX.pattern}')
print(f'  正则二(更宽松的写法):{RX2.pattern}')
print(f'  {"HTML 写法":<22}{"正则一":>14}{"正则二":>14}{"lxml 解析":>14}   (要取的是 /p/1 和 One;其它结果标出)')
tot = {'rx1': 0, 'rx2': 0, 'lx': 0}
def show(r, expect_text='One'):
    if r == [(TARGET[0], expect_text)]: return '正确'
    return '漏掉' if not r else (str(r)[:22] + '…' if len(str(r)) > 22 else str(r))
for lab, h in CASES:
    want = [('/p/1?a=1&b=2', 'One & Two')] if lab == 'HTML 实体' else [('/p/1', 'One')]
    r1, r2, r3 = by_regex(RX, h), by_regex(RX2, h), by_lxml(h)
    ok = lambda r: r == want
    for k, r in (('rx1', r1), ('rx2', r2), ('lx', r3)): tot[k] += bool(ok(r))
    print(f'  {lab:<18}{("✓" if ok(r1) else "✗" + str(len(r1)) + "条"):>14}{("✓" if ok(r2) else "✗" + str(len(r2)) + "条"):>14}{("✓" if ok(r3) else "✗" + str(len(r3)) + "条"):>14}')
print(f'  正确的写法数(共 {len(CASES)} 种):正则一 {tot["rx1"]},正则二 {tot["rx2"]},lxml {tot["lx"]}')
print('== 二:具体看几个失败的结果')
for lab in ('属性顺序不同', '没有引号的属性', '文字里有嵌套标签', '注释里的同样内容', '<script> 里的字符串', '属性值里有 > 符号', 'HTML 实体'):
    h = dict(CASES)[lab]
    print(f'  {lab}:正则一 → {by_regex(RX, h)};正则二 → {by_regex(RX2, h)};lxml → {by_lxml(h)}')
print('== 三:正则回溯:恶劣输入下耗时爆炸(灾难性回溯)。经典写法 ^(\\w+\\s?)+$,输入是 L 个字母后面跟一个 "!"(整体不匹配,引擎会尝试指数多种切分)')
import subprocess
SNIP = "import re,time,sys\nL=int(sys.argv[1]); s='a'*L+'!'\nrx=re.compile(r'^(\\w+\\s?)+$')\nt0=time.perf_counter(); rx.search(s); print(time.perf_counter()-t0)"
prev = None
for L in (12, 16, 18, 20, 22, 24, 26, 28):
    try:
        o = subprocess.run([sys.executable, '-c', SNIP, str(L)], capture_output=True, text=True, timeout=10)
        el = float(o.stdout); print(f'  L = {L}:匹配失败,耗时 {el * 1000:.1f} ms' + (f'(比上一行 L 小 2 时慢 {el / prev:.1f} 倍)' if prev else '')); prev = el
    except subprocess.TimeoutExpired:
        print(f'  L = {L}:超过 10 秒仍没有结束(被我强制终止)'); break
print('  正则一/二那种不带嵌套量词的写法不会这样,但页面的内容不受你控制,嵌套量词一旦写进去就有这个风险')
print('== 四:同样规模的页面,正则与解析器的速度(5000 个商品链接的页面,各 50 次)')
big = '<html><body>' + ''.join(f'<li><a class="item" href="/p/{i}">Item {i}</a></li>' for i in range(5000)) + '</body></html>'
def per(fn, n=50):
    t0 = time.perf_counter()
    for _ in range(n): fn()
    return (time.perf_counter() - t0) / n * 1000
print(f'  正则一 findall:{per(lambda: RX.findall(big)):.2f} ms;lxml 解析 + xpath:{per(lambda: lxml.html.fromstring(big).xpath("//a/@href")):.2f} ms;只解析不取值:{per(lambda: lxml.html.fromstring(big)):.2f} ms')
print('  结论:速度不是正则的理由——它快得有限,而且在上面 12 种写法里错了好几种')
purge()
