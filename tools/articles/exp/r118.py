import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r118'); R = {}
n = Node(8240, name='r118').start(); c = n.c()
N = 1000000
for i in range(0, N, 20000): c.pipeline([['SET', f'k:{i+j}', 'v'] for j in range(20000)])
print(f'== 一:SCAN 的游标:每次返回 [下一个游标, 一批 key],游标不是递增的序号(库里 {N} 个 key)')
cur = '0'; seq = []
for _ in range(8):
    r = c.do('SCAN', cur, 'COUNT', 10); seq.append((cur, len(r[1]))); cur = r[0]
print('  前 8 次调用的 (传入游标, 返回 key 数):', seq)
print('  一次完整遍历(COUNT 10 时前 8 次的游标值)是:', [s[0] for s in seq], '——不是 0,10,20…,而是按「二进制位倒序」推进')
R['seq'] = seq
print()
print('== 二:每次 SCAN 调用的耗时 vs KEYS *(100 万个 key)')
print(f'{"命令":<22} {"单次耗时 ms":>12} {"完成一轮遍历需要调用次数":>24} {"另一个连接 PING 最大停顿 ms":>26}')
def probe_during(fn):
    stop = threading.Event(); lat = []
    def pr():
        cp = n.c()
        while not stop.is_set(): t = time.perf_counter(); cp.do('PING'); lat.append((time.perf_counter() - t) * 1000); time.sleep(0.0005)
    th = threading.Thread(target=pr); th.start(); time.sleep(0.1); r = fn(); time.sleep(0.05); stop.set(); th.join(); return r, max(lat)
R['cost'] = []
for cnt in (10, 100, 1000, 10000):
    def full():
        cur = '0'; calls = 0; t = []; keys = 0
        while True:
            t0 = time.perf_counter(); r = c.do('SCAN', cur, 'COUNT', cnt); t.append((time.perf_counter() - t0) * 1000); calls += 1; keys += len(r[1]); cur = r[0]
            if cur == '0': break
        return calls, statistics.mean(t), keys
    (calls, mean_ms, keys), stall = probe_during(full) if cnt >= 1000 else (full(), 0)
    print(f'SCAN COUNT {cnt:<10} {mean_ms:>12.3f} {calls:>24} {stall:>26.2f}' if cnt >= 1000 else f'SCAN COUNT {cnt:<10} {mean_ms:>12.3f} {calls:>24} {"(未测)":>26}')
    R['cost'].append((cnt, mean_ms, calls, stall))
def kf():
    t0 = time.perf_counter(); r = c.do('KEYS', '*'); return ((time.perf_counter() - t0) * 1000, len(r))
(ret, stall) = probe_during(kf)
print(f'{"KEYS *":<22} {ret[0]:>12.1f} {1:>24} {stall:>26.2f}')
R['keys'] = (ret[0], stall)
print()
print('== 三:遍历过程中库在变化:SCAN 保证「开始前就在、直到结束都没被删」的 key 一定出现;可能重复;新增的 key 不保证出现')
c.do('FLUSHALL')
for i in range(0, 200000, 20000): c.pipeline([['SET', f'a:{i+j}', 'v'] for j in range(20000)])
seen = []; cur = '0'; added = 0; deleted = 0
first = True
while True:
    r = c.do('SCAN', cur, 'COUNT', 500); seen += r[1]; cur = r[0]
    if added < 400000:                       # 边遍历边增加 key(触发扩容/rehash)
        c.pipeline([['SET', f'b:{added+j}', 'v'] for j in range(10000)]); added += 10000
    if cur == '0': break
u = set(seen); a_seen = sum(1 for k in u if k.startswith('a:')); dup = len(seen) - len(u)
print(f'  开始前的 20 万个 a:* key:遍历到 {a_seen} 个(应为 200000);遍历过程中新增了 {added} 个 b:* key,遍历到其中 {sum(1 for k in u if k.startswith("b:"))} 个;返回的 key 总数 {len(seen)},其中重复 {dup} 个')
R['dyn'] = dict(a_seen=a_seen, added=added, b_seen=sum(1 for k in u if k.startswith('b:')), total=len(seen), dup=dup)
print()
print('== 四:SCAN 的 MATCH 是在取出一批之后再过滤的:COUNT 1000 + MATCH 匹配很少,每次调用可能只返回 0 个')
c.do('FLUSHALL')
for i in range(0, 500000, 20000): c.pipeline([['SET', f'k:{i+j}', 'v'] for j in range(20000)])
c.do('SET', 'special:1', 1); c.do('SET', 'special:2', 1)
cur = '0'; calls = 0; empties = 0; found = 0
while True:
    r = c.do('SCAN', cur, 'MATCH', 'special:*', 'COUNT', 1000); calls += 1; found += len(r[1]); empties += (len(r[1]) == 0); cur = r[0]
    if cur == '0': break
print(f'  50 万个 key、只有 2 个匹配:遍历完需要 {calls} 次调用,其中 {empties} 次返回空数组,共找到 {found} 个')
R['match'] = dict(calls=calls, empties=empties, found=found)
save('r118', R); cleanup([n])
