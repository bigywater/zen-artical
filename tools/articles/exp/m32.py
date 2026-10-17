import sys, os, math; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m32'); reset()
n = Node('m32'); n.start(); c = n.client(); db = c.test
N = 50000; r = random.Random(32)
CLAT, CLON = 31.23, 121.47
pts = [(CLON + r.uniform(-0.25, 0.25), CLAT + r.uniform(-0.25, 0.25)) for _ in range(N)]
db.places.insert_many([{'_id': i, 'name': f'p{i}', 'loc': {'type': 'Point', 'coordinates': [x, y]}} for i, (x, y) in enumerate(pts)])
def hav(lon1, lat1, lon2, lat2):
    R = 6371008.8; p1, p2 = math.radians(lat1), math.radians(lat2); dl = math.radians(lon2 - lon1); dp = p2 - p1
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2; return 2 * R * math.asin(math.sqrt(a))
print(f'== 一:{N:,} 个随机点(中心 [{CLON}, {CLAT}],±0.25 度),loc 上建 2dsphere 索引;索引键数 = 点数')
msh(n, 'db.places.createIndex({loc: "2dsphere"})')
msh(n, 'db.places.getIndexes().filter(i => i.name != "_id_")')
print(f'  validate 的索引条目数: {db.command("validate", "places", full=True)["keysPerIndex"]}')
print('== 二:$near 按距离从近到远返回,$maxDistance 的单位是米。和 Python 里用 haversine 公式暴力算出来的前 10 个比对')
Q = [CLON, CLAT]
rows = list(db.places.find({'loc': {'$near': {'$geometry': {'type': 'Point', 'coordinates': Q}, '$maxDistance': 2000}}}))
bf = sorted(((hav(CLON, CLAT, x, y), i) for i, (x, y) in enumerate(pts)), key=lambda t: t[0]); bf2000 = [i for d, i in bf if d <= 2000]
print(f'  $near(中心点, 2000 米) 返回 {len(rows)} 个;暴力计算 2000 米内有 {len(bf2000)} 个;_id 序列完全一致: {[d["_id"] for d in rows] == bf2000}')
print(f'  最近的 5 个(_id, 暴力算出的距离米): {[(d["_id"], round(hav(CLON, CLAT, *d["loc"]["coordinates"]), 1)) for d in rows[:5]]}')
msh(n, 'db.places.find({loc: {$near: {$geometry: {type: "Point", coordinates: [121.47, 31.23]}, $maxDistance: 2000}}}, {_id: 1}).limit(5).toArray().map(d => d._id)', label='mongosh 里同样的 $near 查询的前 5 个 _id')
print('== 三:explain:$near 用 GEO_NEAR_2DSPHERE 阶段;对比 $geoWithin + $centerSphere 强制全表扫描的耗时')
msh(n, EXJS + 'ex(db.places.find({loc: {$near: {$geometry: {type: "Point", coordinates: [121.47, 31.23]}, $maxDistance: 2000}}}).explain("executionStats"))', label='db.places.find({loc: {$near: ..., $maxDistance: 2000}})', n=12)
R = 2000 / 6378100
t_near = bench(lambda: list(db.places.find({'loc': {'$near': {'$geometry': {'type': 'Point', 'coordinates': Q}, '$maxDistance': 2000}}})), 9)
t_within = bench(lambda: list(db.places.find({'loc': {'$geoWithin': {'$centerSphere': [Q, R]}}})), 9)
t_nat = bench(lambda: list(db.places.find({'loc': {'$geoWithin': {'$centerSphere': [Q, R]}}}).hint([('$natural', 1)])), 5)
print(f'  $near 2000 米 {fm(t_near)};$geoWithin/$centerSphere(用 2dsphere 索引)2000 米 {fm(t_within)};同样的 $geoWithin 强制全表 {fm(t_nat)}')
print('== 四:聚合的 $geoNear:distanceField 给出每个结果的距离(米),可带过滤条件')
msh(n, 'db.places.aggregate([{$geoNear: {near: {type: "Point", coordinates: [121.47, 31.23]}, distanceField: "dist", spherical: true, maxDistance: 1000}}, {$limit: 3}, {$project: {name: 1, dist: {$round: ["$dist", 1]}}}])')
print('== 五:多边形文档会生成多个索引键(S2 单元覆盖),点只有一个;面积越大、形状越复杂键越多')
A = [(1, 'small', {'type': 'Polygon', 'coordinates': [[[121.40, 31.20], [121.41, 31.20], [121.41, 31.21], [121.40, 31.21], [121.40, 31.20]]]}),
     (2, 'big', {'type': 'Polygon', 'coordinates': [[[121.2, 31.0], [121.7, 31.0], [121.7, 31.5], [121.2, 31.5], [121.2, 31.0]]]}),
     (3, 'point', {'type': 'Point', 'coordinates': [121.47, 31.23]})]
db.areas.create_index([('area', '2dsphere')])
for i, nm, g in A:
    db.areas.insert_one({'_id': i, 'name': nm, 'area': g}); one = db[f'area_{nm}']; one.create_index([('area', '2dsphere')]); one.insert_one({'area': g})
    print(f'  {nm:<6}单独放进一个集合,2dsphere 索引条目数 {db.command("validate", f"area_{nm}", full=True)["keysPerIndex"]["area_2dsphere"]}')
print(f'  三个放在一起的索引条目数: {db.command("validate", "areas", full=True)["keysPerIndex"]["area_2dsphere"]}')
msh(n, 'db.areas.find({area: {$geoIntersects: {$geometry: {type: "Point", coordinates: [121.405, 31.205]}}}}, {name: 1}).toArray().map(d => d.name)', label='哪些区域包含点 [121.405, 31.205]')
msh(n, 'db.areas.find({area: {$geoIntersects: {$geometry: {type: "Point", coordinates: [121.5, 31.4]}}}}, {name: 1}).toArray().map(d => d.name)', label='哪些区域包含点 [121.5, 31.4]')
print('== 六:坐标顺序是 [经度, 纬度];写反了:数据在合法范围内时不会报错,只会查不到;越界才报错')
r2 = random.Random(33)
db.eu.insert_many([{'_id': i, 'loc': {'type': 'Point', 'coordinates': [10 + r2.uniform(-0.3, 0.3), 45 + r2.uniform(-0.3, 0.3)]}} for i in range(5000)])
db.eu.create_index([('loc', '2dsphere')])
msh(n, 'db.eu.find({loc: {$near: {$geometry: {type: "Point", coordinates: [10, 45]}, $maxDistance: 5000}}}).toArray().length', label='数据在 [经度 10, 纬度 45] 附近;按 [10, 45] 查 5 km 内')
msh(n, 'db.eu.find({loc: {$near: {$geometry: {type: "Point", coordinates: [45, 10]}, $maxDistance: 5000}}}).toArray().length', label='写反成 [45, 10](纬度 10、经度 45)—— 仍然合法,只是在另一个地方')
msh(n, 'try { db.places.find({loc: {$near: {$geometry: {type: "Point", coordinates: [31.23, 121.47]}}}}).limit(1).toArray() } catch (e) { e.message.slice(0, 160) }', label='上海的 [纬度 31.23, 经度 121.47] 写反:纬度 121.47 越界,直接报错')
msh(n, 'try { db.places.insertOne({loc: {type: "Point", coordinates: [121.47, 95]}}) } catch (e) { e.message.slice(0, 160) }', label='插入纬度 95 的点')
n.stop()
