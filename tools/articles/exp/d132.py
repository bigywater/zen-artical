import sys, os, time, json, re, subprocess, statistics, http.client, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
import asrv
tee('d132'); R = {}
urls = '''
import os
from django.urls import path
from django.http import HttpResponse, FileResponse
from django.template import engines
from django.conf import settings
def ping(r): return HttpResponse('ok')
def page(r):
    return HttpResponse(engines['django'].from_string("{% load static %}<link href=\\"{% static 'app.css' %}\\">").render({}))
def dyn(r): return FileResponse(open(os.path.join(settings.BASE_DIR, 'static', 'app.css'), 'rb'))
urlpatterns = [path('ping/', ping), path('page/', page), path('dyn/', dyn)]
'''
files = {'static/app.css': 'body { background: url("img.png"); }\n' + '/* padding */\n' * 200, 'static/img.png': 'PNG-fake\n'}
d = proj('d132', files=files, urls=urls, apps=['django.contrib.contenttypes', 'django.contrib.staticfiles', 'django.contrib.admin'], with_lab=False, middleware=[], settings_extra=ES + "\nSTATICFILES_DIRS = [BASE_DIR / 'static']\nSTATIC_ROOT = BASE_DIR / 'staticroot'\n")
GUN = str(asrv.BIN / 'gunicorn')
WN = ['whitenoise.middleware.WhiteNoiseMiddleware']
def serve(port, **st):
    return asrv.serve(d, 'gunicorn', port, EXTRA_SETTINGS=json.dumps(dict(ALLOWED_HOSTS=['*'], DEBUG=False, **st)))
def hdrs(port, path='/static/app.css'):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=10); c.request('GET', path); r = c.getresponse(); b = r.read(); return r.status, {k.lower(): v for k, v in r.getheaders()}, b
print('== 一:DEBUG=False、没有 collectstatic、没有静态文件服务:Django 不会提供 /static/')
p = serve(9570)
try: st, h, b = hdrs(9570); print('  GET /static/app.css →', st)
finally: asrv.stop(p)
R['no_serve'] = st
print()
print('== 二:python manage.py collectstatic(INSTALLED_APPS 里有 admin)')
shutil.rmtree(d / 'staticroot', ignore_errors=True)
rc, out1 = smanage(d, 'collectstatic', '--noinput', ALLOWED_HOSTS=['*'], DEBUG=False)
n = sum(1 for _ in (d / 'staticroot').rglob('*') if _.is_file())
print('  输出最后一行:', re.sub(r" to '.*", ' to STATIC_ROOT', out1.strip().splitlines()[-1])); print('  STATIC_ROOT 里的文件数:', n, ' 其中来自自己的 static/:', sorted(x.name for x in (d / 'staticroot').iterdir() if x.is_file()), ' 子目录:', sorted(x.name for x in (d / 'staticroot').iterdir() if x.is_dir()))
R['collect'] = dict(n=n)
rc, out2 = smanage(d, 'collectstatic', '--noinput', ALLOWED_HOSTS=['*'], DEBUG=False)
print('  不改文件再运行一次:', re.sub(r" to '.*", ' to STATIC_ROOT', out2.strip().splitlines()[-1]))
R['collect2'] = re.sub(r" to '.*", ' to STATIC_ROOT', out2.strip().splitlines()[-1])
print()
print('== 三:collectstatic 之后,只靠 gunicorn 仍然 404;加上 WhiteNoise 中间件才有')
p = serve(9571)
try: st1 = hdrs(9571)[0]
finally: asrv.stop(p)
p = serve(9572, MIDDLEWARE=WN)
try: st2, h, b = hdrs(9572)
finally: asrv.stop(p)
print(f'  collectstatic 之后没有中间件   → {st1}'); print(f'  加 WhiteNoiseMiddleware        → {st2}  Content-Length {h.get("content-length")}  Cache-Control: {h.get("cache-control")}  Last-Modified 有: {"last-modified" in h}')
R['wn'] = dict(without=st1, with_=st2, cc=h.get('cache-control'))
print()
print('== 四:ManifestStaticFilesStorage:模板里 {% static %} 在没有 collectstatic 与 collectstatic 之后')
MAN = dict(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'}})
shutil.rmtree(d / 'staticroot', ignore_errors=True)
p = serve(9573, MIDDLEWARE=WN, **MAN)
try: st, h, b = hdrs(9573, '/page/'); print('  没有 collectstatic,GET /page/ →', st, '(模板渲染抛异常)')
finally: asrv.stop(p)
o = srun(d, "from django.template import engines\ntry: engines['django'].from_string(\"{% load static %}{% static 'app.css' %}\").render({})\nexcept Exception as e: print('  同样的模板在脚本里渲染 →', type(e).__name__ + ':', e)", DEBUG=False, ALLOWED_HOSTS=['*'], **MAN)
print(o); R['manifest_missing'] = dict(status=st, msg=o)
smanage(d, 'collectstatic', '--noinput', ALLOWED_HOSTS=['*'], DEBUG=False, **MAN)
p = serve(9574, MIDDLEWARE=WN, **MAN)
try:
    st, h, b = hdrs(9574, '/page/'); print('  collectstatic 之后,GET /page/ →', st, b.decode())
    m = re.search(r'/static/(app\.[0-9a-f]+\.css)', b.decode()); hn = m.group(1) if m else None
    st2, h2, b2 = hdrs(9574, '/static/' + hn) if hn else (0, {}, b'')
    print(f'  GET /static/{hn} → {st2}  Cache-Control: {h2.get("cache-control")}'); css = b2.decode()
    print('  CSS 里的 url() 被改写成:', re.search(r'url\("?([^")]+)', css).group(1) if css else None)
    R['manifest_ok'] = dict(name=hn, cc=h2.get('cache-control'))
finally: asrv.stop(p)
print()
print('== 五:WhiteNoise 提供静态文件 vs Django 视图用 FileResponse 读同一个文件:200 个串行请求的中位延迟(1 个 sync worker)')
p = serve(9575, MIDDLEWARE=WN)
try:
    def med(path, n=200):
        for _ in range(20): hdrs(9575, path)
        xs = []
        for _ in range(n): t0 = time.perf_counter(); hdrs(9575, path); xs.append((time.perf_counter() - t0) * 1000)
        return statistics.median(xs)
    a, b_ = med('/static/app.css'), med('/dyn/'); print(f'  WhiteNoise /static/app.css  {a:.3f} ms'); print(f'  FileResponse 视图 /dyn/      {b_:.3f} ms'); R['lat'] = dict(wn=a, dyn=b_)
finally: asrv.stop(p)
save('d132', R)
