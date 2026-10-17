import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m74'); reset()
nd = Node('m74').start(); c = nd.client()
c.test.t.insert_many([{'_id': i, 'k': i % 100, 'p': 'x' * 100} for i in range(200000)], ordered=False)
def bg(js, label, results):
    def f():
        cl = nd.client(appName=label)
        t0 = time.time()
        try: results[label] = cl.test.command(js)
        except Exception as ex: results[label] = ex
        results[label + '_s'] = time.time() - t0
    t = threading.Thread(target=f, daemon=True); t.start(); return t
def ops(filt=None):
    f = {'$all': False}; 
    r = c.admin.aggregate([{'$currentOp': {'allUsers': True, 'idleConnections': False, 'localOps': True}}] + ([{'$match': filt}] if filt else []))
    return list(r)
print('== 一:$currentOp 聚合阶段(db.currentOp() 的底层):在另一个连接里跑一个长查询($where 里每评估一个文档 sleep 1 秒),在这个连接里看它')
res = {}
t = bg({'find': 't', 'filter': {'$where': 'sleep(1000) || true'}, 'limit': 1}, 'slowfind', res); time.sleep(0.8)
o = [x for x in ops({'appName': 'slowfind', 'op': 'query'})]
print(f'  找到 {len(o)} 个 appName=slowfind 的进行中操作')
if o:
    x = o[0]; print('  字段: ' + str(sorted(x.keys())))
    print('  ' + json.dumps({k: x.get(k) for k in ('type', 'op', 'ns', 'active', 'secs_running', 'microsecs_running', 'planSummary', 'numYields', 'appName', 'client', 'desc')}, default=str, ensure_ascii=False))
    print('  command = ' + json.dumps(x.get('command'), default=str, ensure_ascii=False)[:200])
t.join(30); print(f'  不去管它,该查询总共跑了 {res["slowfind_s"]:.1f} 秒后' + ('正常返回' if not isinstance(res['slowfind'], Exception) else repr(res['slowfind'])[:100]))
print('== 二:killOp:杀掉一个正在跑的操作。被杀的客户端收到什么错误?')
res = {}; t = bg({'find': 't', 'filter': {'$where': 'sleep(1000) || true'}, 'limit': 1}, 'victim', res); time.sleep(0.8)
o = ops({'appName': 'victim', 'op': 'query'}); opid = o[0]['opid']; t0 = time.time()
print(f'  找到 opid = {opid}(secs_running = {o[0].get("secs_running")})')
print('  killOp 返回: ' + str(c.admin.command('killOp', op=opid)))
t.join(30); dt = time.time() - t0
e = res['victim']
print(f'  受害者在 killOp 之后 {dt:.1f} 秒返回(不杀的话要跑约 3 秒,见上一节): ' + (f'code = {e.code}, codeName = {e.details.get("codeName")}, errmsg = {str(e)[:100]}' if hasattr(e, 'code') else repr(e)[:150]))
print('== 三:killOp 对两类操作:$where 里正在 sleep 的 JS,以及 aggregate 的 $function 里的 JS 计算循环(30 万次累加)')
res = {}
def timed(label, cmd, sleep=0.6, kill=True):
    r = {}; t = bg(cmd, label, r); time.sleep(sleep); o = ops({'appName': label, 'op': {'$in': ['query', 'command', 'update', 'getmore']}}); t0 = time.time()
    if not o: print(f'  {label}:没有找到进行中的操作(已经结束?)'); t.join(30); return
    opid = o[0]['opid']; c.admin.command('killOp', op=opid); t.join(120); e = r.get(label)
    print(f'  {label}:killOp 之后 {time.time() - t0:.2f} 秒结束; ' + (f'错误 {e.code} {e.details.get("codeName")}' if hasattr(e, 'code') else '没有错误(已经正常完成)'))
timed('where_sleep', {'find': 't', 'filter': {'$where': 'sleep(1000) || true'}, 'limit': 1})
timed('scan_sort', {'aggregate': 't', 'pipeline': [{'$group': {'_id': '$p', 'n': {'$sum': {'$function': {'body': 'function(x){ let s = 0; for (let i = 0; i < 300000; i++) s += i; return s }', 'args': ['$k'], 'lang': 'js'}}}}}], 'cursor': {}})
print('== 四:maxTimeMS:不用人去杀,让服务端到点自己中止')
t0 = time.time()
try: c.test.command({'find': 't', 'filter': {'$where': 'sleep(1000) || true'}, 'limit': 1, 'maxTimeMS': 1000})
except Exception as ex: print(f'  maxTimeMS = 1000:{time.time() - t0:.2f} 秒后返回错误 code = {ex.code} {ex.details.get("codeName")} {str(ex)[:90]}')
print('== 五:currentOp 过滤:按 secs_running 找长时间运行的操作;idleCursors 能看到空闲的游标')
res = {}; ts = [bg({'find': 't', 'filter': {'$where': 'sleep(1000) || true'}, 'limit': 1}, f'worker{i}', res) for i in range(3)]; time.sleep(1.5)
o = list(c.admin.aggregate([{'$currentOp': {'allUsers': True}}, {'$match': {'active': True, 'secs_running': {'$gte': 1}, 'op': 'query'}}, {'$project': {'appName': 1, 'secs_running': 1, 'ns': 1, 'opid': 1, '_id': 0}}]))
print(f'  secs_running ≥ 1 的 query:{len(o)} 个: ' + str(sorted((x['appName'], x['secs_running']) for x in o)))
for t in ts: t.join(30)
cur = c.test.t.find({}, batch_size=10); cur.next()
o = list(c.admin.aggregate([{'$currentOp': {'allUsers': True, 'idleCursors': True}}, {'$match': {'type': 'idleCursor'}}, {'$project': {'type': 1, 'ns': 1, 'cursor.nDocsReturned': 1, 'cursor.originatingCommand.find': 1, 'cursor.noCursorTimeout': 1, '_id': 0}}]))
print('  idleCursors: ' + json.dumps(o, default=str, ensure_ascii=False)[:300])
cur.close()
print('== 六:所有查询都结束之后,$currentOp 里还有什么:后台线程、每个连接上挂着的命令,以及 $currentOp 自己')
time.sleep(0.5)
o = list(c.admin.aggregate([{'$currentOp': {'allUsers': True}}, {'$project': {'appName': 1, 'op': 1, 'ns': 1, 'active': 1, 'desc': 1, 'secs_running': 1, 'command': 1, '_id': 0}}]))
for x in sorted(o, key=lambda x: (x.get('appName') or '', x.get('desc') or '')):
    print('  ' + json.dumps({k: x.get(k) for k in ('desc', 'appName', 'op', 'ns', 'active')}, ensure_ascii=False, default=str))
print(f'  共 {len(o)} 条。其中 ns = admin.$cmd.aggregate 的那条就是这次 $currentOp 自己')
nd.stop()
