import sys, os, time, json, re, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z63'); R = {}
GC = ZDATA / 'z63' / 'gc.log'; GC.parent.mkdir(parents=True, exist_ok=True); GC.write_text('')
n = Node('z63', 7300, xmx=128, jvm=[f'-Xlog:gc*:file={GC}:time,uptime,level,tags'], conf={'metricsProvider.className': 'org.apache.zookeeper.metrics.prometheus.PrometheusMetricsProvider', 'metricsProvider.httpPort': 7390, 'metricsProvider.httpHost': '127.0.0.1'}).start()
z = client('127.0.0.1:7300'); rs = [z.create_async(f'/n{i}', b'x' * 100) for i in range(5000)]; [r.get() for r in rs]
def scrape():
    c = http.client.HTTPConnection('127.0.0.1', 7390, timeout=5); c.request('GET', '/metrics'); r = c.getresponse(); b = r.read().decode(); return r.status, dict(r.getheaders()).get('Content-Type'), b
st, ct, body = scrape(); lines = body.splitlines()
print('== 一:Prometheus 指标端点(zoo.cfg:metricsProvider.className=…PrometheusMetricsProvider、metricsProvider.httpPort=7390)')
print(f'  GET http://127.0.0.1:7390/metrics → {st},Content-Type: {ct},共 {len(lines)} 行,{len([l for l in lines if l and not l.startswith("#")])} 个样本')
names = sorted({re.match(r'([a-zA-Z_:][a-zA-Z0-9_:]*)', l).group(1) for l in lines if l and not l.startswith('#')})
print('  不同的指标名共', len(names), '个;前 12 个:', names[:12])
print('  指标名前缀分类:', {p: len([x for x in names if x.startswith(p)]) for p in ('znode', 'num_alive', 'jvm_', 'process_', 'fsynctime', 'readlatency', 'updatelatency', 'packets', 'watch', 'outstanding', 'request', 'proposal')}); R['n_lines'] = len(lines); R['n_names'] = len(names)
print()
print('== 二:几个最常用的指标(原样)')
want = ['znode_count', 'num_alive_connections', 'watch_count', 'outstanding_requests', 'packets_received', 'packets_sent', 'node_count', 'fsynctime_count', 'jvm_memory_bytes_used{area="heap"}', 'jvm_gc_collection_seconds_count']
R['samples'] = []
for w_ in want:
    ls = [l for l in lines if l.startswith(w_)][:2]
    for l in ls: print('  ', l[:110]); R['samples'].append(l[:110])
print()
print('== 三:GC 日志(-Xlog:gc*)里的几行:启动 / 第一次年轻代回收')
g = [l for l in GC.read_text().splitlines() if 'Pause' in l or 'Using' in l][:4]; [print('  ', l[:130]) for l in g]; R['gc'] = g
print('  JVM 内部指标 jvm_gc_collection_seconds_* 与 GC 日志的关系:前者是累计次数 / 耗时(适合告警),后者是每一次的细节(适合排查)。')
z.stop(); n.stop(); save('z63', R)
