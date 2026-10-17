import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.security import make_digest_acl, make_acl, Permissions, ACL, Id, OPEN_ACL_UNSAFE, READ_ACL_UNSAFE
from kazoo.exceptions import *
tee('z71'); R = {}
n = Node('z71', 7300).start()
adm = client('127.0.0.1:7300'); adm.add_auth('digest', 'admin:adminpw')
anon = client('127.0.0.1:7300')
def tryit(label, fn):
    try: r = fn(); res = '成功' if r is None or r is True else ('成功:' + str(r)[:40])
    except Exception as e: res = type(e).__name__
    print(f'  {label:<58} → {res}'); return res
print('== 一:默认 ACL:不指定时是 world:anyone 的全部权限(cdrwa)——任何人可读写删')
adm.create('/open', b'hello'); acl, st = adm.get_acls('/open'); print('  /open 的 ACL:', [(a.id.scheme, a.id.id, a.perms) for a in acl], f'(perms={acl[0].perms} = ALL)'); R['default'] = [(a.id.scheme, a.id.id, a.perms) for a in acl]
tryit('匿名连接:读 /open', lambda: anon.get('/open')[0]); tryit('匿名连接:写 /open', lambda: anon.set('/open', b'changed')); tryit('匿名连接:删 /open', lambda: anon.delete('/open'))
print()
print('== 二:用 digest 保护节点:创建 /secret,ACL = digest:admin(全部权限)')
adm.create('/secret', b'top', acl=[make_digest_acl('admin', 'adminpw', all=True)]); acl, st = adm.get_acls('/secret'); print('  /secret 的 ACL:', [(a.id.scheme, a.id.id, a.perms) for a in acl]); R['digest_acl'] = [(a.id.scheme, a.id.id, a.perms) for a in acl]
R['ops'] = {}
for who, c in (('匿名', anon), ('已认证 admin', adm)):
    for op, fn in (('读', lambda c=c: c.get('/secret')[0]), ('写', lambda c=c: c.set('/secret', b'new')), ('读 ACL', lambda c=c: c.get_acls('/secret')[0] and True), ('改 ACL', lambda c=c: c.set_acls('/secret', [make_digest_acl('admin', 'adminpw', all=True)]) and True), ('列子节点', lambda c=c: c.get_children('/secret')), ('创建子节点', lambda c=c: c.create('/secret/c', b'')), ('删子节点', lambda c=c: c.delete('/secret/c') if c is not anon else c.delete('/secret/c'))):
        R['ops'][f'{who}/{op}'] = tryit(f'{who}:{op} /secret', fn)
print()
print('== 三:五种权限 CREATE / READ / WRITE / DELETE / ADMIN 分别控制什么(给用户 reader 只读、writer 读写、不给 admin)')
adm.create('/perm', b'x', acl=[make_digest_acl('admin', 'adminpw', all=True), make_digest_acl('reader', 'rpw', read=True), make_digest_acl('writer', 'wpw', read=True, write=True), make_digest_acl('maker', 'mpw', read=True, create=True), make_digest_acl('deleter', 'dpw', read=True, delete=True)])
R['perm'] = {}
for user, pw, ops in (('reader', 'rpw', ['get', 'set', 'create_child', 'delete_child', 'set_acl']), ('writer', 'wpw', ['get', 'set', 'create_child', 'delete_child', 'set_acl']), ('maker', 'mpw', ['get', 'set', 'create_child', 'delete_child', 'set_acl']), ('deleter', 'dpw', ['get', 'set', 'create_child', 'delete_child', 'set_acl'])):
    c = client('127.0.0.1:7300'); c.add_auth('digest', f'{user}:{pw}'); row = {}
    fns = {'get': lambda: c.get('/perm'), 'set': lambda: c.set('/perm', b'y'), 'create_child': lambda: c.create(f'/perm/{user}', b'', acl=[make_digest_acl('admin', 'adminpw', all=True)]), 'delete_child': lambda: c.delete('/perm/maker'), 'set_acl': lambda: c.set_acls('/perm', [make_digest_acl('admin', 'adminpw', all=True)])}
    for op in ops:
        try: fns[op](); row[op] = '允许'
        except NoAuthError: row[op] = '拒绝(NoAuth)'
        except Exception as e: row[op] = type(e).__name__
    R['perm'][user] = row; print(f'  {user:<8}', row); c.stop()
adm.stop(); anon.stop(); n.stop(); save('z71', R)
