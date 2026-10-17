import sys, time, os, json, threading, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r130'); R = {}
n = Node(9180, name='s130'); n.start(); a = n.c()
def ev(script, *args, c=None):
    return (c or a).do('EVAL', script, 0, *args, raise_err=False)
def brief(r):
    x = re.sub(r' ?script: [0-9a-f]{40}, on @user_script:\d+\.?', '', str(r).replace('(error) ', '')); x = x.replace('user_script:1: ', '')
    m = re.search(r"nonexistent global variable '(\w+)'", x)
    return f"不存在(读取报错:nonexistent global '{m.group(1)}')" if m else x[:150]
print('== 一:脚本里看得到什么?(Redis 8.10.2 的 Lua 环境)')
r = ev("local t = {} for k in pairs(_G) do t[#t+1] = k end table.sort(t) return t"); print('  全局变量:', brief(r) if isinstance(r, Err) else ' '.join(r)); R['globals'] = r if isinstance(r, list) else str(r)
for name in ('os', 'io', 'package', 'debug', 'string', 'table', 'math', 'cjson', 'cmsgpack', 'struct', 'bit', 'redis'):
    r = ev(f"return type({name})"); R.setdefault('types', {})[name] = brief(r)
print('  库(type):'); [print(f'    {k:<10} {v}') for k, v in R['types'].items()]
for name in ('require', 'dofile', 'loadfile', 'loadstring', 'load', 'print', 'setmetatable', 'getmetatable', 'rawset', 'collectgarbage', 'pcall', 'newproxy'):
    R['types'][name] = brief(ev(f"return type({name})"))
print('  函数(type):'); [print(f'    {k:<14} {R["types"][k]}') for k in ('require', 'dofile', 'loadfile', 'loadstring', 'load', 'print', 'setmetatable', 'getmetatable', 'rawset', 'collectgarbage', 'pcall', 'newproxy')]
R['load1'] = brief(ev("return loadstring('return 1+1')()")); R['load2'] = brief(ev("return loadstring('x = 1')()")); print('  loadstring("return 1+1")() →', R['load1'], ' | loadstring("x = 1")() →', R['load2'])
r = ev("local t = {} for k in pairs(os) do t[#t+1] = k end table.sort(t) return t"); print('  os 里有:', ' '.join(r) if isinstance(r, list) else brief(r)); R['os_keys'] = r if isinstance(r, list) else str(r)
print('  os.execute 的类型:', ev('return type(os.execute)'))
r = ev("local t = {} for k in pairs(redis) do t[#t+1] = k end table.sort(t) return t"); print('  redis 表里有:', ' '.join(r) if isinstance(r, list) else brief(r)); R['redis_keys'] = r if isinstance(r, list) else str(r)
print()
print('== 二:脚本能不能改全局环境、改标准库')
R['mod'] = {}
for label, sc in (('x = 1(创建全局变量)', 'x = 1 return 1'), ('_G.y = 1', '_G.y = 1 return 1'), ('string.foo = 1(改标准库表)', 'string.foo = 1 return 1'), ('redis.foo = 1(改 redis 表)', 'redis.foo = 1 return 1'), ('local z = 1(局部变量)', 'local z = 1 return z'), ('setmetatable(_G, {})', 'setmetatable(_G, {}) return 1'), ('os = nil', 'os = nil return 1')):
    r = ev(sc); print(f'  {label:<28} → {brief(r)}'); R['mod'][label] = brief(r)
print()
print('== 三:脚本里调用各种命令(用 redis.pcall,看返回什么)')
R['cmds'] = {}
for cm in (('SET', 'k', 'v'), ('KEYS', '*'), ('FLUSHDB',), ('CONFIG', 'GET', 'dir'), ('CONFIG', 'SET', 'maxmemory', '0'), ('ACL', 'WHOAMI'), ('SUBSCRIBE', 'ch'), ('MONITOR',), ('WATCH', 'k'), ('MULTI',), ('EVAL', 'return 1', '0'), ('SAVE',), ('BGSAVE',), ('DEBUG', 'SLEEP', '0'), ('BLPOP', 'q', '1'), ('SCRIPT', 'FLUSH'), ('CLIENT', 'LIST'), ('SLAVEOF', 'NO', 'ONE'), ('SHUTDOWN', 'NOSAVE')):
    if cm[0] in ('SHUTDOWN',): continue
    args = ', '.join("'" + x + "'" for x in cm)
    r = ev(f"local r = redis.pcall({args}) if type(r) == 'table' and r.err then return 'ERR: ' .. r.err else return 'OK' end")
    R['cmds'][' '.join(cm)] = brief(r); print(f'  {" ".join(cm):<22} → {brief(r)[:120]}')
