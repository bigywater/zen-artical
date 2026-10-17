import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m66'); reset()
cl = Cluster('m66', shards=2, chunk_mb=1).start(); c = cl.client(); adm = c.admin; cfg = c.config
adm.command('enableSharding', 'test')
S0, S1 = cl.shards[0].client(), cl.shards[1].client()
def ins_counts(): return (S0.admin.command('serverStatus')['opcounters']['insert'], S1.admin.command('serverStatus')['opcounters']['insert'])
def dist(coll):
    uuid = cfg.collections.find_one({'_id': coll})['uuid']
    return {x['_id']: x['n'] for x in cfg.chunks.aggregate([{'$match': {'uuid': uuid}}, {'$group': {'_id': '$shard', 'n': {'$sum': 1}}}, {'$sort': {'_id': 1}}])}
def max_chunk_shard(coll):
    uuid = cfg.collections.find_one({'_id': coll})['uuid']; return cfg.chunks.find({'uuid': uuid}).sort('min', -1).limit(1)[0]['shard']
T_BASE = 1_700_000_000_000
from bson.min_key import MinKey
def sustained(coll, mk, secs=30, threads=4, win=5):
    ctr = [0]; lock = threading.Lock(); stop = threading.Event(); wins = []; mcs = []
    def worker(w):
        cc = cl.client().test[coll]
        while not stop.is_set():
            with lock: base = ctr[0]; ctr[0] += 100
            cc.insert_many([mk(base + j) for j in range(100)], ordered=False); time.sleep(0.03)
    ths = [threading.Thread(target=worker, args=(w,), daemon=True) for w in range(threads)]; [t.start() for t in ths]
    prev = ins_counts(); t0 = time.time()
    while time.time() - t0 < secs:
        time.sleep(win); cur = ins_counts(); wins.append((cur[0] - prev[0], cur[1] - prev[1])); prev = cur; mcs.append(max_chunk_shard('test.' + coll))
    stop.set(); [t.join() for t in ths]; return wins, mcs, ctr[0]
def share(wins): s0 = sum(w[0] for w in wins); s1 = sum(w[1] for w in wins); return s0, s1, s0 / max(1, s0 + s1)
adm.command('balancerStop')
print('== 一:单调递增的分片键(ranged,键是递增的时间戳):先关掉 balancer,4 个线程持续写入 30 秒,每 5 秒统计两个分片各收到多少次 insert(关掉 balancer 是为了排除迁移带来的 insert)')
c.test.command('create', 'mono'); adm.command('shardCollection', 'test.mono', key={'ts': 1})
w1, mc1, tot1 = sustained('mono', lambda i: {'ts': T_BASE + i, 'p': 'x' * 300})
for i, (w, m) in enumerate(zip(w1, mc1)): print(f'  第 {(i + 1) * 5:>2} s 窗口:sh0 {w[0]:>6,}  sh1 {w[1]:>6,}   键最大的那个 chunk 在 {m}')
s0, s1, f0 = share(w1); print(f'  合计:sh0 {s0:,}、sh1 {s1:,};sh0 占 {f0:.0%};共写入 {tot1:,} 个文档;chunk 分布 {dist("test.mono")}(balancer 关着,chunk 没有被拆分也没有被迁移:所有写入都进同一个 chunk)')
print('== 二:哈希分片键(同样的写入负载,balancer 仍然关着):shardCollection 时就在两个分片上各建好 chunk,写入被哈希打散')
c.test.command('create', 'hsh'); adm.command('shardCollection', 'test.hsh', key={'ts': 'hashed'})
w2, mc2, tot2 = sustained('hsh', lambda i: {'ts': T_BASE + i, 'p': 'x' * 300})
for i, w in enumerate(w2): print(f'  第 {(i + 1) * 5:>2} s 窗口:sh0 {w[0]:>6,}  sh1 {w[1]:>6,}')
s0, s1, f0 = share(w2); print(f'  合计:sh0 {s0:,}、sh1 {s1:,};sh0 占 {f0:.0%};共写入 {tot2:,} 个文档;chunk 分布 {dist("test.hsh")}')
print('== 三:复合键 {bucket, ts}(bucket 是 8 个桶):手工把 bucket >= 4 的 chunk 搬到 sh1(balancer 仍然关着),写入就分散到两个分片,每个桶内键仍然递增')
c.test.command('create', 'cmp'); adm.command('shardCollection', 'test.cmp', key={'bucket': 1, 'ts': 1})
adm.command('split', 'test.cmp', middle={'bucket': 4, 'ts': MinKey()}); adm.command('moveChunk', 'test.cmp', find={'bucket': 5, 'ts': 0}, to='sh1')
print(f'  手工 split + moveChunk 之后的 chunk 分布 {dist("test.cmp")}')
w3, mc3, tot3 = sustained('cmp', lambda i: {'bucket': i % 8, 'ts': T_BASE + i, 'p': 'x' * 300})
for i, w in enumerate(w3): print(f'  第 {(i + 1) * 5:>2} s 窗口:sh0 {w[0]:>6,}  sh1 {w[1]:>6,}')
s0, s1, f0 = share(w3); print(f'  合计:sh0 {s0:,}、sh1 {s1:,};sh0 占 {f0:.0%};共写入 {tot3:,} 个文档')
print('== 四:单调键再打开 balancer:数据会被搬到另一个分片,但新写入还是追着键最大的 chunk。等 balancer 搬完,再写 20,000 个更大的键,看它们落在哪个分片')
adm.command('balancerStart'); t0 = time.time()
while time.time() - t0 < 120:
    time.sleep(5); sdm = [x for x in adm.aggregate([{'$shardedDataDistribution': {}}]) if x['ns'] == 'test.mono'][0]['shards']
    if len(sdm) == 2 and min(x['numOwnedDocuments'] for x in sdm) > 0.4 * sum(x['numOwnedDocuments'] for x in sdm): break
