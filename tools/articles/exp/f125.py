import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f125'); R = {}
import pathlib
from flask import Flask, send_from_directory, send_file, abort
from werkzeug.security import safe_join
from werkzeug.utils import secure_filename
base = FT / 'f125files'; shutil.rmtree(base, ignore_errors=True); (base / 'pub' / 'sub').mkdir(parents=True); outside = base / 'outside.txt'
outside.write_text('SENTINEL-OUTSIDE'); (base / 'pub' / 'a.txt').write_text('hello a'); (base / 'pub' / 'sub' / 'b.txt').write_text('hello b'); (base / 'pub' / '报告.txt').write_text('中文文件')
PUB = base / 'pub'
app = Flask('d'); app.logger.disabled = True
@app.get('/files/<path:name>')
def files(name): return send_from_directory(PUB, name)
@app.get('/dl/<path:name>')
def dl(name): return send_from_directory(PUB, name, as_attachment=True, download_name='下载 的文件.txt')
c = app.test_client()
def show(label, r): print(f'  {label:<38} → {r.status_code} {r.get_data(as_text=True)[:30]!r}'); return r
print('== 一:send_from_directory 对各种文件名的结果(目录外有一个哨兵文件 outside.txt)')
R['sfd'] = {}
for label, name in (('合法文件 a.txt', 'a.txt'), ('子目录里的 sub/b.txt', 'sub/b.txt'), ('不存在的文件', 'nope.txt'), ('先进再出 sub/../a.txt', 'sub/../a.txt'), ('跳到目录外 ../outside.txt', '../outside.txt'), ('嵌在中间 sub/../../outside.txt', 'sub/../../outside.txt'), ('绝对路径形式', '/outside.txt'), ('含空字节', 'a.txt%00.png'), ('目录本身 sub', 'sub')):
    r = c.get(f'/files/{name}'); show(label, r); R['sfd'][label] = [r.status_code, r.get_data(as_text=True)[:30]]
print('  目录外的哨兵内容有没有出现在任何响应里:', any('SENTINEL' in v[1] for v in R['sfd'].values()))
print()
print('== 二:safe_join 的返回值(None 表示拒绝)')
R['sj'] = {}
for name in ('a.txt', 'sub/b.txt', 'sub/../a.txt', '../outside.txt', '/outside.txt', 'sub/../../outside.txt', ''):
    v = safe_join(str(PUB), name); print(f'  safe_join(基目录, {name!r:<26}) → {str(v).replace(str(base), "<tmp>") if v else None}'); R['sj'][name] = str(v).replace(str(base), '<tmp>') if v else None
print()
print('== 三:符号链接:目录里的链接指向目录外时,send_from_directory 不会拦(它不解析符号链接)')
os.symlink(outside, PUB / 'link.txt'); r = c.get('/files/link.txt'); show('访问 pub/link.txt(链接到目录外)', r); R['symlink'] = [r.status_code, r.get_data(as_text=True)[:30]]
real = os.path.realpath(PUB / 'link.txt'); inside = os.path.commonpath([real, os.path.realpath(PUB)]) == os.path.realpath(PUB); print('  自己再检查 realpath 是否仍在基目录内:', inside, '(False 就该拒绝)'); R['realpath_check'] = inside
print()
print('== 四:下载响应头:as_attachment、中文文件名、Range、条件请求')
r = c.get('/dl/a.txt'); print('  Content-Disposition:', r.headers.get('Content-Disposition')); R['cd'] = r.headers.get('Content-Disposition')
r = c.get('/files/a.txt'); print('  Content-Type:', r.headers.get('Content-Type'), '| ETag:', bool(r.headers.get('ETag')), '| Last-Modified:', bool(r.headers.get('Last-Modified')), '| Cache-Control:', r.headers.get('Cache-Control'), '| Accept-Ranges:', r.headers.get('Accept-Ranges')); R['hdr'] = [r.headers.get('Content-Type'), r.headers.get('Cache-Control'), r.headers.get('Accept-Ranges')]
r2 = c.get('/files/a.txt', headers={'Range': 'bytes=0-4'}); print('  Range: bytes=0-4 →', r2.status_code, repr(r2.get_data(as_text=True)), '| Content-Range:', r2.headers.get('Content-Range')); R['range'] = [r2.status_code, r2.get_data(as_text=True), r2.headers.get('Content-Range')]
r3 = c.get('/files/a.txt', headers={'If-None-Match': r.headers['ETag']}); print('  If-None-Match →', r3.status_code); R['inm'] = r3.status_code
r4 = c.get('/files/报告.txt'); print('  中文名的文件 /files/报告.txt →', r4.status_code, r4.get_data(as_text=True)); R['cn'] = [r4.status_code, r4.get_data(as_text=True)]
print()
print('== 五:secure_filename 对上传文件名的处理(用来生成存盘文件名,不是用来做路径校验)')
R['sf'] = {}
for n in ('report.pdf', 'my file (1).txt', '../x.txt', 'a/b/c.txt', '报告.txt', '.hidden', '', 'CON.txt', 'a.tar.gz'):
    v = secure_filename(n); print(f'  secure_filename({n!r:<20}) → {v!r}'); R['sf'][n] = v
save('f125', R)
