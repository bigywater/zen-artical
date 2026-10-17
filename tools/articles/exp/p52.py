import sys, os, re, random, statistics, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import lxml.html
tee('p52')
rng = random.Random(52)
NAMES = ['Phone', 'Laptop', 'Tablet', 'Camera', 'Watch', 'Speaker', 'Monitor', 'Mouse', 'Keyboard', 'Router']

def price_text(p, fmt):
    if fmt == 'yuan': return f'¥{p:,.2f}'
    if fmt == 'cn': return f'{p:,.0f}元'
    if fmt == 'cents': return str(int(p * 100))
    return f'¥{p:.2f}'

def render(version, n, seed):
    r = random.Random(seed); rows = []; page_new = (version == 'v6 灰度' and random.Random(seed * 7 + 1).random() < 0.3)      # 灰度:按页面决定是否用新版
    for i in range(n):
        name = f'{r.choice(NAMES)} {r.randint(100, 999)}'; price = round(r.uniform(20, 3000), 2); rating = r.randint(1, 5)
        use_new = page_new
        if version in ('v0 基线', 'v1 良性变化', 'v6 灰度') and not use_new:
            rows.append(f'<li class="item"><h3>{name}</h3><span class="price">{price_text(price, "yuan")}</span><span class="rating" data-r="{rating}"></span></li>')
        elif version == 'v2 价格类名改了' or use_new:
            rows.append(f'<li class="item"><h3>{name}</h3><span class="prc">{price_text(price, "yuan")}</span><span class="rating" data-r="{rating}"></span></li>')
        elif version == 'v3 外层容器和类名变了':
            rows.append(f'<li class="item card"><h3>{name}</h3><span class="price">{price_text(price, "yuan")}</span><span class="rating" data-r="{rating}"></span></li>')
        elif version == 'v4 价格格式变了':
            rows.append(f'<li class="item"><h3>{name}</h3><span class="price">{price_text(price, "cn")}</span><span class="rating" data-r="{rating}"></span></li>')
        elif version == 'v5 价格单位变成分':
            rows.append(f'<li class="item"><h3>{name}</h3><span class="price">{price_text(price, "cents")}</span><span class="rating" data-r="{rating}"></span></li>')
        elif version == 'v7 名称移进了链接':
            rows.append(f'<li class="item"><h3><a href="/p/{i}">{name}</a></h3><span class="price">{price_text(price, "yuan")}</span><span class="rating" data-r="{rating}"></span></li>')
    extra = ''
    if version == 'v1 良性变化': extra = '<div class="ad">Sponsored</div>' * 3 + '<p class="note">  New season  </p>'
    wrap = '<div class="grid"><ul>' + ''.join(rows) + '</ul></div>' if version == 'v3 外层容器和类名变了' else '<ul>' + ''.join(rows) + '</ul>'
    return f'<html><head><title>List</title></head><body><header><nav><a href="/">Home</a></nav></header>{extra}<main>{wrap}</main><footer>© shop</footer></body></html>'

def extract(html):
    doc = lxml.html.fromstring(html); out = []
    for li in doc.xpath('//li[@class="item"]'):
        name = (li.xpath('./h3/text()') or [None])[0]; pt = (li.xpath('./span[@class="price"]/text()') or [None])[0]; rt = (li.xpath('./span[@class="rating"]/@data-r') or [None])[0]
        price = None
        if pt and re.search(r'\d', pt):
            price = float(re.sub(r'[^\d.]', '', pt))                    # 宽松解析:去掉所有非数字、非小数点的字符
        out.append(dict(name=name, price=price, rating=int(rt) if rt else None))
    return out

def structure(html):
    """页面结构指纹:所有 标签.类名 的集合(不含文字和数量)"""
    doc = lxml.html.fromstring(html); return {f'{e.tag}.{e.get("class") or ""}' for e in doc.iter() if isinstance(e.tag, str)}
def jaccard(a, b): return len(a & b) / len(a | b)

VERS = ['v0 基线', 'v1 良性变化', 'v2 价格类名改了', 'v3 外层容器和类名变了', 'v4 价格格式变了', 'v5 价格单位变成分', 'v6 灰度', 'v7 名称移进了链接']
base_pages = [render('v0 基线', 30, s) for s in range(20)]
bs = set.union(*[structure(p) for p in base_pages]); b_items = statistics.mean(len(extract(p)) for p in base_pages)
b_prices = [x['price'] for p in base_pages for x in extract(p) if x['price'] is not None]; b_med = statistics.median(b_prices)
def metrics(version):
    pages = [render(version, rng.randint(15, 40) if version == 'v1 良性变化' else 30, 100 + s) for s in range(20)]
    exc = 0; items = []; nulls = collections.Counter(); tot = 0; prices = []; sims = []
    for p in pages:
        try: r = extract(p)
        except Exception: exc += 1; continue
        items.append(len(r)); tot += len(r)
        for x in r:
            for k in ('name', 'price', 'rating'):
                if x[k] is None: nulls[k] += 1
            if x['price'] is not None: prices.append(x['price'])
        sims.append(jaccard(structure(p), bs))
    return dict(exc=exc, items=statistics.mean(items) if items else 0, null={k: nulls[k] / tot if tot else 1.0 for k in ('name', 'price', 'rating')}, med=statistics.median(prices) if prices else None, sim=statistics.mean(sims) if sims else 0, n=len(pages), empty_pages=sum(1 for i in items if i == 0), pages_total=len(pages))

