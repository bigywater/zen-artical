import sys, time, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r125'); R = {}
n = Node(9126, name='s125'); n.start(); a = n.c()
sh(a, 'ACL', 'SETUSER', 'app', 'on', '>pw', '~app:*', '-@all', '+get', '+set', '+eval', '+multi', '+exec', '&ok')
print('== 一:四种拒绝原因各触发一次,看 ACL LOG')
b = n.c(); sh(b, 'AUTH', 'app', 'pw')
sh(b, 'DEL', 'app:1'); sh(b, 'GET', 'other:1'); sh(b, 'PUBLISH', 'secret', 'x')
x = n.c(); sh(x, 'AUTH', 'app', 'wrongpw')
log = a.do('ACL', 'LOG'); print(f'  ACL LOG 共 {len(log)} 条(新的在前)')
for e in log:
    d = kv(e); ci = d['client-info']
    print(f'  reason={d["reason"]:<8} context={d["context"]:<8} object={d["object"]:<8} username={d["username"]:<8} count={d["count"]} age={d["age-seconds"]}')
d0 = kv(log[0]); print('  一条完整记录的字段:', ' '.join(d0.keys()))
print('  client-info 示例:', log[0][log[0].index('client-info') + 1][:140])
R['reasons'] = [(kv(e)['reason'], kv(e)['context'], kv(e)['object'], kv(e)['count']) for e in log]; R['fields'] = list(d0.keys())
print()
print('== 二:同一种失败连续 200 次 → 合并成一条,count 递增')
a.do('ACL', 'LOG', 'RESET')
for i in range(200): b.do('GET', 'other:1', raise_err=False)
log = a.do('ACL', 'LOG'); d = kv(log[0]); print(f'  200 次 GET other:1 被拒后,条数 {len(log)},count={d["count"]},timestamp-created→last-updated 相差 {int(d["timestamp-last-updated"]) - int(d["timestamp-created"])} ms')
R['agg'] = dict(entries=len(log), count=d['count'])
print('  换一个 key 名 → 是另一条(object 不同):')
b.do('GET', 'other:2', raise_err=False); print('  条数变为', len(a.do('ACL', 'LOG')))
print()
print('== 三:暴力猜密码:500 次错误 AUTH(每次新连接)')
a.do('ACL', 'LOG', 'RESET'); t0 = time.perf_counter()
for i in range(500):
    c = n.c(); c.do('AUTH', 'app', f'guess{i}', raise_err=False); c.close()
dt = time.perf_counter() - t0
log = a.do('ACL', 'LOG'); d = kv(log[0]); print(f'  用时 {dt:.2f} s,ACL LOG {len(log)} 条:reason={d["reason"]} object={d["object"]} username={d["username"]} count={d["count"]}')
R['brute'] = dict(n=500, secs=dt, entries=len(log), count=int(d['count']))
print()
print('== 四:MULTI 与 Lua 里被拒:context 字段')
a.do('ACL', 'LOG', 'RESET')
sh(b, 'MULTI'); sh(b, 'DEL', 'app:1'); sh(b, 'EXEC')
sh(b, 'EVAL', "return redis.call('DEL','app:9')", 0)
for e in a.do('ACL', 'LOG'):
    d = kv(e); print(f'  reason={d["reason"]:<8} context={d["context"]:<9} object={d["object"]}')
R['ctx'] = [(kv(e)['reason'], kv(e)['context'], kv(e)['object']) for e in a.do('ACL', 'LOG')]
print()
print('== 五:acllog-max-len 上限(默认值 %s)' % fmt(a.do('CONFIG', 'GET', 'acllog-max-len')[1]))
R['maxlen_default'] = a.do('CONFIG', 'GET', 'acllog-max-len')[1]
sh(a, 'CONFIG', 'SET', 'acllog-max-len', 5); a.do('ACL', 'LOG', 'RESET')
for i in range(12): b.do('GET', f'z{i}', raise_err=False)
log = a.do('ACL', 'LOG'); print('  制造 12 条不同的 key 拒绝后,日志里剩', len(log), '条,保留的 object:', [kv(e)['object'] for e in log])
R['cap'] = dict(kept=len(log), objs=[kv(e)['object'] for e in log])
sh(a, 'ACL', 'LOG', 2, show=False); print('  ACL LOG 2 只取最新 2 条:', len(a.do('ACL', 'LOG', 2)), '条')
sh(a, 'ACL', 'LOG', 'RESET'); print('  RESET 后:', len(a.do('ACL', 'LOG')), '条')
save('r125', R); cleanup([n])
