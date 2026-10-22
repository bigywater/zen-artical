import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
from etcdt import Etcd, b64
import base64 as b64mod, shutil
tee('v43'); reset()
print('用 etcd 3.7.2 的事务(Txn)和 lease 实现分布式锁和 Leader 选举。通过 HTTP/JSON 网关操作:Txn 的 compare 条件(create_revision == 0 表示 key 不存在)、success / failure 分支;lease 让持有者崩溃后锁自动释放。两种锁:(a) 单个 key 的比较并交换(抢到的写入 key,没抢到的重试);(b) 排队锁(etcd concurrency 包 Mutex 的做法):每个竞争者在前缀下写一个自己的 key(带 lease),create_revision 最小的持有锁,其余的只监听比自己小的前一个 key 的删除')
shutil.rmtree(TT / 'etcd_v43_0', ignore_errors=True); E1 = Etcd('v43', n=1).start()
dec = lambda s: b64mod.b64decode(s).decode()
CALLS = collections.Counter(); clk = threading.Lock()
def call(path, body):
    with clk: CALLS[path] += 1
    return E1.call(0, path, body)[1]
def grant(ttl): return call('/v3/lease/grant', {'TTL': str(ttl)})['ID']
def keepalive(lid): return call('/v3/lease/keepalive', {'ID': lid})
def revoke(lid): return call('/v3/lease/revoke', {'ID': lid})
class KA:
    """后台续约线程;stop() = 正常停止,crash() = 突然不再续约(模拟进程崩溃或长时间暂停)"""
    def __init__(self, lid, iv): self.lid, self.iv, self.alive = lid, iv, True; threading.Thread(target=self.run, daemon=True).start()
    def run(self):
        while self.alive:
            time.sleep(self.iv)
            if self.alive:
                try: keepalive(self.lid)
                except Exception: pass
    def crash(self): self.alive = False
# ---------- (a) 单 key CAS 锁 ----------
def cas_lock(key, lid, poll=0.01):
    t0 = time.perf_counter()
    while True:
        d = call('/v3/kv/txn', {'compare': [{'target': 'CREATE', 'key': b64(key), 'result': 'EQUAL', 'create_revision': '0'}], 'success': [{'request_put': {'key': b64(key), 'value': b64('x'), 'lease': lid}}], 'failure': [{'request_range': {'key': b64(key)}}]})
        if d.get('succeeded'): return int(d['header']['revision']), time.perf_counter() - t0
        time.sleep(poll + random.uniform(0, poll))
def cas_unlock(key): call('/v3/kv/deleterange', {'key': b64(key)})
# ---------- (b) 排队锁 ----------
def q_lock(prefix, lid, me):
    mykey = f'{prefix}{me}'; t0 = time.perf_counter()
    d = call('/v3/kv/txn', {'compare': [], 'success': [{'request_put': {'key': b64(mykey), 'value': b64('x'), 'lease': lid}}, {'request_range': {'key': b64(prefix), 'range_end': b64(prefix[:-1] + chr(ord(prefix[-1]) + 1)), 'sort_order': 'ASCEND', 'sort_target': 'CREATE'}}]})
    my_rev = None; kvs = d['responses'][1]['response_range'].get('kvs', [])
    for kv in kvs:
        if dec(kv['key']) == mykey: my_rev = int(kv['create_revision'])
    while True:
        preds = [kv for kv in kvs if int(kv['create_revision']) < my_rev]
        if not preds: return my_rev, time.perf_counter() - t0
        pred = preds[-1]; pk = dec(pred['key'])
        # 监听前一个 key 的删除:从它的 mod_revision 开始 watch(不会错过期间的删除)
        c = http.client.HTTPConnection('127.0.0.1', E1.CP[0], timeout=30)
        with clk: CALLS['/v3/watch'] += 1
        c.request('POST', '/v3/watch', json.dumps({'create_request': {'key': pred['key'], 'start_revision': pred['mod_revision']}}), {'Content-Type': 'application/json'}); r = c.getresponse(); deleted = False
        while not deleted:
            line = r.fp.readline()
            if not line: break
            line = line.strip()
            if not line.startswith(b'{'): continue
            m = json.loads(line).get('result', {})
            if any(e.get('type') == 'DELETE' for e in m.get('events', []) or []): deleted = True
        try: c.sock.shutdown(socket.SHUT_RDWR)
        except Exception: pass
        c.close()
        d = call('/v3/kv/range', {'key': b64(prefix), 'range_end': b64(prefix[:-1] + chr(ord(prefix[-1]) + 1)), 'sort_order': 'ASCEND', 'sort_target': 'CREATE'}); kvs = d.get('kvs', [])
