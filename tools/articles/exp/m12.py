import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.cursor import CursorType
tee('m12'); reset()
n = Node('m12'); n.start(); c = n.client(); db = c.test
print('== 一:max 限制文档数:capped 集合 size=4096、max=5,依次插入 8 个文档,只剩最后 5 个')
db.create_collection('cap5', capped=True, size=4096, max=5)
for i in range(1, 9): db.cap5.insert_one({'_id': i, 'v': f'doc{i}'})
msh(n, 'db.cap5.find({}, {v: 1})')
msh(n, 'var s = db.cap5.stats(); ({capped: s.capped, max: s.max, maxSize: s.maxSize, count: s.count, size: s.size})')
print('== 二:size 限制总字节数:size=4096 的 capped 集合,每个文档 194 字节,连续插入 100 个,文档数很快稳定下来')
db.create_collection('capsz', capped=True, size=4096)
counts = []
for i in range(100):
    db.capsz.insert_one({'_id': i, 'pad': 'x' * 170}); counts.append(db.capsz.count_documents({}))
print(f'  每个文档 {len(bson.encode({"_id": 0, "pad": "x" * 170}))} 字节;插入过程中集合文档数依次(每 10 个取一次): {counts[::10]}')
msh(n, 'var s = db.capsz.stats(); ({count: s.count, size: s.size, maxSize: s.maxSize, storageSize: s.storageSize})')
msh(n, 'db.capsz.find({}, {_id: 1}).toArray().map(d => d._id)')
print('== 三:capped 集合的限制(9.0.2 上实测):删除单个文档、把文档改大、原样大小的更新、drop')
for lab_, js in [('deleteOne', 'db.capsz.deleteOne({_id: 91})'), ('更新:字段变长', 'db.capsz.updateOne({_id: 92}, {$set: {pad: "y".repeat(400)}})'), ('更新:大小不变', 'db.capsz.updateOne({_id: 93}, {$set: {pad: "z".repeat(170)}})'), ('更新:变短', 'db.capsz.updateOne({_id: 94}, {$set: {pad: "w"}})'), ('replaceOne 变长', 'db.capsz.replaceOne({_id: 95}, {pad: "y".repeat(400)})')]:
    msh(n, f'try {{ ({js}) }} catch (e) {{ e.message.slice(0, 160) }}', label=js)
msh(n, 'db.capsz.find({_id: {$in: [91, 92, 93, 94, 95]}}).toArray().map(d => [d._id, d.pad.length])')
print('== 四:自然顺序就是插入顺序;可以用 $natural 倒着读最新的 N 条')
msh(n, 'db.capsz.find({}, {_id: 1}).sort({$natural: -1}).limit(3).toArray().map(d => d._id)')
msh(n, 'db.capsz.getIndexes().map(i => i.name)')
print('== 五:tailable 游标:一个线程用 TAILABLE_AWAIT 一直等,另一个线程之后插入,前者收到新文档')
db.create_collection('tail', capped=True, size=1 << 20); db.tail.insert_one({'_id': 0, 'm': 'first'})
got = []
def tailer():
    cur = n.client().test.tail.find({}, cursor_type=CursorType.TAILABLE_AWAIT).max_await_time_ms(500); t0 = time.time()
    while time.time() - t0 < 4 and len(got) < 4:
        for d in cur: got.append((round(time.time() - t0, 1), d['_id']))
        if not cur.alive: break
th = threading.Thread(target=tailer); th.start(); time.sleep(1)
for i in (1, 2, 3): db.tail.insert_one({'_id': i, 'm': f'new{i}'}); time.sleep(0.7)
th.join(); print(f'  tailable 游标收到(距启动的秒数, _id): {got}')
c2 = db.tail.find({'_id': 99}, cursor_type=CursorType.TAILABLE); print(f'  对普通(非 capped)集合 tailable 会怎样: ', end='')
db.plain.insert_one({'x': 1})
try: list(db.plain.find({}, cursor_type=CursorType.TAILABLE))
except Exception as e: print(' '.join(str(e).split())[:140])
print('== 六:把普通集合转成 capped(convertToCapped),以及在线修改大小(collMod cappedSize / cappedMax)')
db.reg.insert_many([{'_id': i, 'pad': 'x' * 100} for i in range(1000)])
print(f'  转换前 reg: {db.reg.count_documents({})} 个文档,capped={db.command("collStats", "reg").get("capped")}')
r = db.command('convertToCapped', 'reg', size=32768); print(f'  convertToCapped(size=32768): {r}')
st = db.command('collStats', 'reg'); print(f'  转换后: capped={st["capped"]},count={st["count"]},maxSize={st["maxSize"]},size={st["size"]}(最老的文档被丢弃,留下最新的)')
print(f'  最早的 _id = {db.reg.find_one(sort=[("$natural", 1)])["_id"]},最晚的 _id = {db.reg.find_one(sort=[("$natural", -1)])["_id"]}')
r = db.command('collMod', 'reg', cappedSize=16384, cappedMax=50); print(f'  collMod cappedSize=16384, cappedMax=50: {r}')
st = db.command('collStats', 'reg'); print(f'  之后: count={st["count"]}, maxSize={st["maxSize"]}, max={st.get("max")}')
db.reg.insert_one({'_id': 5000, 'pad': 'x' * 100}); st = db.command('collStats', 'reg'); print(f'  再插入 1 个文档之后: count={st["count"]}(新的上限立刻生效),最早的 _id = {db.reg.find_one(sort=[("$natural", 1)])["_id"]}')
n.stop()
