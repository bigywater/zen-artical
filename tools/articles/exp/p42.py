import sys, os, email.utils, datetime, re, hashlib, urllib.parse as up; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests
tee('p42')

class Site:
    def __init__(self, n=100, size=200 * 1024):
        self.pages = {i: dict(ver=1, lm=1_790_000_000 + i) for i in range(n)}      # lm = 最后修改时间(Unix 秒,整数)
        self.size = size; self.mode = 'both'; self.counts = {200: 0, 304: 0}; self.cc = None
    def body(self, i, ver): return (f'page {i} version {ver} '.encode() * 20000)[:self.size]
    def etag(self, i): return f'"p{i}-v{self.pages[i]["ver"]}"'
    def handler(self, h):
        m = re.match(r'/p/(\d+)$', h.path.split('?')[0])
        if not m: return h.reply(404, b'')
        i = int(m.group(1)); pg = self.pages[i]; hd = {k.lower(): v for k, v in h.hdrs}
        hdrs = {}
        if self.cc: hdrs['Cache-Control'] = self.cc
        if self.mode in ('etag', 'both'): hdrs['ETag'] = self.etag(i)
        if self.mode in ('lm', 'both'): hdrs['Last-Modified'] = email.utils.formatdate(pg['lm'], usegmt=True)
        not_modified = False
        if self.mode != 'none':
            inm = hd.get('if-none-match'); ims = hd.get('if-modified-since')
            if inm is not None and self.mode in ('etag', 'both'):
                cands = [x.strip() for x in inm.split(',')]
                strip = lambda t: t[2:] if t.startswith('W/') else t
                not_modified = inm.strip() == '*' or any(strip(c) == self.etag(i) for c in cands)
            elif ims is not None and self.mode in ('lm', 'both'):
                try: t = email.utils.parsedate_to_datetime(ims).timestamp(); not_modified = int(pg['lm']) <= int(t)
                except (TypeError, ValueError): not_modified = False      # 无法解析的日期:忽略这个头
        if not_modified:
            self.counts[304] += 1; return h.reply(304, b'', headers=hdrs, length=False)
        self.counts[200] += 1; h.reply(200, self.body(i, pg['ver']), headers=hdrs)

