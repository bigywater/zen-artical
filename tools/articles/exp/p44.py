import sys, os, re, hashlib, collections, urllib.parse as up; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, lxml.html
tee('p44')
NP = 60; NL = 10
def page(title, body, canon=None, extra=''):
    return f'<html><head><title>{title}</title>' + (f'<link rel="canonical" href="{canon}">' if canon else '') + extra + f'</head><body><h1>{title}</h1><p>{body}</p><footer>generated at {time.time_ns()}</footer></body></html>'

def site(h):
    u = up.urlsplit(h.path); p = u.path; q = dict(up.parse_qsl(u.query)); H = f'http://127.0.0.1:{h.server.srv.port}'
    m = re.match(r'^/(product|p)/(\d+)/?$', p)
    if m:
        i = int(m.group(2)); body = f'Product {i} details ' * 30
        if m.group(1) == 'p': return h.reply(200, page(f'Product {i}', body, f'{H}/product/{i}').encode(), headers={'Content-Type': 'text/html'})
        if p.endswith('/'): return h.reply(200, page(f'Product {i}', body, f'{H}/product/{i}').encode())
        if 'ref' in q: return h.reply(200, page(f'Product {i}', body, f'/product/{i}').encode())          # 相对的 canonical
        if 'sort' in q: return h.reply(200, page(f'Product {i}', body).encode(), headers={'Link': f'<{H}/product/{i}>; rel="canonical"'})  # 只有 Link 响应头
        return h.reply(200, page(f'Product {i}', body, f'{H}/product/{i}').encode())
    if p == '/list':
        n = int(q.get('page', 1)); return h.reply(200, page(f'List page {n}', f'items {n * 100}-{n * 100 + 99} ' * 20, f'{H}/list').encode())    # 所有分页都指向第 1 页:指错了
    m = re.match(r'^/(chain|loop)/(\w)$', p)
    if m:
        kind, ch = m.groups()
        nxt = {'chain': {'a': 'b', 'b': 'c', 'c': 'c'}, 'loop': {'a': 'b', 'b': 'a'}}[kind][ch]
        return h.reply(200, page(f'{kind} {ch}', f'{kind}-{ch} content ' * 20, f'{H}/{kind}/{nxt}').encode())
    if p == '/multi':
        return h.reply(200, ('<html><head><title>multi</title><link rel="canonical" href="%s/html-says"><link rel="canonical" href="%s/html-second"><meta property="og:url" content="%s/og-says"></head><body><h1>multi</h1><p>multi content</p></body></html>' % (H, H, H)).encode(), headers={'Link': f'<{H}/header-says>; rel="canonical"'})
    if p == '/bad':
        return h.reply(200, page('bad', 'bad page content ' * 20, f'{H}/gone').encode())
    h.reply(404, b'')

