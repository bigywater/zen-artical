import sys, time, os, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r126'); R = {}
n = Node(9126 + 10, name='s126'); n.start(); a = n.c()
print('== 一:没有设密码时,发 AUTH 会怎样')
R['auth_nopw'] = str(sh(a, 'AUTH', 'whatever'))
print()
print('== 二:设了 requirepass 之后,没登录的连接能做什么')
sh(a, 'CONFIG', 'SET', 'requirepass', 'S3cretPw')
sh(a, 'CONFIG', 'GET', 'requirepass')
u = n.c(); allowed = {}
for cm in (('PING',), ('GET', 'k'), ('SET', 'k', 'v'), ('ECHO', 'x'), ('INFO',), ('COMMAND', 'COUNT'), ('CLIENT', 'SETNAME', 'x'), ('SELECT', 0), ('HELLO', 2), ('QUIT',)):
    try:
        r = u.do(*cm, raise_err=False)
    except Exception as e:
        r = f'<{type(e).__name__}>'; u = n.c()
    allowed[' '.join(map(str, cm))] = str(r)[:70]; print(f'  {" ".join(map(str, cm)):<20} → {fmt(r) if not isinstance(r, str) or r.startswith("<") is False else r}'[:150]); 
    if cm[0] == 'QUIT': u = n.c()
R['unauth'] = allowed
print()
print('== 三:三种登录方式与失败')
b = n.c(); sh(b, 'AUTH', 'wrongpw'); R['wrong'] = str(sh(b, 'AUTH', 'wrongpw', raise_err=False) if False else b.do('AUTH', 'wrongpw', raise_err=False))
sh(b, 'AUTH', 'S3cretPw'); sh(b, 'ACL', 'WHOAMI')
c = n.c(); sh(c, 'AUTH', 'default', 'S3cretPw')
d = n.c(); sh(d, 'HELLO', 2, 'AUTH', 'default', 'S3cretPw', show=False); print('> HELLO 2 AUTH default S3cretPw  → 登录后 ACL WHOAMI =', d.do('ACL', 'WHOAMI'))
e = n.c(); r = e.do('HELLO', 2, 'AUTH', 'default', 'bad', raise_err=False); print('> HELLO 2 AUTH default bad →', fmt(r)); R['hello_bad'] = str(r)
print()
print('== 四:requirepass 与 default 用户是同一回事(以及一个容易踩的坑)')
sh(a, 'AUTH', 'S3cretPw'); sh(a, 'ACL', 'LIST')
sh(a, 'ACL', 'SETUSER', 'default', 'nopass'); sh(a, 'CONFIG', 'GET', 'requirepass'); sh(a, 'ACL', 'LIST')
print('  现在 default 已是 nopass,但 CONFIG GET requirepass 还显示旧密码。再执行一次相同值的 CONFIG SET requirepass:')
sh(a, 'CONFIG', 'SET', 'requirepass', 'S3cretPw'); lst = sh(a, 'ACL', 'LIST'); R['same_value'] = lst[0]
sh(a, 'ACL', 'SETUSER', 'default', 'resetpass', '>S3cretPw'); print('  用 ACL SETUSER default resetpass >S3cretPw 恢复:'); lst2 = sh(a, 'ACL', 'LIST'); R['restored'] = lst2[0]
sh(a, 'CONFIG', 'SET', 'requirepass', 'S3cretPw')
print()
print('== 五:同一连接里再次 AUTH:切换身份;失败的 AUTH 会不会把已有登录踢掉?')
sh(a, 'ACL', 'SETUSER', 'alice', 'on', '>ap', '~*', '+@all'); sh(a, 'ACL', 'SETUSER', 'bob', 'on', '>bp', '~*', '+@all')
x = n.c(); sh(x, 'AUTH', 'alice', 'ap'); sh(x, 'ACL', 'WHOAMI'); sh(x, 'AUTH', 'bob', 'bp'); sh(x, 'ACL', 'WHOAMI')
R['after_fail'] = str(sh(x, 'AUTH', 'bob', 'nope')); r2 = sh(x, 'ACL', 'WHOAMI'); R['whoami_after_fail'] = str(r2)
print()
print('== 六:改密码之后,已经登录的连接还有效吗')
old = n.c(); sh(old, 'AUTH', 'S3cretPw')
sh(a, 'CONFIG', 'SET', 'requirepass', 'NewPw!')
R['old_conn'] = str(sh(old, 'GET', 'k')); nc = n.c(); R['oldpw_new_conn'] = str(sh(nc, 'AUTH', 'S3cretPw')); sh(nc, 'AUTH', 'NewPw!')
print()
print('== 七:密码会不会漏在 MONITOR / SLOWLOG / CLIENT LIST 里')
sh(a, 'AUTH', 'NewPw!'); sh(a, 'CONFIG', 'SET', 'slowlog-log-slower-than', 0)
m = n.c(); m.do('AUTH', 'NewPw!'); m.send('MONITOR'); print('  MONITOR 回复:', m.read())
z = n.c(); z.do('AUTH', 'NewPw!'); z.do('AUTH', 'alice', 'ap'); z.do('AUTH', 'alice', 'bad-guess', raise_err=False)
z.do('ACL', 'SETUSER', 'alice', '>newalicepw', raise_err=False); a.do('CONFIG', 'SET', 'requirepass', 'NewPw!')
lines = []
m.s.settimeout(1)
try:
    while True: lines.append(m.read())
