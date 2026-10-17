import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r117'); R = {}
n = Node(8270, name='r116', conf={'enable-debug-command': 'yes'}).start(); c = n.c()
for i in range(0, 300000, 20000): c.pipeline([['SET', f'small:{i+j}', 'v' * 20] for j in range(20000)])
c.do('SET', 'big:string', 'x' * (5 * 1024 * 1024))
for i in range(0, 200000, 20000): c.pipeline([['RPUSH', 'big:list'] + [f'e{i+j}' for j in range(20000)]])
for i in range(0, 100000, 10000): c.pipeline([['HSET', 'big:hash'] + [x for j in range(10000) for x in (f'f{i+j}', f'value-{i+j}')]])
for i in range(0, 150000, 30000): c.pipeline([['SADD', 'big:set'] + [f'm{i+j}' for j in range(30000)]])
for i in range(0, 50000, 10000): c.pipeline([['ZADD', 'big:zset'] + [x for j in range(10000) for x in (i + j, f'z{i+j}')]])
c.do('HSET', 'small:hash', 'a', 1)
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
def run(args):
    t0 = time.perf_counter(); r = subprocess.run(['redis-cli', '-p', '8270'] + args, capture_output=True, text=True, timeout=300); return ANSI.sub('', r.stdout + r.stderr), time.perf_counter() - t0
print('== 一:redis-cli --bigkeys(按「元素个数」找每种类型最大的 key;字符串按字节数),-i 0.01 表示每 100 次 SCAN 睡 0.01 秒')
out, dt = run(['--bigkeys', '-i', '0.01']); L = [l for l in out.splitlines() if l.strip() and not l.startswith('[') or 'Biggest' in l or 'found' in l]
for l in out.splitlines():
    if l.strip() and (l.startswith('[00.00%]') is False or True) and any(k in l for k in ('Biggest', 'found', 'keys with', 'Sampled', 'total', '------', 'summary')): print('  ' + l[:140])
print(f'  (耗时 {dt:.1f} s)'); R['bigkeys'] = [l for l in out.splitlines() if 'Biggest' in l or 'found' in l or 'Sampled' in l][:14]; R['bk_s'] = dt
print()
print('== 二:redis-cli --memkeys(按 MEMORY USAGE 字节数找每种类型最大的 key)')
out, dt = run(['--memkeys', '-i', '0.01'])
for l in out.splitlines():
    if any(k in l for k in ('Biggest', 'found', 'Sampled', 'total', '-----', 'summary')): print('  ' + l[:140])
print(f'  (耗时 {dt:.1f} s)'); R['memkeys'] = [l for l in out.splitlines() if 'Biggest' in l or 'found' in l or 'Sampled' in l][:14]
print()
print('== 三:两者排出的「最大」并不相同:--bigkeys 里 list 是 200000 个元素最多,而字节数最大的其实是 big:set')
for k in ('big:list', 'big:hash', 'big:set', 'big:zset', 'big:string'):
    print(f'  {k:<12} 元素数 {c.do({"big:list":"LLEN","big:hash":"HLEN","big:set":"SCARD","big:zset":"ZCARD","big:string":"STRLEN"}[k], k):>8}  MEMORY USAGE {c.do("MEMORY", "USAGE", k):>9}')
save('r117', R); cleanup([n])
