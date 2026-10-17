import sys, os, re, random, collections, urllib.parse as up; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, lxml.html
tee('p40')
rng = random.Random(40)
COLORS = ['red', 'blue', 'green', 'black', 'white', 'gray']; SIZES = ['s', 'm', 'l', 'xl', 'xxl', 'xs']; SORTS = ['price', 'name', 'new', 'rating']; ORDERS = ['asc', 'desc']
def html(links, title=''): return '<html><head><title>%s</title></head><body>%s</body></html>' % (title, ''.join(f'<a href="{l}">x</a>' for l in links))

def site(h):
    u = up.urlsplit(h.path); q = dict(up.parse_qsl(u.query)); p = u.path
    real = None
    if p in ('/', '/index'):
        links = [f'/articles?page={i}' for i in range(1, 11)] + ['/calendar', '/sess/0?sid=' + str(rng.randint(10 ** 5, 10 ** 6)), '/facets', '/loop/']; real = 'home'
    elif p == '/articles':
        pg = int(q.get('page', 1)); links = [f'/article/{(pg - 1) * 20 + k}' for k in range(20)]; real = f'articles-{pg}'
    elif p.startswith('/article/'):
        n = int(p.split('/')[-1]); links = ['/', f'/article/{(n + 1) % 200}']; real = f'article-{n}'
    elif p == '/calendar' or p == '/cal':
        y = int(q.get('y', 2026)); m = int(q.get('m', 10)); py, pm = (y, m - 1) if m > 1 else (y - 1, 12); ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
        links = [f'/cal?y={py}&m={pm}', f'/cal?y={ny}&m={nm}'] + [f'/cal/day?d={y}-{m:02d}-{d:02d}' for d in range(1, 29)]; real = None
    elif p == '/cal/day': links = ['/calendar']; real = None
    elif p.startswith('/sess/'):
        n = int(p.split('/')[-1]); links = [f'/sess/{(n + k) % 20}?sid={rng.randint(10 ** 5, 10 ** 6)}' for k in (1, 2, 3)] + ['/']; real = f'sess-{n}'
    elif p == '/facets':
        links = [f'/facets?color={c}&size={s}&sort={so}&order={o}' for c in COLORS for s in SIZES for so in SORTS for o in ORDERS][:60] if not q else []
        if q:
            def other(k, vals): return [f'/facets?' + up.urlencode({**q, k: v}) for v in vals]
            links = other('color', COLORS) + other('size', SIZES) + other('sort', SORTS) + other('order', ORDERS) + [f'/product/{i}' for i in range(30)]
        real = 'facets' if not q else 'facets-list'
    elif p.startswith('/product/'): links = ['/facets']; real = f'product-{p.split("/")[-1]}'
    elif p.startswith('/loop/'): links = [u.path + 'loop/', '/']; real = 'loop'
    else: return h.reply(404, b'')
    h.reply(200, html(links).encode(), headers={'X-Real-Id': real or ''})

TOTAL_REAL = 1 + 10 + 200 + 20 + 1 + 30 + 1       # 首页 + 10 个列表页 + 200 篇文章 + 20 个会话页 + 筛选首页 + 30 个商品 + loop
# 真实内容页:home, articles-1..10, article-0..199, sess-0..19, facets, product-0..29, loop ;facets-list 是同样 30 个商品的不同排列(算作重复,不计入)

def template(url):
    u = up.urlsplit(url); path = re.sub(r'\d+', '#', u.path)
    q = '&'.join(sorted(k + '=*' for k, _ in up.parse_qsl(u.query)))
    return path + ('?' + q if q else '')
def strip_sid(url):
    u = up.urlsplit(url); q = [(k, v) for k, v in up.parse_qsl(u.query) if k != 'sid']
    return up.urlunsplit((u.scheme, u.netloc, u.path, up.urlencode(q), ''))