site = Site()
with Srv(site.handler) as sv:
    U = lambda i=0: sv.url(f'/p/{i}')
    print('== 一:单个页面(200 KB)的几种请求方式')
    t0 = time.perf_counter(); r1 = requests.get(U()); t1 = ms(t0)
    et, lm = r1.headers.get('ETag'), r1.headers.get('Last-Modified')
    print(f'  第一次 GET:{r1.status_code},{len(r1.content) // 1024} KB,耗时 {t1:.1f} ms;ETag={et},Last-Modified={lm}')
    for lab, hd in (('If-None-Match: ETag', {'If-None-Match': et}), ('If-Modified-Since: Last-Modified', {'If-Modified-Since': lm}), ('两个头一起带', {'If-None-Match': et, 'If-Modified-Since': lm}),
                    ('If-None-Match 带了错误的 ETag', {'If-None-Match': '"other"'}), ('If-None-Match 是列表(含正确的一个)', {'If-None-Match': f'"x", {et}, "y"'}), ('If-None-Match: *', {'If-None-Match': '*'}),
                    ('弱校验 W/ 前缀', {'If-None-Match': 'W/' + et}), ('ETag 去掉引号', {'If-None-Match': et.strip('"')}),
                    ('If-Modified-Since 是更早的时间', {'If-Modified-Since': email.utils.formatdate(1_000_000_000, usegmt=True)}), ('If-Modified-Since 格式乱写', {'If-Modified-Since': 'yesterday'})):
        t0 = time.perf_counter(); r = requests.get(U(), headers=hd); t = ms(t0)
        print(f'  {lab:<34}→ {r.status_code},响应体 {len(r.content):>6} 字节,耗时 {t:.1f} ms')
    print('  304 响应里也带 ETag/Last-Modified 头:' + str({k: v for k, v in requests.get(U(), headers={'If-None-Match': et}).headers.items() if k.lower() in ('etag', 'last-modified')}))

    print('== 二:抓 100 个页面(各 200 KB)两遍,第二遍前有 10 个页面更新了。无条件请求 与 带 If-None-Match(客户端自己保存 ETag 和内容)')
    def crawl(cond, store):
        site.counts = {200: 0, 304: 0}; got = 0; t0 = time.perf_counter(); s = requests.Session(); fresh = 0
        for i in range(100):
            hd = {}
            if cond and i in store: hd['If-None-Match'] = store[i][0]
            r = s.get(U(i), headers=hd)
            if r.status_code == 200: store[i] = (r.headers.get('ETag'), r.content); got += len(r.content)
            elif r.status_code == 304: fresh += 1
        return got, time.perf_counter() - t0, dict(site.counts), fresh
    st = {}
    g1, t1, c1, _ = crawl(True, st); print(f'  第一遍(都是新页面):响应体共 {g1 / 1048576:.1f} MiB,{t1:.2f} 秒;服务器回 200 × {c1[200]}、304 × {c1[304]}')
    for i in range(10): site.pages[i]['ver'] += 1
    st2 = dict(st)
    g2, t2, c2, f2 = crawl(False, {}); print(f'  第二遍,无条件请求:响应体共 {g2 / 1048576:.1f} MiB,{t2:.2f} 秒;200 × {c2[200]}、304 × {c2[304]}')
    g3, t3, c3, f3 = crawl(True, st2); print(f'  第二遍,带 If-None-Match:响应体共 {g3 / 1048576:.1f} MiB,{t3:.2f} 秒;200 × {c3[200]}、304 × {c3[304]}(客户端复用了本地保存的 {f3} 个页面)')

    print('== 三:Last-Modified 只精确到秒:同一秒内内容改了两次')
    site.mode = 'lm'; site.pages[50]['lm'] = 1_790_100_000; site.pages[50]['ver'] = 1
    r = requests.get(U(50)); lm = r.headers['Last-Modified']; v1 = r.content[:40]
    site.pages[50]['ver'] = 2        # 内容变了,但 Last-Modified 没变(同一秒内,这里直接保持相同)
    r2 = requests.get(U(50), headers={'If-Modified-Since': lm})
    print(f'  内容从 version 1 变成 version 2,Last-Modified 仍是 {lm}:带 If-Modified-Since 的请求得到 {r2.status_code}(客户端会认为没变,实际已经变了:服务器回 304)')
    site.mode = 'etag'
    r = requests.get(U(50)); et = r.headers['ETag']; site.pages[50]['ver'] = 3
    r2 = requests.get(U(50), headers={'If-None-Match': et}); print(f'  换成只用 ETag:内容再变一次后,带旧 ETag 的请求得到 {r2.status_code}({"拿到新内容" if r2.status_code == 200 else "错过更新"})')

    print('== 四:服务器不支持条件请求(动态页面、没有 ETag 也没有 Last-Modified)')
    site.mode = 'none'; site.counts = {200: 0, 304: 0}
    r = requests.get(U(3)); r2 = requests.get(U(3), headers={'If-None-Match': '"p3-v1"', 'If-Modified-Since': email.utils.formatdate(2_000_000_000, usegmt=True)})
    print(f'  响应头里有 ETag:{"ETag" in r.headers},有 Last-Modified:{"Last-Modified" in r.headers};带条件头重复请求得到 {r2.status_code},响应体 {len(r2.content) // 1024} KB——条件头被无视,每次都完整下载')

    print('== 五:同一个页面(200 KB)被重复访问 100 次:三种客户端策略下,服务器收到多少请求、一共传输多少字节')
    site.mode = 'both'; site.cc = 'max-age=60'
    def visit(strategy, n=100):
        site.counts = {200: 0, 304: 0}; store = None; fetched_at = 0.0; nbytes = 0; t0 = time.perf_counter(); s = requests.Session()
        for _ in range(n):
            if strategy == 'plain':
                r = s.get(U(7)); nbytes += len(r.content)
            elif strategy == 'revalidate':
                hd = {'If-None-Match': store[0]} if store else {}
                r = s.get(U(7), headers=hd)
                if r.status_code == 200: store = (r.headers['ETag'], r.content); nbytes += len(r.content)
            else:   # 遵守 max-age:新鲜期内不发请求;过期再用条件请求重新验证
                if store and time.perf_counter() - fetched_at < store[2]: continue
                hd = {'If-None-Match': store[0]} if store else {}
                r = s.get(U(7), headers=hd); m = re.search(r'max-age=(\d+)', r.headers.get('Cache-Control', '')); age = int(m.group(1)) if m else 0
                if r.status_code == 200: store = (r.headers['ETag'], r.content, age); nbytes += len(r.content)
                elif store: store = (store[0], store[1], age)
                fetched_at = time.perf_counter()
        return dict(site.counts), nbytes, time.perf_counter() - t0
    for lab, st in (('每次都完整下载(不带条件头)', 'plain'), ('每次都带 If-None-Match 重新验证', 'revalidate'), ('遵守 Cache-Control: max-age=60,新鲜期内不发请求', 'fresh')):
        c, nb, t = visit(st)
        print(f'  {lab}:服务器收到 {c[200] + c[304]} 个请求(200 × {c[200]}、304 × {c[304]}),响应体共 {nb / 1048576:.1f} MiB,总耗时 {t * 1000:.0f} ms')
    site.cc = None
purge()
