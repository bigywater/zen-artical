import sys, os, re, json, time, statistics, urllib.parse as up, urllib.robotparser, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
from pcdp import Chrome
import requests, lxml.html
tee('p69')
d = pdir('p69')
CSS = """.hid-ext{display:none} .sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap} body{background:#fff;color:#000}"""
JS = """document.addEventListener('DOMContentLoaded', () => { document.getElementById('jshide').style.display = 'none';
  setTimeout(() => { const a = document.createElement('a'); a.href = '/t/js_created'; a.textContent = 'js created'; document.body.appendChild(a); }, 300); });"""
TECH = [  # (名字, HTML 片段, 人眼能看到?)
    ('visible', '<a href="/t/visible">visible</a>', True),
    ('aria_hidden', '<a href="/t/aria_hidden" aria-hidden="true" tabindex="-1">aria-hidden 但看得见</a>', True),
    ('display_none', '<a href="/t/display_none" style="display:none">x</a>', False),
    ('visibility_hidden', '<a href="/t/visibility_hidden" style="visibility:hidden">x</a>', False),
    ('opacity_0', '<a href="/t/opacity_0" style="opacity:0">x</a>', False),
    ('hidden_attr', '<a href="/t/hidden_attr" hidden>x</a>', False),
    ('zero_size', '<a href="/t/zero_size" style="display:inline-block;width:0;height:0;overflow:hidden">x</a>', False),
    ('offscreen', '<a href="/t/offscreen" style="position:absolute;left:-9999px">x</a>', False),
    ('font_size_0', '<a href="/t/font_size_0" style="font-size:0">x</a>', False),
    ('text_same_color', '<a href="/t/text_same_color" style="color:#fff;background:#fff">x</a>', False),
    ('parent_hidden', '<div style="display:none"><a href="/t/parent_hidden">x</a></div>', False),
    ('ext_css_class', '<a href="/t/ext_css_class" class="hid-ext">x</a>', False),
    ('js_hidden', '<a id="jshide" href="/t/js_hidden">js 加载后隐藏</a>', False),
    ('js_created', '(页面脚本 0.3 秒后才创建这个链接)', True),
    ('noscript', '<noscript><a href="/t/noscript">noscript 里的链接</a></noscript>', False),
    ('html_comment', '<!-- <a href="/t/html_comment">x</a> -->', False),
    ('skip_link(无障碍,屏幕外)', '<a href="/t/skip_link" class="sr-only">跳到正文</a>', False),
]
PAGE = '<!doctype html><html><head><link rel="stylesheet" href="/s.css"><script src="/s.js"></script></head><body><p>正文</p>' + ''.join(f'<div>{h}</div>' for _, h, _ in TECH) + '</body></html>'
site_pages = {}
def srv(h):
    u = up.urlsplit(h.path); p = u.path
    if p == '/': return h.reply(200, PAGE.encode(), headers={'Content-Type': 'text/html; charset=utf-8'})
    if p == '/s.css': return h.reply(200, CSS.encode(), headers={'Content-Type': 'text/css'})
    if p == '/s.js': return h.reply(200, JS.encode(), headers={'Content-Type': 'application/javascript'})
    if p == '/robots.txt': return h.reply(200, b'User-agent: *\nDisallow: /trap/\n', headers={'Content-Type': 'text/plain'})
    m = re.match(r'/p/(\d+)$', p)
    if m:
        i = int(m.group(1)); real = ''.join(f'<li><a href="/p/{(i * 7 + k) % 60}">页面 {(i * 7 + k) % 60}</a></li>' for k in range(1, 9))
        trap = f'<a href="/trap/{i}" style="display:none">more</a>'
        return h.reply(200, f'<!doctype html><html><body><ul>{real}</ul>{trap}</body></html>'.encode(), headers={'Content-Type': 'text/html; charset=utf-8'})
    h.reply(200, b'ok')
INLINE_HIDE = re.compile(r'display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?![.\d])|font-size\s*:\s*0(?![.\d])|(?:^|;)\s*(?:width|height)\s*:\s*0(?![.\d])|left\s*:\s*-\d{3,}px', re.I)
def static_visible(a):
    for el in a.iterancestors():
        if el.get('hidden') is not None or INLINE_HIDE.search(el.get('style') or ''): return False
    return a.get('hidden') is None and not INLINE_HIDE.search(a.get('style') or '')
