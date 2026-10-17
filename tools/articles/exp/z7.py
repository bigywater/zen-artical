import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.security import make_digest_acl_credential, ACL, Permissions
tee('z7'); R = {}
n = Node('z7', 7300).start(); z = client('127.0.0.1:7300')
F = ['czxid', 'mzxid', 'pzxid', 'version', 'cversion', 'aversion', 'numChildren', 'dataLength', 'ephemeralOwner']
def st(p): s = z.get(p)[1]; return {f: getattr(s, f) for f in F} | {'ctime': s.ctime, 'mtime': s.mtime}
def diff(a, b): return {k: f'{a[k]:#x}→{b[k]:#x}' if k.endswith('zxid') else f'{a[k]}→{b[k]}' for k in a if a[k] != b[k]}
print('== 一:Stat 的字段:新建 /p 之后')
z.create('/p', b'hello'); s0 = st('/p')
for f in F: print(f'  {f:<15} = {s0[f]:#x}' if f.endswith('zxid') or f == 'ephemeralOwner' else f'  {f:<15} = {s0[f]}')
R['stat0'] = s0
print()
print('== 二:每种操作改变了哪些字段(只列出变化的)')
ops = [('set /p 新数据', lambda: z.set('/p', b'newer-data')), ('创建子节点 /p/c', lambda: z.create('/p/c', b'')), ('再创建 /p/d', lambda: z.create('/p/d', b'')), ('修改子节点数据 /p/c', lambda: z.set('/p/c', b'x')), ('删除子节点 /p/d', lambda: z.delete('/p/d')), ('setACL /p', lambda: z.set_acls('/p', [ACL(Permissions.ALL, __import__('kazoo.security', fromlist=['ANYONE_ID_UNSAFE']).ANYONE_ID_UNSAFE)]))]
prev = st('/p'); R['ops'] = []
for label, fn in ops:
    fn(); cur = st('/p'); d = diff(prev, cur); R['ops'].append((label, d)); print(f'  {label:<22} → /p 的变化: {d or "(无变化)"}'); prev = cur
print('  子节点 /p/c 的 stat(它没被 /p 的操作影响):', {k: v for k, v in st('/p/c').items() if k in ('czxid', 'mzxid', 'version', 'cversion', 'numChildren')})
print()
print('== 三:时间戳:ctime / mtime 是服务端写入时的毫秒时间,不是客户端时间')
s = z.get('/p')[1]; print(f'  /p 的 ctime = {s.ctime}、mtime = {s.mtime}(毫秒);与本机时间差:{abs(time.time() * 1000 - s.mtime):.0f} ms(同一台机器)')
print()
print('== 四:路径规则:用官方 ZooKeeperMain(Java 客户端)创建各种路径,看它的校验信息')
cases = ['/ok', '/中文', '/a/', '//a', '/a//b', '/.', '/a/./b', '/a/../b', 'noslash', '/zookeeper/x', '/a/b', '/tab\tx']
outs = cli(7300, *[f'create {p} x' for p in cases[:-1]]); R['paths'] = []
for p, o in zip(cases, outs):
    first = o.splitlines()[0] if o else '(无输出)'; R['paths'].append((p, first)); print(f'  create {p!r:<16} → {first[:80]}')
z.stop(); n.stop(); save('z7', R)
