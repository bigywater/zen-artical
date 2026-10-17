import sys, os, hashlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s21'); reset_s()
class Site:
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(dict(path=h.path, hdrs=dict(h.hdrs)))
        p = h.path.split('?')[0]
        if p == '/ok': h.reply(200, '<html>ok</html>', {'Content-Type': 'text/html'})
        elif p == '/404': h.reply(404, 'nf', {'Content-Type': 'text/plain'})
        elif p == '/500': h.reply(500, 'err', {'Content-Type': 'text/plain'})
        elif p == '/r302': h.reply(302, b'', {'Location': '/ok'})
        elif p == '/nostore': h.reply(200, '<html>ns</html>', {'Content-Type': 'text/html', 'Cache-Control': 'no-store'})
        elif p == '/maxage': h.reply(200, '<html>ma</html>', {'Content-Type': 'text/html', 'Cache-Control': 'max-age=3600'})
        elif p == '/etag':
            if dict(h.hdrs).get('If-None-Match') == '"v1"': h.reply(304, b'', {'ETag': '"v1"'})
            else: h.reply(200, '<html>etag body</html>', {'Content-Type': 'text/html', 'ETag': '"v1"', 'Cache-Control': 'max-age=0'})
        elif p == '/lm':
            if dict(h.hdrs).get('If-Modified-Since'): h.reply(304, b'', {})
            else: h.reply(200, '<html>lm</html>', {'Content-Type': 'text/html', 'Last-Modified': 'Mon, 01 Jan 2024 00:00:00 GMT', 'Cache-Control': 'max-age=0'})
        else: h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
def run(paths, settings, cache, sv=None, meta='{}', tag='s21', port=None, down=False):
    d = sdir(tag) if not isinstance(tag, pathlib.Path) else tag
    sv = sv or Site()
    class Dummy:
        def __init__(self, port): self.port = port
        def url(self, p): return f'http://127.0.0.1:{self.port}{p}'
        def __enter__(self): return self
        def __exit__(self, *a): pass
    with (Dummy(port) if down else Srv(sv, port=port)) as s:
        code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        for p in {paths!r}: yield scrapy.Request('{s.url("")}' + p, callback=self.cb, errback=self.eb, meta={meta})
    def cb(self, response): EV(p=response.url.split('{s.port}')[-1], status=response.status, flags=response.flags, body=response.text[:20])
    def eb(self, failure): EV(p=failure.request.url.split('{s.port}')[-1], err=type(failure.value).__name__)
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO', 'HTTPCACHE_ENABLED': 1, 'HTTPCACHE_DIR': str(cache)}, **settings))
    return sv, ev(d), out, stats(out)
def hc(st): return {k.split('httpcache/')[1]: v for k, v in sorted(st.items()) if k.startswith('httpcache/')}

print('== 一:默认关闭;打开后第一次运行全部 miss 并存储,第二次运行全部 hit,服务器 0 个请求(默认 DummyPolicy:什么都缓存、永不过期)')
cache = sdir('s21cache1')
for i in (1, 2):
    sv, E, out, st = run(['/ok', '/a', '/b'], {}, cache, tag=f's21a{i}')
    print(f'  第 {i} 次运行:服务器收到 {len(sv.log)} 个请求;cache stats {hc(st)};响应 flags {sorted({tuple(x["flags"]) for x in E})}')
sv, E, out, st = run(['/ok'], {'HTTPCACHE_ENABLED': 0}, cache, tag='s21a3')
print(f'  HTTPCACHE_ENABLED=0(同一个目录):服务器收到 {len(sv.log)} 个请求;cache stats {hc(st)}')

print('== 二:磁盘上的布局(FilesystemCacheStorage):<目录>/<spider 名>/<指纹前 2 位>/<指纹>/ 下的文件(7 个)')
cache = sdir('s21cache2'); sv, E, out, st = run(['/ok'], {}, cache, tag='s21b')
fs = sorted(p for p in cache.rglob('*') if p.is_file())
for p in fs: print(f'  {str(p.relative_to(cache)).replace(p.parent.name, p.parent.name[:8] + "…"):<44}{p.stat().st_size:>6} 字节')
rb = [p for p in fs if p.name == 'response_body'][0].read_bytes(); rh = [p for p in fs if p.name == 'response_headers'][0].read_bytes()
print(f'  response_body = {rb!r}')
print(f'  response_headers 的头两行 = {rh.decode().splitlines()[:2]}')
print(f'  pickled_meta 里的键 = {sorted(__import__("pickle").loads([p for p in fs if p.name == "pickled_meta"][0].read_bytes()))}')

