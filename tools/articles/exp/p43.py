import sys, os, gzip, io, tracemalloc, datetime, xml.etree.ElementTree as ET; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, lxml.etree as LE
tee('p43')
NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
def urlset(urls, extra_ns=''):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="%s"%s>\n' % (NS, extra_ns) + ''.join(f'  <url><loc>{u}</loc>' + (f'<lastmod>{lm}</lastmod>' if lm else '') + '<changefreq>daily</changefreq><priority>0.5</priority></url>\n' for u, lm in urls) + '</urlset>\n').encode()
def sm_index(locs): return ('<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="%s">\n' % NS + ''.join(f'  <sitemap><loc>{l}</loc><lastmod>2026-10-01</lastmod></sitemap>\n' for l in locs) + '</sitemapindex>\n').encode()
H = 'http://shop.test'
S1 = urlset([(f'{H}/p/{i}', '2026-10-0%d' % (1 + i % 9)) for i in range(5)])
S2 = urlset([(f'{H}/q/{i}', '2026-10-11T08:30:00+08:00') for i in range(5)])
S3 = urlset([(f'{H}/r/{i}', None) for i in range(5)])
def route(h):
    p = h.path
    if p == '/sitemap_index.xml': return h.reply(200, sm_index([f'{H}/sitemap1.xml', f'{H}/sitemap2.xml.gz', f'{H}/sitemap3.xml']), headers={'Content-Type': 'application/xml'})
    if p == '/sitemap1.xml': return h.reply(200, S1, headers={'Content-Type': 'application/xml'})
    if p == '/sitemap2.xml.gz': return h.reply(200, gz(S2), headers={'Content-Type': 'application/gzip'})
    if p == '/sitemap3.xml': return h.reply(200, gz(S3), headers={'Content-Type': 'application/xml', 'Content-Encoding': 'gzip'})
    h.reply(404, b'')

with Srv(route) as sv:
    B = sv.url('')
    def get(path): return requests.get(B + path)
    print('== 一:sitemap 索引 → 子 sitemap;XML 命名空间')
    r = get('/sitemap_index.xml'); root = ET.fromstring(r.content)
    print(f'  根元素标签:{root.tag}')
    print(f'  不写命名空间 root.findall("sitemap/loc") → {len(root.findall("sitemap/loc"))} 个;写上命名空间 root.findall("{{ns}}sitemap/{{ns}}loc") → {len(root.findall(f"{{{NS}}}sitemap/{{{NS}}}loc"))} 个')
    print(f'  用 lxml 的 xpath("//*[local-name()=\'loc\']/text()")(不依赖命名空间)→ {len(LE.fromstring(r.content).xpath("//*[local-name()=\'loc\']/text()"))} 个')
    print('== 二:gzip 的两种形式:文件本身是 .xml.gz,或者 HTTP 层 Content-Encoding: gzip')
    for path in ('/sitemap2.xml.gz', '/sitemap3.xml'):
        r = get(path); head = r.content[:2]
        print(f'  {path}:Content-Type={r.headers.get("Content-Type")},Content-Encoding={r.headers.get("Content-Encoding")};requests 给出的 r.content 开头字节 {head.hex()}({"仍是 gzip,需要自己解压" if head == b"\x1f\x8b" else "已经是明文 XML,requests 解开了 HTTP 层的 gzip"})')
    r = get('/sitemap2.xml.gz'); print(f'  对 .xml.gz 自己 gzip.decompress 之后能解析:{len(ET.fromstring(gzip.decompress(r.content)).findall(f"{{{NS}}}url"))} 个 URL')
    try: ET.fromstring(r.content)
    except Exception as e: print(f'  不解压直接 ET.fromstring(r.content):{type(e).__name__}: {str(e)[:50]}')
    print('== 三:lastmod 的几种写法与增量过滤(只抓上次抓取之后改过的)')
    def parse_lm(s):
        try:
            d = datetime.datetime.fromisoformat(s)
            return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
        except ValueError: return None
    for s in ('2026-10-11', '2026-10-11T08:30:00+08:00', '2026-10-11T00:30:00Z', '2026-10-11 08:30', '11/10/2026', 'Sun, 11 Oct 2026 00:30:00 GMT', ''):
        print(f'  lastmod {s!r:<34}→ {parse_lm(s)}')
    last = datetime.datetime(2026, 10, 5, tzinfo=datetime.timezone.utc)
    ents = []
    for path in ('/sitemap1.xml', '/sitemap2.xml.gz', '/sitemap3.xml'):
        r = get(path); data = gzip.decompress(r.content) if path.endswith('.gz') else r.content
        for u in ET.fromstring(data).findall(f'{{{NS}}}url'):
            lm = u.find(f'{{{NS}}}lastmod'); ents.append((u.find(f'{{{NS}}}loc').text, parse_lm(lm.text) if lm is not None else None))
    new = [e for e in ents if e[1] and e[1] > last]; nolm = [e for e in ents if e[1] is None]
    print(f'  3 个子 sitemap 共 {len(ents)} 条 URL;上次抓取时间 2026-10-05:lastmod 更新的 {len(new)} 条,没有 lastmod 的 {len(nolm)} 条(这种条目不能用来判断是否更新,只能当作"需要抓")')

print('== 四:大 sitemap(50000 条 URL)的解析:一次性 fromstring 对 iterparse 边读边丢')
big = urlset([(f'http://shop.test/item/{i}?id={i}', '2026-10-11') for i in range(50000)])
print(f'  文件大小 {len(big) / 1048576:.1f} MiB(未压缩),gzip 后 {len(gz(big)) / 1048576:.2f} MiB')
def full():
    root = ET.fromstring(big); return sum(1 for _ in root.iter(f'{{{NS}}}loc'))
def streamed():
    n = 0
    for ev, el in ET.iterparse(io.BytesIO(big), events=('end',)):
        if el.tag == f'{{{NS}}}url': n += 1; el.clear()
    return n
for name, fn in (('ElementTree.fromstring', full), ('ElementTree.iterparse(边读边 clear)', streamed)):
    tracemalloc.start(); t0 = time.perf_counter(); n = fn(); el = time.perf_counter() - t0; cur, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    print(f'  {name}:{n} 条,{el * 1000:.0f} ms,内存峰值 {peak / 1048576:.1f} MiB')

print('== 五:脏数据')
bad = b'<?xml version="1.0"?><urlset xmlns="%s"><url><loc>http://shop.test/a?x=1&y=2</loc></url><url><loc>http://other.test/zzz</loc></url><url><loc>/relative/path</loc></url><url><loc>http://shop.test/a?x=1&amp;y=2</loc></url></urlset>' % NS.encode()
try: ET.fromstring(bad)
except Exception as e: print(f'  未转义的 & :标准库 ElementTree 报错 {type(e).__name__}: {str(e)[:60]}')
root = LE.fromstring(bad, LE.XMLParser(recover=True))
locs = root.xpath("//*[local-name()='loc']/text()")
print(f'  lxml 的 recover=True 能读出 {len(locs)} 条:{locs}')
base_host = 'shop.test'
import urllib.parse as up
for l in locs:
    p = up.urlsplit(l); flag = '相对路径,没有主机' if not p.netloc else ('跨主机(与 sitemap 所在主机不同)' if p.netloc != base_host else '同主机')
    print(f'      {l:<40}→ {flag}')
purge()
