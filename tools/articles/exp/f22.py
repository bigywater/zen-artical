import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f22'); R = {}
from flask import Flask
d = mkapp('f22', {'main.py': '''
from flask import Flask
app = Flask(__name__)
app2 = Flask(__name__, static_folder="assets", static_url_path="/files")
app3 = Flask(__name__, static_folder=None)
app4 = Flask(__name__, static_url_path="")
''', 'static/app.js': 'console.log("hi")\n', 'static/css/site.css': 'body{color:red}\n', 'static/big.bin': 'x' * 10000, 'static/.hidden': 'h', 'assets/logo.txt': 'LOGO', 'secret.txt': 'TOP SECRET'})
import importlib.util
sys.path.insert(0, str(d)); os.chdir(d)
import main
c = main.app.test_client()
def show(r, names=('Content-Type', 'Content-Length', 'Cache-Control', 'ETag', 'Last-Modified', 'Content-Range', 'Accept-Ranges')):
    return f'{r.status_code}  ' + ' | '.join(f'{n}: {r.headers[n]}' for n in names if n in r.headers)
print('== 一:默认的 /static 路由:能访问 static 目录下的文件;不存在返回 404;目录与隐藏文件')
R['basic'] = {}
for p in ('/static/app.js', '/static/css/site.css', '/static/nope.js', '/static/css/', '/static/.hidden'):
    r = c.get(p); R['basic'][p] = show(r, ('Content-Type', 'Content-Length')); print(f'  GET {p:<22} → {R["basic"][p]}')
print()
print('== 二:路径穿越:../ 出不了 static 目录(werkzeug 的 safe_join)')
R['trav'] = {}
for p in ('/static/../secret.txt', '/static/%2e%2e/secret.txt', '/static/css/../../secret.txt', '/static/..%2fsecret.txt', '/static//etc/passwd'):
    r = c.get(p); R['trav'][p] = r.status_code; print(f'  GET {p:<34} → {r.status_code}' + (f' Location={r.headers.get("Location")}' if r.status_code in (301, 302, 308) else ''))
print('  同一个文件直接请求 /static/app.js →', c.get('/static/app.js').status_code, '| secret.txt 在 static 目录之外,没有任何一种写法读到:', all(v != 200 for v in R['trav'].values()))
print()
print('== 三:缓存相关的头:ETag、Last-Modified、Cache-Control,以及条件请求(304)')
r = c.get('/static/app.js'); print('  首次:', show(r)); R['hdr'] = dict(r.headers)
etag = r.headers['ETag']; lm = r.headers['Last-Modified']
r2 = c.get('/static/app.js', headers={'If-None-Match': etag}); print('  If-None-Match =', etag, '→', r2.status_code, '| 正文长度', len(r2.data)); R['inm'] = [r2.status_code, len(r2.data)]
r3 = c.get('/static/app.js', headers={'If-Modified-Since': lm}); print('  If-Modified-Since =', lm, '→', r3.status_code); R['ims'] = r3.status_code
print('  config SEND_FILE_MAX_AGE_DEFAULT =', main.app.config['SEND_FILE_MAX_AGE_DEFAULT'], '(None → Cache-Control: no-cache)'); R['maxage_default'] = main.app.config['SEND_FILE_MAX_AGE_DEFAULT']
main.app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600; r4 = main.app.test_client().get('/static/app.js'); print('  设成 3600 后:', show(r4, ('Cache-Control', 'Expires'))); R['maxage_3600'] = [r4.headers.get('Cache-Control'), r4.headers.get('Expires')]; main.app.config['SEND_FILE_MAX_AGE_DEFAULT'] = None
print()
print('== 四:Range 请求:静态文件支持断点下载')
r = c.get('/static/big.bin', headers={'Range': 'bytes=0-99'}); print('  Range: bytes=0-99 →', show(r)); R['range'] = [r.status_code, r.headers.get('Content-Range'), len(r.data)]
r = c.head('/static/app.js'); print('  HEAD →', show(r), '| 正文长度', len(r.data)); R['head'] = [r.status_code, r.headers.get('Content-Length'), len(r.data)]
print()
print('== 五:自定义 static_folder 与 static_url_path;static_folder=None;static_url_path="" 把静态文件挂在根路径')
c2 = main.app2.test_client(); print('  app2(static_folder="assets", static_url_path="/files"):', {p: c2.get(p).status_code for p in ('/files/logo.txt', '/static/logo.txt')}); R['app2'] = {p: c2.get(p).status_code for p in ('/files/logo.txt', '/static/logo.txt')}
print('  app2 的规则:', [str(r) for r in main.app2.url_map.iter_rules()])
c3 = main.app3.test_client(); print('  app3(static_folder=None):规则 =', [str(r) for r in main.app3.url_map.iter_rules()], '| GET /static/app.js →', c3.get('/static/app.js').status_code); R['app3'] = c3.get('/static/app.js').status_code
c4 = main.app4.test_client(); print('  app4(static_url_path=""):', {p: c4.get(p).status_code for p in ('/app.js', '/css/site.css', '/nope')}, '| 规则 =', [str(r) for r in main.app4.url_map.iter_rules()]); R['app4'] = {p: c4.get(p).status_code for p in ('/app.js', '/css/site.css', '/nope')}
print()
print('== 六:Flask 发静态文件的开销:发 10 KB 文件的耗时(test client,3000 次)与直接读文件的耗时')
import timeit
tf = min(timeit.timeit(lambda: c.get('/static/big.bin'), number=3000) / 3000 * 1e6 for _ in range(3)); tr = min(timeit.timeit(lambda: open(d / 'static' / 'big.bin', 'rb').read(), number=3000) / 3000 * 1e6 for _ in range(3))
print(f'  Flask /static 每个请求 {tf:.1f} µs;直接 open().read() 同一个文件 {tr:.1f} µs'); R['cost'] = [tf, tr]
save('f22', R)
