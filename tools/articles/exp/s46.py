import sys, os, hashlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s46'); reset_s()
PDF = b'%PDF-1.4\n' + os.urandom(20000)
class Site:
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(h.path); p = h.path.split('?')[0]
        if p == '/': h.reply(200, '<html>index</html>', {'Content-Type': 'text/html'})
        elif p == '/f/a.txt': h.reply(200, b'hello file a\n', {'Content-Type': 'text/plain'})
        elif p == '/f/b.pdf': h.reply(200, PDF, {'Content-Type': 'application/pdf'})
        elif p == '/dl': h.reply(200, PDF, {'Content-Type': 'application/pdf', 'Content-Disposition': 'attachment; filename="report.pdf"'})
        elif p == '/f/redir': h.reply(302, b'', {'Location': '/f/a.txt'})
        else: h.reply(404, 'nf', {'Content-Type': 'text/plain'})
URLS = ['/f/a.txt', '/f/b.pdf', '/dl?id=3', '/f/a.txt', '/f/missing.txt', '/f/redir']
def go(store, urls=URLS, settings=None, extra='', tag='s46', sv=None):
    d = sdir(tag); sv = sv or Site()
    with Srv(sv) as s:
        code = f"""
import scrapy
{extra}
class S(scrapy.Spider):
    name = 's'
    custom_settings = {{'ITEM_PIPELINES': {{PIPE: 1}}, 'FILES_STORE': {str(store)!r}}}
    async def start(self): yield scrapy.Request('{s.url("/")}')
    def parse(self, response): yield {{'title': 'x', 'file_urls': [response.urljoin(u) for u in {urls!r}]}}
class PIPE_PLACEHOLDER: pass
""".replace('PIPE_PLACEHOLDER', 'XX')
        code = code.replace("{PIPE: 1}", "{'scrapy.pipelines.files.FilesPipeline': 1}") if 'MyFiles' not in extra else code.replace("{PIPE: 1}", "{MyFiles: 1}")
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO'}, **(settings or {})))
    return sv, ev(d), out, stats(out)
def fs(st): return {k: v for k, v in sorted(st.items()) if k.startswith('file_')}
def listing(store):
    return [(str(p.relative_to(store)), p.stat().st_size) for p in sorted(store.rglob('*')) if p.is_file()]
code_item_dump = "class Dump:\n    def process_item(self, item): EV(files=item.get('files'), urls=len(item['file_urls'])); return item\n"

print('== 一:FilesPipeline:item 里的 file_urls 列表(6 个 URL:a.txt 出现两次、b.pdf、无扩展名的 /dl?id=3、404、302 重定向)→ 下载到 FILES_STORE/full/<SHA1(URL)><扩展名>;结果写进 item["files"]')
store = sdir('s46store1')
sv, E, out, st = go(store, extra=code_item_dump.replace('class Dump', 'class Dump') , settings={'ITEM_PIPELINES': json.dumps({'scrapy.pipelines.files.FilesPipeline': 1, 'spider.Dump': 2}), 'FILES_STORE': str(store)})
fl = [x for x in E if 'files' in x][0]
print(f'  服务器收到的请求:{sv.log}')
from urllib.parse import urlparse
print(f'  item["files"] 共 {len(fl["files"])} 个结果(file_urls 有 {fl["urls"]} 个:a.txt 出现两次得到两条同样的结果但只请求了一次,404 与 302 没有结果):')
for f in fl['files']: print(f'    status={f["status"]:<10}path={f["path"]:<50}checksum={f["checksum"]}   url={urlparse(f["url"]).path}' + ('?' + urlparse(f['url']).query if urlparse(f['url']).query else ''))
print('  磁盘上:' + ', '.join(f'{p}({n} 字节)' for p, n in listing(store)))
print(f'  SHA1("http://…/f/a.txt") 对得上文件名:{any(hashlib.sha1(f["url"].encode()).hexdigest() in f["path"] for f in fl["files"])};stats {fs(st)}')
print('  日志:' + ' | '.join(l.split('] ', 1)[1].strip()[:120] for l in out.split('\n') if 'File (' in l and 'WARNING' in l))
expected_md5 = hashlib.md5(b'hello file a\n').hexdigest()
print(f'  a.txt 的 checksum = md5 内容:{expected_md5 in [f["checksum"] for f in fl["files"]]}')

print('== 二:第二次运行(同一个 FILES_STORE):已经下载过且没过期的文件状态变成 uptodate,不再请求服务器;FILES_EXPIRES 控制过期(天)')
sv2 = Site()
sv_, E, out, st = go(store, extra=code_item_dump, settings={'ITEM_PIPELINES': json.dumps({'scrapy.pipelines.files.FilesPipeline': 1, 'spider.Dump': 2}), 'FILES_STORE': str(store)}, sv=sv2)
fl = [x for x in E if 'files' in x][0]
print(f'  第二次:服务器收到 {[p for p in sv2.log]};files 状态 {[f["status"] for f in fl["files"]]};stats {fs(st)}')
sv3 = Site()
sv_, E, out, st = go(store, extra=code_item_dump, settings={'ITEM_PIPELINES': json.dumps({'scrapy.pipelines.files.FilesPipeline': 1, 'spider.Dump': 2}), 'FILES_STORE': str(store), 'FILES_EXPIRES': 0}, sv=sv3)
fl = [x for x in E if 'files' in x][0]
print(f'  FILES_EXPIRES=0(任何已有的文件都算过期):服务器收到 {sv3.log};files 状态 {[f["status"] for f in fl["files"]]}')

print('== 三:重定向与 MEDIA_ALLOW_REDIRECTS:文件 URL 返回 302 时,默认不跟着走(下载失败),设 True 才跟')
for tag, val in (('默认(False)', None), ('MEDIA_ALLOW_REDIRECTS=True', 'True')):
    store3 = sdir('s46store3')
    st_ = {'ITEM_PIPELINES': json.dumps({'scrapy.pipelines.files.FilesPipeline': 1, 'spider.Dump': 2}), 'FILES_STORE': str(store3)}
    if val: st_['MEDIA_ALLOW_REDIRECTS'] = val
    sv, E, out, st = go(store3, urls=['/f/redir'], extra=code_item_dump, settings=st_)
    fl = [x for x in E if 'files' in x][0]
    print(f'  {tag}:files={[{k: v for k, v in f.items() if k in ("status", "path")} for f in fl["files"]]};服务器收到 {sv.log};日志 {[l.split("] ", 1)[1].strip()[:100] for l in out.split(chr(10)) if "File (" in l][:1]}')

print('== 四:自定义文件名:子类重写 file_path(),用 URL 里的原始文件名(或 Content-Disposition)')
EXTRA = '''
from scrapy.pipelines.files import FilesPipeline
from urllib.parse import urlparse
import os as _os
class MyFiles(FilesPipeline):
    def file_path(self, request, response=None, info=None, *, item=None):
        return 'by-name/' + (_os.path.basename(urlparse(request.url).path) or 'index') + ('-' + urlparse(request.url).query.replace('=', '') if urlparse(request.url).query else '')
''' + code_item_dump
store4 = sdir('s46store4')
sv, E, out, st = go(store4, urls=['/f/a.txt', '/f/b.pdf', '/dl?id=3'], extra=EXTRA, settings={'ITEM_PIPELINES': json.dumps({'spider.MyFiles': 1, 'spider.Dump': 2}), 'FILES_STORE': str(store4)})
print('  磁盘上:' + ', '.join(f'{p}({n} 字节)' for p, n in listing(store4)))
