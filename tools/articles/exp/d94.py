import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d94'); R = {}
from rl import Node, C
rn = Node(9462, name='d94redis'); rn.start(); rc_ = rn.c()
d = proj('d94', apps=['django.contrib.contenttypes'], with_lab=False, files={'proj/kf.py': "def my_key(key, key_prefix, version): return f'{key_prefix}|v{version}|{key}'.lower()\n"}, settings_extra="\nCACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': 'redis://127.0.0.1:9462/0', 'KEY_PREFIX': 'shop'}, 'plain': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': 'redis://127.0.0.1:9462/1'}, 'custom': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': 'redis://127.0.0.1:9462/2', 'KEY_PREFIX': 'K', 'VERSION': 3, 'KEY_FUNCTION': 'proj.kf.my_key'}}\n")
def run(code): rc, out = pyscript(d, "import logging, warnings; logging.disable(logging.CRITICAL)\nfrom django.core.cache import caches\nfor c in ('default', 'plain', 'custom'): caches[c].clear()\ncache = caches['default']; plain = caches['plain']; custom = caches['custom']\n" + code); return out.rstrip()
print('== 一:make_key 的规则:前缀:版本:key —— 直接看 Redis 里的真实 key')
o = run("""
cache.set('user:1', 'a'); plain.set('user:1', 'b'); custom.set('User:1', 'c')
print('make_key(default)  :', cache.make_key('user:1'))
print('make_key(plain 没有前缀):', plain.make_key('user:1'))
print('make_key(custom 自定义函数):', custom.make_key('User:1'))
""")
print(o); R['make'] = o
for db, label in ((0, 'default(KEY_PREFIX=shop)'), (1, 'plain(无前缀)'), (2, 'custom')):
    c = C(9462); c.do('SELECT', db); print(f'  Redis db{db} 里的 key({label}):', c.do('KEYS', '*'))
R['redis_keys'] = {str(db): C(9462).do('KEYS', '*') if False else None for db in (0, 1, 2)}
for db in (0, 1, 2):
    c = C(9462); c.do('SELECT', db); R['redis_keys'][str(db)] = c.do('KEYS', '*')
print()
print('== 二:version:同一个 key 名的不同版本互不可见;incr_version;整体换版本相当于批量作废')
o = run("""
cache.set('k', 'v1', version=1); cache.set('k', 'v2', version=2)
print("get('k') 默认版本 =", cache.get('k'), ' version=2:', cache.get('k', version=2), ' version=3:', cache.get('k', version=3))
print('incr_version("k") 返回', cache.incr_version('k'), ' 之后 version=2 的 =', cache.get('k', version=2), ' version=3 的 =', cache.get('k', version=3), ' 旧版本 1:', cache.get('k', version=1), '(incr_version 把 v1 移到了 v2,原来的 v2 被覆盖)')
""")
print(o); R['version'] = o
print()
print('== 三:key 的限制:含空格/控制字符、超过 250 字符 → CacheKeyWarning(为了兼容 memcached);Redis 后端不受这个限制,但会警告')
o = run("""
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    cache.set('has space', 1); cache.set('x' * 300, 1); cache.set('ok', 1); cache.set('unicode键', 1)
    print('警告条数:', len(w), [str(x.message)[:60] for x in w])
print("get('has space') =", cache.get('has space'), ' get(300 字符 key) =', cache.get('x' * 300), ' get(unicode键) =', cache.get('unicode键'))
""")
print(o); R['limits'] = o
print()
print('== 四:key 里带用户输入时的碰撞与命名:同一个前缀 + 相同 key 不同数据库/环境会互相覆盖;KEY_PREFIX 用来隔离')
o = run("""
a = caches['default']; a.set('shared', 'from-app-A')
from django.core.cache import caches as cs
print('同一个后端、同一个前缀下,另一个应用写同名 key 会覆盖:', end=' ')
a.set('shared', 'from-app-B'); print(a.get('shared'))
print('不同 KEY_PREFIX 互相隔离:default 与 custom 的 "shared" ->', a.get('shared'), '/', custom.get('shared'))
""")
print(o); R['collide'] = o
rn.stop(); save('d94', R)
