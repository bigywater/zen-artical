import sys, time, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r124'); R = {}
n = Node(9125, name='s124'); n.start(); a = n.c()
print('== 一:默认值')
sh(a, 'CONFIG', 'GET', 'acl-pubsub-default'); R['default'] = a.do('CONFIG', 'GET', 'acl-pubsub-default')
print()
print('== 二:新建用户,只给命令权限、不给频道权限')
sh(a, 'ACL', 'SETUSER', 'u1', 'on', 'nopass', '~*', '+@all')
print('  ', [l for l in a.do("ACL", "LIST") if l.startswith("user u1 ")][0])
b = n.c(); sh(b, 'AUTH', 'u1', 'x'); R['pub_noperm'] = str(sh(b, 'PUBLISH', 'news:1', 'hi')); R['sub_noperm'] = str(sh(b, 'SUBSCRIBE', 'news:1'))
print()
print('== 三:给 &news:* 后:PUBLISH / SUBSCRIBE / PSUBSCRIBE 各自的结果')
sh(a, 'ACL', 'SETUSER', 'u2', 'on', 'nopass', '~*', '+@all', 'resetchannels', '&news:*')
print('  ', [l for l in a.do("ACL", "LIST") if l.startswith("user u2 ")][0])
t = {}
for cm in (('PUBLISH', 'news:1', 'hi'), ('PUBLISH', 'other', 'hi'), ('SUBSCRIBE', 'news:1'), ('SUBSCRIBE', 'news:*'), ('SUBSCRIBE', 'other'), ('PSUBSCRIBE', 'news:*'), ('PSUBSCRIBE', 'news:a*'), ('PSUBSCRIBE', '*'), ('SSUBSCRIBE', 'news:1')):
    r = a.do('ACL', 'DRYRUN', 'u2', *cm, raise_err=False); t[' '.join(cm)] = str(r); print(f'  DRYRUN u2 {" ".join(cm):<26} → {fmt(r)}')
R['t'] = t
print()
print('== 四:订阅中途撤销频道权限:已经订阅的连接会怎样?')
sub = n.c(); sh(sub, 'AUTH', 'u2', 'x'); print('  订阅:', fmt(sub.do('SUBSCRIBE', 'news:1')))
print('  管理员发布一条:', a.do('PUBLISH', 'news:1', 'before'), '个订阅者收到 ->', fmt(sub.read()))
sh(a, 'ACL', 'SETUSER', 'u2', 'resetchannels')
time.sleep(0.2)
try:
    sub.s.settimeout(2); x = sub.read(); print('  撤销之后订阅连接读到:', fmt(x)); R['revoke'] = str(x)
except EOFError: print('  撤销之后订阅连接:服务端已断开连接(EOF)'); R['revoke'] = 'EOF'
except Exception as e: print('  撤销之后订阅连接:', type(e).__name__); R['revoke'] = type(e).__name__
print('  之后发布,订阅者数:', a.do('PUBLISH', 'news:1', 'after'))
print('  PUBSUB CHANNELS:', fmt(a.do('PUBSUB', 'CHANNELS')))
print()
print('== 五:allchannels / acl-pubsub-default allchannels 对新用户的影响')
sh(a, 'ACL', 'SETUSER', 'u3', 'on', 'nopass', '~*', '+@all', 'allchannels'); print('  ', [l for l in a.do("ACL", "LIST") if l.startswith("user u3 ")][0])
sh(a, 'CONFIG', 'SET', 'acl-pubsub-default', 'allchannels')
sh(a, 'ACL', 'SETUSER', 'u4', 'on', 'nopass', '~*', '+@all'); print('  ', [l for l in a.do("ACL", "LIST") if l.startswith("user u4 ")][0])
R['u4'] = [l for l in a.do("ACL", "LIST") if l.startswith("user u4 ")][0]
sh(a, 'CONFIG', 'SET', 'acl-pubsub-default', 'resetchannels')
print()
print('== 六:键空间通知的频道也要授权')
sh(a, 'CONFIG', 'SET', 'notify-keyspace-events', 'KEA')
sh(a, 'ACL', 'SETUSER', 'u5', 'on', 'nopass', '~*', '+@all', 'resetchannels', '&news:*')
for cm in (('PSUBSCRIBE', '__keyspace@0__:*'),): 
    r = a.do('ACL', 'DRYRUN', 'u5', *cm, raise_err=False); print(f'  DRYRUN u5 {" ".join(cm)} → {fmt(r)}'); R['ks'] = str(r)
save('r124', R); cleanup([n])