with Srv(site) as sv:
    B = sv.url('')
    urls = []
    for i in range(NP):
        urls += [f'/product/{i}', f'/product/{i}/', f'/product/{i}?ref=mail', f'/p/{i}', f'/product/{i}?sort=asc']
    urls += [f'/list?page={n}' for n in range(1, NL + 1)]
    truth_of = lambda u: ('P', int(re.search(r'/(\d+)', u).group(1))) if re.match(r'^/(product|p)/\d+', u) else ('L', int(u.split('=')[1]))
    TRUTH = len({truth_of(u) for u in urls})
    s = requests.Session(); docs = {}
    for u in urls:
        r = s.get(B + u); doc = lxml.html.fromstring(r.content)
        text = ' '.join(doc.xpath('//h1/text()|//p/text()'))
        canon_html = doc.xpath('//link[@rel="canonical"]/@href'); canon_hdr = re.findall(r'<([^>]+)>;\s*rel="?canonical"?', r.headers.get('Link', ''))
        canon = (canon_html or canon_hdr or [None])[0]
        docs[u] = dict(text=text, canon=up.urljoin(B + u, canon) if canon else None, raw=hashlib.sha1(r.content).hexdigest(), texth=hashlib.sha1(text.encode()).hexdigest(), via=('HTML' if canon_html else ('Link 头' if canon_hdr else '无')))
    print(f'== 一:站点:{NP} 个商品,每个有 5 种地址(/product/i、/product/i/、/product/i?ref=mail、/p/i、/product/i?sort=asc);{NL} 个分页列表页 /list?page=n(内容各不相同,但 canonical 都写成 /list);共 {len(urls)} 个 URL,真实不同的内容 {TRUTH} 个')
    print('  每种地址怎么声明 canonical:' + '、'.join(f'{k} → {v}' for k, v in collections.Counter(d['via'] for d in docs.values()).items()))
    print(f'  相对路径的 canonical(/product/i?ref=mail 页面里写的是 "/product/i")需要用页面 URL 解析;例:{docs["/product/3?ref=mail"]["canon"].replace(B, "<站点>")}')
    def evaluate(keyfn):
        groups = collections.defaultdict(set)
        for u in urls: groups[keyfn(u)].add(truth_of(u))
        merged_wrong = sum(1 for g in groups.values() if len(g) > 1); lost = TRUTH - len({t for g in groups.values() for t in [sorted(g)[0]]})
        kinds_per_truth = collections.defaultdict(set)
        for u in urls: kinds_per_truth[truth_of(u)].add(keyfn(u))
        split = sum(1 for v in kinds_per_truth.values() if len(v) > 1)
        return len(groups), merged_wrong, split
    def norm(u):                            # 只做 URL 规范化:去掉末尾斜杠和查询串里的 ref/sort
        p = up.urlsplit(u); q = [(k, v) for k, v in up.parse_qsl(p.query) if k not in ('ref', 'sort')]
        return up.urlunsplit(('', '', p.path.rstrip('/') or '/', up.urlencode(q), ''))
    print('== 二:四种合并方式,得到多少个"页面组",有几组把不同的内容错误地合在了一起,有几个真实页面被拆成了多组(理想:%d 组,0 错并,0 拆分)' % TRUTH)
    print(f'  {"合并方式":<40}{"页面组数":>8}{"错并":>6}{"被拆分":>8}')
    A = evaluate(lambda u: u); print(f'  {"不合并(每个 URL 一组)":<34}{A[0]:>8}{A[1]:>6}{A[2]:>8}')
    A = evaluate(norm); print(f'  {"只做 URL 规范化(去斜杠、ref、sort)":<30}{A[0]:>8}{A[1]:>6}{A[2]:>8}')
    A = evaluate(lambda u: (docs[u]['canon'] or norm(u)).replace(B, '')); print(f'  {"信任 canonical(没有则规范化 URL)":<30}{A[0]:>8}{A[1]:>6}{A[2]:>8}')
    cache = {}
    def verified(u):
        c = docs[u]['canon']
        if not c: return norm(u)
        key = c.replace(B, '')
        if key not in cache:
            r = s.get(c); t = ' '.join(lxml.html.fromstring(r.content).xpath('//h1/text()|//p/text()')) if r.status_code == 200 else None; cache[key] = t
        return key if cache[key] == docs[u]['text'] else norm(u)       # canonical 目标的内容与自己一致才信任
    A = evaluate(verified); print(f'  {"canonical + 内容校验(目标内容一致才信任)":<26}{A[0]:>8}{A[1]:>6}{A[2]:>8}')
    A = evaluate(lambda u: docs[u]['texth']); print(f'  {"只看正文哈希(去掉了 footer 时间戳)":<28}{A[0]:>8}{A[1]:>6}{A[2]:>8}')
    A = evaluate(lambda u: docs[u]['raw']); print(f'  {"整页字节哈希(含 footer 时间戳)":<28}{A[0]:>8}{A[1]:>6}{A[2]:>8}   ← 页面里每次变化的时间戳让哈希永远不同,什么都合并不了')

    print('== 三:canonical 指错了:10 个分页列表页内容各不相同,但都声明 canonical 是 /list')
    lst = [u for u in urls if u.startswith('/list')]
    print(f'  信任 canonical 之后,这 10 个页面合成 {len({docs[u]["canon"] for u in lst})} 组,内容各不相同的页面有 {len({docs[u]["text"] for u in lst})} 个——被丢掉的页面 {len({docs[u]["text"] for u in lst}) - 1} 个')
    ok = sum(1 for u in lst if verified(u) == norm(u)); print(f'  加了内容校验(canonical 目标 /list 的内容与自己不一致 → 不信任):{ok} / {len(lst)} 个页面保留了自己的身份')

    print('== 四:canonical 链、环与失效的目标')
    for name, start in (('canonical 链 a → b → c(c 指向自己)', '/chain/a'), ('canonical 环 a → b → a', '/loop/a'), ('canonical 指向 404', '/bad')):
        seen = []; u = B + start
        for _ in range(6):
            if u in seen: seen.append(u + '(又回到已访问过的)'); break
            seen.append(u); r = s.get(u)
            if r.status_code != 200: seen.append(f'{u}(HTTP {r.status_code})'); break
            c = lxml.html.fromstring(r.content).xpath('//link[@rel="canonical"]/@href')
            if not c or up.urljoin(u, c[0]) == u: break
            u = up.urljoin(u, c[0])
        print(f'  {name}:' + ' → '.join(x.replace(B, '') for x in seen))
    print('== 五:同一个页面里有多处声明且互相冲突:两个 <link rel="canonical">、一个 Link 响应头、一个 og:url')
    r = s.get(B + '/multi'); doc = lxml.html.fromstring(r.content)
    print('  HTML 里的 <link rel="canonical">(按出现顺序):' + str([x.replace(B, '') for x in doc.xpath('//link[@rel="canonical"]/@href')]))
    print('  Link 响应头里的 canonical:' + str([x.replace(B, '') for x in re.findall(r'<([^>]+)>;\s*rel="?canonical"?', r.headers.get('Link', ''))]))
    print('  og:url:' + str([x.replace(B, '') for x in doc.xpath('//meta[@property="og:url"]/@content')]))
    print('  → 三处给出 3 个不同的 URL(HTML 里还有 2 个)。取哪个由爬虫自己的策略决定;上面第二节的"信任 canonical"取的是 HTML 里的第一个,没有再取 Link 头')
purge()