print()
print('== 四:ACL 对脚本内部的每一次 redis.call 都生效')
a.do('ACL', 'SETUSER', 'luser', 'on', 'nopass', '~app:*', '-@all', '+eval', '+eval_ro', '+get', '+set')
b = n.c(); b.do('AUTH', 'luser', 'x')
R['acl'] = {}
for label, sc in (("GET app:1", "return redis.call('GET','app:1')"), ("GET other:1", "return redis.call('GET','other:1')"), ("DEL app:1", "return redis.call('DEL','app:1')"), ("KEYS *", "return redis.call('KEYS','*')"), ("SET app:2(KEYS 里没声明该 key)", "return redis.call('SET','app:2','v')"), ("pcall(DEL app:1)", "local r = redis.pcall('DEL','app:1') if type(r)=='table' and r.err then return 'ERR: '..r.err end return 'OK'")):
    r = b.do('EVAL', sc, 0, raise_err=False); R['acl'][label] = brief(r); print(f'  luser 的脚本 {label:<32} → {brief(r)[:170]}')
r = b.do('EVAL_RO', "return redis.call('SET','app:3','v')", 0, raise_err=False); print('  EVAL_RO 里 SET →', brief(r)[:160]); R['acl']['EVAL_RO SET'] = brief(r)
print()
print('== 五:限制脚本:-@scripting 与「只禁 EVAL 系列」的差别(ACL DRYRUN)')
a.do('ACL', 'SETUSER', 'u_cat', 'on', 'nopass', '~*', '&*', '+@all', '-@scripting')
a.do('ACL', 'SETUSER', 'u_eval', 'on', 'nopass', '~*', '&*', '+@all', '-eval', '-evalsha', '-eval_ro', '-evalsha_ro')
tab = {}
for cm in (('EVAL', 'return 1', '0'), ('EVALSHA', 'a' * 40, '0'), ('SCRIPT', 'LOAD', 'return 1'), ('FUNCTION', 'LOAD', '#!lua name=x\nredis.register_function("f", function() return 1 end)'), ('FCALL', 'f', '0'), ('FUNCTION', 'FLUSH')):
    row = [('允许' if a.do('ACL', 'DRYRUN', u, *cm, raise_err=False) == 'OK' else '拒绝') for u in ('u_cat', 'u_eval')]; tab[' '.join(cm)[:24].split('\n')[0]] = row
    print(f'  {" ".join(cm)[:24].split(chr(10))[0]:<26} -@scripting:{row[0]}   只禁 4 条 EVAL 系列:{row[1]}')
R['tab'] = tab
print('  @scripting 分类里的命令:', ' '.join(a.do('ACL', 'CAT', 'scripting')))
print()
print('== 六:死循环脚本与 SCRIPT KILL')
print('  busy-reply-threshold 默认值:', a.do('CONFIG', 'GET', 'busy-reply-threshold')[1], 'ms'); R['thr_default'] = a.do('CONFIG', 'GET', 'busy-reply-threshold')[1]
a.do('CONFIG', 'SET', 'busy-reply-threshold', '500')
def loop_case(script, label):
    victim = n.c(timeout=40); watcher = n.c(timeout=10); killer = n.c(timeout=10); res = {}
    def run():
        t = time.perf_counter()
        try: r = victim.do('EVAL', script, 0, raise_err=False)
        except Exception as e: r = f'<{type(e).__name__}>'
        res['victim'] = (time.perf_counter() - t, brief(r))
    th = threading.Thread(target=run); th.start(); time.sleep(0.1)
    t0 = time.perf_counter(); r = watcher.do('PING', raise_err=False); res['ping'] = (time.perf_counter() - t0, brief(r))
    t1 = time.perf_counter(); r = killer.do('SCRIPT', 'KILL', raise_err=False); res['kill'] = (time.perf_counter() - t1, brief(r))
    return th, res, victim
th, res, victim = loop_case("while true do end", '纯死循环'); th.join(15)
print(f'  纯死循环:另一个连接的 PING 等了 {res["ping"][0]*1000:.0f} ms 才得到 → {res["ping"][1]}')
print(f'  SCRIPT KILL → {res["kill"][1]};死循环那条连接得到 → {res.get("victim", ("", "还在跑"))[1]}')
R['loop'] = dict(ping_ms=res['ping'][0] * 1000, ping=res['ping'][1], kill=res['kill'][1], victim=res.get('victim', ('', ''))[1])
th, res, victim = loop_case("redis.call('SET','w','1') while true do end", '先写后循环')
print(f'  先 SET 再死循环:PING → {res["ping"][1]}')
print(f'  SCRIPT KILL → {res["kill"][1]}'); R['loop_w'] = dict(ping=res['ping'][1], kill=res['kill'][1])
k2 = n.c(timeout=10)
try:
    r = k2.do('SHUTDOWN', 'NOSAVE', raise_err=False); print('  SHUTDOWN NOSAVE →', brief(r))
except Exception as e: print('  SHUTDOWN NOSAVE → 连接断开(进程退出)', type(e).__name__)
time.sleep(1); alive = n.p.poll() is None; print('  进程还在运行吗:', alive); R['loop_w']['alive_after_shutdown'] = alive
save('r130', R); cleanup([n])
