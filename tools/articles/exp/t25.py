import sys, os, itertools; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from etcdt import Etcd, Px
import redis as redislib
from rl import Node as RNode
tee('t25'); reset(); subprocess.run("pkill -f 'etcd --name t25' 2>/dev/null; true", shell=True)
E = Etcd('t25').start(); L = E.leader_idx(); F = [i for i in range(E.n) if i != L]
print(f'etcd 3.7.2 三个节点(leader = t24 风格的编号 t25n{L},follower = {[f"t25n{i}" for i in F]});读写走 HTTP/JSON 网关长连接;所有 peer 通信经过可调延迟的代理(第一、四节用来制造“follower 落后一点”);Redis 8.10.2 一主一从(异步复制),replica 到 master 的连接也经过同样的延迟代理')
def pct(l, p): return sorted(l)[max(int(len(l) * p) - 1, 0)]

print('== 一:etcd 里“写完立刻读”:对 leader 写 key = i 并等到确认,马上到一个 follower 上读。可串行化读(serializable,只读该 follower 自己的状态)vs 线性一致读(默认,要向 leader 确认);各 300 次')
rows = []
for dname, d in (('网络无额外延迟', 0), ('peer 通信每个方向 +20 ms', 20)):
    E.set_delay(d); time.sleep(0.6); cw = E.conn(L); cr = E.conn(F[0]); res = {}
    for mode, ser in (('serializable', True), ('linearizable', False)):
        stale = 0; lat = []
        for i in range(300):
            v = f'{mode}-{d}-{i}'; E.put(L, 'k', v, c=cw)
            t0 = time.perf_counter(); got = E.get(F[0], 'k', serializable=ser, c=cr); lat.append(time.perf_counter() - t0); stale += (got != v)
        res[mode] = (stale, statistics.median(lat) * 1000, pct(lat, 0.99) * 1000)
    rows.append((dname, f'{res["serializable"][0]} / 300', f'{res["serializable"][1]:.2f} ms', f'{res["linearizable"][0]} / 300', f'{res["linearizable"][1]:.2f} ms', f'{res["linearizable"][2]:.1f} ms'))
E.set_delay(0)
table(rows, ['条件', '可串行化读读到旧值的次数', '可串行化读延迟中位数', '线性一致读读到旧值的次数', '线性一致读延迟中位数', '线性一致读 p99'])
print('  可串行化读不需要问 leader,所以快,但读到的是这个 follower 当前应用到的状态——可能比刚确认的写入旧;线性一致读要先向 leader 确认当前的提交位置再读,保证读到的不比任何已完成的写入旧,代价是多一次与 leader 的往返')

print('== 二:Redis 主从(异步复制):写 master、立刻读 replica(300 次);对照写完之后用 WAIT 1 0 等 replica 确认再读')
RPM, RPR, RPX = free_port(), free_port(), free_port()
rm = RNode(RPM, 't25_m').start(); px = Px(RPX, RPM, 0); rr = RNode(RPR, 't25_r', conf={'replicaof': f'127.0.0.1 {RPX}'}).start()
M = redislib.Redis(port=RPM, decode_responses=True); Rr = redislib.Redis(port=RPR, decode_responses=True)
t0 = time.time()
while Rr.info('replication').get('master_link_status') != 'up' and time.time() - t0 < 20: time.sleep(0.1)
time.sleep(1.0)
for i in range(300): M.set('warm', i)                                  # 预热:让复制流量真正跑起来,等 replica 的偏移量追上 master
while Rr.info('replication').get('slave_repl_offset') != M.info('replication').get('master_repl_offset') and time.time() - t0 < 30: time.sleep(0.05)
rows = []
for dname, d in (('无额外延迟', 0), ('master ↔ replica 每个方向 +5 ms', 5), ('每个方向 +20 ms', 20)):
    px.d = d / 1000.0; time.sleep(0.3); out = {}
    for mode in ('async', 'wait'):
        stale = 0; lat = []
        for i in range(300):
            v = f'{mode}-{d}-{i}'; t0 = time.perf_counter(); M.set('k', v)
            if mode == 'wait': M.execute_command('WAIT', 1, 0)
            got = Rr.get('k'); lat.append(time.perf_counter() - t0); stale += (got != v)
        out[mode] = (stale, statistics.median(lat) * 1000)
    rows.append((dname, f'{out["async"][0]} / 300', f'{out["async"][1]:.2f} ms', f'{out["wait"][0]} / 300', f'{out["wait"][1]:.2f} ms'))
table(rows, ['条件', '异步复制:读 replica 读到旧值的次数', '写 + 读的总耗时(中位数)', '写后 WAIT 1 0 再读:读到旧值的次数', '写 + WAIT + 读的总耗时(中位数)'])
print('  Redis 的复制是异步的:master 回复写入时 replica 往往还没收到。WAIT 1 0 让写入等到 1 个 replica 确认,之后读这个 replica 就不会旧,代价是每次写多一个往返(不是线性一致:WAIT 只保证到这个 replica 已确认,别的读者和别的 replica 不在保证里)')

