import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.write_concern import WriteConcern
tee('m10'); reset()
def trial(name, wc, run_s=1.5, extra=(), fsync_end=False, tail_j=False):
    """起 mongod、连续写入 run_s 秒、kill -9、重启,返回 (客户端确认的最大 i, 恢复后存在的最大 i, 恢复后的文档数)。"""
    n = Node(name, args=list(extra)); n.start(); c = n.client(); coll = c.test.get_collection('t', write_concern=wc)
    state = {'acked': -1}; stop = threading.Event()
    def w():
        i = 0
        while not stop.is_set():
            try: coll.insert_one({'_id': i, 'pad': 'x' * 100})
            except Exception: break
            state['acked'] = i; i += 1
    th = threading.Thread(target=w); th.start(); time.sleep(run_s)
    if tail_j: 
        stop.set(); th.join(); c.test.get_collection('t', write_concern=WriteConcern(j=True)).insert_one({'_id': -1}); state['acked'] = state['acked']
    n.p.kill(); n.p.wait(); stop.set(); th.join()
    c.close()
    n.start(); c2 = n.client()
    cnt = c2.test.t.count_documents({}); mx = c2.test.t.find_one(sort=[('_id', -1)])
    top = mx['_id'] if mx else -1
    rec = n
    return state['acked'], top, cnt, n
print('== 一:方法:写线程用 insert_one 连续单条写入(每条 ~130 字节),记下客户端收到确认的最大序号;1.5 秒后对 mongod 发 SIGKILL(kill -9);重启,看数据库里还剩到哪个序号')
print('  丢失条数 = 客户端确认过的最大序号 - 恢复后的最大序号(正数表示“确认过但丢了”)')
print('== 二:写关注 w:1(默认,不等 journal 落盘):5 次试验')
res = {}
def many(label, wc, k=5, **kw):
    out = []
    for t in range(k):
        a, top, cnt, nd = trial(f'm10{label}{t}', wc, **kw); out.append((a, top, cnt, max(0, a - top))); 
        print(f'  试验 {t + 1}: 确认到 {a:>6,}  恢复后最大 _id {top:>6,}  文档数 {cnt:>6,}  丢失 {max(0, a - top):>4}')
        nd.stop(); shutil.rmtree(nd.d, ignore_errors=True)
    res[label] = out; return out
many('w1', WriteConcern(w=1))
print('== 三:写关注 j:true(等 journal 落盘才确认):5 次试验')
many('j', WriteConcern(w=1, j=True))
print('== 四:journal 刷盘间隔 --journalCommitInterval(毫秒,默认 100)取 10、100、500,w:1 的丢失条数各 8 次试验')
stats = {}
for ms_ in (10, 100, 500):
    out = []
    for t in range(8):
        a, top, cnt, nd = trial(f'm10i{ms_}_{t}', WriteConcern(w=1), extra=['--journalCommitInterval', str(ms_)]); out.append(max(0, a - top))
        if t == 0: opt = nd.client().admin.command('getCmdLineOpts')['parsed'].get('storage', {}).get('journal')
        nd.stop(); shutil.rmtree(nd.d, ignore_errors=True)
    stats[ms_] = out
    print(f'  commitIntervalMs={ms_:<4} 生效的配置 {opt};丢失条数 {sorted(out)},中位数 {median(out):.0f},最大 {max(out)}')
print('== 五:重启时的日志:没有做过 checkpoint(刚启动不到 60 秒),数据是从 journal 重放出来的')
a, top, cnt, nd = trial('m10log', WriteConcern(w=1, j=True))
logs = nd.logs(r'(?i)recover')
print(f'  重启后日志里含 recover 的行: {len(logs)} 条;msg 字段:')
seen = []
for j in logs:
    m = j.get('msg', '')
    if m not in seen: seen.append(m)
for m in seen[:8]: print('    ' + m[:110])
msgs = []
for j in logs:
    at = j.get('attr', {}).get('message')
    if isinstance(at, dict) and at.get('category') == 'WT_VERB_RECOVERY' and at.get('msg') not in msgs: msgs.append(at.get('msg'))
print(f'  WiredTiger 的 recovery 日志里不同的消息 {len(msgs)} 条,前几条:')
for m in msgs[:6]: print('    ' + str(m)[:150])
nd.stop()
print('== 六:j:true 的写入之前,所有 w:1 的写入都已落盘:前 1.5 秒 w:1 写入,最后补一次 j:true 的写入,然后 kill -9')
out = []
for t in range(4):
    a, top, cnt, nd = trial(f'm10t{t}', WriteConcern(w=1), tail_j=True); out.append((a, top, cnt)); nd.stop(); shutil.rmtree(nd.d, ignore_errors=True)
for t, (a, top, cnt) in enumerate(out): print(f'  试验 {t + 1}: 确认到 {a:,},恢复后最大 _id {top:,},文档数 {cnt:,}(含 _id=-1 的那条 j:true 写入),丢失 {max(0, a - top)}')
