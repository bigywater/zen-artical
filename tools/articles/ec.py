"""数据编码与压缩系列的实验公共库:合成数据集(固定随机种子)、计时、体积统计。"""
import sys, os, json, time, random, statistics, zlib, gzip, math, collections, base64
sys.path.insert(0, '/private/tmp/claude-501/-Users-w-Desktop-zen/ba230915-496f-4157-87cf-8cee4040b1b9/scratchpad/enc_site')
from pl import tee, pdir, purge
import lz4.frame, lz4.block, zstandard
try:
    import snappy, msgpack, cbor2, orjson
except Exception: pass

def _vocab(seed=7, n=4000):
    r = random.Random(seed); cons = 'bcdfghjklmnprstvwz'; vow = 'aeiou'
    return [''.join(r.choice(cons) + r.choice(vow) for _ in range(r.randint(2, 4))) for _ in range(n)]
VOC = _vocab()
TAGS = [f'tag-{w}' for w in VOC[:60]]
CATS = ['/'.join(VOC[i:i + 3]) for i in range(0, 90, 3)]

def products(n=20000, seed=1):
    """爬虫抓到的商品记录:字符串多、字段名每条都重复"""
    r = random.Random(seed); out = []
    for i in range(n):
        out.append({'id': 1000000 + i, 'url': f'https://shop.example.com/item/{1000000 + i}?ref=list&page={i % 40}',
                    'title': ' '.join(r.choice(VOC[:1500]) for _ in range(r.randint(5, 12))), 'price': round(r.lognormvariate(3.5, 1.0), 2),
                    'currency': r.choice(['CNY', 'CNY', 'CNY', 'USD']), 'stock': r.randint(0, 500), 'rating': round(r.uniform(1, 5), 1),
                    'tags': r.sample(TAGS, 3), 'category': r.choice(CATS), 'updated_at': f'2026-10-{r.randint(1, 12):02d}T{r.randint(0, 23):02d}:{r.randint(0, 59):02d}:{r.randint(0, 59):02d}Z',
                    'seller': {'id': r.randint(1, 800), 'name': 'shop-' + r.choice(VOC[:800])}})
    return out

def timeseries(n=50000, seed=2):
    """数值密集:时间戳递增、数值随机游走"""
    r = random.Random(seed); v = 20.0; out = []; ts = 1760000000
    for i in range(n):
        ts += r.choice([1, 1, 1, 2]); v += r.gauss(0, 0.05); out.append({'ts': ts, 'sensor': i % 8, 'value': round(v + (i % 8), 3), 'status': 0 if r.random() < 0.98 else r.randint(1, 4)})
    return out

def nested(n=3000, seed=3):
    """嵌套较深、键名大量重复的配置式文档"""
    r = random.Random(seed)
    def node(d):
        if d == 0: return {'enabled': r.random() < 0.5, 'threshold': r.randint(0, 100), 'label': r.choice(VOC[:200])}
        return {'name': r.choice(VOC[:300]), 'children': [node(d - 1) for _ in range(r.randint(1, 3))], 'options': {'retries': r.randint(0, 5), 'timeout_ms': r.choice([500, 1000, 3000])}}
    return [node(4) for _ in range(n)]

def blobby(n=3000, seed=4):
    """带二进制字段(缩略图),内容不可压缩"""
    r = random.Random(seed)
    return [{'id': i, 'name': 'img-' + r.choice(VOC[:500]), 'w': r.choice([64, 128]), 'h': r.choice([64, 128]), 'thumb': r.randbytes(512)} for i in range(n)]

def pages(n=1500, seed=5):
    """类 HTML 页面文本(用于纯压缩实验)"""
    r = random.Random(seed); out = []
    for i in range(n):
        body = ''.join(f'<li class="item"><a href="/p/{r.randint(0, 9999)}">{" ".join(r.choice(VOC[:1200]) for _ in range(r.randint(3, 8)))}</a><span class="price">{r.randint(1, 999)}.{r.randint(0, 99):02d}</span></li>' for _ in range(120))
        out.append(f'<!doctype html><html><head><title>page {i}</title><link rel="stylesheet" href="/s.css"></head><body><nav><a href="/">home</a><a href="/cat">cat</a></nav><ul>{body}</ul><footer>copyright shop example</footer></body></html>'.encode())
    return out

def j(o): return json.dumps(o, ensure_ascii=False, separators=(',', ':')).encode()
def jl(rows): return b'\n'.join(j(x) for x in rows)

def timeit(fn, n=5, warm=1):
    for _ in range(warm): fn()
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
    ts.sort(); return ts[len(ts) // 2], ts[0], ts[-1]
def mib(b): return b / 1048576
def pct(a, b): return f'{a * 100 / b:.1f}%'

# ---- LZ77 与 deflate 的长度/距离码表(第 11 篇的实现,后面的文章复用) ----
LB = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]; LE = [0] * 8 + [1] * 4 + [2] * 4 + [3] * 4 + [4] * 4 + [5] * 4 + [0]
DB = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577]; DE = [0, 0, 0, 0] + [k // 2 - 1 for k in range(4, 30)]
def lcode(L):
    for k in range(len(LB) - 1, -1, -1):
        if L >= LB[k]: return k
def dcode(D):
    for k in range(len(DB) - 1, -1, -1):
        if D >= DB[k]: return k
def lz77(data, window=32768, chain=32, lazy=False, minlen=3, maxlen=258):
    n = len(data); table = {}; toks = []; i = 0
    def find(i):
        if i + minlen > n: return 0, 0
        lst = table.get(data[i:i + 3]); best = 0; bd = 0
        if not lst: return 0, 0
        lim = min(maxlen, n - i); k = 0
        for c in reversed(lst):
            k += 1
            if k > chain or i - c > window: break
            L = 0
            while L < lim and data[c + L] == data[i + L]: L += 1
            if L > best: best, bd = L, i - c
            if best == lim: break
        return best, bd
    def ins(p):
        if p + 3 <= n: table.setdefault(data[p:p + 3], []).append(p)
    while i < n:
        L, d = find(i)
        if L >= minlen and lazy and i + 1 < n:
            ins(i); L2, d2 = find(i + 1)
            if L2 > L: toks.append((0, data[i])); i += 1; continue
            toks.append((d, L))
            for p in range(i + 1, i + L): ins(p)
            i += L; continue
        if L >= minlen:
            toks.append((d, L))
            for p in range(i, i + L): ins(p)
            i += L
        else: toks.append((0, data[i])); ins(i); i += 1
    return toks
def H0(counter):
    n = sum(counter.values()); return -sum(c / n * math.log2(c / n) for c in counter.values() if c)
def huff_cost(fr):
    """Huffman 编码 fr(符号→次数)需要的总位数(不含码表)"""
    import heapq
    if len(fr) == 1: return sum(fr.values())
    h = [(c, i, (s,)) for i, (s, c) in enumerate(sorted(fr.items()))]; heapq.heapify(h); dep = collections.Counter(); tk = len(h)
    while len(h) > 1:
        c1, _, a = heapq.heappop(h); c2, _, b = heapq.heappop(h)
        for s in a + b: dep[s] += 1
        heapq.heappush(h, (c1 + c2, tk, a + b)); tk += 1
    return sum(fr[s] * dep[s] for s in fr)
