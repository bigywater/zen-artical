import sys, time, random, os, json, subprocess, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r47'); R = {}
n = Node(7147).start(); c = n.c()
def xlen(k): return c.do('XLEN', k)
print('== 一:XADD 5000 条,MAXLEN 1000 与 MAXLEN ~ 1000 的最终长度(stream-node-max-entries=100)')
for name, args in (('MAXLEN 1000', ['MAXLEN', 1000]), ('MAXLEN ~ 1000', ['MAXLEN', '~', 1000]), ('无裁剪', [])):
    c.do('DEL', 'k')
    for i in range(0, 5000, 500): c.pipeline([['XADD', 'k', *args, '*', 'v', i + j] for j in range(500)])
    d = kv(c.do('XINFO', 'STREAM', 'k'))
    print(f'{name:<16} XLEN = {d["length"]:>5}   radix-keys = {d["radix-tree-keys"]}')
print()
print('== 二:逐条 XADD 300 次,每条之后读一次 XLEN:精确裁剪恒为 1000,近似裁剪在一个区间里锯齿')
R['saw'] = {}
for name, args in (('MAXLEN 1000', ['MAXLEN', 1000]), ('MAXLEN ~ 1000', ['MAXLEN', '~', 1000])):
    c.do('DEL', 'k')
    for i in range(0, 5050, 505): c.pipeline([['XADD', 'k', *args, '*', 'v', i + j] for j in range(505)])
    seq = []
    for i in range(300):
        c.do('XADD', 'k', *args, '*', 'v', i); seq.append(xlen('k'))
    print(f'{name:<16} XLEN 最小 {min(seq)} 最大 {max(seq)};每 20 次取样: {seq[::20]}')
    R['saw'][name] = seq
print()
print('== 三:stream-node-max-entries 改变近似裁剪的最终长度(每种配置 5000 条后取 XLEN)')
print(f'{"node-max-entries":>17} {"XLEN 结果":>10}')
R['len'] = []
for me in (10, 100, 500):
    c.do('CONFIG', 'SET', 'stream-node-max-entries', me); c.do('DEL', 'k')
    for i in range(0, 5000, 500): c.pipeline([['XADD', 'k', 'MAXLEN', '~', 1000, '*', 'v', i + j] for j in range(500)])
    print(f'{me:>17} {xlen("k"):>10}'); R['len'].append((me, xlen('k')))
c.do('CONFIG', 'SET', 'stream-node-max-entries', 100)
print()
print('== 四:代价:稳态(流已满 1000 条)之后,每条 XADD 的耗时。20 万条管道写入,重复 3 次取中位')
import statistics
def bench(args, n_=200000):
    c.do('DEL', 'k'); c.pipeline([['XADD', 'k', '*', 'v', i] for i in range(1000)])
    t0 = time.perf_counter()
    for i in range(0, n_, 2000): c.pipeline([['XADD', 'k', *args, '*', 'v', 'x'] for _ in range(2000)])
    return (time.perf_counter() - t0) / n_ * 1e6
res = {}
for name, args in (('不裁剪', []), ('MAXLEN 1000', ['MAXLEN', 1000]), ('MAXLEN ~ 1000', ['MAXLEN', '~', 1000])):
    v = [bench(args) for _ in range(3)]; res[name] = statistics.median(v)
    print(f'{name:<16} {res[name]:6.2f} µs/条   (三次: {", ".join(f"{x:.2f}" for x in v)})')
R['bench'] = res
print()
print('== 五:一次性裁很多的代价:100 万条流,XTRIM MAXLEN 0 vs MAXLEN ~ 0 LIMIT,看命令耗时')
def big():
    c.do('DEL', 'k')
    for i in range(0, 1000000, 5000): c.pipeline([['XADD', 'k', '*', 'v', 'x'] for _ in range(5000)])
big(); t0 = time.perf_counter(); r = c.do('XTRIM', 'k', 'MAXLEN', 0); d1 = time.perf_counter() - t0
print(f'XTRIM k MAXLEN 0                 删除 {r:>8} 条,命令耗时 {d1*1000:8.1f} ms')
big(); t0 = time.perf_counter(); r = c.do('XTRIM', 'k', 'MAXLEN', '~', 0); d2 = time.perf_counter() - t0
print(f'XTRIM k MAXLEN ~ 0               删除 {r:>8} 条,命令耗时 {d2*1000:8.1f} ms')
big(); t0 = time.perf_counter(); r = c.do('XTRIM', 'k', 'MAXLEN', '~', 0, 'LIMIT', 1000); d3 = time.perf_counter() - t0
print(f'XTRIM k MAXLEN ~ 0 LIMIT 1000    删除 {r:>8} 条,命令耗时 {d3*1000:8.1f} ms  (XLEN 剩 {xlen("k")})')
sh(c, 'XTRIM', 'k', 'MAXLEN', 0, 'LIMIT', 1000)
R['big'] = [d1, d2, d3]
save('r47', R); cleanup([n])
