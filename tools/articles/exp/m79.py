import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m79'); reset()
nd = Node('m79').start(); c = nd.client()
c.test.one.insert_one({'_id': 1})
def Q(kind='read'):
    x = c.admin.command('serverStatus')['queues']['execution'][kind]['normalPriority']
    return {k: x[k] for k in ('out', 'available', 'totalTickets', 'queueLength', 'addedToQueue', 'removedFromQueue', 'totalTimeQueuedMicros', 'finishedProcessing')}
def P(): return {k: v for k, v in c.admin.command('getParameter', '*').items() if k in ('executionControlConcurrencyAdjustmentAlgorithm', 'executionControlConcurrentReadTransactions', 'executionControlConcurrentWriteTransactions')}
SLEEP = 300
def one_op(cl):
    t0 = time.perf_counter()
    try: cl.test.command({'find': 'one', 'filter': {'$where': f'sleep({SLEEP}) || true'}, 'limit': 1})
    except Exception as ex: return -1
    return (time.perf_counter() - t0) * 1000
clients = [nd.client() for _ in range(64)]
for x in clients: x.admin.command('ping')
def burst(n):
    """n 个并发的慢读同时开始;返回各自的耗时 (ms),以及期间采样到的 out / queueLength 最大值。"""
    res = [None] * n; mx = {'out': 0, 'queueLength': 0}; stop = threading.Event()
    def sampler():
        while not stop.is_set():
            q = Q(); mx['out'] = max(mx['out'], q['out']); mx['queueLength'] = max(mx['queueLength'], q['queueLength']); time.sleep(0.05)
    sm = threading.Thread(target=sampler, daemon=True); sm.start()
    bar = threading.Barrier(n)
    def w(i): bar.wait(); res[i] = one_op(clients[i])
    ts = [threading.Thread(target=w, args=(i,), daemon=True) for i in range(n)]
    t0 = time.perf_counter()
    for t in ts: t.start()
    for t in ts: t.join(120)
    total = (time.perf_counter() - t0) * 1000; stop.set(); sm.join(2)
    return sorted(res), mx, total
def summ(res): return f'最快 {res[0]:.0f} ms,中位数 {res[len(res) // 2]:.0f} ms,最慢 {res[-1]:.0f} ms'
def waves(res, step):
    from collections import Counter
    return dict(sorted(Counter(int(r // step) * step for r in res).items()))
print('== 一:空闲时的 ticket:serverStatus.queues.execution 里 read / write 各有 normalPriority 的 out(已发出的 ticket)、available、totalTickets;以及控制并发的参数')
print('  read.normalPriority  = ' + str(Q('read'))); print('  write.normalPriority = ' + str(Q('write')))
print('  参数: ' + str(P()))
print('== 二:单个慢读(sleep 300 ms)的基线耗时;然后 40 个并发同时开始(初始 totalTickets = 10)')
base = [one_op(clients[0]) for _ in range(3)]
print(f'  单个慢读的耗时:{", ".join(f"{b:.0f} ms" for b in base)}')
res, mx, total = burst(40)
print(f'  40 个并发:{summ(res)};全部做完共 {total:.0f} ms;期间采样到 out 最大 = {mx["out"]},queueLength 最大 = {mx["queueLength"]}')
print(f'  耗时分布(按 {SLEEP} ms 一档的计数): ' + str(waves(res, SLEEP)))
print('  之后 read.normalPriority = ' + str(Q('read')))
print('== 三:持续负载下 totalTickets 会自动调整吗?(throughputProbing)64 个线程循环发慢读 30 秒,每 3 秒取一次 totalTickets / out')
stop = threading.Event()
def loop(i):
    while not stop.is_set(): one_op(clients[i])
ts = [threading.Thread(target=loop, args=(i,), daemon=True) for i in range(64)]
for t in ts: t.start()
samples = []
for k in range(10):
    time.sleep(3); q = Q(); samples.append((3 * (k + 1), q['totalTickets'], q['out'], q['queueLength']))
stop.set()
for t in ts: t.join(30)
print('  (秒, totalTickets, out, queueLength): ' + str(samples))
print('== 四:固定并发:executionControlConcurrencyAdjustmentAlgorithm = fixedConcurrentTransactions,读 ticket 先试 4(被拒绝),再设成最小值 5;16 个并发慢读')
print('  setParameter: ' + str(c.admin.command('setParameter', 1, executionControlConcurrencyAdjustmentAlgorithm='fixedConcurrentTransactions')) )
try: c.admin.command('setParameter', 1, executionControlConcurrentReadTransactions=4)
except Exception as ex: print(f'  setParameter executionControlConcurrentReadTransactions=4 → code {ex.code} {ex.details.get("codeName")}: {ex.details.get("errmsg")}')
print('  setParameter executionControlConcurrentReadTransactions=5: ' + str(c.admin.command('setParameter', 1, executionControlConcurrentReadTransactions=5)))
time.sleep(1); print('  参数: ' + str(P()) + ';read.normalPriority = ' + str(Q('read')))
q0 = Q()
res, mx, total = burst(16)
q1 = Q()
print(f'  16 个并发:{summ(res)};全部做完共 {total:.0f} ms;out 最大 = {mx["out"]},queueLength 最大 = {mx["queueLength"]}')
print(f'  耗时分布(按 {SLEEP} ms 一档的计数): ' + str(waves(res, SLEEP)))
print('== 五:同样的 16 个并发,ticket 放大到 128')
print('  setParameter: ' + str(c.admin.command('setParameter', 1, executionControlConcurrentReadTransactions=128)))
time.sleep(1); print('  read.normalPriority = ' + str(Q('read')))
q2 = Q()
res2, mx2, total2 = burst(16)
q3 = Q()
print(f'  16 个并发:{summ(res2)};全部做完共 {total2:.0f} ms;out 最大 = {mx2["out"]},queueLength 最大 = {mx2["queueLength"]}')
print(f'  耗时分布(按 {SLEEP} ms 一档的计数): ' + str(waves(res2, SLEEP)))
print('== 六:serverStatus 里的排队统计:同样两次 burst 前后的增量')
for label, a, b in (('ticket = 5(16 个并发)', q0, q1), ('ticket = 128(16 个并发)', q2, q3)):
    d = {k: b[k] - a[k] for k in ('addedToQueue', 'removedFromQueue', 'totalTimeQueuedMicros', 'finishedProcessing')}
    avg = d['totalTimeQueuedMicros'] / d['addedToQueue'] / 1000 if d['addedToQueue'] else 0
    print(f'  {label}:addedToQueue +{d["addedToQueue"]},removedFromQueue +{d["removedFromQueue"]},totalTimeQueuedMicros +{d["totalTimeQueuedMicros"]:,},finishedProcessing +{d["finishedProcessing"]}' + (f' → 排队的操作平均排队 {avg:.0f} ms' if d['addedToQueue'] else ' → 没有排队'))
nd.stop()