def q_unlock(prefix, me): call('/v3/kv/deleterange', {'key': b64(f'{prefix}{me}')})

# ============ 一 ============
print('== 一:互斥与开销。20 个线程(模拟 20 个进程)各抢同一把锁 15 次(共 300 次),拿到锁后“工作” 5 ms(检查同一时刻持有者的数量),再释放。比较单 key CAS 锁(没抢到就随机退避 10~20 ms 后重试)和排队锁(监听前一个竞争者)。统计:同一时刻最多有几个持有者(必须是 1)、总用时、发给 etcd 的请求数、每次拿到锁的等待时间 p50 / p99、是否严格先到先得(按 etcd 里 create_revision 排序的 FIFO)')
def run_lock(kind):
    CALLS.clear(); holders = [0]; maxh = [0]; lk = threading.Lock(); waits = []; order = []; arrivals = []
    def worker(w):
        for k in range(15):
            lid = grant(30); me = f'w{w}-{k}'
            ts = time.perf_counter()
            if kind == 'cas': rv, wt = cas_lock('/lock/cas', lid)
            else: rv, wt = q_lock('/lock/q/', lid, me)
            with lk: holders[0] += 1; maxh[0] = max(maxh[0], holders[0]); waits.append(wt); order.append((me, rv))
            time.sleep(0.005)
            with lk: holders[0] -= 1
            if kind == 'cas': cas_unlock('/lock/cas')
            else: q_unlock('/lock/q/', me)
            revoke(lid)
    t0 = time.perf_counter(); ths = [threading.Thread(target=worker, args=(w,)) for w in range(20)]; [t.start() for t in ths]; [t.join() for t in ths]; dt = time.perf_counter() - t0
    inc = sum(1 for a, b in zip(order, order[1:]) if b[1] > a[1]) / max(1, len(order) - 1)
    tot = sum(CALLS.values()); return maxh[0], dt, tot, pct(waits, 50), pct(waits, 99), inc
rows = []
for name, kind in (('(a) 单 key CAS 锁 + 随机退避重试', 'cas'), ('(b) 排队锁 + 监听前一个 key', 'q')):
    mh, dt, tot, p50, p99, inc = run_lock(kind)
    rows.append((name, mh, f'{dt:.1f} s', tot, f'{p50 * 1000:.0f} ms', f'{p99 * 1000:.0f} ms', f'{inc:.0%}' if kind == 'q' else '(不适用)'))
table(rows, ['锁', '同一时刻最多持有者', '300 次总用时', '发给 etcd 的请求数', '等待 p50', '等待 p99', '相邻两次获取锁按 create_revision 递增的比例(FIFO 的话应为 100%)'])
print('  两种锁都做到了互斥(最多 1 个持有者)。CAS 锁在竞争激烈时,大量请求浪费在失败的重试上;排队锁每个竞争者只监听前一个,请求数少、没有惊群,并且按 create_revision 先到先得,最坏等待更可预期')

# ============ 二 ============
print('== 二:持有者崩溃和“暂停”。lease TTL 2 s。(a) 持有者崩溃(不再续约,也不释放):看另一个等待者多久拿到锁;(b) 持有者没有崩溃,只是被暂停了 3 秒(比如 GC 停顿或机器卡住),期间 lease 过期、锁被别人拿走,等它恢复后它自己还以为持有锁——两个“持有者”写同一个共享资源;(c) 同 (b),但共享资源按 fencing token(拿锁时的 create_revision)拒绝过期的写入')
def holder_crash():
    lid1 = grant(2); ka1 = KA(lid1, 0.5); rv1, _ = cas_lock('/lock/crash', lid1); t_crash = time.perf_counter(); ka1.crash()
    lid2 = grant(30); rv2, wt = cas_lock('/lock/crash', lid2, poll=0.05); got = time.perf_counter() - t_crash; cas_unlock('/lock/crash'); revoke(lid2); return got
ds = [holder_crash() for _ in range(3)]
rows = [('(a) 持有者崩溃,等待者拿到锁用了', ' / '.join(f'{d:.2f} s' for d in ds))]
class Store:
    def __init__(self, fencing): self.fencing, self.max_tok, self.log = fencing, 0, []
    def write(self, who, tok):
        if self.fencing and tok < self.max_tok: self.log.append((who, tok, '拒绝')); return False
        self.max_tok = max(self.max_tok, tok); self.log.append((who, tok, '写入')); return True