except Exception: pass
print('  MONITOR 里与认证相关的行:')
for l in lines:
    if any(k in l.lower() for k in ('auth', 'setuser', 'requirepass')): print('   ', l[:160])
R['monitor'] = [l for l in lines if any(k in l.lower() for k in ('auth', 'setuser', 'requirepass'))]
sl = a.do('SLOWLOG', 'GET', 30); print('  SLOWLOG 里与认证相关的条目(命令参数):')
sla = []
for ent in sl:
    args = ent[3]
    if args and args[0].lower() in ('auth', 'acl', 'config'): 
        if args[0].lower() == 'config' and not (len(args) > 2 and args[2].lower() == 'requirepass'): continue
        if args[0].lower() == 'acl' and args[1].lower() != 'setuser': continue
        print('   ', args); sla.append(args)
R['slowlog'] = sla
print('  CLIENT LIST 里有没有密码文本:', 'NewPw!' in a.do('CLIENT', 'LIST') or 'ap' in a.do('CLIENT', 'LIST').split('cmd=')[-1] and False)
print()
print('== 八:猜密码能有多快?未登录的连接,错误密码的尝试速度')
w = n.c(); t0 = time.perf_counter(); N1 = 5000
for i in range(N1): w.do('AUTH', 'default', f'guess{i}', raise_err=False)
dt1 = time.perf_counter() - t0
print(f'  一问一答:{N1} 次错误 AUTH {dt1:.2f} s → {N1 / dt1:.0f} 次/秒')
st0 = int(info(a, 'stats')['acl_access_denied_auth'])
import socket as _s
sk = _s.create_connection(('127.0.0.1', n.port)); sk.settimeout(0.2)
N2 = 20000; pw = 'NewPw!'
payload = b''.join(C.enc(['AUTH', 'default', f'guess{i}']) for i in range(N2)) + C.enc(['AUTH', 'default', pw]) + C.enc(['PING'])
t0 = time.perf_counter(); sk.sendall(payload); buf = b''; tok = None
while time.perf_counter() - t0 < 20:
    try:
        x = sk.recv(65536)
        if not x: break
        buf += x
    except _s.timeout:
        pass
    if b'+PONG' in buf: tok = time.perf_counter() - t0; break
dt2 = tok if tok else time.perf_counter() - t0
st1 = int(info(a, 'stats')['acl_access_denied_auth'])
print(f'  流水线:{N2} 次错误 AUTH + 1 次正确 AUTH + PING 一次性发出,{dt2:.2f} s 后收到 PONG;')
print(f'  收到的全部回复字节数 {len(buf)},其中 WRONGPASS {buf.count(b"WRONGPASS")} 条、OK {buf.count(b"+OK")} 条、PONG {buf.count(b"+PONG")} 条')
print(f'  服务端 INFO stats 里 acl_access_denied_auth 增加了 {st1 - st0}(这 {N2} 次错误尝试都被计数,但客户端只收到 {buf.count(b"WRONGPASS")} 条错误回复)')
R['brute'] = dict(n1=N1, secs1=dt1, rate1=N1 / dt1, n2=N2, secs2=dt2, rate2=N2 / dt2, wrong_replies=buf.count(b'WRONGPASS'), ok=buf.count(b'+OK'), pong=buf.count(b'+PONG'), counter=st1 - st0)
save('r126', R); cleanup([n])
