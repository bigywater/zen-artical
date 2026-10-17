import sys, os, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
import bson.objectid as oid
tee('m4'); reset()
PY = sys.executable
def split(o):
    h = o.binary
    return f'{h[:4].hex()} {h[4:9].hex()} {h[9:].hex()}'
print('== 一:ObjectId 的 12 个字节 = 4 字节时间戳 + 5 字节进程内随机值 + 3 字节计数器(全部大端)')
ids = [ObjectId() for _ in range(4)]
print(f'  {"十六进制":<26}{"时间戳(4)":<10}{"随机(5)":<12}{"计数器(3)"}')
for o in ids: print(f'  {str(o):<26}{o.binary[:4].hex():<10}{o.binary[4:9].hex():<12}{o.binary[9:].hex()}  = {int.from_bytes(o.binary[9:], "big")}')
print(f'  时间戳 {int.from_bytes(ids[0].binary[:4], "big")} 秒 = {ids[0].generation_time.strftime("%Y-%m-%d %H:%M:%S")} UTC(pymongo 的 generation_time)')
print('== 二:时间戳只有秒精度:同一秒生成的 ObjectId 时间部分相同,靠计数器区分;时间戳可以反推创建时间')
t0 = int(time.time()); batch = [ObjectId() for _ in range(100000)]; t1 = int(time.time())
secs = sorted(set(int.from_bytes(o.binary[:4], 'big') - t0 for o in batch))
print(f'  连续生成 100,000 个:覆盖的秒数偏移 {secs}(相对生成前的整秒);其中第 1 个和最后 1 个的计数器 {int.from_bytes(batch[0].binary[9:], "big")} → {int.from_bytes(batch[-1].binary[9:], "big")}')
print(f'  整批在同一个进程里 5 字节随机部分的取值个数: {len(set(o.binary[4:9] for o in batch))}')
fd = ObjectId.from_datetime(dt := __import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc))
print(f'  ObjectId.from_datetime(2026-01-01) = {fd}(后面 8 字节全 0,常用来做按时间范围的 _id 查询边界)')
print('== 三:不同进程的 5 字节随机值不同:三个独立的 Python 进程各生成 2 个')
for i in range(3):
    r = subprocess.run([PY, '-c', 'from bson import ObjectId\nfor _ in range(2): print(ObjectId())'], capture_output=True, text=True).stdout.split()
    print(f'  进程 {i + 1}: ' + '  '.join(f'{x[:8]} {x[8:18]} {x[18:]}' for x in r))
print('== 四:计数器每次 +1,到 0xffffff 之后回绕到 0(pymongo 里把内部计数器设到 0xfffffe 来演示)')
oid.ObjectId._inc = 0xfffffd
for _ in range(5): o = ObjectId(); print(f'  {o}  计数器 {o.binary[9:].hex()}')
print('== 五:是否严格递增:单进程内递增,多进程并发时 _id 的排序不等于创建的先后')
code = 'import time\nfrom bson import ObjectId\nt=time.time()\nout=[]\nwhile time.time()-t<1.5:\n    out.append((time.time_ns(),str(ObjectId())))\n    time.sleep(0.0005)\nfor a,b in out: print(a,b)'
procs = [subprocess.Popen([PY, '-c', code], stdout=subprocess.PIPE, text=True) for _ in range(3)]
rows = []
for k, p in enumerate(procs): rows += [(int(l.split()[0]), l.split()[1], k) for l in p.communicate()[0].splitlines()]
rows.sort()
by_time = [r[1] for r in rows]; by_id = sorted(by_time)
inv = sum(1 for a, b in zip(by_time, by_time[1:]) if a > b)
print(f'  3 个进程各生成约 {len(rows) // 3} 个,共 {len(rows)} 个 ObjectId;按创建时间(纳秒时钟)排好之后,相邻两个中 _id 反而变小的有 {inv} 对')
print(f'  按 _id 排序是否等于按创建时间排序: {by_time == by_id}')
for k in range(3):
    mine = [r[1] for r in rows if r[2] == k]; print(f'  进程 {k + 1} 内部是否严格递增: {all(a < b for a, b in zip(mine, mine[1:]))}')
print('== 六:_id 缺省时谁生成?驱动在发送前就生成并写进文档;绕过驱动的这一步,服务端也会补一个')
n = Node('m4'); n.start()
msh(n, 'oid = ObjectId("65a1b2c3d4e5f60718293a4b"); [oid.getTimestamp(), oid.toString(), oid.id.toString("hex").length]')
c = n.client(); d = {'y': 2}
print(f'  pymongo: insert_one 之前 doc = {d};')
r = c.test.c.insert_one(d)
print(f'  insert_one 之后同一个字典变成 {{"y": 2, "_id": ObjectId(...)}}: {sorted(d)},_id 的类型 {type(d["_id"]).__name__},与 inserted_id 相同: {d["_id"] == r.inserted_id}')
c.test.command('insert', 'c3', documents=[{'z': 1}])
back = c.test.c3.find_one()
print(f'  用原始 insert 命令发送一个没有 _id 的文档 {{"z": 1}},读回来: {sorted(back)},_id 类型 {type(back["_id"]).__name__}')
msh(n, 'db.c3.aggregate([{$project: {t: {$toDate: "$_id"}, idtype: {$type: "$_id"}}}])')
n.stop()
