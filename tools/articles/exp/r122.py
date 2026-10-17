import sys, time, os, json, hashlib, pathlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r122'); R = {}
n = Node(9122, name='s122'); (n.dir / 'users.acl').write_text(''); n.conf['aclfile'] = str(n.dir / 'users.acl'); n.start()
a = n.c()
print('== 一:出厂状态:只有一个 default 用户,任何人不用密码就能做任何事')
sh(a, 'ACL', 'WHOAMI'); sh(a, 'ACL', 'LIST'); sh(a, 'ACL', 'USERS')
print()
print('== 二:建一个只能读写 app:* 的用户 alice,再用她的身份登录')
sh(a, 'ACL', 'SETUSER', 'alice', 'on', '>secret123', '~app:*', '+get', '+set')
sh(a, 'ACL', 'GETUSER', 'alice')
b = n.c(); sh(b, 'AUTH', 'alice', 'secret123'); sh(b, 'ACL', 'WHOAMI')
res = {}
for cmd in (('SET', 'app:1', 'v'), ('GET', 'app:1'), ('GET', 'other:1'), ('SET', 'other:1', 'v'), ('DEL', 'app:1'), ('PING',), ('KEYS', '*'), ('ACL', 'LIST')):
    res[' '.join(cmd)] = str(sh(b, *cmd))
R['alice'] = res
print()
print('== 三:密码不是明文存的')
lst = a.do('ACL', 'LIST'); line = [l for l in lst if l.startswith('user alice')][0]
print(' ', line)
h = hashlib.sha256(b'secret123').hexdigest()
print(f'  sha256("secret123") = {h}')
print('  ACL LIST 里的哈希与之相同:', ('#' + h) in line)
R['hash_match'] = ('#' + h) in line
print()
print('== 四:关闭 / 删除用户,对已经登录的连接有没有影响?')
c1 = n.c(); sh(c1, 'AUTH', 'alice', 'secret123')
sh(a, 'ACL', 'SETUSER', 'alice', 'off')
print('  alice off 之后,已登录的连接 c1 继续发命令:'); r = sh(c1, 'SET', 'app:2', 'v'); R['off_existing'] = str(r)
c2 = n.c(); print('  alice off 之后,新连接登录:'); r = sh(c2, 'AUTH', 'alice', 'secret123'); R['off_new'] = str(r)
sh(a, 'ACL', 'SETUSER', 'alice', 'on')
c3 = n.c(); sh(c3, 'AUTH', 'alice', 'secret123')
sh(a, 'ACL', 'DELUSER', 'alice')
try:
    r = c3.do('GET', 'app:1', raise_err=False); print('  DELUSER 后 c3 继续发命令:', fmt(r)); R['del_existing'] = str(r)
except Exception as e:
    print('  DELUSER 后 c3 继续发命令:连接已被服务端断开', type(e).__name__); R['del_existing'] = 'closed'
print()
print('== 五:改权限对已登录连接是即时生效的吗')
sh(a, 'ACL', 'SETUSER', 'bob', 'on', '>pw', '~*', '+@all')
d = n.c(); sh(d, 'AUTH', 'bob', 'pw'); sh(d, 'SET', 'k', 1)
sh(a, 'ACL', 'SETUSER', 'bob', '-set')
R['revoke'] = str(sh(d, 'SET', 'k', 2)); sh(d, 'GET', 'k')
print()
print('== 六:持久化:ACL SAVE 写入 aclfile,重启后用户还在;没配 aclfile 的实例 ACL SAVE 会报错')
sh(a, 'ACL', 'SAVE')
print('  users.acl 内容:'); print('   ' + '\n   '.join((n.dir / 'users.acl').read_text().splitlines()))
n.stop(); n.start(rewrite=False); a = n.c(); sh(a, 'ACL', 'USERS')
R['persist_users'] = a.do('ACL', 'USERS')
m = Node(9123, name='s122b').start(); mc = m.c()
sh(mc, 'ACL', 'SETUSER', 'carol', 'on', 'nopass', '~*', '+@all')
r = sh(mc, 'ACL', 'SAVE'); R['nosave'] = str(r)
m.stop(); m.start(rewrite=False); mc = m.c(); print('  没有 aclfile 的实例重启后:'); sh(mc, 'ACL', 'USERS'); R['noacl_after_restart'] = mc.do('ACL', 'USERS')
save('r122', R); cleanup([n, m])
