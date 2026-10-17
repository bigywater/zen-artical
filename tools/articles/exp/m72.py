import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
import bson as _b
tee('m72'); reset()
rs = ReplSet('m72', n=3).start(); c = rs.client()
tgt = Node('m72r').start(); tc = tgt.client()
D = mdir('m72dump')
NB = 150000
for i in range(0, NB, 10000): c.test.c_w.insert_many([{'_id': -(i + j) - 1, 'p': 'x' * 1000} for j in range(10000)], ordered=False)
c.test.a_counter.insert_one({'_id': 1, 'n': NB})
stop = threading.Event()
def writer():
    cs = c.start_session(); i = 0
    while not stop.is_set():
        try:
            with cs.start_transaction():
                c.test.c_w.insert_one({'_id': i}, session=cs); c.test.a_counter.update_one({'_id': 1}, {'$inc': {'n': 1}}, session=cs)
            i += 1
        except Exception: pass
th = threading.Thread(target=writer, daemon=True); th.start(); time.sleep(1)
def sh(cmd, n=14, filt=None):
    shown = tidy(cmd).replace(RSU, '<副本集>').replace(tgt.uri, '<目标>')
    print(f'  $ {shown}')
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, env={'PATH': '/usr/bin:/bin:/opt/homebrew/bin', 'HOME': str(MHOME)})
    out = tidy(r.stdout + r.stderr); ls = [re.sub(r'^\d{4}-\d\d-\d\dT[\d:.+]+\s+', '', l) for l in out.split('\n') if l.strip()]
    if filt: ls = [l for l in ls if re.search(filt, l)]
    for l in ls[:n]: print(f'  {l[:170]}')
    if len(ls) > n: print(f'  …(共 {len(ls)} 行)')
    return r.returncode, out
def state(label):
    n = tc.test.a_counter.find_one()['n']; w = tc.test.c_w.count_documents({})
    print(f'  {label}:a_counter.n = {n:,},c_w 文档数 = {w:,} → ' + ('一致(n == w)' if n == w else f'不一致,n - w = {n - w}'))
    return n, w
RSU = rs.uri() + '/?replicaSet=' + rs.rs
URI = f"'{RSU}'"
print('== 一:写入进行中做普通 mongodump(不带 --oplog):c_w 预先有 15 万个 1 KB 的文档,a_counter.n 起始也是 150,000;一个后台事务循环每次往 c_w 插入 1 个文档并把 a_counter.n 加 1,所以任何时刻 n == c_w 文档数。mongodump 默认并行导出各个集合,小的 a_counter 几乎瞬间导完,大的 c_w 要导好一会儿')
rc, o = sh(f"mongodump --uri={URI} --db=test --out={D}/plain", filt='done dumping|writing')
rc, o = sh(f"mongorestore --uri='{tgt.uri}' --drop --nsInclude='test.*' {D}/plain", filt='finished restoring|document')
state('普通 dump 恢复后')
print('== 二:同样写入进行中,带 --oplog:dump 开始时记下 oplog 的位置,结束时把这段 oplog 一起写进 oplog.bson')
rc, o = sh(f"mongodump --uri={URI} --oplog --out={D}/withoplog", filt='done dumping|oplog|writing')
print('  $ ls dump/ dump/test/')
print('  ' + ' '.join(sorted(os.listdir(f'{D}/withoplog'))) + '  |  test/: ' + ' '.join(sorted(os.listdir(f'{D}/withoplog/test'))))
ops = list(_b.decode_file_iter(open(f'{D}/withoplog/oplog.bson', 'rb')))
def flat(e):
    if e['op'] == 'c' and 'applyOps' in e['o']: return e['o']['applyOps']
    return [e]
ins = sum(1 for e in ops for x in flat(e) if x['op'] == 'i' and x['ns'] == 'test.c_w'); upd = sum(1 for e in ops for x in flat(e) if x['op'] == 'u' and x['ns'] == 'test.a_counter')
kinds = {}
for e in ops: k = e['op'] + (':applyOps' if e['op'] == 'c' and 'applyOps' in e['o'] else ''); kinds[k] = kinds.get(k, 0) + 1
print(f'  oplog.bson 里有 {len(ops)} 条 oplog 记录({kinds}),时间戳从 {ops[0]["ts"].time}:{ops[0]["ts"].inc} 到 {ops[-1]["ts"].time}:{ops[-1]["ts"].inc},其中对 test.c_w 的 insert 共 {ins} 个、对 test.a_counter 的 update 共 {upd} 个')
print('  oplog.bson 第一条记录里的操作(applyOps 展开,ns / op / o / o2): ' + json.dumps([{k: x.get(k) for k in ('op', 'ns', 'o', 'o2')} for x in flat(ops[0])], ensure_ascii=False, default=str))
print('== 三:带 --oplogReplay 恢复:mongorestore 在导入完集合后重放 oplog.bson,把各个集合拉到同一个时间点')
rc, o = sh(f"mongorestore --uri='{tgt.uri}' --drop --oplogReplay {D}/withoplog", filt='finished restoring|oplog|replay')
n_full, w_full = state('--oplogReplay 恢复后')
print('== 四:同一份带 oplog.bson 的 dump,恢复时不带 --oplogReplay:oplog.bson 被忽略')
rc, o = sh(f"mongorestore --uri='{tgt.uri}' --drop {D}/withoplog", filt='finished restoring|oplog|replay|skip|ignor')
state('不带 --oplogReplay 恢复后')
print('== 五:--oplogLimit:只重放到某个时间戳(取 oplog.bson 里中间那条记录的时间戳),恢复到 dump 期间的某个中间点')
mid = ops[len(ops) // 2]['ts']; lim = f'{mid.time}:{mid.inc}'
print(f'  选取的时间戳 {lim}(oplog.bson 第 {len(ops) // 2 + 1}/{len(ops)} 条)')
rc, o = sh(f"mongorestore --uri='{tgt.uri}' --drop --oplogReplay --oplogLimit={lim} {D}/withoplog", filt='finished restoring|oplog|replay')
n_mid, w_mid = state('--oplogLimit 恢复后')
print(f'  对比完整重放:n = {n_full:,}、c_w = {w_full:,}')
last = ops[-1]['ts']; lim2 = f'{last.time}:{last.inc}'
rc, o = sh(f"mongorestore --uri='{tgt.uri}' --drop --oplogReplay --oplogLimit={lim2} {D}/withoplog", filt='applied')
state('--oplogLimit = 最后一条记录的时间戳')
rc, o = sh(f"mongorestore --uri='{tgt.uri}' --drop --oplogReplay --oplogLimit={last.time}:{last.inc + 1} {D}/withoplog", filt='applied')
state('--oplogLimit = 最后一条记录的时间戳 + 1')
print('== 六:--oplog 的限制:不能和 --db 一起用;不能对非副本集(没有 oplog)的 mongod 用')
rc, o = sh(f"mongodump --uri={URI} --oplog --db=test --out={D}/bad1", n=4)
rc, o = sh(f"mongodump --uri='{tgt.uri}' --oplog --out={D}/bad2", n=4)
rc, o = sh(f"mongorestore --uri='{tgt.uri}' --oplogReplay --db=test {D}/withoplog/test", n=4)
stop.set(); th.join(2); rs.stop(); tgt.stop()
