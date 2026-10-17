import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r51'); R = {}
n = Node(7151).start(); c = n.c()
def sub(pats):
    s = C(7151); s.do('PSUBSCRIBE', *pats); return s
def drain(s, t=0.3):
    out = []
    while s.avail(t): out.append(s.read()); t = 0.05
    return out
print('== 一:默认关闭')
sh(c, 'CONFIG', 'GET', 'notify-keyspace-events')
s = sub(['__key*__:*']); c.do('SET', 'k', 'v'); print('订阅 __key*__:* 后 SET k v,收到:', drain(s))
print()
print('== 二:CONFIG SET notify-keyspace-events KEA 之后,一个命令产生两条通知(keyspace 与 keyevent)')
sh(c, 'CONFIG', 'SET', 'notify-keyspace-events', 'KEA')
for cmd in (['SET', 'k', 'v'], ['LPUSH', 'l', 'a'], ['EXPIRE', 'k', 100], ['RENAME', 'k', 'k2'], ['DEL', 'k2']):
    c.do(*cmd); ev = drain(s)
    print('>', ' '.join(map(str, cmd))); [print('   ', e[2], '→', e[3]) for e in ev]
R['n_per_cmd'] = 2
print()
print('== 三:过期事件不是准点的:每次 SET k 值 PX 300,然后等 expired 事件,量它比 300 ms 晚多少(空闲实例,30 次)')
sh(c, 'CONFIG', 'SET', 'notify-keyspace-events', 'Ex')
s.close(); s = C(7151); s.do('SUBSCRIBE', '__keyevent@0__:expired')
d1 = []
for i in range(30):
    t0 = time.perf_counter(); c.do('SET', f'e{i}', 'v', 'PX', 300)
    while not s.avail(0.01): pass
    ev = s.read(); d1.append((time.perf_counter() - t0) * 1000 - 300)
print(f'延迟(事件到达时间 − 300 ms):最小 {min(d1):.1f}  中位 {statistics.median(d1):.1f}  最大 {max(d1):.1f} ms')
R['idle'] = d1
print()
print('== 四:池子里有大量 TTL 很长的 key 时,少量短 TTL key 的 expired 事件要等多久?(每组同时设 30 个 PX 300 的 key,最多等 20 秒)')
R['pool'] = []
print(f'{"长 TTL key 数":>12} {"20 秒内收到":>10} {"最早(ms)":>9} {"中位(ms)":>9} {"最晚(ms)":>9}')
have = 0
for N in (0, 1000, 10000, 100000, 300000):
    while have < N:
        c.pipeline([['SET', f'big{have+j}', 'v', 'EX', 3600] for j in range(5000)]); have += 5000
    tag = f'q{N}'; t0 = time.perf_counter()
    c.pipeline([['SET', f'{tag}_{i}', 'v', 'PX', 300] for i in range(30)])
    dl = []
    while time.perf_counter() - t0 < 20 and len(dl) < 30:
        if s.avail(0.05):
            ev = s.read()
            if ev[2].startswith(tag): dl.append((time.perf_counter() - t0) * 1000 - 300)
    c.pipeline([['DEL', f'{tag}_{i}'] for i in range(30)])
    row = dict(N=N, got=len(dl), lo=min(dl) if dl else None, med=statistics.median(dl) if dl else None, hi=max(dl) if dl else None)
    R['pool'].append(row)
    f = lambda v: f'{v:9.0f}' if v is not None else '        -'
    print(f'{N:>12} {len(dl):>8}/30 {f(row["lo"])} {f(row["med"])} {f(row["hi"])}')
print()
print('== 五:惰性删除:key 已经过期、但后台还没清到它,谁先访问它,expired 事件就在那一刻发出')
c.do('CONFIG', 'SET', 'hz', 1); drain(s, 0.3)
def wait_ev(name, tmax):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < tmax:
        if s.avail(0.01):
            ev = s.read()
            if ev[2] == name: return (time.perf_counter() - t0) * 1000
    return None
c.do('SET', 'lazy', 'v', 'PX', 100); time.sleep(0.5)
t0 = time.perf_counter(); r = c.do('GET', 'lazy'); ms = wait_ev('lazy', 2)
print(f'过期 0.4 秒后,GET lazy → {r};expired 事件在 GET 之后 {ms:.1f} ms 内到达' if ms is not None else f'GET lazy → {r};2 秒内没有收到事件')
R['lazy'] = ms
c.do('SET', 'lazy2', 'v', 'PX', 100)
ms2 = wait_ev('lazy2', 8)
print(f'另一个 key:PX 100,不去访问,(池子里有 {c.do("DBSIZE")} 个 key,hz=1)等 8 秒:' + (f'事件 {ms2:.0f} ms 后到' if ms2 is not None else '8 秒内没有收到 expired 事件'))
R['nolazy'] = ms2
c.do('CONFIG', 'SET', 'hz', 10)
print()
print('== 六:发后即忘:订阅者不在时事件就没了')
s.close()
c.do('SET', 'gone', 'v', 'PX', 100); time.sleep(0.5)
s = C(7151); s.do('SUBSCRIBE', '__keyevent@0__:expired'); print('重新订阅后收到:', drain(s, 0.5) or '什么都没有')
print()
print('== 七:开启通知的写入开销:管道 SET 20 万条,重复 3 次取中位')
def tp(): 
    v = []
    for _ in range(3):
        t = time.perf_counter()
        for i in range(0, 200000, 2000): c.pipeline([['SET', f'p{j}', 'v'] for j in range(i, i + 2000)])
        v.append(200000 / (time.perf_counter() - t))
    return statistics.median(v)
c.do('CONFIG', 'SET', 'notify-keyspace-events', ''); a = tp()
c.do('CONFIG', 'SET', 'notify-keyspace-events', 'KEA'); b = tp()
p = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'subs.py'), '7151', '1', '__keyevent@0__:set'], stdout=subprocess.PIPE, text=True); p.stdout.readline(); time.sleep(0.3)
d = tp(); p.kill(); p.wait()
print(f'关闭通知:{a/1000:.0f}k/s   KEA 但无订阅者:{b/1000:.0f}k/s   KEA 且有 1 个订阅 set 事件的订阅者:{d/1000:.0f}k/s')
R['tp'] = [a, b, d]
save('r51', R); cleanup([n])
