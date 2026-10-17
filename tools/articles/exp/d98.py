import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d98'); R = {}
from rl import Node, C
rn = Node(9463, name='d98redis', conf={'maxmemory-policy': 'allkeys-lru'}); rn.start(); admin = rn.c()
urls = "from django.urls import path\nfrom django.http import JsonResponse\ndef me(request): return JsonResponse({'user': str(request.user)})\nurlpatterns = [path('me/', me)]\n"
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions']
CFG = {
    'cache(Redis)': "\nSESSION_ENGINE = 'django.contrib.sessions.backends.cache'\nCACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': 'redis://127.0.0.1:9463/0'}}\n",
    'cached_db(Redis+DB)': "\nSESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'\nCACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': 'redis://127.0.0.1:9463/0'}}\n",
    'db': "\nSESSION_ENGINE = 'django.contrib.sessions.backends.db'\n",
}
def build(name):
    d = proj('d98', urls=urls, apps=apps, middleware=['django.contrib.sessions.middleware.SessionMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware'], with_lab=False, settings_extra=CFG[name]); manage(d, 'migrate'); return d
def run(d, code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.contrib.auth.models import User\nUser.objects.filter(username='u').delete(); User.objects.create_user('u', password='p')\n" + code); return out.rstrip()
print('== 一:Redis 里的 session:key、TTL、内容')
admin.do('FLUSHALL'); d = build('cache(Redis)')
o = run(d, "c = Client(); c.login(username='u', password='p'); print('sessionid cookie =', c.cookies['sessionid'].value[:10] + '…')")
ks = admin.do('KEYS', '*'); print('  Redis 里的 key:', ks); R['keys'] = ks
k = ks[0]; ttl = admin.do('TTL', k); print('  TTL =', ttl, '秒(SESSION_COOKIE_AGE 默认 1209600 = 14 天)'); R['ttl'] = ttl
val = admin.do('GET', k, raw=True); print('  值的前 40 字节:', val[:40], '(pickle 序列化的字典)'); R['val_head'] = repr(val[:40])
print()
print('== 二:Redis 被清空 / 重启不持久化 / 内存淘汰后,用户的登录状态')
R['flush'] = {}
for name in CFG:
    admin.do('FLUSHALL'); d = build(name)
    o = run(d, """
c = Client(); c.login(username='u', password='p'); print('登录后:', c.get('/me/').json())
""")
    import subprocess as sp
    admin.do('FLUSHALL')
    o2 = run(d, """
c = Client(); c.login(username='u', password='p')
import redis; r = redis.Redis(port=9463); 
r.flushall()
print('Redis 被 FLUSHALL 之后:', c.get('/me/').json())
""")
    print(f'  [{name}] ', o2.strip().splitlines()[-1]); R['flush'][name] = o2.strip().splitlines()[-1]
print()
print('== 三:内存淘汰:maxmemory 很小 + allkeys-lru,写入大量别的缓存 key 之后,session 还在吗')
admin.do('FLUSHALL'); admin.do('CONFIG', 'SET', 'maxmemory', '2mb')
R['evict'] = {}
for name in ('cache(Redis)', 'cached_db(Redis+DB)'):
    d = build(name)
    o = run(d, """
import redis; r = redis.Redis(port=9463)
c = Client(); c.login(username='u', password='p'); print('登录后:', c.get('/me/').json()['user'])
for i in range(3000): r.set('filler:%d' % i, 'x' * 1000)
print('用 3 MB 的其它 key 挤满 maxmemory=2mb 之后,Redis key 数:', r.dbsize(), ' 该会话在 Redis 里:', any(k.startswith(b':1:django.contrib.sessions') for k in r.scan_iter('*django.contrib.sessions*')))
print('之后再访问:', c.get('/me/').json())
""")
    print(f'  [{name}]'); [print('    ' + l) for l in o.strip().splitlines()]; R['evict'][name] = o.strip().splitlines()[-1]
    admin.do('FLUSHALL')
admin.do('CONFIG', 'SET', 'maxmemory', '0')
print()
print('== 四:每个请求的耗时:三种后端(300 次中位,含 Client 开销)')
R['lat'] = {}
for name in CFG:
    admin.do('FLUSHALL'); d = build(name)
    o = run(d, """
import time, statistics
c = Client(); c.login(username='u', password='p'); c.get('/me/')
xs = []
for _ in range(300):
    t0 = time.perf_counter(); c.get('/me/'); xs.append((time.perf_counter() - t0) * 1000)
print('%.3f' % statistics.median(xs))
""")
    R['lat'][name] = float(o.strip().splitlines()[-1]); print(f'  {name:<22} {R["lat"][name]:.3f} ms')
rn.stop(); save('d98', R)
