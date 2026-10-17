import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.security import make_digest_acl, ACL, Id
from kazoo.exceptions import *
tee('z73'); R = {}
n = Node('z73', 7300).start(); adm = client('127.0.0.1:7300'); adm.add_auth('digest', 'admin:adminpw'); anon = client('127.0.0.1:7300')
A = make_digest_acl('admin', 'adminpw', all=True)
def res(fn):
    try: r = fn(); return '允许'
    except NoAuthError: return '拒绝(NoAuth)'
    except Exception as e: return type(e).__name__
print('== 一:ACL 不继承:父节点用 digest 保护,在它下面创建子节点不指定 ACL → 子节点是 world:anyone')
adm.create('/p', b'', acl=[A]); adm.create('/p/c', b'child-data'); acl, _ = adm.get_acls('/p/c'); print('  /p/c 的 ACL:', [(a.id.scheme, a.id.id, a.perms) for a in acl]); R['child_acl'] = [(a.id.scheme, a.id.id, a.perms) for a in acl]
print('  匿名按完整路径读 /p/c →', res(lambda: anon.get('/p/c')), '(父节点受保护,但子节点自己的 ACL 是 world)'); R['anon_read_child'] = res(lambda: anon.get('/p/c'))
print('  匿名列出 /p 的子节点 →', res(lambda: anon.get_children('/p'))); R['anon_list_parent'] = res(lambda: anon.get_children('/p'))
print()
print('== 二:创建 / 删除子节点要看「父节点」的 ACL,读写子节点的数据看「子节点自己」的 ACL')
print('  匿名在 /p 下创建子节点 →', res(lambda: anon.create('/p/x', b''))); print('  匿名删除 /p/c(子节点是 world,但父节点 /p 只允许 admin)→', res(lambda: anon.delete('/p/c')))
print('  匿名修改 /p/c 的数据(子节点 world:cdrwa)→', res(lambda: anon.set('/p/c', b'hacked'))); R['parent_rules'] = dict(create=res(lambda: anon.create('/p/x2', b'')), delete=res(lambda: anon.delete('/p/c')), setdata=res(lambda: anon.set('/p/c', b'hacked')))
print()
print('== 三:要保护整棵子树,必须自己递归地设置每个节点的 ACL。统计:给一棵 5 层、每层 5 个子节点的树逐个 set_acls 的用时')
def build(path, depth):
    if depth == 0: return 0
    c = 0
    for i in range(5):
        p = f'{path}/n{i}'; adm.create(p, b'', acl=[ACL(31, Id('world', 'anyone'))]); c += 1 + build(p, depth - 1)
    return c
adm.create('/tree', b'', acl=[ACL(31, Id('world', 'anyone'))]); t0 = time.perf_counter(); N = build('/tree', 5) + 1; tb = time.perf_counter() - t0
anon_ok = sum(1 for p in ('/tree/n0', '/tree/n0/n1/n2') if res(lambda p=p: anon.get(p)) == '允许'); print(f'  建树 {N} 个节点用时 {tb:.1f} s;全是 world,匿名读两个深层节点:{anon_ok}/2 成功')
def walk(path):
    yield path
    for c in adm.get_children(path): yield from walk(f'{path}/{c}')
t0 = time.perf_counter(); paths = list(walk('/tree')); [adm.set_acls(p, [A]) for p in paths]; ts = time.perf_counter() - t0
print(f'  递归 set_acls {len(paths)} 个节点用时 {ts:.1f} s(逐个同步请求);之后匿名读深层节点:', res(lambda: anon.get('/tree/n0/n1/n2'))); R['recursive'] = dict(n=len(paths), build=tb, secure=ts, after=res(lambda: anon.get('/tree/n0/n1/n2')))
print()
print('== 四:新建的子节点仍然不继承:递归加固之后再创建的节点又是 world')
adm.create('/tree/n0/new', b''); acl, _ = adm.get_acls('/tree/n0/new'); print('  /tree/n0/new 的 ACL:', [(a.id.scheme, a.id.id) for a in acl]); R['new_child'] = [(a.id.scheme, a.id.id) for a in acl]
print('  创建时就带上 ACL(create 的 acl 参数)或者在创建后立刻 set_acls,否则会有一小段「裸奔」的时间窗。')
adm.stop(); anon.stop(); n.stop(); save('z73', R)
