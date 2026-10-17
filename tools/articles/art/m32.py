from lib import *
S = SS('m32')
steps = [
    step("50,000 个随机点(中心 [121.47, 31.23],±0.25 度),loc 上建 2dsphere 索引:key 是 { loc: '2dsphere' },2dsphereIndexVersion 4;validate 里索引条目数是 50000(一个点一个键)。", t=tl(S(1)), mark=lidx(S(1), "2dsphereIndexVersion", "'loc_2dsphere': 50000"), done=lidx(S(1), "key: { loc: '2dsphere' }"), kv=KV([['2dsphere 索引', '版本 4'], ['一个点', '一个索引条目'], ['50,000 个点', '50,000 个条目']], ['一个点'])),
    step("$near 按距离从近到远返回,$maxDistance 单位是米:2000 米内返回 272 个,Python 用 haversine 公式暴力计算也是 272 个,而且 _id 的先后顺序完全一致(True);最近的 5 个是 17981(88.4 米)、18246(136.0)、44372(273.2)、31564(279.6)、31867(288.2);mongosh 里同样查询的前 5 个 _id 相同。", t=tl(S(2)), mark=lidx(S(2), '272 个', '[ 17981, 18246, 44372, 31564, 31867 ]'), done=lidx(S(2), '最近的 5 个'), kv=KV([['$near', '按球面距离由近到远'], ['与暴力计算对比', '个数与顺序都一致'], ['maxDistance', '米']], ['与暴力计算对比'])),
    step("explain:$near 的计划是 GEO_NEAR_2DSPHERE 加三段 FETCH > IXSCAN(loc_2dsphere)(逐圈向外扩展搜索),检查 452 个键、381 个文档,返回 272 个。耗时:$near 2000 米 1.2 ms;$geoWithin + $centerSphere 同样半径用索引 0.8 ms;同样的 $geoWithin 强制全表扫描 24 ms。", t=tl(S(3)), mark=lidx(S(3), 'GEO_NEAR_2DSPHERE', '强制全表'), done=lidx(S(3), 'keysExamined: 452', 'docsExamined: 381'), b=bars([['$near 用索引', 1.2, '1.2 ms'], ['$geoWithin 用索引', 0.8, '0.8 ms'], ['$geoWithin 全表', 24, '24 ms']], 24, mark=[2], done=[0, 1]), kv=KV([['GEO_NEAR_2DSPHERE', '分几圈由近到远扫描'], ['keysExamined', '452(返回 272)'], ['全表', '24 ms']], ['GEO_NEAR_2DSPHERE'])),
    step("聚合的 $geoNear(distanceField: \"dist\"、spherical: true、maxDistance: 1000):结果带距离字段,前 3 个是 p17981(88.5 米)、p18246(136.1)、p44372(273.5)。(与上面 haversine 算出的 88.4 / 136.0 / 273.2 差在地球半径的取值上。)", t=tl(S(4)), mark=lidx(S(4), 'dist: 88.5', 'dist: 136.1', 'dist: 273.5'), done=lidx(S(4), 'p17981'), kv=KV([['$geoNear', '聚合第一阶段,给出 dist'], ['dist 单位', '米'], ['与 haversine', '差零点几米,半径取值不同']], ['$geoNear'])),
    step("多边形会生成多个索引键(S2 单元覆盖):单独放进集合时,约 1 km² 的 small 多边形有 5 条索引条目,约 2500 km² 的 big 多边形有 20 条,点只有 1 条;三个放一起共 26 条。$geoIntersects 点 [121.405, 31.205] 在 small 和 big 里,点 [121.5, 31.4] 只在 big 里。", t=tl(S(5)), mark=lidx(S(5), 'small 单独', 'big   单独'), done=lidx(S(5), 'point 单独', '26', "'small', 'big'"), b=bars([['点', 1, '1 条'], ['small 多边形', 5, '5 条'], ['big 多边形', 20, '20 条']], 20, mark=[1, 2], done=[0]), kv=KV([['点', '1 个键'], ['多边形', '覆盖它的 S2 单元数个键'], ['$geoIntersects', '点在哪些多边形里']], ['多边形'])),
    step("坐标顺序是 [经度, 纬度]:数据在 [经度 10, 纬度 45] 附近,按 [10, 45] 查 5 km 内返回 125 个;写反成 [45, 10](仍是合法经纬度)返回 0 个,不报错;上海的数据写反成 [31.23, 121.47] 则因为纬度 121.47 越界直接报错 Longitude/latitude is out of bounds;插入纬度 95 的点也报错 Could not extract geo keys。", t=tl(S(6)), mark=lidx(S(6), '  0', 'out of bounds', 'Could not extract geo keys'), done=lidx(S(6), '  125'), kv=KV([['写反且仍在合法范围', '不报错,查不到'], ['写反且越界', '报错 out of bounds'], ['经纬度范围', '经度 ±180,纬度 ±90']], ['写反且仍在合法范围'])),
]
A = mkartm('m32', 32, 'MongoDB,2dsphere,地理索引,$near,$geoNear,GeoJSON,真实验证,动画演示',
    '实测 2dsphere 地理索引:5 万个点每个一个索引条目;$near 按距离排序,与 Python haversine 暴力计算的 272 个结果顺序完全一致;GEO_NEAR_2DSPHERE 逐圈扩展搜索(452 个键);多边形生成 5~20 个索引键;经纬度写反的两种后果。',
    '$near 到底怎么查?结果对不对?这篇用 5 万个点对比 Python 的 haversine 暴力计算,看 explain 的逐圈搜索、多边形的索引键数,以及经纬度顺序写反会怎样。',
    [('272 / 272', '$near 2000 米内返回的点数与暴力计算的点数,顺序也一致'), ('452 个键', '$near 返回 272 个结果时检查的索引键数'), ('5 / 20 / 1', '约 1 km² 多边形、约 2500 km² 多边形、点分别生成的 2dsphere 索引条目数')],
    [('点的索引', '<p>2dsphere 索引为每个点生成一个条目,版本 4;GeoJSON 坐标顺序是 [经度, 纬度]。</p>'),
     ('$near 的正确性', '<p>2000 米内 $near 返回的 272 个点,与用 haversine 公式在 Python 里暴力计算的集合、顺序完全一致。</p>'),
     ('怎么扫描', '<p>计划是 <code>GEO_NEAR_2DSPHERE</code> 加几段 FETCH + IXSCAN,由近到远逐圈扩展;检查 452 个键、381 个文档返回 272 个。强制全表的 $geoWithin 要 24 ms,用索引不到 1 ms。</p>'),
     ('$geoNear', '<p>聚合的 <code>$geoNear</code> 在结果里给出 <code>distanceField</code>,单位米。</p>'),
     ('多边形', '<p>多边形被 S2 单元覆盖,产生多个索引键:约 1 km² 的 5 条,约 2500 km² 的 20 条;点只有 1 条。</p>'),
     ('经纬度顺序', '<p>写反了不一定报错:在合法范围内只是查不到(0 个),越界才报错。</p>')],
    steps,
    [ENV_M + '。haversine 暴力计算用地球半径 6371008.8 米;随机点由固定种子生成',
     '没有验证:2d(平面)索引与 legacy 坐标对;$geoWithin 的 $geometry 多边形与跨 180 度经线;2dsphere 复合索引(与非地理字段);S2 覆盖精度参数(2dsphereCoarsestIndexedLevel);$near 在分片集群上的行为;大规模数据下的性能'],
    '2dsphere 地理索引')
