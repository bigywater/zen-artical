import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
from etcdt import Etcd, b64
import base64 as b64mod, shutil
tee('v47'); reset()
print('注册中心(3 节点 etcd 3.7.2)不可用时,服务调用方会怎样。3 个后端实例(本进程里的 Python 服务)把自己登记成 /svc/i0、/svc/i1、/svc/i2(带 lease,TTL 20 s,由后台线程续约)。调用方每 1 s 从 etcd 读一次 /svc/ 前缀得到实例列表,请求在列表里轮询。通过 HTTP/JSON 网关访问 etcd(单个调用方依次尝试 3 个节点的端点)')
for i in range(3): shutil.rmtree(TT / f'etcd_v47_{i}', ignore_errors=True)
C = Etcd('v47', n=3).start(); dec = lambda s: b64mod.b64decode(s).decode()
def ecall(path, body, timeout=1.0):
    last = None
    for i in range(3):
        try:
            s, d = C.call(i, path, body, timeout)
            if s == 200: return d
            last = (i, s, str(d)[:80])
        except Exception as e: last = (i, type(e).__name__)
    raise RuntimeError(last)
def list_instances(serializable=False):
    d = ecall('/v3/kv/range', {'key': b64('/svc/'), 'range_end': b64('/svc0'), 'serializable': serializable})
    return sorted((dec(kv['key']).split('/')[-1], int(dec(kv['value']))) for kv in d.get('kvs', []))
class Inst:
    def __init__(s, iid):
        s.iid = iid; s.alive = True; s.svc = Svc(lambda h: h.reply(200, iid.encode())); s.port = s.svc.port
        d = ecall('/v3/lease/grant', {'TTL': '20'}); s.lid = d['ID']; ecall('/v3/kv/put', {'key': b64(f'/svc/{iid}'), 'value': b64(str(s.port)), 'lease': s.lid})
        threading.Thread(target=s._ka, daemon=True).start()
    def _ka(s):
        while s.alive:
            time.sleep(2.0)
            try: ecall('/v3/lease/keepalive', {'ID': s.lid})
            except Exception: pass
    def kill(s): s.alive = False; s.svc.stop()
def traffic(policy, dur, events, rate=40, passive=False):
    """policy: 'stale'(刷新失败就保留旧列表)/ 'drop'(刷新失败就清空列表);events: [(时刻, 动作)]。返回按秒的 (成功, 失败) 列表"""
    cache = [list_instances()]; stop = threading.Event(); eject = {}; rr = [0]; lk = threading.Lock(); T0 = time.perf_counter()
    def refresher():
        while not stop.is_set():
            try: cache[0] = list_instances()
            except Exception:
                if policy == 'drop': cache[0] = []
            time.sleep(1.0)
    threading.Thread(target=refresher, daemon=True).start()
    def ev():
        for t, fn in events:
            d = T0 + t - time.perf_counter()
            if d > 0: time.sleep(d)
            fn()
    threading.Thread(target=ev, daemon=True).start()
    def one(i):
        now = time.perf_counter(); lst = [x for x in cache[0] if eject.get(x[0], 0) < now]
        if not lst: return 'err'
        with lk: rr[0] += 1; k = rr[0]
        iid, port = lst[k % len(lst)]; st, b, dt = rpc(port, '/', 0.5, keepalive=False)
        if st == 200: return 'ok'
        if passive: eject[iid] = now + 30
        return 'err'
    res = openloop(one, rate, dur, workers=100); stop.set()
    return [(sum(1 for ts, r in res if int(ts) == s and r == 'ok'), sum(1 for ts, r in res if int(ts) == s and r == 'err')) for s in range(int(dur))]

# ============ 一 ============
print('== 一:注册中心整体不可用。第 2 秒杀掉 etcd 的全部 3 个节点,第 8 秒不再恢复;调用方 40 个请求/秒,共 10 秒。两种调用方:(a) 刷新失败就保留旧列表(stale-if-error);(b) 刷新失败就把列表清空(把“拿不到列表”当成“没有实例”)。三个实例一直活着。每秒的 成功/失败 数')
ins = [Inst(f'i{k}') for k in range(3)]
def kill_all():
    for i in range(3): C.kill_node(i)
rows = []
ra = traffic('stale', 10, [(2.0, kill_all)])
rows.append(('(a) 刷新失败保留旧列表',) + tuple(f'{s}/{f}' for s, f in ra))
# 重新起集群
for i in range(3): C.start_node(i)
C.wait_leader(30); time.sleep(1.0)
rb = traffic('drop', 10, [(2.0, kill_all)])
rows.append(('(b) 刷新失败清空列表',) + tuple(f'{s}/{f}' for s, f in rb))
table(rows, ['调用方'] + [f'第 {s} 秒 成功/失败' for s in range(10)])
print('  注册中心整体挂掉时,后端实例其实都还活着:保留旧列表的调用方什么都没感觉;把“拿不到列表”当成“没有实例”的调用方,在下一次刷新失败时(最多一个刷新周期之后)所有请求都失败——为了“一致”而丢掉可用的缓存,把一个控制面故障放大成了数据面故障')