def paused(fencing):
    st = Store(fencing); lid1 = grant(2); ka1 = KA(lid1, 0.5); rv1, _ = cas_lock('/lock/pause', lid1); st.write('A', rv1)
    ka1.crash()                                         # A 被暂停:不再续约
    lid2 = grant(30); rv2, _ = cas_lock('/lock/pause', lid2, poll=0.05); st.write('B', rv2)        # 约 2 s 后 B 拿到锁
    time.sleep(1.2); st.write('A', rv1)                  # A 恢复,以为自己还持有锁
    cas_unlock('/lock/pause'); revoke(lid2); return st.log
log_a = paused(False); log_b = paused(True)
rows.append(('(b) 暂停的持有者恢复后继续写(没有 fencing)', ' → '.join(f'{w}(token {t}):{r}' for w, t, r in log_a)))
rows.append(('(c) 同上,共享资源检查 fencing token', ' → '.join(f'{w}(token {t}):{r}' for w, t, r in log_b)))
table(rows, ['情形', '结果'])
print('  锁靠 lease 保活,持有者崩溃之后要等 lease 过期(约 TTL 再加一点)别人才能拿到;但 lease 过期而持有者自己不知道时(进程被暂停、时钟跳变),它醒来之后仍然以为持有锁。锁服务本身无法阻止这件事,要靠共享资源一侧检查 fencing token(拿锁时 etcd 返回的单调递增 revision)拒绝旧持有者的写入')

# ============ 三 ============
print('== 三:Leader 选举。5 个候选者竞选:每个候选者在 /election/ 下写一个带 lease 的 key,create_revision 最小的是 leader,其余观察 leader 是谁。leader 失去 leader 身份有两种方式:(a) 崩溃(不再续约);(b) resign(主动删除自己的 key)。TTL 分别是 2 s 和 5 s,续约间隔 TTL/3。统计从“失效”到“新 leader 出现”(别的候选者从 etcd 读到新的最小 create_revision)用了多久')
def cur_leader():
    d = call('/v3/kv/range', {'key': b64('/election/'), 'range_end': b64('/election0'), 'sort_order': 'ASCEND', 'sort_target': 'CREATE', 'limit': '1'}); kvs = d.get('kvs', [])
    return dec(kvs[0]['key']).split('/')[-1] if kvs else None
def election(ttl, mode):
    call('/v3/kv/deleterange', {'key': b64('/election/'), 'range_end': b64('/election0')}); cands = {}
    for i in range(5):
        lid = grant(ttl); ka = KA(lid, ttl / 3); call('/v3/kv/put', {'key': b64(f'/election/c{i}'), 'value': b64('x'), 'lease': lid}); cands[f'c{i}'] = (lid, ka); time.sleep(0.05)
    first = cur_leader(); lid, ka = cands[first]; t0 = time.perf_counter()
    if mode == 'crash': ka.crash()
    else: call('/v3/kv/deleterange', {'key': b64(f'/election/{first}')})
    while cur_leader() == first and time.perf_counter() - t0 < 30: time.sleep(0.02)
    dt = time.perf_counter() - t0; new = cur_leader()
    for l, k in cands.values(): k.crash()
    return first, new, dt
rows = []
for ttl in (2, 5):
    for mode, mname in (('crash', '(a) 崩溃'), ('resign', '(b) resign')):
        rs = [election(ttl, mode) for _ in range(3)]; rows.append((f'{ttl} s', mname, ' / '.join(f'{r[2]:.2f} s' for r in rs), ' / '.join(f'{r[0]}→{r[1]}' for r in rs)))
table(rows, ['lease TTL', '失效方式', '新 leader 出现用了多久(3 次)', '前任 → 新 leader'])
print('  崩溃的故障转移时间与 TTL 相当(看上表:TTL 2 s 约 2 s,TTL 5 s 约 5 s,里面包括 etcd 检查 lease 到期的延迟);主动 resign 几乎是立刻的。TTL 越短故障转移越快,但网络抖动时 leader 被误判失效(丢掉领导权)的概率越高——和第 40 篇里心跳与 TTL 的关系是同一个取舍。新 leader 总是 create_revision 次小的候选者,所以顺序是确定的(先来的先当)')
E1.procs[0].kill()
