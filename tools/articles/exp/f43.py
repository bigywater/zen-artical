import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f43'); R = {}
import io, threading
from flask import Flask, send_file, send_from_directory, abort
d = mkapp('f43', {'main.py': '''
import io, os
from flask import Flask, send_file, send_from_directory, abort
app = Flask(__name__)
@app.get("/file")
def f(): return send_file("data/report.txt")
@app.get("/abs")
def a(): return send_file(os.path.join(app.root_path, "data", "report.txt"))
@app.get("/dl")
def dl(): return send_file("data/report.txt", as_attachment=True)
@app.get("/dl-cn")
def dlcn(): return send_file("data/report.txt", as_attachment=True, download_name="月度 报告(1).txt")
@app.get("/mem")
def mem(): return send_file(io.BytesIO(b"in memory"), mimetype="text/plain", download_name="m.txt")
@app.get("/mem-bad")
def membad(): return send_file(io.BytesIO(b"in memory"))
@app.get("/mem-name")
def memname(): return send_file(io.BytesIO(b"a,b\\n1,2\\n"), download_name="export.csv")
@app.get("/nocache")
def nc(): return send_file("data/report.txt", max_age=0, etag=False, last_modified=None)
@app.get("/age")
def age(): return send_file("data/report.txt", max_age=3600)
@app.get("/nocond")
def nocond(): return send_file("data/report.txt", conditional=False)
@app.get("/dir/<path:name>")
def sd(name): return send_from_directory(os.path.join(app.root_path, "data"), name)
@app.get("/dir-rel/<path:name>")
def sdr(name): return send_from_directory("data", name)
@app.get("/missing")
def missing(): return send_file("data/nope.txt")
@app.get("/typ/<name>")
def typ(name): return send_file(f"data/{name}")
@app.get("/override")
def ov(): return send_file("data/report.txt", mimetype="application/x-custom")
@app.get("/env")
def env_(): return {"file_wrapper": str(request.environ.get("wsgi.file_wrapper"))}
from flask import request
''', 'data/report.txt': 'quarterly report\n', 'data/pic.png': 'PNGDATA', 'data/page.html': '<b>x</b>', 'data/note.md': '# n', 'data/data.json': '{}', 'data/archive.tar.gz': 'z', 'data/noext': 'n', 'data/script.js': 'x', 'secret.txt': 'SECRET OUTSIDE'})
sys.path.insert(0, str(d)); os.chdir(d)
import main
app = main.app; app.logger.disabled = True; c = app.test_client()
def H(r, names=('Content-Type', 'Content-Length', 'Content-Disposition', 'Cache-Control', 'ETag', 'Last-Modified', 'Expires', 'X-Sendfile')): return ' | '.join(f'{n}: {r.headers[n]}' for n in names if n in r.headers)
print('== 一:send_file 一个文件:头里有什么;相对路径相对 app.root_path;as_attachment 与 download_name')
R['one'] = {}
for p in ('/file', '/abs', '/dl', '/dl-cn'):
    r = c.get(p); R['one'][p] = [r.status_code, H(r)]; print(f'  GET {p:<7} → {r.status_code} {H(r)}')
print()
print('== 二:内存里的文件(BytesIO):必须给 mimetype 或 download_name,否则 TypeError')
for p in ('/mem', '/mem-bad', '/mem-name'):
    try: r = c.get(p); print(f'  GET {p:<9} → {r.status_code} {H(r, ("Content-Type", "Content-Disposition", "Content-Length", "ETag", "Last-Modified")) or r.get_data(as_text=True)[:60]}'); R.setdefault('mem', {})[p] = [r.status_code, H(r)]
    except Exception as e: print(f'  GET {p:<9} → 抛出 {type(e).__name__}: {" ".join(str(e).split())[:150]}'); R.setdefault('mem', {})[p] = [type(e).__name__, ' '.join(str(e).split())]
with app.test_request_context('/'):
    try: main.membad()
    except Exception as e: print('  直接调用 /mem-bad 的视图 →', type(e).__name__ + ':', ' '.join(str(e).split())[:220]); R['membad'] = [type(e).__name__, ' '.join(str(e).split())]
