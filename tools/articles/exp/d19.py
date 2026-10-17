import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d19'); R = {}
d = proj('d19', apps=['django.contrib.contenttypes'], with_lab=False, urls="from django.urls import path\nfrom django.http import HttpResponse, JsonResponse\ndef probe(request):\n    try: b = request.body\n    except Exception as e: return HttpResponse(type(e).__name__ + ': ' + str(e)[:80], status=400)\n    return HttpResponse('body 长度 %d' % len(b))\nurlpatterns = [path('probe/', probe)]\n")
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\n" + code); return out.rstrip()
print('== 一:body / POST / read() 的读取顺序:请求体只能读一次,Django 缓存了哪些')
o = run('''
from django.test import RequestFactory
rf = RequestFactory()
def mk(kind):
    if kind == 'urlencoded': return rf.post('/x/', 'a=1&b=2', content_type='application/x-www-form-urlencoded')
    if kind == 'multipart': return rf.post('/x/', {'a': '1', 'b': '2'}, content_type='multipart/form-data; boundary=BOUND') if False else rf.post('/x/', {'a': '1', 'f': __import__('io').BytesIO(b'filedata')})
    if kind == 'json': return rf.post('/x/', '{"a": 1}', content_type='application/json')
def attempt(kind, order):
    r = mk(kind); out = []
    for step in order:
        try:
            if step == 'POST': out.append('POST=' + str(dict(r.POST.lists())))
            elif step == 'body': out.append('body=' + repr(r.body[:40]))
            elif step == 'read': out.append('read()=' + repr(r.read(5)))
        except Exception as e: out.append(step + ' → ' + type(e).__name__ + ': ' + str(e)[:70])
    return out
for kind in ('urlencoded', 'multipart', 'json'):
    for order in (('POST', 'body'), ('body', 'POST'), ('read', 'body'), ('read', 'POST')):
        print(f'[{kind:<10}] 先 {order[0]:<4} 再 {order[1]:<4}:', ' | '.join(attempt(kind, order)))
''')
print(o); R['orders'] = o
print()
print('== 二:PUT / PATCH 的表单体不会被解析成 POST')
o = run('''
from django.test import RequestFactory
rf = RequestFactory()
for m in ('post', 'put', 'patch'):
    r = getattr(rf, m)('/x/', 'a=1&b=2', content_type='application/x-www-form-urlencoded')
    print(f'{m.upper():<6} request.POST = {dict(r.POST.lists())}   request.body = {r.body!r}')
''')
print(o); R['put'] = o
print()
print('== 三:DATA_UPLOAD_MAX_MEMORY_SIZE(默认值与超过时的行为)')
o = run('''
from django.conf import settings
from django.test import Client
print('DATA_UPLOAD_MAX_MEMORY_SIZE 默认 =', settings.DATA_UPLOAD_MAX_MEMORY_SIZE, '字节(%.2f MiB)' % (settings.DATA_UPLOAD_MAX_MEMORY_SIZE / 1048576))
c = Client(raise_request_exception=False)
for size in (settings.DATA_UPLOAD_MAX_MEMORY_SIZE, settings.DATA_UPLOAD_MAX_MEMORY_SIZE + 1):
    r = c.post('/probe/', b'x' * size, content_type='application/octet-stream'); print(f'JSON/二进制体 {size} 字节 → status {r.status_code}  {r.content.decode()[:110]}')
r = c.post('/probe/', {'f': __import__('io').BytesIO(b'x' * (settings.DATA_UPLOAD_MAX_MEMORY_SIZE + 1000))}); print('multipart 里的文件 2.5MiB+1000 字节 → status', r.status_code, r.content.decode()[:60])
''')
print(o); R['limit'] = o
print()
print('== 四:一个请求对象的内部:_stream / body 缓存')
o = run('''
from django.test import RequestFactory
rf = RequestFactory(); r = rf.post('/x/', '{"a": 1}', content_type='application/json')
print('读取前 _stream 类型:', type(r._stream).__name__, ' 是否已有 _body:', hasattr(r, '_body'))
b = r.body
print('读取 body 之后 是否有 _body:', hasattr(r, '_body'), ' 第二次 r.body is r.body:', r.body is r.body)
print('body 之后 read():', r.read()); print('body 之后 _stream 类型:', type(r._stream).__name__)
''')
print(o); R['internals'] = o
save('d19', R)
