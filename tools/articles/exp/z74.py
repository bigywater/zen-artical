import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.security import make_digest_acl, ACL, Id
from kazoo.exceptions import *
tee('z74'); R = {}
n = Node('z74', 7300).start(); px = Proxy(7390, 7300).start()
admin = client('127.0.0.1:7300'); admin.add_auth('digest', 'root:rootpw')
OLD, NEW = make_digest_acl('svc', 'old-pw', all=True), make_digest_acl('svc', 'new-pw', all=True)
ROOT = make_digest_acl('root', 'rootpw', all=True)
admin.create('/cfg', b'v1', acl=[ROOT, OLD])
def res(fn):
    try: fn(); return '允许'
    except NoAuthError: return '拒绝'
    except Exception as e: return type(e).__name__
print('== 一:服务 svc 用旧口令连上并读取;管理员把 ACL 换成新口令后,svc 已经建立的会话还有权限吗?')
svc = client('127.0.0.1:7390', timeout=20); svc.add_auth('digest', 'svc:old-pw'); print('  svc(旧口令)读 /cfg →', res(lambda: svc.get('/cfg')))
admin.set_acls('/cfg', [ROOT, NEW]); print('  管理员把 ACL 换成 svc:new-pw 之后,svc 的现有会话读 /cfg →', res(lambda: svc.get('/cfg'))); R['live_session'] = res(lambda: svc.get('/cfg'))
print()
print('== 二:svc 的连接断开重连(代理断连)后:kazoo 会用最初的旧口令重新认证,然后呢?')
px.close_all(); time.sleep(3); print('  重连之后,svc 读 /cfg →', res(lambda: svc.get('/cfg'))); R['after_reconnect'] = res(lambda: svc.get('/cfg'))
print()
print('== 三:平滑轮换的正确顺序:先让 ACL 同时包含新旧两个 id,等所有客户端都换成新口令,最后再删掉旧的')
admin.set_acls('/cfg', [ROOT, OLD, NEW]); svc2 = client('127.0.0.1:7300'); svc2.add_auth('digest', 'svc:new-pw'); print('  ACL = root + 旧 + 新:旧口令的新会话读 /cfg →', end=' ')
sv_old = client('127.0.0.1:7300'); sv_old.add_auth('digest', 'svc:old-pw'); r_old = res(lambda: sv_old.get('/cfg')); print(r_old, '| 新口令的新会话读 /cfg →', res(lambda: svc2.get('/cfg'))); R['both'] = (r_old, res(lambda: svc2.get('/cfg')))
admin.set_acls('/cfg', [ROOT, NEW]); sv_old2 = client('127.0.0.1:7300'); sv_old2.add_auth('digest', 'svc:old-pw'); print('  去掉旧 id 之后:旧口令的新会话读 /cfg →', res(lambda: sv_old2.get('/cfg')), '| 新口令的会话读 →', res(lambda: svc2.get('/cfg'))); R['new_only'] = (res(lambda: sv_old2.get('/cfg')), res(lambda: svc2.get('/cfg')))
print()
print('== 四:在已有的会话里,可以再 add_auth 一个新身份(同一个连接可以带多个身份)')
svc3 = client('127.0.0.1:7300'); print('  未认证读 →', res(lambda: svc3.get('/cfg')), end=' '); svc3.add_auth('digest', 'svc:new-pw'); print('| add_auth(新口令)之后读 →', res(lambda: svc3.get('/cfg'))); R['add_auth_later'] = res(lambda: svc3.get('/cfg'))
for c in (svc, svc2, sv_old, sv_old2, svc3, admin): 
    try: c.stop()
    except Exception: pass
px.stop(); n.stop(); save('z74', R)