print()
print('== 三:缓存相关参数:max_age、etag、last_modified、conditional;默认 Cache-Control 是 no-cache')
for p in ('/age', '/nocache', '/nocond'): r = c.get(p); print(f'  GET {p:<9} → {r.status_code} {H(r, ("Cache-Control", "ETag", "Last-Modified", "Expires"))}'); R.setdefault('cache', {})[p] = H(r, ('Cache-Control', 'ETag', 'Last-Modified', 'Expires'))
r = c.get('/file'); etag = r.headers['ETag']
r2 = c.get('/file', headers={'If-None-Match': etag}); print('  带 If-None-Match →', r2.status_code, '| 正文', len(r2.data), '字节'); R['inm'] = [r2.status_code, len(r2.data)]
r3 = c.get('/nocond', headers={'If-None-Match': etag}); print('  conditional=False 的路由带 If-None-Match →', r3.status_code); R['nocond_inm'] = r3.status_code
print()
print('== 四:send_from_directory:目录加不可信的文件名;路径穿越返回 404')
R['sd'] = {}
for p in ('/dir/report.txt', '/dir/../secret.txt', '/dir/..%2fsecret.txt', '/dir/%2e%2e/secret.txt', '/dir//etc/passwd', '/dir/sub/../report.txt', '/dir/nope.txt', '/dir-rel/report.txt'):
    r = c.get(p); R['sd'][p] = r.status_code; print(f'  GET {p:<28} → {r.status_code}')
with app.test_request_context('/'):
    try: main.missing()
    except Exception as e: print('  找不到文件 send_file("data/nope.txt") → 视图里抛出', type(e).__name__, '→ 经过 HTTP 是', c.get('/missing').status_code); R['missing'] = [type(e).__name__, c.get('/missing').status_code]
    try: send_from_directory(os.path.join(app.root_path, 'data'), 'nope.txt')
    except Exception as e: print('  找不到文件 send_from_directory(目录, "nope.txt") →', type(e).__name__, '→ HTTP', c.get('/dir/nope.txt').status_code); R['missing_sd'] = [type(e).__name__, c.get('/dir/nope.txt').status_code]
print()
print('== 五:Content-Type 靠文件扩展名猜(mimetypes 模块);可以用 mimetype= 覆盖')
R['types'] = {}
for name in ('report.txt', 'pic.png', 'page.html', 'note.md', 'data.json', 'archive.tar.gz', 'noext', 'script.js'):
    r = c.get('/typ/' + name); R['types'][name] = r.content_type; print(f'  {name:<16} → {r.content_type}')
print('  覆盖 mimetype="application/x-custom" →', c.get('/override').content_type); R['override'] = c.get('/override').content_type
print()
print('== 六:USE_X_SENDFILE:让前面的 Nginx/Apache 发文件,Flask 只返回头(自己得配合服务器规则)')
app.config['USE_X_SENDFILE'] = True; r = c.get('/file'); print('  USE_X_SENDFILE=True → 状态', r.status_code, '| X-Sendfile =', (r.headers.get('X-Sendfile') or '').replace(str(d), '<项目>'), '| 正文长度', len(r.data)); R['xsend'] = [r.status_code, (r.headers.get('X-Sendfile') or '').replace(str(d), '<项目>'), len(r.data)]; app.config['USE_X_SENDFILE'] = False
print()
print('== 七:真实服务器下 wsgi.file_wrapper 是什么(影响是否用 sendfile 系统调用),以及下载 300 MB 文件的峰值内存')
big = d / 'data' / 'big.bin'
with open(big, 'wb') as f_:
    for _ in range(300): f_.write(b'x' * 1024 * 1024)
(d / 'main.py').write_text((d / 'main.py').read_text() + '\n@app.get("/big-sendfile")\ndef bs(): return send_file("data/big.bin")\n@app.get("/big-read")\ndef br(): return open("data/big.bin", "rb").read()\n')
def rss_of_tree(pid):
    kids = subprocess.run(['pgrep', '-P', str(pid)], capture_output=True, text=True).stdout.split(); tot = 0
    for p in [str(pid)] + kids:
        o = subprocess.run(['ps', '-o', 'rss=', '-p', p], capture_output=True, text=True).stdout.strip(); tot = max(tot, int(o) if o else 0)
    return tot / 1024
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--workers', '1', 'main:app']) as s:
    r = subprocess.run(['curl', '-s', f'http://127.0.0.1:{s.port}/env'], capture_output=True, text=True); print('  gunicorn 下 wsgi.file_wrapper =', r.stdout.strip()); R['wrapper'] = r.stdout.strip()
    base = rss_of_tree(s.p.pid); R['mem'] = {}
    for label, path in (('send_file', '/big-sendfile'), ('open().read() 整个读进内存', '/big-read')):
        stop = [False]; peak = [0.0]
        def poll():
            while not stop[0]: peak[0] = max(peak[0], rss_of_tree(s.p.pid)); time.sleep(0.02)
        th = threading.Thread(target=poll); th.start(); r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{size_download} 字节 %{time_total}s', f'http://127.0.0.1:{s.port}{path}'], capture_output=True, text=True); stop[0] = True; th.join()
        R['mem'][label] = [round(peak[0]), r.stdout.strip()]; print(f'  {label:<24} 峰值 RSS ≈ {peak[0]:.0f} MiB(基线 {base:.0f} MiB)| curl:{r.stdout.strip()}')
    R['base'] = round(base)
big.unlink()
save('f43', R)