print('  balancer 搬了 %.0f 秒后 test.mono 的数据分布: ' % (time.time() - t0) + ';'.join(f'{s["shardName"]} 拥有 {s["numOwnedDocuments"]:,} 个文档' for s in sdm))
adm.command('balancerStop'); time.sleep(5)
cc = cl.client().test.mono; hi = T_BASE + 10 ** 9
for i in range(0, 20000, 1000): cc.insert_many([{'ts': hi + i + j, 'p': 'z' * 100} for j in range(1000)], ordered=False)
n0 = S0.test.mono.count_documents({'ts': {'$gte': hi}}); n1 = S1.test.mono.count_documents({'ts': {'$gte': hi}})
print(f'  新写入的 20,000 个更大的键:直连 sh0 里 ts >= {hi} 的有 {n0:,} 个,sh1 里有 {n1:,} 个;键最大的 chunk 在 {max_chunk_shard("test.mono")}')
print('== 五:代价:哈希键下按时间范围查询要问所有分片(scatter-gather),ranged 键下可以只问一个分片(targeted)')
def shards_hit(coll, q):
    e = c.test.command('explain', {'find': coll, 'filter': q}, verbosity='queryPlanner'); return sorted(s['shardName'] for s in e['queryPlanner']['winningPlan'].get('shards', []))
q = {'ts': {'$gte': T_BASE + 1000, '$lt': T_BASE + 1100}}
print(f'  范围查询 ts ∈ [t+1000, t+1100):ranged 涉及的分片 {shards_hit("mono", q)};hashed 涉及的分片 {shards_hit("hsh", q)};复合键(不带 bucket)涉及的分片 {shards_hit("cmp", q)}')
print(f'  等值查询 ts = t+1000:ranged {shards_hit("mono", {"ts": T_BASE + 1000})};hashed {shards_hit("hsh", {"ts": T_BASE + 1000})}')
print(f'  带 bucket 的查询(bucket = 3 且 ts 范围):复合键涉及的分片 {shards_hit("cmp", {"bucket": 3, "ts": {"$gte": T_BASE, "$lt": T_BASE + 5000}})};bucket = 6 的:{shards_hit("cmp", {"bucket": 6, "ts": {"$gte": T_BASE, "$lt": T_BASE + 5000}})}')
print('== 六:汇总(balancer 关着时各键 30 秒写入的文档数与 sh0 占比)')
print(f'  {"分片键":<24}{"写入文档数":>12}{"sh0 占比":>10}')
for lab_, ww, tt in [('ranged {ts}(单调)', w1, tot1), ('hashed {ts}', w2, tot2), ('复合 {bucket, ts}(手工分两半)', w3, tot3)]: print(f'  {lab_:<24}{tt:>12,}{share(ww)[2]:>10.0%}')
cl.stop()