print('== 三:最终一致的“收敛时间”:写 master 之后,轮询 replica 直到看到新值,各 200 次的分布')
rows = []
for dname, d in (('无额外延迟', 0), ('每个方向 +5 ms', 5), ('每个方向 +20 ms', 20)):
    px.d = d / 1000.0; time.sleep(0.3); conv = []
    for i in range(200):
        v = f'c-{d}-{i}'; t0 = time.perf_counter(); M.set('k2', v)
        while Rr.get('k2') != v: pass
        conv.append(time.perf_counter() - t0)
    rows.append((dname, f'{statistics.median(conv) * 1000:.2f} ms', f'{pct(conv, 0.99) * 1000:.2f} ms', f'{max(conv) * 1000:.2f} ms'))
table(rows, ['条件', '收敛时间中位数', 'p99', '最大'])
print('  “最终”有多久,取决于复制延迟:无延迟时是亚毫秒到毫秒,链路延迟越大越长;没有人保证它有上限(链路断了就一直不收敛)')
M.close(); Rr.close(); px.close(); rm.kill9(); rr.kill9()
import rl; shutil.rmtree(rl.RDATA / 't25_m', ignore_errors=True); shutil.rmtree(rl.RDATA / 't25_r', ignore_errors=True)

print('== 四:用线性一致性检查器判定:4 个客户端各做 3 次操作(读或写同一个 key),记录每个操作的开始 / 结束时间,检查有没有一个总顺序既满足“已经结束的操作排在后开始的操作前面”、又满足寄存器语义;etcd 上 100 段历史,读走 follower')
def linearizable(ops):
    """ops: [(invoke, ret, kind, value)];单个寄存器,初值 None。DFS:每一步挑一个“没有别的未放置操作在它开始之前就已结束”的操作放进总顺序。"""
    n = len(ops); memo = set()
    def go(placed, state):
        if placed == (1 << n) - 1: return True
        key = (placed, state)
        if key in memo: return False
        mret = min(ops[j][1] for j in range(n) if not placed >> j & 1)
        for i in range(n):
            if placed >> i & 1: continue
            inv, ret, kind, val = ops[i]
            if inv > mret: continue                                  # 有别的操作在它开始之前就结束了,它不能排在那个操作前面
            if kind == 'r' and val != state: continue
            if go(placed | 1 << i, val if kind == 'w' else state): return True
        memo.add(key); return False
    return go(0, None)
def history(mode, seed):
    rng = random.Random(seed); E.put(L, 'x', 'init'); ops = []; lk = threading.Lock(); ctr = itertools.count(1); E.put(L, 'x', 'v0')
    def client(cid):
        cw = E.conn(L); cr = E.conn(F[cid % 2]); r = random.Random(seed * 10 + cid)
        for _ in range(3):
            time.sleep(r.random() * 0.01)
            if r.random() < 0.45:
                v = f'w{next(ctr)}'; t0 = time.perf_counter(); E.put(L, 'x', v, c=cw); t1 = time.perf_counter()
                with lk: ops.append((t0, t1, 'w', v))
            else:
                t0 = time.perf_counter(); got = E.get(F[cid % 2], 'x', serializable=(mode == 'serializable'), c=cr); t1 = time.perf_counter()
                with lk: ops.append((t0, t1, 'r', got))
        cw.close(); cr.close()
    ts = [threading.Thread(target=client, args=(c,)) for c in range(4)]; [t.start() for t in ts]; [t.join() for t in ts]
    return [(a, b, k, 'v0' if (k == 'r' and False) else v) for a, b, k, v in ops]
rows = []
for dname, d in (('网络无额外延迟', 0), ('peer 通信每个方向 +20 ms', 20)):
    E.set_delay(d); time.sleep(0.6)
    for mode in ('serializable', 'linearizable'):
        bad = 0; first_bad = None; n = 100
        for s in range(n):
            h = history(mode, s)
            # 初值:每段历史开头先写入 v0,把它当作一个在所有操作之前完成的写
            h2 = [(-1.0, -0.5, 'w', 'v0')] + h
            if not linearizable(h2):
                bad += 1; first_bad = first_bad or h2
        rows.append((dname, '读走 follower 的可串行化读' if mode == 'serializable' else '读走 follower 的线性一致读', n, bad))
        if first_bad and mode == 'serializable' and d == 20:
            print('  一段不可线性化的历史(每段开头先写 init、再写 v0,两次写入在其它操作开始之前就已经确认;下面是之后的操作,按开始时间排序,时间相对第一个操作,ms;读到 init 的读,读到的比已经确认的 v0 还旧):')
            t_base = min(o[0] for o in first_bad[1:])
            for inv, ret, kind, val in sorted(first_bad[1:], key=lambda o: o[0]): print(f'    {(inv - t_base) * 1000:7.2f} → {(ret - t_base) * 1000:7.2f}  {"写" if kind == "w" else "读"} {val}')
E.set_delay(0)
table(rows, ['条件', '读的方式', '历史段数', '不可线性化的段数'])
print('  线性一致读下 100 段历史全部可以找到合法的总顺序;可串行化读在 follower 落后(这里靠加延迟制造)时,会出现“某个写已经确认、之后开始的读却读到更旧的值”的历史,检查器找不到任何合法的顺序')
E.stop(); reset(); subprocess.run("pkill -f 'etcd --name t25' 2>/dev/null; true", shell=True)
