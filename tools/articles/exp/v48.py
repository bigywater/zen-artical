import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
from etcdt import Etcd, b64
import shutil
tee('v48'); reset()
print('服务发现的一致性取舍:CP(分区时宁可不可用也不返回不一致的结果)与 AP(分区时两边都继续服务,事后合并)。真实的 CP 系统:etcd 3.7.2 和 Consul 2.0.4(各自 3 个 server 的集群,都是 Raft);AP 的一边,用我写的一个很小的多主复制模型(没有真的用 Nacos 的 AP 实现)演示分区期间两边都可用、事后合并时的冲突。分区用“杀掉其余节点,只剩一个”来模拟(从剩下那个节点看,和被分区隔离出来是一样的)')
for i in range(3): shutil.rmtree(TT / f'etcd_v48_{i}', ignore_errors=True); shutil.rmtree(TT / f'v48c_{i}', ignore_errors=True)

# ============ 一 ============
print('== 一:Consul 失去多数。3 个 server,杀掉 2 个,只剩 1 个。在这个剩下的节点上做:默认读(GET /v1/kv/k)、?stale 读、?consistent 读、写入(PUT)、查询服务目录(默认 / ?stale)。约 3 秒后开始,请求超时 5 s。对照 etcd(第 47 篇测过:线性一致读、写入、续约都超时,serializable 读成功)')
CC = ConsulCluster('v48c', 3).start(); CC.http(0, 'PUT', '/v1/kv/k', b'v1'); CC.http(0, 'PUT', '/v1/agent/service/register', {'Name': 'web', 'ID': 'web1', 'Port': 8080}); time.sleep(1.0)
leader = CC.leader(); lport = int(leader.split(':')[1]); li = next(i for i in range(3) if CC.ports[i]['srv'] == lport); fol = [i for i in range(3) if i != li]; alone = fol[0]
CC.kill_node(li); CC.kill_node(fol[1]); time.sleep(3.0)
def attempt(method, path, body=None, to=5.0):
    t0 = time.perf_counter()
    try: s, d = CC.http(alone, method, path, body, to); return f'HTTP {s}' + (f'({d[:60].decode(errors="replace").strip()})' if s != 200 else (f',读到 {len(json.loads(d)) if d.startswith(b"[") else "ok"}' if method == 'GET' else '')) + f' · {(time.perf_counter() - t0) * 1000:.0f} ms'
    except Exception as e: return f'失败:{type(e).__name__} · {(time.perf_counter() - t0) * 1000:.0f} ms'
rows = [('读 KV(默认)', attempt('GET', '/v1/kv/k')), ('读 KV(?stale)', attempt('GET', '/v1/kv/k?stale')), ('读 KV(?consistent)', attempt('GET', '/v1/kv/k?consistent')), ('写 KV', attempt('PUT', '/v1/kv/k', b'v2')), ('服务目录(默认)', attempt('GET', '/v1/catalog/service/web')), ('服务目录(?stale)', attempt('GET', '/v1/catalog/service/web?stale'))]
table(rows, ['操作(只剩 1 个 server)', '结果'])
CC.stop_all()
print('  Consul 默认的读要经过 leader,没有 leader 就失败;加 ?stale 之后任何 server 都可以回答(可能是旧数据),所以剩下的节点还能返回服务目录;写入需要多数,失败。和 etcd 的 serializable 读是同一个思路:用“可能旧”换“可用”,由调用方显式选择')

# ============ 二 ============
print('== 二:leader 挂了之后多久恢复写入。3 节点集群,每秒写一次(超时 1 s),杀掉 leader,统计从杀掉到第一次写入成功的时间(每个系统重复 4 次,每次之后把被杀的节点拉起来并等集群恢复)。etcd 3.7.2 默认选举超时 1 s;Consul 用默认的 Raft 参数')
E3 = Etcd('v48', n=3).start(); CC = ConsulCluster('v48c2', 3)
for i in range(3): shutil.rmtree(TT / f'v48c2_{i}', ignore_errors=True)
CC.start()
def etcd_put(i):
    try: s, d = E3.call(i, '/v3/kv/put', {'key': b64('/k'), 'value': b64('v')}, 1.0); return s == 200
    except Exception: return False
def consul_put(i):
    try: s, d = CC.http(i, 'PUT', '/v1/kv/k', b'v', 1.0); return s == 200 and d.strip() == b'true'
    except Exception: return False
res = {'etcd': [], 'consul': []}
for rnd in range(4):
    li = E3.leader_idx(); alive = [i for i in range(3) if i != li]; t0 = time.perf_counter(); E3.kill_node(li); dt = None
    while time.perf_counter() - t0 < 30:
        if any(etcd_put(i) for i in alive): dt = time.perf_counter() - t0; break
        time.sleep(0.05)
    res['etcd'].append(dt); E3.start_node(li); E3.wait_leader(30); time.sleep(1.5)