print('== 三:各种状态码和响应头,默认 DummyPolicy 下第二次运行是否命中(HTTPCACHE_IGNORE_HTTP_CODES 可排除)')
cache = sdir('s21cache3'); paths = ['/ok', '/404', '/500', '/r302', '/nostore', '/maxage']
run(paths, {}, cache, tag='s21c1')
sv, E, out, st = run(paths, {}, cache, tag='s21c2')
print(f'  第二次运行服务器仍收到的路径:{[l["path"] for l in sv.log] or "(无)"};stats {hc(st)}')
cache = sdir('s21cache3b'); run(paths, {'HTTPCACHE_IGNORE_HTTP_CODES': '404,500'}, cache, tag='s21c3')
sv, E, out, st = run(paths, {'HTTPCACHE_IGNORE_HTTP_CODES': '404,500'}, cache, tag='s21c4')
print(f'  HTTPCACHE_IGNORE_HTTP_CODES=404,500:第二次运行服务器收到 {[l["path"] for l in sv.log]};stats {hc(st)}')

print('== 四:RFC2616Policy:尊重 Cache-Control / ETag / Last-Modified;第二次运行 /nostore 不缓存,/maxage 新鲜命中,/etag 与 /lm 带条件头重新验证,304 就用缓存的正文')
P = {'HTTPCACHE_POLICY': 'scrapy.extensions.httpcache.RFC2616Policy'}
cache = sdir('s21cache4'); paths = ['/nostore', '/maxage', '/etag', '/lm', '/ok']
run(paths, P, cache, tag='s21d1')
sv, E, out, st = run(paths, P, cache, tag='s21d2')
print('  第二次运行服务器收到的请求(及条件头):')
for l in sv.log: print(f'    {l["path"]:<10}If-None-Match={l["hdrs"].get("If-None-Match", "(无)")}  If-Modified-Since={l["hdrs"].get("If-Modified-Since", "(无)")}')
print(f'  stats {hc(st)}')
for x in sorted(E, key=lambda x: x['p']): print(f'    回调:{x["p"]:<10}status={x["status"]} flags={x["flags"]} body={x["body"]!r}')

print('== 五:过期 HTTPCACHE_EXPIRATION_SECS=2:第二次运行在 0 秒内命中,3 秒后过期(DummyPolicy)')
cache = sdir('s21cache5'); S5 = {'HTTPCACHE_EXPIRATION_SECS': 2}
run(['/ok'], S5, cache, tag='s21e1')
sv, E, out, st = run(['/ok'], S5, cache, tag='s21e2'); print(f'  立即再跑:服务器收到 {len(sv.log)} 个;{hc(st)}')
time.sleep(3)
sv, E, out, st = run(['/ok'], S5, cache, tag='s21e3'); print(f'  3 秒后再跑:服务器收到 {len(sv.log)} 个;{hc(st)}')

print('== 六:meta dont_cache 跳过缓存;HTTPCACHE_IGNORE_MISSING 只读缓存(缓存里没有的请求直接忽略)')
cache = sdir('s21cache6'); run(['/ok'], {}, cache, tag='s21f1')
sv, E, out, st = run(['/ok'], {}, cache, meta="{'dont_cache': True}", tag='s21f2'); print(f'  dont_cache=True:服务器收到 {len(sv.log)} 个;{hc(st)}')
sv, E, out, st = run(['/ok', '/never-seen'], {'HTTPCACHE_IGNORE_MISSING': 1}, cache, tag='s21f3'); print(f'  HTTPCACHE_IGNORE_MISSING=1:服务器收到 {len(sv.log)} 个;{hc(st)};回调 {[x.get("p") for x in E if "status" in x]},错误 {[(x["p"], x["err"]) for x in E if "err" in x]}')

print('== 七:下载失败时用旧缓存兜底(stats httpcache/errorrecovery):RFC2616Policy 下 /etag 已缓存但需要重新验证,此时服务器关了(连接被拒)')
cache = sdir('s21cache7'); port = free_port(9990)
run(['/etag', '/ok'], P, cache, port=port, tag='s21g1')
sv, E, out, st = run(['/etag', '/ok'], dict(P, RETRY_ENABLED=0), cache, port=port, down=True, tag='s21g2')
print(f'  第二次运行服务器已关闭:stats {hc(st)};回调 {[(x["p"], x["status"], x["flags"]) for x in E if "status" in x]};错误 {[(x["p"], x["err"]) for x in E if "err" in x]}')
