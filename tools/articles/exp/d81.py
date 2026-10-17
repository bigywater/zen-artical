import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d81'); R = {}
urls = '''
from django.urls import path
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
def add(request):
    n = int(request.GET.get('n', 1)); size = int(request.GET.get('size', 10))
    import secrets\n    for i in range(n): messages.info(request, 'm%d ' % i + secrets.token_hex(size // 2 + 1)[:size])
    return HttpResponse('added')
def add_levels(request):
    messages.debug(request, 'dbg'); messages.info(request, 'inf'); messages.success(request, 'ok'); messages.warning(request, 'warn'); messages.error(request, 'err'); return HttpResponse('levels')
def show(request):
    msgs = [(m.level_tag, m.message[:12]) for m in messages.get_messages(request)]
    return JsonResponse({'msgs': msgs})
def peek(request):
    st = messages.get_messages(request); return JsonResponse({'storage': type(st).__name__, 'len': len(st)})
def noop(request): return HttpResponse('noop')
urlpatterns = [path('add/', add), path('levels/', add_levels), path('show/', show), path('peek/', peek), path('noop/', noop)]
'''
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions', 'django.contrib.messages']
mw = ['django.contrib.sessions.middleware.SessionMiddleware', 'django.contrib.messages.middleware.MessageMiddleware']
def build(storage=None):
    extra = '' if storage is None else f"\nMESSAGE_STORAGE = {storage!r}\n"
    d = proj('d81', urls=urls, apps=apps, middleware=mw, with_lab=False, settings_extra=extra); manage(d, 'migrate'); return d
def run(d, code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.contrib.sessions.models import Session\ndef state(c, r):\n    return {'Set-Cookie messages': 'messages' in r.cookies, 'session 行数': Session.objects.count()}\n" + code); return out.rstrip()
d = build()
print('== 一:默认存储 FallbackStorage:先放 cookie;读取一次之后就没了')
o = run(d, """
Session.objects.all().delete(); c = Client()
r = c.get('/add/?n=2'); print('添加 2 条(短消息):', state(c, r), ' messages cookie 长度 =', len(r.cookies['messages'].value) if 'messages' in r.cookies else None)
r = c.get('/show/'); print('下一个请求读取:', r.json(), ' 读取后 cookie 被删除(Set-Cookie 过期):', r.cookies['messages']['expires'] if 'messages' in r.cookies else None)
r = c.get('/show/'); print('再读一次:', r.json())
""")
print(o); R['basic'] = o
print()
print('== 二:消息级别:默认最低 INFO,debug() 被忽略;级别 → tag')
o = run(d, """
c = Client(); c.get('/levels/'); print(c.get('/show/').json())
from django.contrib.messages import constants; from django.conf import settings; print('settings 里有没有 MESSAGE_LEVEL:', hasattr(settings, 'MESSAGE_LEVEL'), '; 常量 INFO =', constants.INFO, ', DEBUG =', constants.DEBUG, '(未设置时最低级别是 INFO,所以 debug() 没有保存)')
""")
print(o); R['levels'] = o
print()
print('== 三:消息的用完即删是「读取时标记」:遍历过才算用过;只取长度不算')
o = run(d, """
Session.objects.all().delete(); c = Client(); c.get('/add/?n=1')
print('/peek/ 只取 len() 与类型:', c.get('/peek/').json()); print('之后 /show/ 还能读到:', c.get('/show/').json())
c2 = Client(); c2.get('/add/?n=1'); c2.get('/noop/'); print('中间发了一个没读消息的请求 /noop/,再 /show/:', c2.get('/show/').json(), '(消息没读之前一直保留)')
""")
print(o); R['used'] = o
print()
print('== 四:cookie 存不下时回退到 session:FallbackStorage 的溢出行为(cookie 上限约 2048 字节)')
o = run(d, """
Session.objects.all().delete()
for n, size in ((1, 50), (5, 300), (2, 3000)):
    c = Client(); Session.objects.all().delete(); r = c.get(f'/add/?n={n}&size={size}')
    ck = r.cookies['messages'].value if 'messages' in r.cookies else ''
    print(f'{n} 条 × {size} 字符:messages cookie 长度 {len(ck):>5}  session 行数 {Session.objects.count()}  读取到 {len(c.get("/show/").json()["msgs"])} 条')
""")
print(o); R['overflow'] = o
print()
print('== 五:三种存储后端各自把消息放哪')
R['stores'] = {}
for name in ('django.contrib.messages.storage.cookie.CookieStorage', 'django.contrib.messages.storage.session.SessionStorage', 'django.contrib.messages.storage.fallback.FallbackStorage'):
    dd = build(name)
    o = run(dd, """
c = Client(); r = c.get('/add/?n=1')
print('Set-Cookie messages:', 'messages' in r.cookies, '| session 行数:', Session.objects.count(), '| 读取:', c.get('/show/').json())
""")
    short = name.split('.')[-1]; print(f'  [{short}]', o.strip()); R['stores'][short] = o.strip()
save('d81', R)
