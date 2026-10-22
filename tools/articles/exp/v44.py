import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
from etcdt import Etcd, b64
import base64 as b64mod, shutil
tee('v44'); reset()
print('etcd 3.7.2 里把服务实例当作 key 存在一个前缀下(比如 /services/<服务名>/<实例 id>)时,前缀查询(range)的代价。单节点,通过 HTTP/JSON 网关访问(响应是 JSON,key 和 value 是 base64),延迟包含 JSON 解析;批量写入用 Txn,一次最多 128 个 put(etcd 默认 --max-txn-ops=128)')
shutil.rmtree(TT / 'etcd_v44_0', ignore_errors=True); E1 = Etcd('v44', n=1).start()
def txn_put(items):
    for i in range(0, len(items), 128):
        E1.call(0, '/v3/kv/txn', {'success': [{'request_put': {'key': b64(k), 'value': b64(v)}} for k, v in items[i:i + 128]]}, 60)
def fill(prefix, n, vsize=200, start=0):
    txn_put([(f'{prefix}{i:07d}', 'v' * vsize) for i in range(start, start + n)])
def rng(prefix, **kw):
    body = {'key': b64(prefix), 'range_end': b64(prefix[:-1] + chr(ord(prefix[-1]) + 1))}; body.update(kw)
    c = E1.conn(0, 60); t0 = time.perf_counter(); c.request('POST', '/v3/kv/range', json.dumps(body), {'Content-Type': 'application/json'}); r = c.getresponse(); raw = r.read(); t1 = time.perf_counter(); d = json.loads(raw); t2 = time.perf_counter(); c.close()
    return d, len(raw), t1 - t0, t2 - t0
def status(): return E1.call(0, '/v3/maintenance/status', {}, 60)[1]

# ============ 一 ============
print('== 一:前缀查询的延迟与响应大小。/svc/ 下放 N 个 key(每个 value 200 字节)。对同一个前缀做:完整查询 / 只要 key(keys_only)/ 只要个数(count_only)/ limit 100;linearizable(默认)与 serializable。每种做 10 次取中位数;“耗时”是从发出请求到解析完 JSON,括号里是不含解析的时间')
rows = []; n_have = 0
for n in (1_000, 10_000, 100_000):
    fill('/svc/', n - n_have, start=n_have); n_have = n; row = [f'{n:,}']
    for name, kw in (('完整', {}), ('keys_only', {'keys_only': True}), ('count_only', {'count_only': True}), ('limit 100', {'limit': '100'}), ('完整 + serializable', {'serializable': True})):
        ts = []; ts2 = []; sz = 0
        for _ in range(10): d, sz, t1, t2 = rng('/svc/', **kw); ts.append(t2); ts2.append(t1)
        row.append(f'{statistics.median(ts) * 1000:.1f} ms({statistics.median(ts2) * 1000:.1f}) · {sz / 1024:.0f} KB')
    rows.append(tuple(row))
table(rows, ['key 数', '完整查询', 'keys_only', 'count_only', 'limit 100', '完整 + serializable'])
print('  完整查询的代价随 key 数线性增长,而且响应是 base64 编码的 JSON,体积比原始数据大;keys_only 省掉 value,count_only 只返回个数,limit 100 只取 100 条,代价几乎不随 N 增长。服务发现的客户端每次变化都全量查询的话,实例数一大就很贵,应该首次全量加 watch 增量')

# ============ 二 ============
print('== 二:分页扫描。10 万个 key 的前缀,三种读法:(a) 一次完整查询;(b) 每页 1000 个,用“上一页最后一个 key + \\0”作下一页起点,不固定 revision;(c) 同 (b),但所有页都固定在第一页响应里的 header.revision 上(一致快照)。同时在扫描期间另一个线程每 10 ms 改一个已有的 key,统计扫描得到的 key 数和有多少个 key 读到的版本(mod_revision)比第一页读取时的 revision 还新')
def scan(page, pin):
    out = {}; start = '/svc/'; end = '/svc0'; rev = None; t0 = time.perf_counter(); pages = 0
    while True:
        body = {'key': b64(start), 'range_end': b64(end), 'limit': str(page)}
        if pin and rev: body['revision'] = rev
        d = E1.call(0, '/v3/kv/range', {**body}, 60)[1]; pages += 1
        if rev is None: rev = d['header']['revision']
        for kv in d.get('kvs', []): out[kv['key']] = int(kv['mod_revision'])
        if not d.get('more'): break
        start = b64mod.b64decode(d['kvs'][-1]['key']).decode() + '\x00'
    return out, time.perf_counter() - t0, pages, int(rev)
