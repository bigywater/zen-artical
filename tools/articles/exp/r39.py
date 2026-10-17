import sys, time, random, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r39'); R = {}
n = Node(7139).start(); c = n.c()

def fill(key, N, fields=('temp', '21.5', 'city', 'sh')):
    B = 2000
    for i in range(0, N, B):
        c.pipeline([['XADD', key, '*', *fields] for _ in range(min(B, N - i))])
    return c.do('XINFO', 'STREAM', key)

print('== 一:条目数与 radix-tree-keys / nodes(默认 stream-node-max-entries=100, stream-node-max-bytes=4096)')
print(f'{"entries":>8} {"radix-keys":>11} {"radix-nodes":>12} {"entries/key":>12} {"MEMORY USAGE":>13} {"B/entry":>8}')
R['grow'] = []
for N in (1, 50, 100, 101, 1000, 10000, 100000):
    k = f's{N}'; kv_ = kv(fill(k, N)); m = c.do('MEMORY', 'USAGE', k, 'SAMPLES', 0)
    keys, nodes = kv_['radix-tree-keys'], kv_['radix-tree-nodes']
    print(f'{N:>8} {keys:>11} {nodes:>12} {N/keys:>12.1f} {m:>13} {m/N:>8.1f}')
    R['grow'].append(dict(N=N, keys=keys, nodes=nodes, mem=m))

print()
print('== 二:XADD 用 * 生成的 ID,同一个毫秒内 seq 递增(连续 XADD 5 条)')
c.do('DEL', 'demo')
ids = [c.do('XADD', 'demo', '*', 'i', i) for i in range(5)]
print(ids); R['ids'] = ids

print()
print('== 三:调 stream-node-max-entries 对 radix 树和内存的影响(同样 10000 条,4 个字段)')
print(f'{"max-entries":>12} {"radix-keys":>11} {"radix-nodes":>12} {"MEMORY USAGE":>13} {"B/entry":>8}')
R['maxent'] = []
for me in (1, 10, 100, 1000, 10000):
    c.do('CONFIG', 'SET', 'stream-node-max-entries', me); c.do('CONFIG', 'SET', 'stream-node-max-bytes', 0)
    k = f'm{me}'; kv_ = kv(fill(k, 10000)); m = c.do('MEMORY', 'USAGE', k, 'SAMPLES', 0)
    print(f'{me:>12} {kv_["radix-tree-keys"]:>11} {kv_["radix-tree-nodes"]:>12} {m:>13} {m/10000:>8.1f}')
    R['maxent'].append(dict(me=me, keys=kv_['radix-tree-keys'], nodes=kv_['radix-tree-nodes'], mem=m))
c.do('CONFIG', 'SET', 'stream-node-max-entries', 100); c.do('CONFIG', 'SET', 'stream-node-max-bytes', 4096)

print()
print('== 四:字段名相同 vs 每条字段不同(各 10000 条,默认配置)')
c.do('DEL', 'same', 'diff')
c.pipeline([['XADD', 'same', '*', 'temp', i, 'city', 'sh'] for i in range(10000)])
c.pipeline([['XADD', 'diff', '*', f'f{i}', i, f'g{i}', 'sh'] for i in range(10000)])
ms, md = c.do('MEMORY', 'USAGE', 'same', 'SAMPLES', 0), c.do('MEMORY', 'USAGE', 'diff', 'SAMPLES', 0)
print(f'相同字段名: {ms} B ({ms/10000:.1f} B/条)   每条不同字段名: {md} B ({md/10000:.1f} B/条)   比值 {md/ms:.2f}')
R['fields'] = dict(same=ms, diff=md)

print()
print('== 五:按 ID 点查的耗时(XRANGE key id id,管道 2000 条一批,共 20000 次随机点查)')
R['lookup'] = []
for N in (1000, 100000, 1000000):
    k = f's{N}' if N <= 100000 else 'big'
    if N == 1000000:
        for i in range(0, N, 5000):
            c.pipeline([['XADD', k, '*', 'temp', '21.5', 'city', 'sh'] for _ in range(5000)])
    allids = [e[0] for e in c.do('XRANGE', k, '-', '+', 'COUNT', 20000)] if N <= 100000 else None
    if allids is None:  # 百万条:先取前面一段、再从末尾一段各取一部分,不然要拉全量
        first = [e[0] for e in c.do('XRANGE', k, '-', '+', 'COUNT', 10000)]
        last = [e[0] for e in c.do('XREVRANGE', k, '+', '-', 'COUNT', 10000)]
        allids = first + last
    random.seed(1); pick = [random.choice(allids) for _ in range(20000)]
    t0 = time.perf_counter()
    for i in range(0, len(pick), 2000):
        c.pipeline([['XRANGE', k, x, x] for x in pick[i:i+2000]])
    dt = time.perf_counter() - t0
    kv_ = kv(c.do('XINFO', 'STREAM', k))
    print(f'N={N:>8}  radix-keys={kv_["radix-tree-keys"]:>6}  20000 次点查 {dt*1000:7.1f} ms  ({dt/20000*1e6:5.1f} µs/次)')
    R['lookup'].append(dict(N=N, keys=kv_['radix-tree-keys'], us=dt / 20000 * 1e6))
print()
print('== 六:节点还受 stream-node-max-bytes(默认 4096)限制:1000 条,值越大,每个 radix key 装得越少')
print(f'{"value bytes":>12} {"radix-keys":>11} {"entries/key":>12}')
R['bytes'] = []
for vb in (10, 100, 500, 2000):
    k = f'v{vb}'; c.do('DEL', k)
    c.pipeline([['XADD', k, '*', 'v', 'x' * vb] for _ in range(1000)])
    kk = kv(c.do('XINFO', 'STREAM', k))['radix-tree-keys']
    print(f'{vb:>12} {kk:>11} {1000/kk:>12.1f}'); R['bytes'].append(dict(vb=vb, keys=kk))
save('r39', R); cleanup([n])
