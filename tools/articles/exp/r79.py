import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r79'); R = {}
ANSI = re.compile(r'\x1b\[[0-9;]*m')
cl = Cluster(7490, 3, 1, name='c79'); time.sleep(1)
N = 300000
cc = CC([7490])
t0 = time.perf_counter()
pipes = collections.defaultdict(list)
for i in range(N):
    pipes[cc.slots[keyslot(f'r:{i}')]].append(['SET', f'r:{i}', i])
for port, cmds in pipes.items():
    c = C(port)
    for j in range(0, len(cmds), 5000): c.pipeline(cmds[j:j + 5000])
print(f'== 一:准备:3 主 3 从,写入 {N} 个 key({time.perf_counter()-t0:.1f} s),每个主库的 DBSIZE:', {n.port: n.c().do('DBSIZE') for n in cl.nodes if 'master' in n.c().do('ROLE')[0]})
time.sleep(1)
# 新增一个空主库
new = Node(7496, name='c79new', conf={'cluster-enabled': 'yes', 'cluster-config-file': 'nodes.conf', 'cluster-node-timeout': '3000', 'appendonly': 'no'}).start()
r = subprocess.run(['redis-cli', '--cluster', 'add-node', '127.0.0.1:7496', '127.0.0.1:7490'], capture_output=True, text=True, timeout=60)
print('\n== 二:redis-cli --cluster add-node(新增一个空主库 7496)')
print('\n'.join('  ' + l for l in ANSI.sub('', r.stdout).strip().splitlines()[-3:]))
time.sleep(2)
def slots_of(port): return sum(int(x.split('-')[-1]) - int(x.split('-')[0]) + 1 for x in [y for z in cluster_nodes(C(7490)) if z['port'] == port for y in z['slots']])
print('  新节点的槽位数:', slots_of(7496))
# 后台流量
stop = threading.Event(); ops = []; errs = []
def traffic():
    c2 = CC([7490]); rnd = random.Random(9); i = 0
    while not stop.is_set():
        k = f'r:{rnd.randrange(N)}'; t = time.perf_counter()
        try:
            if i % 2 == 0:
                v = c2.do(k, 'GET', k); ok = (v == k.split(':')[1])
            else:
                c2.do(k, 'SET', k, k.split(':')[1]); ok = True
            ops.append((t, (time.perf_counter() - t) * 1e6, ok))
        except Exception as e:
            errs.append((t, type(e).__name__))
        i += 1
    ops.append(('stats', c2.moved, c2.ask))
th = threading.Thread(target=traffic); th.start(); time.sleep(2.0)
print('\n== 三:redis-cli --cluster rebalance --cluster-use-empty-masters(把槽位均分给 4 个主库),同时流量不停')
ts = time.perf_counter()
r = subprocess.run(['redis-cli', '--cluster', 'rebalance', '127.0.0.1:7490', '--cluster-use-empty-masters'], capture_output=True, text=True, timeout=600)
te = time.perf_counter()
time.sleep(2.0); stop.set(); th.join()
out_ = ANSI.sub('', r.stdout)
moves = re.findall(r'Moving (\d+) slots from ([\d.:]+) to ([\d.:]+)', out_)
print('  rebalance 输出:'); [print('   ', l) for l in out_.strip().splitlines() if 'Moving' in l or 'Rebalancing' in l or 'Performing' in l]
tot = sum(int(m[0]) for m in moves)
print(f'  搬了 {tot} 个槽,耗时 {te-ts:.1f} s;搬完后各主库槽位数:', {p: slots_of(p) for p in (7490, 7491, 7492, 7496)})
st = [o for o in ops if o[0] == 'stats'][0]; ops = [o for o in ops if o[0] != 'stats']
def phase(a, b):
    L = [o[1] for o in ops if a <= o[0] < b]
    return dict(n=len(L), rate=len(L) / max(b - a, 1e-9), p50=statistics.median(L) if L else 0, p99=sorted(L)[int(len(L) * .99)] if L else 0, mx=max(L) if L else 0)
t_first = ops[0][0]
ph = dict(before=phase(t_first, ts), during=phase(ts, te), after=phase(te, ops[-1][0] + 1e-6))
print()
print(f'  {"阶段":<8} {"操作数":>7} {"ops/s":>8} {"p50 µs":>8} {"p99 µs":>9} {"max µs":>10}')
for nm, k in (('搬迁前', 'before'), ('搬迁中', 'during'), ('搬迁后', 'after')):
    p = ph[k]; print(f'  {nm:<8} {p["n"]:>7} {p["rate"]:>8.0f} {p["p50"]:>8.0f} {p["p99"]:>9.0f} {p["mx"]:>10.0f}')
print(f'  客户端遇到的重定向:MOVED {st[1]} 次,ASK {st[2]} 次;错误 {len(errs)} 次;读到错误值的操作 {sum(1 for o in ops if not o[2])} 次')
R['ph'] = ph; R['moves'] = moves; R['tot'] = tot; R['sec'] = te - ts; R['moved'] = st[1]; R['ask'] = st[2]; R['errs'] = len(errs); R['bad'] = sum(1 for o in ops if not o[2])
print()
print('== 四:搬完后逐个校验 30 万个 key')
cc2 = CC([7490]); bad = 0; t0 = time.perf_counter()
pipes = collections.defaultdict(list)
for i in range(N): pipes[cc2.slots[keyslot(f'r:{i}')]].append(i)
for port, idx in pipes.items():
    c = C(port)
    for j in range(0, len(idx), 5000):
        chunk = idx[j:j + 5000]; res = c.pipeline([['GET', f'r:{i}'] for i in chunk])
        bad += sum(1 for i, v in zip(chunk, res) if v != str(i))
print(f'  校验 {N} 个 key({time.perf_counter()-t0:.1f} s):错误 {bad} 个;新分布 DBSIZE:', {n.port: n.c().do('DBSIZE') for n in cl.nodes + [new] if 'master' in n.c().do('ROLE')[0]})
R['verify_bad'] = bad
R['dbs'] = {str(n.port): n.c().do('DBSIZE') for n in cl.nodes + [new] if 'master' in n.c().do('ROLE')[0]}
save('r79', R); cleanup(cl.nodes + [new])
