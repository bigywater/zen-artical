import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m5'); reset()
n = Node('m5'); n.start(); c = n.client(); db = c.test
LIM = 16 * 1024 * 1024
print('== 一:服务端告诉客户端的几个上限(hello 命令)')
msh(n, 'h = db.hello(); ({maxBsonObjectSize: h.maxBsonObjectSize, maxMessageSizeBytes: h.maxMessageSizeBytes, maxWriteBatchSize: h.maxWriteBatchSize})')
print(f'  maxBsonObjectSize = {LIM:,} = 16 × 1024 × 1024')
def doc_of(total):
    base = len(bson.encode({'_id': 1, 's': ''})); return {'_id': 1, 's': 'x' * (total - base)}
print('== 二:刚好 16 MiB 的文档能插入,多 1 个字节服务端就拒绝(错误码 10334)')
d = doc_of(LIM); print(f'  文档编码后 {len(bson.encode(d)):,} 字节(= {len(bson.encode(d)) / LIM:.4f} × 16 MiB)')
t0 = time.perf_counter(); db.big.insert_one(d); print(f'  insert_one 成功,耗时 {(time.perf_counter() - t0) * 1000:.0f} ms;读回 len(s) = {len(db.big.find_one()["s"]):,}')
d2 = doc_of(LIM + 1); d2['_id'] = 2
try: db.big.insert_one(d2)
except Exception as e: print(f'  多 1 字节({len(bson.encode(d2)):,}): {type(e).__name__}: {str(e)[:160]}')
print('== 三:绕过 insert_one 的拆包,用原始 insert 命令把超限文档放进 documents 数组:服务端按文档逐个拒绝,在回复里给出 writeErrors(命令本身不抛异常)')
for extra in (1, 1024):
    dd = doc_of(LIM + extra); dd['_id'] = 100 + extra
    r = db.command('insert', 'big', documents=[dd]); print(f'  文档 {len(bson.encode(dd)):,} 字节(超 {extra} 字节): n={r["n"]}, writeErrors={r["writeErrors"]}')
dd = doc_of(LIM + 16 * 1024); dd['_id'] = 3
try: db.command('insert', 'big', documents=[dd])
except Exception as e: print(f'  超 16 KiB: {type(e).__name__}: {str(e)[:150]}')
print(f'  集合里最后的文档数: {db.big.count_documents({})}(只有最开始刚好 16 MiB 的那一个)')
print('== 四:update 把文档撑过 16 MiB:服务端报错,原文档不变')
db.grow.insert_one({'_id': 1, 's': 'x' * (LIM - 2 * 1024 * 1024)})
print(f'  起点文档约 {len(bson.encode(db.grow.find_one())) / 1024 / 1024:.1f} MiB')
msh(n, 'try { db.grow.updateOne({_id: 1}, [{$set: {s: {$concat: ["$s", "$s"]}}}]) } catch (e) { e.message }')
msh(n, 'bsonsize(db.grow.findOne({_id: 1})) / 1024 / 1024')
db.arr.insert_one({'_id': 1, 'a': []})
msh(n, 'var r = null; for (var i = 0; i < 40; i++) { try { db.arr.updateOne({_id: 1}, {$push: {a: "x".repeat(1024 * 1024)}}); } catch (e) { r = "第 " + (i + 1) + " 次 $push 1MiB 报错: " + e.message; break } } r')
msh(n, 'db.arr.aggregate([{$project: {n: {$size: "$a"}}}])')
print('== 五:嵌套深度:找出服务端接受的最大深度(二分),看看错误信息')
def nest(k):
    d = {'v': 1}
    for _ in range(k - 1): d = {'a': d}
    return d
def ok(k):
    try: db.deep.insert_one({'_id': k, 'doc': nest(k)}); return True
    except Exception as e: ok.err = str(e); return False
lo, hi = 100, 200
assert ok(lo) and not ok(hi)
while hi - lo > 1:
    mid = (lo + hi) // 2
    if ok(mid): lo = mid
    else: hi = mid
print(f'  内嵌 100 层: 成功;二分查找得到:内嵌 {lo} 层成功,{hi} 层失败(外层文档本身也算 1 层,即总深度 {lo + 1} 成功)')
ok(hi); print(f'  失败时的错误: {ok.err.split(", full error")[0]}')
ok(250); print(f'  内嵌 250 层(超过 BSON 解析上限):{ok.err[:60]}…{ok.err.split("}")[-1][-40:] if False else ""}')
msh(n, 'db.adminCommand({getParameter: 1, maxBSONDepth: 1})')
print('== 六:聚合产生超过 16 MiB 的文档:$group 把 20 个 1 MiB 的字符串 $push 进一个数组')
db.parts.insert_many([{'_id': i, 'g': 1, 's': 'y' * (1024 * 1024)} for i in range(20)])
msh(n, 'r = db.parts.aggregate([{$group: {_id: "$g", all: {$push: "$s"}}}]).toArray()[0]; [r.all.length, bsonsize(r), bsonsize(r) > 16 * 1024 * 1024]')
msh(n, 'try { db.parts.aggregate([{$group: {_id: "$g", all: {$push: "$s"}}}, {$out: "outc"}]).toArray(); "ok" } catch (e) { e.message.slice(0, 200) }')
msh(n, 'db.parts.aggregate([{$group: {_id: "$g", n: {$sum: 1}, bytes: {$sum: {$strLenBytes: "$s"}}}}])')
n.stop()