def crawl(sv, budget=2000, depth_limit=None, template_cap=None, norm_sid=False, repeat_seg=None, maxlen=None):
    s = requests.Session(); start = sv.url('/'); base = sv.url('')
    seen = {start}; fr = collections.deque([(start, 0)]); fetched = 0; real = set(); per_tpl = collections.Counter(); wasted_traps = collections.Counter(); tpl_skipped = 0
    while fr and fetched < budget:
        u, d = fr.popleft()
        r = s.get(u); fetched += 1
        rid = r.headers.get('X-Real-Id', '')
        path = up.urlsplit(u).path
        kind = 'cal' if path.startswith('/cal') else 'sess' if path.startswith('/sess') else 'facets' if path.startswith('/facets') else 'loop' if path.startswith('/loop') else 'real'
        if rid and not rid.endswith('-list') and rid not in real: real.add(rid)      # 第一次见到的真实内容
        else: wasted_traps[kind] += 1                                                 # 日历页、筛选排列页、或者已经见过的内容又抓了一遍
        if r.status_code != 200: continue
        doc = lxml.html.fromstring(r.content)
        for a in doc.iter('a'):
            v = up.urljoin(u, a.get('href', ''));
            if not v.startswith(base): continue
            if norm_sid: v = strip_sid(v)
            if v in seen: continue
            if depth_limit is not None and d + 1 > depth_limit: continue
            if maxlen and len(v) > maxlen: continue
            if repeat_seg and re.search(r'(/[^/]+)\1{%d,}' % (repeat_seg - 1), up.urlsplit(v).path): continue
            if template_cap:
                t = template(v)
                if per_tpl[t] >= template_cap: tpl_skipped += 1; continue
                per_tpl[t] += 1
            seen.add(v); fr.append((v, d + 1))
    return dict(fetched=fetched, real=len(real), tr=dict(wasted_traps), skipped=tpl_skipped, q=len(fr))

with Srv(site) as sv:
    print(f'== 一:一个故意带陷阱的本机站点:真实内容页共 {TOTAL_REAL} 个(1 首页 + 10 个文章列表 + 200 篇文章 + 20 个会话页 + 筛选首页 + 30 个商品 + 1 个 loop);陷阱:① 日历(上/下一月无限,每月 28 个日期页);② 会话页(同样 20 个页面,链接里每次带不同的随机 sid);③ 筛选列表(颜色 6 × 尺寸 6 × 排序 4 × 方向 2 = 288 种参数组合,都列同样的 30 个商品);④ 相对链接循环(/loop/ → /loop/loop/ → …)')
    print(f'  BFS,最多抓 2000 个页面,各防御措施下找到多少个真实内容页、预算花在了哪类页面上')
    print(f'  {"防御措施":<32}{"抓到的真实页":>12}{"覆盖率":>8}  {"浪费的请求(重复内容或无内容:日历/会话/筛选/循环)":<40}')
    CFG = [('无防御', {}), ('只限制深度 ≤ 6', dict(depth_limit=6)), ('URL 长度 ≤ 80', dict(maxlen=80)), ('检测路径段重复 ≥ 3 次', dict(repeat_seg=3)), ('规范化时去掉 sid 参数', dict(norm_sid=True)),
           ('每个 URL 模板最多 50 个', dict(template_cap=50)), ('去 sid + 路径重复 + 模板上限 50', dict(norm_sid=True, repeat_seg=3, template_cap=50)), ('去 sid + 路径重复 + 模板上限 300', dict(norm_sid=True, repeat_seg=3, template_cap=300))]
    for lab, kw in CFG:
        r = crawl(sv, **kw); tr = r['tr']
        print(f'  {lab:<28}{r["real"]:>9} / {TOTAL_REAL}{r["real"] / TOTAL_REAL * 100:>7.0f}%  日历 {tr.get("cal", 0)}、会话 {tr.get("sess", 0)}、筛选 {tr.get("facets", 0)}、循环 {tr.get("loop", 0)}、其它 {tr.get("real", 0)}(共抓 {r["fetched"]})')
    print('== 二:预算更大时(抓 6000 个页面),还是同样的防御')
    for lab, kw in (CFG[0], CFG[-2], CFG[-1]):
        r = crawl(sv, budget=6000, **kw); print(f'  {lab}:抓 {r["fetched"]} 个页面,找到真实页 {r["real"]} / {TOTAL_REAL};队列里还剩 {r["q"]} 个待抓')
purge()