stop = threading.Event(); writes = [0]
def writer():
    i = 0
    while not stop.is_set():
        E1.call(0, '/v3/kv/put', {'key': b64(f'/svc/{(99999 - 500 * i) % 100000:07d}'), 'value': b64('NEW' + 'v' * 197)}); writes[0] += 1; i += 1; time.sleep(0.01)
rows = []
for name, page, pin in (('(a) 一次完整查询', 0, False), ('(b) 每页 1000,不固定 revision', 1000, False), ('(c) 每页 1000,固定 revision', 1000, True)):
    stop.clear(); writes[0] = 0; th = threading.Thread(target=writer, daemon=True); th.start()
    if page == 0:
        t0 = time.perf_counter(); d, sz, t1, t2 = rng('/svc/'); dt = time.perf_counter() - t0; out = {kv['key']: int(kv['mod_revision']) for kv in d['kvs']}; pages = 1; rev0 = int(d['header']['revision'])
    else: out, dt, pages, rev0 = scan(page, pin)
    stop.set(); th.join()
    new = sum(1 for v in out.values() if v > rev0)
    rows.append((name, len(out), pages, f'{dt:.2f} s', writes[0], new))
table(rows, ['读法', '读到的 key 数', '请求数', '总用时', '扫描期间的写入数', '读到的、版本比“第一页读取时的 revision”还新的 key 数'])
print('  一次完整查询是一个一致的快照,但响应很大;分页不固定 revision 时,各页读自不同的时刻,读到的是混合了新旧版本的视图;固定 revision 的分页每一页都读同一个快照,代价是该 revision 不能被 compaction 压缩掉')
stop.clear()

# ============ 三 ============
print('== 三:写入产生的历史与 compaction / defrag。对 /hist/ 下的 5000 个 key(每个 200 字节)反复更新 20 轮(共 10 万次写入)。看 etcd 的数据库大小(dbSize)与实际在用的大小(dbSizeInUse),以及 compaction 之后、defrag 之后的变化。注意数据库里还留着前两节写入的 10 万个 /svc/ key(约 30 MB 的底数),下面的大小都包含它')
fill('/hist/', 5000)
def sizes(): s = status(); return int(s['dbSize']) / 1e6, int(s['dbSizeInUse']) / 1e6 if 'dbSizeInUse' in s else None
b0 = sizes()
for rnd in range(20): txn_put([(f'/hist/{i:07d}', f'r{rnd}' + 'x' * 198) for i in range(5000)])
b1 = sizes(); cur = int(status()['header']['revision'])
E1.call(0, '/v3/kv/compaction', {'revision': str(cur), 'physical': True}, 120); time.sleep(0.5); b2 = sizes()
E1.call(0, '/v3/maintenance/defragment', {}, 300); time.sleep(1.0); b3 = sizes()
table([('初始(5000 个 key 各写一次之后)', f'{b0[0]:.1f} MB', f'{b0[1]:.1f} MB' if b0[1] else '-'), ('更新 20 轮(10 万次写入)之后', f'{b1[0]:.1f} MB', f'{b1[1]:.1f} MB' if b1[1] else '-'), ('compact 到当前 revision 之后', f'{b2[0]:.1f} MB', f'{b2[1]:.1f} MB' if b2[1] else '-'), ('defrag 之后', f'{b3[0]:.1f} MB', f'{b3[1]:.1f} MB' if b3[1] else '-')], ['阶段', 'dbSize(文件大小)', 'dbSizeInUse(实际在用)'])
print('  每次更新都会产生一个新 revision,旧版本留在数据库里;compaction 把旧版本标记为可回收,但文件不会变小(dbSize 不变,dbSizeInUse 变小);defrag 才真正把空闲页还给文件系统。服务注册这类频繁续约、更新的场景,不定期 compaction 和 defrag,数据库会一直长大')
E1.procs[0].kill()
