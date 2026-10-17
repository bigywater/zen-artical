import sys, os, time, json, re, signal, http.client, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d90'); R = {}
GUN = str(HERE.parent / 'djlab' / 'bin' / 'gunicorn')
css = ('.card{margin:0 auto;padding:1rem 2rem;border:1px solid #ccc;border-radius:8px}\n' * 400)
files = {'assets/css/site.css': css, 'assets/js/app.js': 'console.log("hello");\n' * 300, 'assets/img/tiny.png': 'PNGDATA' * 10, 'media/upload.txt': 'user upload'}
urls = "from django.urls import path\nfrom django.http import HttpResponse\nurlpatterns = [path('', lambda r: HttpResponse('home'))]\n"
def make(debug, whitenoise):
    mw = ['django.middleware.security.SecurityMiddleware'] + (['whitenoise.middleware.WhiteNoiseMiddleware'] if whitenoise else [])
    stor = "'whitenoise.storage.CompressedManifestStaticFilesStorage'" if whitenoise else "'django.contrib.staticfiles.storage.StaticFilesStorage'"
    ex = f"\nDEBUG = {debug}\nSTATICFILES_DIRS = [BASE_DIR / 'assets']\nSTATIC_ROOT = BASE_DIR / 'collected'\nMEDIA_ROOT = BASE_DIR / 'media'\nMEDIA_URL = 'media/'\nSTORAGES = {{'default': {{'BACKEND': 'django.core.files.storage.FileSystemStorage'}}, 'staticfiles': {{'BACKEND': {stor}}}}}\n"
    d = proj('d90', files=files, urls=urls, apps=['django.contrib.contenttypes', 'django.contrib.staticfiles'], middleware=mw, with_lab=False, settings_extra=ex)
    if not debug or whitenoise: manage(d, 'collectstatic', '--noinput')
    return d
PORT = 9450
def serve(d, runserver=False):
    cmd = [PY, 'manage.py', 'runserver', f'127.0.0.1:{PORT}', '--noreload'] if runserver else [GUN, 'proj.wsgi:application', '-b', f'127.0.0.1:{PORT}', '-w', '1', '--log-level', 'error']
    p = subprocess.Popen(cmd, cwd=d, env=env(d), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try: http.client.HTTPConnection('127.0.0.1', PORT, timeout=1).request('GET', '/'); break
        except Exception: time.sleep(0.1)
    time.sleep(0.4); return p
def stop(p):
    p.send_signal(signal.SIGTERM)
    try: p.wait(10)
    except Exception: p.kill()
    subprocess.run(['pkill', '-f', f'127.0.0.1:{PORT}'], capture_output=True); time.sleep(0.5)
def get(path, headers=None):
    c = http.client.HTTPConnection('127.0.0.1', PORT, timeout=10); c.request('GET', path, headers=headers or {}); r = c.getresponse(); b = r.read(); return r.status, {k.lower(): v for k, v in r.getheaders()}, len(b)
KEYS = ('cache-control', 'etag', 'last-modified', 'content-encoding', 'content-length', 'vary', 'content-type')
def show(label, st, h, n): print(f'  {label:<44} status {st}  ' + '  '.join(f'{k}={h[k]}' for k in KEYS if k in h) + f'  (响应体 {n} 字节)')
print('== 一:runserver(DEBUG=True,staticfiles app 直接从源目录提供):响应头')
d = make(True, False); p = serve(d, runserver=True)
st, h, n = get('/static/css/site.css'); show('/static/css/site.css', st, h, n); R['dev'] = dict(status=st, headers={k: h.get(k) for k in KEYS}, size=n)
st2, h2, n2 = get('/static/css/site.css', {'If-Modified-Since': h.get('last-modified', '')}); show('带 If-Modified-Since', st2, h2, n2); R['dev_304'] = st2
st3, h3, n3 = get('/media/upload.txt'); show('/media/upload.txt(runserver 不服务媒体文件)', st3, h3, n3); R['dev_media'] = st3
stop(p)
print()
print('== 二:gunicorn + DEBUG=False + 没有 WhiteNoise:Django 自己不提供静态文件')
d = make(False, False); p = serve(d)
st, h, n = get('/static/css/site.css'); show('/static/css/site.css', st, h, n); R['prod_plain'] = st
stop(p)
print()
print('== 三:gunicorn + DEBUG=False + WhiteNoise(CompressedManifestStaticFilesStorage)')
d = make(False, True); p = serve(d)
col = d / 'collected'; fl = sorted(str(x.relative_to(col)) for x in col.rglob('*') if x.is_file() and x.name != 'staticfiles.json'); print('  collected 下的文件:', fl); R['files'] = fl
hashed = [f for f in fl if re.search(r'site\.[0-9a-f]{12}\.css$', f)][0]
R['sizes'] = {f: (col / f).stat().st_size for f in fl if f.startswith('css/site')}
st, h, n = get('/static/' + hashed); show('带哈希的文件(不带 Accept-Encoding)', st, h, n); R['hashed'] = dict(status=st, headers={k: h.get(k) for k in KEYS}, size=n)
st, h, n = get('/static/' + hashed, {'Accept-Encoding': 'gzip'}); show('带哈希 + Accept-Encoding: gzip', st, h, n); R['hashed_gz'] = dict(headers={k: h.get(k) for k in KEYS}, size=n)
st, h, n = get('/static/' + hashed, {'Accept-Encoding': 'br, gzip'}); show('带哈希 + Accept-Encoding: br, gzip', st, h, n); R['hashed_br'] = dict(headers={k: h.get(k) for k in KEYS}, size=n)
st, h, n = get('/static/css/site.css'); show('原名(没有哈希)', st, h, n); R['plain'] = dict(status=st, headers={k: h.get(k) for k in KEYS}, size=n)
st, h0, n = get('/static/' + hashed); st2, h2, n2 = get('/static/' + hashed, {'If-None-Match': h0.get('etag', '')}); show('If-None-Match(带上上面的 ETag)', st2, h2, n2); R['etag304'] = st2
st3, h3, n3 = get('/media/upload.txt'); show('/media/upload.txt(WhiteNoise 不服务 MEDIA)', st3, h3, n3); R['media'] = st3
stop(p)
save('d90', R)