# ============ 二 ============
print('== 二:注册中心不可用期间实例死了。第 2 秒杀掉 etcd 全部节点,第 4 秒让实例 i0 崩溃(它的 key 没人能删,因为注册中心已经不可用);调用方保留旧列表。比较:(a) 没有被动摘除(旧列表里一直有 i0);(b) 被动摘除(请求失败就把该实例从本地列表里排除 30 s)。40 个请求/秒,共 10 秒')
for i in range(3): C.start_node(i)
C.wait_leader(30); time.sleep(1.0)
rows = []
for name, passive in (('(a) 无被动摘除', False), ('(b) 请求失败就本地摘除 30 s', True)):
    for i in ins:
        if i.alive is False: pass
    ins2 = [Inst(f'i{k}') for k in range(3)]; ecall('/v3/kv/range', {'key': b64('/svc/'), 'limit': 1})
    def kill_etcd(): [C.kill_node(i) for i in range(3)]
    r = traffic('stale', 10, [(2.0, kill_etcd), (4.0, ins2[0].kill)], passive=passive)
    tot_ok = sum(s for s, f in r); tot_err = sum(f for s, f in r)
    rows.append((name,) + tuple(f'{s}/{f}' for s, f in r) + (f'{tot_err} / {tot_ok + tot_err}',))
    for i in ins2: i.kill()
    for i in range(3): C.start_node(i)
    C.wait_leader(30); time.sleep(1.0)
table(rows, ['做法'] + [f'第 {s} 秒' for s in range(10)] + ['失败 / 总数'])
print('  实例死了而注册中心恰好也不可用时,没有人能把它从列表里去掉:没有被动摘除的调用方会一直把约三分之一的请求发给死实例;被动摘除让调用方靠自己的调用结果修正缓存(第 4 秒之后很快就不再失败)')

# ============ 三 ============
print('== 三:etcd 少数派(失去多数)。3 节点集群,杀掉其中 2 个,只剩 1 个节点(没有多数,没有 leader)。分别尝试:线性一致读、serializable 读(本地读)、写入、lease 续约;然后恢复被杀的节点,看实例的 key 和 lease 是否还在。lease TTL 20 s,故障持续约 8 秒')
C.wait_leader(30); time.sleep(1.0)       # 第二节最后已经把 3 个节点都拉起来了,这里不能再 start_node(会起出占不到端口的第二个进程,后面就杀不掉真正的节点)
ins3 = [Inst(f'j{k}') for k in range(3)]; li = C.leader_idx(); fol = [i for i in range(3) if i != li]; alone = fol[0]
t_kill = time.perf_counter(); C.kill_node(li); C.kill_node(fol[1]); time.sleep(2.0)
def try_(f):
    t0 = time.perf_counter()
    try: r = f(); return f'成功({(time.perf_counter() - t0) * 1000:.0f} ms)', r
    except Exception as e: return f'失败:{type(e).__name__}({(time.perf_counter() - t0) * 1000:.0f} ms)', None
def one(path, body, to=2.0): 
    s, d = C.call(alone, path, body, to); 
    if s != 200: raise RuntimeError(f'HTTP {s}: {str(d)[:60]}')
    return d
rows = []
r, d = try_(lambda: one('/v3/kv/range', {'key': b64('/svc/'), 'range_end': b64('/svc0'), 'serializable': False})); rows.append(('线性一致读(默认)', r))
r, d = try_(lambda: one('/v3/kv/range', {'key': b64('/svc/'), 'range_end': b64('/svc0'), 'serializable': True})); rows.append(('serializable 读(本地读)', r + (f',读到 /svc/ 下 {len(d.get("kvs", []))} 个 key(3 个是本节的 j*,其余是前面几节登记后 lease 还没过期的 i*)' if d else '')))
r, d = try_(lambda: one('/v3/kv/put', {'key': b64('/svc/new'), 'value': b64('1')})); rows.append(('写入', r))
r, d = try_(lambda: one('/v3/lease/keepalive', {'ID': ins3[0].lid})); rows.append(('lease 续约', r))
time.sleep(6.0)
for i in (li, fol[1]): C.start_node(i)
C.wait_leader(30); time.sleep(1.5)
d = ecall('/v3/kv/range', {'key': b64('/svc/'), 'range_end': b64('/svc0')}); n_after = len([kv for kv in d.get('kvs', []) if dec(kv['key']).startswith('/svc/j')])
tt = [ecall('/v3/lease/timetolive', {'ID': x.lid}) for x in ins3]
rows.append(('恢复多数之后 /svc/j* 还在的实例', f'{n_after} / 3'))
rows.append(('恢复之后各 lease 的剩余 TTL(秒)', ', '.join(str(t.get('TTL')) for t in tt)))
table(rows, ['操作(只剩 1 个节点,约 2 秒后开始)', '结果'])
print('  少数派节点上:线性一致读和写入都不可用(等不到多数),serializable 读还能读本地的数据(可能是旧的);lease 续约要经过 leader,也不可用。恢复多数、选出新 leader 之后,实例的 key 还在,lease 的剩余时间被重置(见第 41 篇),不会因为故障期间没续上约而大批过期')
for x in ins3: x.kill()
for i in range(3): C.kill_node(i)
