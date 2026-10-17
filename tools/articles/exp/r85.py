import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r85'); R = {}
t0 = time.perf_counter()
# 手工起:先起主从和 sentinel,量 sentinel 互相发现与发现从库的耗时
nc = {'repl-diskless-sync-delay': '0'}
nodes = [Node(7600, name='s85m', conf=nc)] + [Node(7601 + i, name=f's85r{i}', conf=dict(nc, replicaof='127.0.0.1 7600')) for i in range(2)]
for n in nodes: n.start()
for n in nodes[1:]: wait_link(n.c())
sents = [Node(7620 + i, name=f's85s{i}', conf={'sentinel monitor': 'mymaster 127.0.0.1 7600 2', 'sentinel down-after-milliseconds': 'mymaster 3000', 'sentinel failover-timeout': 'mymaster 10000', 'sentinel parallel-syncs': 'mymaster 1'}, sentinel=True) for i in range(3)]
print('== 一:sentinel 配置里只写了主库地址。启动 3 个 sentinel 后,它们多久才发现另外两个 sentinel 和 2 个从库?')
ts = time.perf_counter()
for s in sents: s.start()
seen = {}
while time.perf_counter() - ts < 30:
    for i, s in enumerate(sents):
        m = sentinel_master(s.c()); k = (i, int(m['num-slaves']), int(m['num-other-sentinels']))
        if k not in seen: seen[k] = time.perf_counter() - ts; print(f'  +{seen[k]*1000:6.0f} ms  sentinel{i}: 已知从库 {k[1]} 个,已知其它 sentinel {k[2]} 个')
    if all(int(sentinel_master(s.c())['num-slaves']) == 2 and int(sentinel_master(s.c())['num-other-sentinels']) == 2 for s in sents): break
    time.sleep(0.05)
tready = time.perf_counter() - ts
print(f'  三个 sentinel 都发现了 2 个从库、2 个其它 sentinel:{tready:.1f} s')
R['ready'] = tready
c = sents[0].c()
print()
print('== 二:SENTINEL MASTER(节选)')
m = sentinel_master(c)
for k in ('name', 'ip', 'port', 'flags', 'num-slaves', 'num-other-sentinels', 'quorum', 'down-after-milliseconds', 'failover-timeout', 'parallel-syncs', 'last-ping-reply', 'role-reported'): print(f'  {k:<26} {m.get(k)}')
print()
print('== 三:SENTINEL REPLICAS 与 SENTINEL SENTINELS')
for r_ in c.do('SENTINEL', 'REPLICAS', 'mymaster'):
    d = kv(r_); print(f'  replica {d["ip"]}:{d["port"]} flags={d["flags"]} master-link-status={d["master-link-status"]} slave-priority={d["slave-priority"]} slave-repl-offset={d["slave-repl-offset"]}')
for s_ in c.do('SENTINEL', 'SENTINELS', 'mymaster'):
    d = kv(s_); print(f'  sentinel {d["ip"]}:{d["port"]} flags={d["flags"]} last-hello-message={d["last-hello-message"]} ms')
sh(c, 'SENTINEL', 'CKQUORUM', 'mymaster')
print()
print('== 四:sentinel 对主库的探测频率:12 秒内主库上各命令调用次数的增量(来自 INFO commandstats)')
mc = nodes[0].c();
def cs():
    d = info(mc, 'commandstats'); return {k.replace('cmdstat_', ''): int(v.split(',')[0].split('=')[1]) for k, v in d.items() if k.startswith('cmdstat_')}
a = cs(); time.sleep(12); b = cs()
diff = {k: b.get(k, 0) - a.get(k, 0) for k in b if b.get(k, 0) - a.get(k, 0) > 0}
print('  ', diff, '(3 个 sentinel,12 秒)')
R['probe'] = diff
cl = [l for l in mc.do('CLIENT', 'LIST').splitlines() if 'sentinel' in l]
print(f'  主库上的 sentinel 连接 {len(cl)} 个,示例:', re.sub(r'(id|addr|laddr|fd|age|idle|tot-[a-z-]+|omem|events|user|redir|resp|lib-[a-z]+|io-thread|argv-mem|multi-mem|obl|oll|qbuf[a-z-]*|flags|db|sub|psub|ssub|multi|watch|cmd)=\S+ ?', lambda m_: m_.group(0) if m_.group(1) in ('name', 'cmd', 'flags') else '', cl[0]).strip()[:150] if cl else '')
names = sorted(set(re.search(r'name=(\S+)', l).group(1)[:14] for l in cl if 'name=' in l))
R['nconn'] = len(cl)
print()
print('== 五:sentinel 把发现的拓扑写回自己的配置文件')
print('  ' + '\n  '.join(l for l in (sents[0].dir / 'sentinel.conf').read_text().splitlines() if l.startswith('sentinel') and 'known' in l or l.startswith('sentinel monitor') or 'myid' in l or 'current-epoch' in l))
save('r85', R); cleanup(sents + nodes)
