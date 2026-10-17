import sys, os, datetime as dt; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m14'); reset()
n = Node('m14'); n.start(); c = n.client(); db = c.test
T0 = dt.datetime(2026, 1, 1, 0, 0, 0)
print('== 一:创建时序集合:timeField、metaField、granularity。listCollections 把它标成 timeseries,选项里多了 bucketMaxSpanSeconds')
msh(n, 'db.createCollection("m", {timeseries: {timeField: "ts", metaField: "sensor", granularity: "seconds"}})')
msh(n, 'db.getCollectionInfos().map(c => ({name: c.name, type: c.type, ts: c.options.timeseries}))')
msh(n, 'db.getSiblingDB("test").runCommand({listCollections: 1, filter: {name: /system.buckets/}}).cursor.firstBatch.map(c => c.name)')
msh(n, 'try { db.system.buckets.m.countDocuments() } catch (e) { e.message.slice(0, 260) }')
print('== 二:插入 3 个传感器各 400 个测量(每秒一个),用 rawData 选项直接读底层的 bucket 文档,看实际存了几个')
import random; r = random.Random(14)
docs = []
for s_ in ('A', 'B', 'C'):
    for i in range(400): docs.append({'ts': T0 + dt.timedelta(seconds=i), 'sensor': s_, 'temp': round(20 + r.random() * 5, 2), 'hum': r.randrange(30, 70)})
r.shuffle(docs); db.m.insert_many(docs, ordered=False)
print(f'  插入了 {len(docs)} 个测量文档;db.m.countDocuments = {db.m.count_documents({})}')
RAW = 'db.runCommand({aggregate: "m", cursor: {}, rawData: true, pipeline: %s}).cursor.firstBatch'
msh(n, RAW % '[{$count: "buckets"}]')
msh(n, RAW % '[{$project: {_id: 0, sensor: "$meta", n: "$control.count", version: "$control.version", first: "$control.min.ts", last: "$control.max.ts"}}, {$sort: {sensor: 1}}]')
print('== 三:一个 bucket 文档的结构:control(版本、最小值、最大值、计数)、meta(传感器)、data(每个字段一列,二进制压缩)')
msh(n, 'db.runCommand({find: "m", filter: {meta: "A"}, limit: 1, rawData: true}).cursor.firstBatch[0]', n=40, w=100)
msh(n, RAW % '[{$match: {meta: "A"}}, {$limit: 1}, {$project: {_id: 0, version: "$control.version", ts: {$type: "$data.ts"}, temp: {$type: "$data.temp"}, hum: {$type: "$data.hum"}, sensor: {$type: "$meta"}, ts_bytes: {$binarySize: "$data.ts"}, temp_bytes: {$binarySize: "$data.temp"}}}]')
print('== 四:bucket 上限:同一个传感器在 1 小时里写 3000 个测量,会拆成几个 bucket?')
db.create_collection('m2', timeseries={'timeField': 'ts', 'metaField': 'sensor', 'granularity': 'seconds'})
db.m2.insert_many([{'ts': T0 + dt.timedelta(seconds=i), 'sensor': 'X', 'v': i} for i in range(3000)], ordered=False)
msh(n, 'db.runCommand({aggregate: "m2", cursor: {}, rawData: true, pipeline: [{$project: {_id: 0, n: "$control.count", from: "$control.min.ts", to: "$control.max.ts"}}, {$sort: {from: 1}}]}).cursor.firstBatch')
msh(n, 'var t = db.m2.aggregate([{$collStats: {storageStats: {}}}]).toArray()[0].storageStats.timeseries; ({bucketCount: t.bucketCount, numBucketInserts: t.numBucketInserts, numBucketsClosedDueToCount: t.numBucketsClosedDueToCount, numBucketsClosedDueToSize: t.numBucketsClosedDueToSize, avgNumMeasurementsPerCommit: t.avgNumMeasurementsPerCommit})')
print('== 五:磁盘占用:同样的 60,000 条测量放进时序集合与普通集合')
mk = lambda i: {'ts': T0 + dt.timedelta(seconds=i // 3), 'sensor': f's{i % 3}', 'temp': round(20 + (i % 97) / 10, 1), 'hum': 40 + i % 23}
db.create_collection('ts_big', timeseries={'timeField': 'ts', 'metaField': 'sensor', 'granularity': 'seconds'})
rows = [mk(i) for i in range(60000)]
for i in range(0, 60000, 5000): db.ts_big.insert_many(rows[i:i + 5000], ordered=False); db.reg_big.insert_many([dict(x) for x in rows[i:i + 5000]], ordered=False)
c.admin.command('fsync'); time.sleep(2); c.admin.command('fsync')
st1 = db.command('collStats', 'ts_big'); st2 = db.command('collStats', 'reg_big')
print(f'  时序集合: storageSize {st1["storageSize"]:,},bucket 数 {st1["timeseries"]["bucketCount"]},平均每个 bucket {st1["timeseries"]["avgNumMeasurementsPerCommit"]}')
print(f'  普通集合: storageSize {st2["storageSize"]:,},文档数 {st2["count"]:,}')
print(f'  比例: 时序集合是普通集合的 {st1["storageSize"] / st2["storageSize"]:.0%}')
print('== 六:查询怎么走:explain 里能看到 bucket 的展开阶段;限制:不能随意更新单个测量')
msh(n, 'var p = db.m.explain().aggregate([{$match: {sensor: "A", ts: {$gte: ISODate("2026-01-01T00:00:10Z"), $lt: ISODate("2026-01-01T00:00:20Z")}}}]); JSON.stringify(p.stages ? p.stages.map(s => Object.keys(s)[0]) : p.queryPlanner.winningPlan.stage)')
msh(n, 'db.m.getIndexes()')
for lab_, js in [('updateOne 改测量字段', 'db.m.updateOne({sensor: "A"}, {$set: {temp: 0}})'), ('updateMany 只按 meta 过滤改 meta', 'db.m.updateMany({sensor: "A"}, {$set: {sensor: "A2"}})'), ('deleteOne 按测量字段', 'db.m.deleteOne({temp: 20})'), ('deleteMany 按 meta', 'db.m.deleteMany({sensor: "B"})')]:
    msh(n, f'try {{ ({js}) }} catch (e) {{ e.message.slice(0, 170) }}', label=js)
n.stop()
