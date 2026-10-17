import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r115'); R = {}
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
n = Node(8280, name='r115', conf={'maxmemory-policy': 'allkeys-lfu', 'maxmemory': '2gb'}).start(); c = n.c()
N = 100000
for i in range(0, N, 20000): c.pipeline([['SET', f'k:{i+j}', 'v' * 20] for j in range(20000)])
c.do('SET', 'hot:1', 'x'); c.do('SET', 'hot:2', 'x')
rnd = random.Random(2); total = 500000; cnt = collections.Counter(); cmds = []
for _ in range(total):
    r = rnd.random()
    k = 'hot:1' if r < 0.30 else ('hot:2' if r < 0.40 else f'k:{rnd.randrange(N)}')
    cnt[k] += 1; cmds.append(['GET', k])
for i in range(0, total, 5000): c.pipeline(cmds[i:i + 5000])
print(f'== 一:负载:{total} 次 GET;hot:1 占 30%,hot:2 占 10%,其余 {N} 个 key 均匀(每个约 {(total*0.6)/N:.1f} 次)')
print('  实际次数:', dict(cnt.most_common(3)))
R['cnt'] = dict(cnt.most_common(3))
print()
print('== 二:OBJECT FREQ(LFU 策略下的对数访问频率计数器,0–255)')
for k in ('hot:1', 'hot:2', 'k:1', 'k:2', 'k:3'): print(f'  {k:<7} OBJECT FREQ = {c.do("OBJECT", "FREQ", k)}   真实访问次数 {cnt[k]}')
R['freq'] = {k: (c.do('OBJECT', 'FREQ', k), cnt[k]) for k in ('hot:1', 'hot:2', 'k:1', 'k:2')}
print()
print('== 三:redis-cli --hotkeys(需要 maxmemory-policy 是 LFU 类;扫全库读每个 key 的 OBJECT FREQ)')
t0 = time.perf_counter(); r = subprocess.run(['redis-cli', '-p', '8280', '--hotkeys', '-i', '0.01'], capture_output=True, text=True, timeout=300); dt = time.perf_counter() - t0
out = ANSI.sub('', r.stdout + r.stderr)
for l in out.splitlines():
    if any(k in l for k in ('summary', 'hot key', 'Sampled', 'Hot key')) or l.strip().startswith('hot key'): print('  ' + l[:140])
print(f'  (耗时 {dt:.1f} s)'); R['hot'] = [l for l in out.splitlines() if 'hot key found' in l or 'Sampled' in l or l.strip().startswith('hot key')][:8]
print()
print('== 四:LFU 未启用时 --hotkeys 拒绝工作')
c.do('CONFIG', 'SET', 'maxmemory-policy', 'noeviction')
r = subprocess.run(['redis-cli', '-p', '8280', '--hotkeys'], capture_output=True, text=True, timeout=60); msg = ANSI.sub('', r.stdout + r.stderr).strip().splitlines()
print('  ', msg[-2:] if len(msg) > 1 else msg); R['noevict'] = msg[-2:]
print('  OBJECT FREQ hot:1(policy 非 LFU 时)→', c.do('OBJECT', 'FREQ', 'hot:1', raise_err=False))
R['objfreq_err'] = str(c.do('OBJECT', 'FREQ', 'hot:1', raise_err=False))
print()
print('== 五:热 key 对分片的影响(按 CRC16 计算,不是在真实集群上跑的):3 个分片上这 50 万次请求的分布')
own = lambda k: keyslot(k) * 3 // 16384
shard = collections.Counter()
for k, v in cnt.items(): shard[own(k)] += v
print('  各分片的请求数:', dict(sorted(shard.items())), ' 热 key hot:1 所在分片 =', own('hot:1'), ',hot:2 所在分片 =', own('hot:2'))
R['shard'] = dict(shard); R['hot1'] = own('hot:1'); R['hot2'] = own('hot:2')
save('r115', R); cleanup([n])