print(f'== 一:同一个提取器(针对 v0 基线写的 XPath),对 8 个版本的页面各抓 20 页:提取结果的统计(基线:平均每页 {b_items:.0f} 个商品,价格中位数 {b_med:.0f})')
print(f'  {"版本":<24}{"异常":>5}{"每页商品数":>10}{"名称空":>8}{"价格空":>8}{"评分空":>8}{"价格中位数":>10}{"结构相似度":>10}')
M = {}
for v in VERS:
    m = metrics(v); M[v] = m
    print(f'  {v:<20}{m["exc"]:>5}{m["items"]:>10.1f}{m["null"]["name"] * 100:>7.0f}%{m["null"]["price"] * 100:>7.0f}%{m["null"]["rating"] * 100:>7.0f}%{(f'{m["med"]:.0f}' if m["med"] is not None else '—'):>10}{m["sim"]:>10.2f}')

print('== 二:几种检查各自会不会报警(阈值:商品数低于基线 50%、任一字段空值率超过 10%、价格中位数偏离基线 3 倍以上、结构相似度低于 0.9)')
CHK = [('只看有没有抛异常', lambda m: m['exc'] > 0), ('商品数是否骤降', lambda m: m['items'] < 0.5 * b_items), ('字段空值率是否超过 10%', lambda m: max(m['null'].values()) > 0.10),
       ('价格中位数是否偏离基线 3 倍', lambda m: m['med'] is None or not (b_med / 3 <= m['med'] <= b_med * 3)), ('页面结构相似度是否低于 0.9', lambda m: m['sim'] < 0.9)]
print(f'  {"版本":<24}' + ''.join(f'{n[:9]:>13}' for n, _ in CHK) + '   实际是否真的坏了')
TRUTH = {'v0 基线': '好', 'v1 良性变化': '好', 'v2 价格类名改了': '坏', 'v3 外层容器和类名变了': '坏', 'v4 价格格式变了': '好(宽松解析照样取对)', 'v5 价格单位变成分': '坏(价格 ×100)', 'v6 灰度': '部分页面坏', 'v7 名称移进了链接': '坏'}
for v in VERS: print(f'  {v:<20}' + ''.join(f'{"报警" if f(M[v]) else "·":>13}' for _, f in CHK) + f'   {TRUTH[v]}')
print('  检查项依次为:' + ';'.join(n for n, _ in CHK))
print('== 三:每种检查在 8 个版本上的表现(报警且确实坏了 = 命中;报警但其实没坏 = 误报;没报警但确实坏了 = 漏报)')
bad = {v for v, t in TRUTH.items() if not t.startswith('好')}
for n, f in CHK:
    hit = sum(1 for v in VERS if f(M[v]) and v in bad); fp = sum(1 for v in VERS if f(M[v]) and v not in bad); miss = sum(1 for v in VERS if not f(M[v]) and v in bad)
    print(f'  {n}:命中 {hit} / {len(bad)},误报 {fp},漏报 {miss}')
combo = lambda m: any(f(m) for _, f in CHK[1:])
print(f'  组合(后四项任一报警):命中 {sum(1 for v in VERS if combo(M[v]) and v in bad)} / {len(bad)},误报 {sum(1 for v in VERS if combo(M[v]) and v not in bad)},漏报 {sum(1 for v in VERS if not combo(M[v]) and v in bad)}')
print('== 四:灰度发布(30% 的页面用了新版)只看总体平均会被稀释:按页面逐个看')
r = random.Random(7); pages = [render('v6 灰度', 30, 300 + s) for s in range(40)]
rates = [sum(1 for x in extract(p) if x['price'] is None) / max(1, len(extract(p))) for p in pages]
print(f'  40 个页面里,价格提取失败比例的分布:最小 {min(rates) * 100:.0f}%、中位 {statistics.median(rates) * 100:.0f}%、最大 {max(rates) * 100:.0f}%;整体平均 {statistics.mean(rates) * 100:.0f}%;超过 10% 的页面有 {sum(1 for x in rates if x > 0.1)} 个')
purge()