with Srv(srv) as sv, Chrome(free_port(9970), d) as ch:
    B = sv.url('')
    doc = lxml.html.fromstring(requests.get(B + '/').text)
    d1 = {a.get('href').split('/')[-1] for a in doc.xpath('//a[@href]')}
    d2 = {a.get('href').split('/')[-1] for a in doc.xpath('//a[@href]') if static_visible(a)}
    pg = ch.new_page(); pg.goto(B + '/'); pg.drain(0.8)
    links = pg.eval("""JSON.stringify([...document.querySelectorAll('a[href]')].map(a => { const r = a.getBoundingClientRect(); return {href: a.getAttribute('href'), vis: a.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}), w: r.width, h: r.height, right: r.right, bottom: r.bottom}; }))""")
    links = json.loads(links); pg.close()
    d3 = {l['href'].split('/')[-1] for l in links if l['vis'] and l['w'] > 1 and l['h'] > 1 and l['right'] > 0 and l['bottom'] > 0}
    d3_all = {l['href'].split('/')[-1] for l in links}
    print('== 一:17 种写法的链接,三种"挑链接"的办法各会跟进哪些(✓ = 会跟进)。A=lxml 解析静态 HTML 取全部 a[href];B=A 加上对内联 style 和 hidden 属性的正则过滤;C=Chrome 加载后用 checkVisibility + 位置尺寸判断')
    print(f'  {"写法":24s} {"人眼能看到":8s} {"A":3s} {"B":3s} {"C":3s}')
    for name, html, human in TECH:
        key = name.split('(')[0]
        mark = lambda s: '✓' if key in s else '-'
        print(f'  {name:24s} {"能" if human else "不能":8s} {mark(d1):3s} {mark(d2):3s} {mark(d3):3s}')
    print('== 二:汇总——三种办法"跟进了人眼看不到的链接"几个、"漏掉了人眼看得到的链接"几个')
    hidden = {n.split('(')[0] for n, _, hu in TECH if not hu and n != 'html_comment'}; shown = {n.split('(')[0] for n, _, hu in TECH if hu}
    for lab, s in (('A 静态全取', d1), ('B 静态 + 内联过滤', d2), ('C Chrome 可见性', d3)):
        print(f'  {lab}:跟进了 {len(s & hidden)}/{len(hidden)} 个人眼看不到的链接 {sorted(s & hidden)};漏掉 {len(shown - s)}/{len(shown)} 个人眼看得到的链接 {sorted(shown - s)}')
    print(f'  静态 HTML 里一共有 {len(d1)} 个 a[href]({"含" if "js_created" in d1 else "不含"}脚本创建的 js_created,{"含" if "noscript" in d1 else "不含"} noscript 里的链接);Chrome 里一共 {len(d3_all)} 个(含 js_created:{"js_created" in d3_all},含 noscript 里的:{"noscript" in d3_all})')
    print('== 三:robots.txt 里写了 Disallow: /trap/;一个页面的 8 个正常链接加 1 个指向 /trap/ 的隐藏链接(/p/0)')
    rp = urllib.robotparser.RobotFileParser(); rp.parse(requests.get(B + '/robots.txt').text.splitlines())
    doc = lxml.html.fromstring(requests.get(B + '/p/0').text); doc.make_links_absolute(B + '/p/0'); urls = [a.get('href') for a in doc.xpath('//a[@href]')]
    print(f'  页面里共 {len(urls)} 个链接,其中 /trap/ 开头的 {sum(1 for u in urls if "/trap/" in u)} 个;robotparser.can_fetch 允许 {sum(1 for u in urls if rp.can_fetch("MyCrawler", u))} 个、禁止 {sum(1 for u in urls if not rp.can_fetch("MyCrawler", u))} 个(被禁止的就是 /trap/ 那一个)')
    print('== 四:一个 60 页的合成站点(每页 8 个指向其他页面的真链接 + 1 个 display:none 的 /trap/<页号> 链接),三种爬虫从 /p/0 出发各爬一遍')
    def crawl(kind):
        sv.reset(); seen = {'/p/0'}; q = ['/p/0']; t_pages = {}; s = requests.Session(); pg = ch.new_page() if kind == 'C' else None; t0 = time.time()
        while q:
            path = q.pop(0)
            if kind == 'C':
                pg.goto(B + path); pg.drain(0.05); ls = json.loads(pg.eval("""JSON.stringify([...document.querySelectorAll('a[href]')].filter(a => { const r = a.getBoundingClientRect(); return a.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}) && r.width > 1 && r.height > 1; }).map(a => a.getAttribute('href')))"""))
            else:
                if kind == 'B' and not rp.can_fetch('MyCrawler', B + path): continue
                doc = lxml.html.fromstring(s.get(B + path).text); ls = [a.get('href') for a in doc.xpath('//a[@href]')]
            for href in ls:
                if kind == 'B' and not rp.can_fetch('MyCrawler', B + href): continue
                if href not in seen: seen.add(href); q.append(href)
        if pg: pg.close()
        paths = [l['path'] for l in sv.log]; return len([p for p in paths if p.startswith('/p/')]), len([p for p in paths if p.startswith('/trap/')]), time.time() - t0
    for kind, lab in (('A', 'A 取全部 a[href],不看 robots.txt'), ('B', 'B 取全部 a[href],遵守 robots.txt'), ('C', 'C 用 Chrome,只跟进可见的链接')):
        pages, traps, el = crawl(kind); print(f'  {lab}:请求了 {pages} 个真页面(站点共 60 个),{traps} 个 /trap/ 页面;用时 {el:.1f} 秒')
    print('== 五:站长在访问日志里看到的陷阱请求(爬虫 A):这个请求与它所在的页面相隔多久、带不带 Referer')
    sv.reset(); s = requests.Session(); gaps = []; refs = collections.Counter()
    for i in range(20):
        t_page = time.time(); doc = lxml.html.fromstring(s.get(B + f'/p/{i}').text); t_after = time.time()
        for a in doc.xpath('//a[@href]'):
            if '/trap/' in a.get('href'): t = time.time(); s.get(B + a.get('href')); gaps.append((time.time() - t_after) * 1000)
    for l in sv.log:
        if l['path'].startswith('/trap/'): refs[dict((k.lower(), v) for k, v in l['hdrs']).get('referer', '(没有)')] += 1
    print(f'  取到页面之后 {statistics.median(gaps):.1f} ms(中位,共 {len(gaps)} 次)就请求了陷阱链接;陷阱请求的 Referer:{dict(refs)};UA:{dict(collections.Counter(dict((k.lower(), v) for k, v in l["hdrs"]).get("user-agent") for l in sv.log if l["path"].startswith("/trap/")))}')
purge()
