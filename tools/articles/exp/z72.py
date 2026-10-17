import sys, os, time, json, re, hashlib, base64; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.security import make_digest_acl, make_acl, ACL, Id, Permissions
from kazoo.exceptions import *
tee('z72'); R = {}
n = Node('z72', 7300).start(); adm = client('127.0.0.1:7300'); adm.add_auth('digest', 'admin:adminpw'); anon = client('127.0.0.1:7300')
def can(c, path): 
    try: c.get(path); return '允许'
    except NoAuthError: return '拒绝'
print('== 一:world:任何人(唯一的 id 是 anyone)——默认方案')
adm.create('/w', b'x', acl=[ACL(31, Id('world', 'anyone'))]); print('  匿名读 /w →', can(anon, '/w')); R['world'] = can(anon, '/w')
print()
print('== 二:auth:「当前已认证的所有用户」——创建时自动变成创建者的 digest id(不用写密码)')
c1 = client('127.0.0.1:7300'); c1.add_auth('digest', 'alice:apw'); c1.create('/a', b'x', acl=[ACL(31, Id('auth', ''))]); acl, _ = c1.get_acls('/a'); print('  alice 用 auth:"" 创建 /a,实际保存的 ACL:', [(a.id.scheme, a.id.id) for a in acl]); R['auth_acl'] = [(a.id.scheme, a.id.id) for a in acl]
c2 = client('127.0.0.1:7300'); c2.add_auth('digest', 'bob:bpw'); print('  bob 读 /a →', can(c2, '/a'), '| alice 读 /a →', can(c1, '/a'), '| 匿名读 /a →', can(anon, '/a')); R['auth_read'] = (can(c2, '/a'), can(c1, '/a'), can(anon, '/a'))
print()
print('== 三:digest:id 是 user:base64(sha1(user:password)) ——ACL 里保存的是哈希,但没有加盐,弱口令可以被离线猜出来')
h = base64.b64encode(hashlib.sha1(b'alice:apw').digest()).decode(); print('  我自己算的 alice:apw 的 digest:', f'alice:{h}', '| ZooKeeper 保存的:', acl[0].id.id, '| 一致:', acl[0].id.id == f'alice:{h}'); R['digest_match'] = acl[0].id.id == f'alice:{h}'
print('  同样的口令在任何节点上的哈希都一样(无盐):再算一次 =', f'alice:{base64.b64encode(hashlib.sha1(b"alice:apw").digest()).decode()}')
print()
print('== 四:ip:按客户端 IP / CIDR 授权(本机客户端来自 127.0.0.1)')
adm.create('/ip-ok', b'x', acl=[ACL(31, Id('ip', '127.0.0.1'))]); adm.create('/ip-net', b'x', acl=[ACL(31, Id('ip', '127.0.0.0/8'))]); adm.create('/ip-no', b'x', acl=[ACL(31, Id('ip', '10.0.0.0/8'))])
R['ip'] = {p: can(anon, p) for p in ('/ip-ok', '/ip-net', '/ip-no')}
for p in ('/ip-ok', '/ip-net', '/ip-no'): print(f'  匿名(127.0.0.1)读 {p:<8} → {R["ip"][p]}')
print('  注意:ip 方案信任连接的源地址,经过 NAT / 代理之后所有客户端看起来是同一个 IP。')
print()
print('== 五:sasl / x509 方案需要服务端先启用对应的认证提供者(第 76、77 篇),没有启用时用它们设置 ACL 的结果:')
for scheme in ('sasl', 'x509'):
    try: adm.create(f'/{scheme}-node', b'x', acl=[ACL(31, Id(scheme, 'someone'))]); r = '创建成功(但此时没有任何客户端能满足它)'
    except Exception as e: r = type(e).__name__
    print(f'  create 带 {scheme}:someone 的 ACL → {r}'); R[scheme] = r
print()
print('== 六:digest 超级用户与「忘了密码」:自己创建的节点如果 ACL 里没有 admin 权限,连删除都做不了')
adm.create('/lost', b'x', acl=[make_digest_acl('bob', 'bpw', read=True)])
try: adm.get('/lost'); r1 = '允许'
except NoAuthError: r1 = '拒绝'
try: adm.set_acls('/lost', [ACL(31, Id('world', 'anyone'))]); r2 = '允许'
except NoAuthError: r2 = '拒绝'
print('  admin 读 /lost →', r1, '| admin 改 /lost 的 ACL →', r2, '(只有 bob 有读权限,没有人有 ADMIN 权限:这个节点的 ACL 再也改不了)'); R['lost'] = (r1, r2)
for c in (c1, c2, adm, anon): c.stop()
n.stop(); save('z72', R)
