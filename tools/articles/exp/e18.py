import sys, os, subprocess, urllib.parse as up; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
import brotli, requests
from pl import Srv
tee('e18')
P = products(); PG = pages()
page = PG[0]; pj = jl(P[:200]); small_html = b'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Welcome to our online store</title><link rel="stylesheet" href="/static/css/main.css"></head><body><header><nav><ul><li><a href="/">Home</a></li><li><a href="/products">Products</a></li><li><a href="/about">About us</a></li><li><a href="/contact">Contact</a></li></ul></nav></header><main><h1>Welcome</h1><p>Browse our latest products and special offers.</p></main><footer><p>Copyright 2026. All rights reserved.</p></footer></body></html>'
_r = random.Random(5); gib = ' '.join(_r.choice(VOC) for _ in range(len(small_html) // 6)).encode()[:len(small_html)]
zc = lambda lv=3: zstandard.ZstdCompressor(level=lv)
print(f'== 一:brotli 自带一份静态字典(英文词、HTML/JS/CSS 常见片段),很小的输入也能压:同样长度的"真实英文 HTML 样板"与"合成乱码词"(brotli {brotli.__version__})')
print(f'  {"输入":34s} {"原字节":>7s} {"gzip-9":>7s} {"zstd-19":>8s} {"brotli q11":>10s} {"brotli q5":>9s}')
for lab, d in (('英文 HTML 样板(导航、页脚)', small_html), ('英文 HTML 样板前 300 字节', small_html[:300]), ('合成乱码词(我的 VOC 词表)', gib), ('products JSON 3 条', jl(P[:3])), ('一页 13 KiB 合成页面', page)):
    print(f'  {lab:34s} {len(d):7d} {len(zlib.compress(d, 9)):7d} {len(zc(19).compress(d)):8d} {len(brotli.compress(d, quality=11)):10d} {len(brotli.compress(d, quality=5)):9d}')
print('== 二:较大的数据——合成页面 20 MiB 中取一页(13 KiB)、200 条 JSON Lines(72 KB)、整份 pages 8 MiB')
big = b''.join(PG)[:8 << 20]
print(f'  {"输入":28s} {"原字节":>9s} {"gzip-6":>9s} {"gzip-9":>9s} {"zstd-3":>9s} {"zstd-19":>9s} {"br q5":>9s} {"br q9":>9s} {"br q11":>9s}')
for lab, d in (('一页 HTML 13 KiB', page), ('200 条 products JSON Lines', pj), ('pages 8 MiB', big)):
    print(f'  {lab:28s} {len(d):9d} {len(zlib.compress(d, 6)):9d} {len(zlib.compress(d, 9)):9d} {len(zc(3).compress(d)):9d} {len(zc(19).compress(d)):9d} {len(brotli.compress(d, quality=5)):9d} {len(brotli.compress(d, quality=9)):9d} {len(brotli.compress(d, quality=11)):9d}')
print('== 三:一个按 Accept-Encoding 协商的本机 HTTP 服务器——requests 默认发的头,以及线上实际传输的字节')
def srv(h):
    ae = dict((k.lower(), v) for k, v in h.hdrs).get('accept-encoding', ''); u = up.urlsplit(h.path); q = dict(up.parse_qsl(u.query)); body = jl(P[:2000]) if u.path == '/data' else page
    enc = None
    for pref in (q.get('prefer', 'br,zstd,gzip')).split(','):
        if pref in [x.strip().split(';')[0] for x in ae.split(',')]: enc = pref; break
    if enc == 'br': out = brotli.compress(body, quality=5)
    elif enc == 'zstd': out = zc(3).compress(body)
    elif enc == 'gzip': out = gzip.compress(body, 6, mtime=0)
    else: out = body
    hd = {'Content-Type': 'application/json' if u.path == '/data' else 'text/html', 'Vary': 'Accept-Encoding'}
    if enc: hd['Content-Encoding'] = enc
    h.reply(200, out, headers=hd)
with Srv(srv) as sv:
    s = requests.Session(); r = s.get(sv.url('/data')); sent = dict((k.lower(), v) for k, v in sv.log[-1]['hdrs'])['accept-encoding']
    print(f'  requests {requests.__version__} 默认发出的 Accept-Encoding:{sent!r};服务器选了 {r.headers.get("Content-Encoding")},线上正文 {r.headers.get("Content-Length")} 字节,解码后 {len(r.content)} 字节')
    for ae in ('identity', 'gzip', 'br', 'zstd', 'gzip, br, zstd'):
        for path in ('/data', '/page'):
            r = requests.get(sv.url(path), headers={'Accept-Encoding': ae}); print(f'  Accept-Encoding: {ae:16s} 请求 {path:6s} → Content-Encoding={r.headers.get("Content-Encoding")},线上 {r.headers.get("Content-Length"):>7s} 字节,解码后 {len(r.content)} 字节,{"解码正确" if r.content == (jl(P[:2000]) if path == "/data" else page) else "解码出错"}')
print('== 四:已经压缩过或本来就无法压缩的内容再压一次')
rnd = random.Random(8).randbytes(1 << 20); gz1 = gzip.compress(big[:1 << 20], 6, mtime=0); jpg_like = rnd
print(f'  {"内容":26s} {"原字节":>8s} {"gzip-6":>8s} {"br q5":>8s} {"zstd-3":>8s}')
for lab, d in (('随机字节(像 JPEG/加密数据)', jpg_like), ('已经 gzip 过的文本', gz1), ('原始文本(未压缩)', big[:1 << 20])):
    print(f'  {lab:26s} {len(d):8d} {len(zlib.compress(d, 6)):8d} {len(brotli.compress(d, quality=5)):8d} {len(zc(3).compress(d)):8d}')
print('== 五:每个请求现压缩要花多少 CPU 时间(一页 13 KiB 的 HTML;1000 次的中位数,每次几十微秒到几十毫秒)')
for lab, f in (('gzip level 1', lambda: zlib.compress(page, 1)), ('gzip level 6', lambda: zlib.compress(page, 6)), ('gzip level 9', lambda: zlib.compress(page, 9)), ('zstd level 3', lambda: zc(3).compress(page)), ('zstd level 19', lambda: zc(19).compress(page)), ('brotli q4', lambda: brotli.compress(page, quality=4)), ('brotli q5', lambda: brotli.compress(page, quality=5)), ('brotli q9', lambda: brotli.compress(page, quality=9)), ('brotli q11', lambda: brotli.compress(page, quality=11))):
    m = timeit(f, 30 if 'q11' in lab or 'level 19' in lab else 300)[0]; print(f'  {lab:14s} {len(f()):6d} 字节  中位 {m * 1e6:9.0f} 微秒/页  → 单核每秒约 {1 / m:8.0f} 页')
print('== 六:总耗时模型——压缩 + 传输 + 解压(用上面量到的体积和耗时算出来的估算,不是实测网络;一页 13 KiB HTML,四种带宽)')
dec = {'identity': lambda c: c, 'gzip-6': zlib.decompress, 'zstd-3': zstandard.ZstdDecompressor().decompress, 'br q5': brotli.decompress, 'br q11': brotli.decompress}
comp = {'identity': lambda: page, 'gzip-6': lambda: zlib.compress(page, 6), 'zstd-3': lambda: zc(3).compress(page), 'br q5': lambda: brotli.compress(page, quality=5), 'br q11': lambda: brotli.compress(page, quality=11)}
stat = {}
for k in comp:
    c = comp[k](); tc = timeit(comp[k], 30 if k == 'br q11' else 200)[0]; td = timeit(lambda: dec[k](c), 200)[0]; stat[k] = (len(c), tc, td)
print(f'  {"编码":10s} {"字节":>7s} {"压缩":>9s} {"解压":>9s}' + ''.join(f'{"@" + str(bw) + " Mbit/s":>14s}' for bw in (1, 10, 100, 1000)))
for k, (n, tc, td) in stat.items():
    print(f'  {k:10s} {n:7d} {tc * 1e6:7.0f}微秒 {td * 1e6:7.0f}微秒' + ''.join(f'{(tc + td + n * 8 / (bw * 1e6)) * 1000:11.2f} ms' for bw in (1, 10, 100, 1000)))
print('  (总耗时 = 压缩时间 + 字节数×8/带宽 + 解压时间,忽略了延迟、TCP 慢启动、并发;如果压缩是预先做好的静态文件,压缩时间不计入请求)')
purge()
