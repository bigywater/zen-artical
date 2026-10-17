import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m75'); reset()
nd = Node('m75', cache=0.25).start(); c = nd.client()
def ss(): return c.admin.command('serverStatus')
def get(d, path):
    for k in path.split('.'): d = d[k]
    return d
def delta(a, b, paths): return {p: (int(get(b, p)) - int(get(a, p))) for p in paths}
print('== 一:opcounters:一组已知的操作前后,各计数器涨了多少(计数器是自进程启动的累计值)')
c.test.t.drop(); s0 = ss()
c.test.t.insert_many([{'_id': i, 'k': i % 100, 'p': 'x' * 100} for i in range(1000)], ordered=False)
for i in range(500): c.test.t.find_one({'_id': i})
for i in range(200): c.test.t.update_one({'_id': i}, {'$set': {'z': 1}})
for i in range(100): c.test.t.delete_one({'_id': i})
for i in range(50): c.test.command('ping')
s1 = ss(); P = ['opcounters.insert', 'opcounters.query', 'opcounters.update', 'opcounters.delete', 'opcounters.getmore', 'opcounters.command']
print('  做了:insert_many 1,000 个文档(1 次调用)、find_one 500 次、update_one 200 次、delete_one 100 次、ping 50 次')
print('  opcounters 的增量: ' + str(delta(s0, s1, P)))
a = ss(); b = ss(); print('  连续两次 serverStatus,中间什么都不做: opcounters.command 增量 = ' + str(b['opcounters']['command'] - a['opcounters']['command']) + '(所以上面 51 = 50 次 ping + 最后那次 serverStatus 自己)')
print('  insert 记的是文档数(insert_many 的 1 个命令记了 1,000)')
print('== 二:metrics.document:服务端内部的文档级计数(returned / inserted / updated / deleted),与 opcounters 对照')
s0 = ss()
list(c.test.t.find({'k': {'$lt': 10}})); c.test.t.update_many({'k': 1}, {'$set': {'z': 2}}); c.test.t.delete_many({'k': 2})
s1 = ss(); P = ['metrics.document.returned', 'metrics.document.inserted', 'metrics.document.updated', 'metrics.document.deleted']
n_find = c.test.t.count_documents({'k': {'$lt': 10}})
print('  做了:find {k < 10}(1 次)、update_many {k: 1}(1 次)、delete_many {k: 2}(1 次)')
print('  metrics.document 增量: ' + str(delta(s0, s1, P)))
print('  opcounters 增量: ' + str(delta(s0, s1, ['opcounters.query', 'opcounters.update', 'opcounters.delete'])))
print('== 三:metrics.queryExecutor:scanned(扫描的索引键)与 scannedObjects(扫描的文档)——没有索引与有索引的同一个查询')
c.test.t.insert_many([{'_id': 10000 + i, 'k': i % 100, 'p': 'x' * 100} for i in range(49000)], ordered=False)
def scan_stats(label, fn):
    a = ss(); fn(); b = ss(); d = delta(a, b, ['metrics.queryExecutor.scanned', 'metrics.queryExecutor.scannedObjects', 'metrics.document.returned'])
    print(f'  {label}: 扫描索引键 {d["metrics.queryExecutor.scanned"]:,},扫描文档 {d["metrics.queryExecutor.scannedObjects"]:,},返回 {d["metrics.document.returned"]:,}')
scan_stats('k = 7,没有 k 索引(全表扫描)', lambda: list(c.test.t.find({'k': 7})))
c.test.t.create_index('k')
scan_stats('k = 7,有 k 索引', lambda: list(c.test.t.find({'k': 7})))
scan_stats('只要 k(覆盖查询)', lambda: list(c.test.t.find({'k': 7}, {'k': 1, '_id': 0})))
print('== 四:connections 与 network:开 20 个客户端连接;一次返回大结果集的查询对 network 计数的影响')
s0 = ss(); print('  connections 基线: ' + str({k: s0['connections'][k] for k in ('current', 'available', 'totalCreated', 'active')}))
cls = [nd.client() for _ in range(20)]
for x in cls: x.admin.command('ping')
s1 = ss(); print('  再开 20 个客户端并各 ping 一次: ' + str({k: s1['connections'][k] for k in ('current', 'available', 'totalCreated', 'active')}))
print(f'  每个客户端对象占 {(s1["connections"]["current"] - s0["connections"]["current"]) / 20:.0f} 个连接(一个操作连接 + 驱动的 2 个监控连接)')
for x in cls: x.close()
time.sleep(0.5); s2 = ss(); print('  这 20 个客户端 close 之后 0.5 秒: ' + str({k: s2['connections'][k] for k in ('current', 'available', 'totalCreated', 'active')}))
time.sleep(3); s2 = ss(); print('  close 之后 3.5 秒: ' + str({k: s2['connections'][k] for k in ('current', 'available', 'totalCreated', 'active')}))
a = ss(); docs = list(c.test.t.find({'k': {'$lt': 50}})); b = ss()
print(f'  返回了 {len(docs):,} 个文档:network.bytesOut 增加 {b["network"]["bytesOut"] - a["network"]["bytesOut"]:,} 字节,bytesIn 增加 {b["network"]["bytesIn"] - a["network"]["bytesIn"]:,} 字节,numRequests 增加 {b["network"]["numRequests"] - a["network"]["numRequests"]}')
print('== 五:wiredTiger.cache:写入一个约 100 MB 的集合、重启(清空缓存)、再读一遍,cache 的 bytes currently in the cache、pages read into cache、dirty 怎么变')
CK = ['bytes currently in the cache', 'maximum bytes configured', 'tracked dirty bytes in the cache', 'pages read into cache', 'bytes read into cache', 'bytes written from cache']
def cache():
    w = ss()['wiredTiger']['cache']; return {k: w.get(k) for k in CK}
print('  基线: ' + str(cache()))
c.test.big.insert_many([{'i': i, 'p': 'y' * 1000} for i in range(100000)], ordered=False)
print('  写入 10 万个 1 KB 文档(约 100 MB)后: ' + str(cache()))
nd.restart(); c = nd.client()
print('  重启后(缓存是空的): ' + str(cache()))
a = cache(); n = sum(1 for _ in c.test.big.find()); b = cache()
print(f'  读完 {n:,} 个文档后: ' + str(b))
print(f'  pages read into cache 增加 {b["pages read into cache"] - a["pages read into cache"]:,};bytes currently in the cache 增加 {b["bytes currently in the cache"] - a["bytes currently in the cache"]:,} 字节')
print('== 六:opLatencies:累计延迟(微秒)与操作数,相除得到平均延迟;分别看 reads / writes / commands')
def lat(): 
    o = ss()['opLatencies']; return {k: (o[k]['latency'], o[k]['ops']) for k in ('reads', 'writes', 'commands')}
a = lat()
for i in range(2000): c.test.small.insert_one({'_id': i})
for i in range(2000): c.test.small.find_one({'_id': i})
b = lat()
for k in ('reads', 'writes', 'commands'):
    dl, do = b[k][0] - a[k][0], b[k][1] - a[k][1]
    print(f'  {k}:延迟增加 {dl:,} μs,操作数增加 {do:,} → 平均 {dl / do if do else 0:.1f} μs')
print('  (做了 2,000 次 insert_one 和 2,000 次 find_one;commands 多出的 1 个操作是 b 那次 serverStatus 自己)')
nd.stop()