for rnd in range(4):
    lp = int(CC.leader().split(':')[1]); li = next(i for i in range(3) if CC.ports[i]['srv'] == lp); alive = [i for i in range(3) if i != li]; t0 = time.perf_counter(); CC.kill_node(li); dt = None
    while time.perf_counter() - t0 < 60:
        if any(consul_put(i) for i in alive): dt = time.perf_counter() - t0; break
        time.sleep(0.05)
    res['consul'].append(dt); CC.start_node(li); time.sleep(4.0); CC.wait_leader(30)
table([(k, ' / '.join(f'{x:.2f} s' if x is not None else '超时' for x in v), f'{statistics.median([x for x in v if x is not None]):.2f} s' if any(x is not None for x in v) else '-') for k, v in res.items()], ['系统', '4 次:杀掉 leader 到写入恢复', '中位数'])
for i in range(3): E3.kill_node(i)
CC.stop_all()
print('  两个 CP 系统在 leader 挂掉之后都要先重新选主才能继续写,期间(这里是秒级)写入不可用;时间取决于选举超时等参数(这里用的都是默认值,不同的调参结果不同)')

# ============ 三 ============
print('== 三:AP 模型:多主复制 + 最后写入者胜。3 个副本 R0、R1、R2 都接受读写,每 0.3 s 做一次反熵(互相交换比自己新的条目,按时间戳取较新的);登记了一个实例 /svc/web = v1。然后把 R0 和 {R1, R2} 分区 3 秒:两边都继续接受写入。分区期间:R0 一侧把 /svc/web 改成 "from-R0",{R1, R2} 一侧改成 "from-R12";另外两边各登记一个不同的新实例。统计:分区期间写入成功率、两边读到的值、愈合之后多久一致、最后留下的值,以及被覆盖(丢掉)的写入')
class AP:
    def __init__(s, rid): s.rid, s.d, s.lk = rid, {}, threading.Lock()
    def put(s, k, v): 
        with s.lk: s.d[k] = (time.time_ns(), v, s.rid)
    def get(s, k): 
        with s.lk: return s.d.get(k, (0, None, ''))[1]
    def merge_from(s, o):
        with o.lk: items = list(o.d.items())
        with s.lk:
            for k, e in items:
                if k not in s.d or e[0] > s.d[k][0]: s.d[k] = e
R = [AP(f'R{i}') for i in range(3)]; part = {'on': False}; stop = threading.Event()
def reach(a, b): return not (part['on'] and ((a == 0) != (b == 0)))
def gossip():
    while not stop.is_set():
        for a in range(3):
            for b in range(3):
                if a != b and reach(a, b): R[a].merge_from(R[b])
        time.sleep(0.3)
threading.Thread(target=gossip, daemon=True).start()
R[0].put('/svc/web', 'v1'); time.sleep(1.0)
part['on'] = True; t_part = time.perf_counter(); ok = 0; tot = 0
R[0].put('/svc/web', 'from-R0'); ok += 1; tot += 1; time.sleep(0.01); R[1].put('/svc/web', 'from-R12'); ok += 1; tot += 1
R[0].put('/svc/a', 'only-R0'); R[2].put('/svc/b', 'only-R12'); ok += 2; tot += 2; time.sleep(1.0)
reads_during = [(f'R{i}', R[i].get('/svc/web'), R[i].get('/svc/a'), R[i].get('/svc/b')) for i in range(3)]
time.sleep(2.0); part['on'] = False; t_heal = time.perf_counter()
while time.perf_counter() - t_heal < 10 and len({R[i].get('/svc/web') for i in range(3)}) > 1: time.sleep(0.02)
conv = time.perf_counter() - t_heal; time.sleep(0.5); stop.set()
table([(f'分区期间 {r[0]} 读到', r[1], r[2], r[3]) for r in reads_during] + [('愈合后三个副本读到', ' / '.join(str(R[i].get('/svc/web')) for i in range(3)), ' / '.join(str(R[i].get('/svc/a')) for i in range(3)), ' / '.join(str(R[i].get('/svc/b')) for i in range(3)))], ['时刻', '/svc/web', '/svc/a', '/svc/b'])
final = R[0].get('/svc/web'); lost = 'from-R0' if final == 'from-R12' else 'from-R12'
print(f'  分区期间 4 次写入全部成功({ok} / {tot}),两边都能读也都能写——可用性是 100%,代价是两边读到不一样的值(/svc/web 在 R0 一侧是 from-R0,在另一侧是 from-R12;/svc/a、/svc/b 只在各自一侧可见)。愈合后 {conv:.2f} s 三个副本收敛到同一个值,/svc/web 留下的是 {final},被覆盖(丢掉)的写入是 {lost};/svc/a 和 /svc/b 因为 key 不同,都保留了下来。对照:CP 系统在少数派一侧(第 1 节)拒绝写入,没有分叉,也没有丢更新;AP 系统用冲突解决(这里是最后写入者胜)换来了分区期间的可用')
