import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z26'); R = {}
def run(label, jvm, port):
    n = Node(f'z26-{port}', port, jvm=jvm).start(); z = client(f'127.0.0.1:{port}')
    t0 = time.perf_counter(); rs = [z.create_async(f'/n{i}', b'x' * 100) for i in range(20000)]; [r.get() for r in rs]; dt = time.perf_counter() - t0
    m = kv(n.four('mntr')); out = dict(tput=20000 / dt, outstanding=m.get('zk_outstanding_requests'), max_lat=m.get('zk_max_latency'), thr_wait=m.get('zk_avg_request_throttle_queue_time_ms'), throttled=m.get('zk_throttled_ops'), maxreq=m.get('zk_max_request_throttle_queue_time_ms'))
    print(f'  {label:<48} 吞吐 {out["tput"]:7.0f} 次/秒  max_latency {out["max_lat"]} ms  throttle 队列平均等待 {out["thr_wait"]} ms  zk_throttled_ops {out["throttled"]}')
    z.stop(); n.stop(); return out
print('== 一:20000 次异步 create(全部流水线发出)在不同的限流参数下的吞吐')
R['default'] = run('默认', [], 7300)
R['gol10'] = run('-Dzookeeper.globalOutstandingLimit=10', ['-Dzookeeper.globalOutstandingLimit=10'], 7301)
R['thr10'] = run('-Dzookeeper.request_throttle_max_requests=10', ['-Dzookeeper.request_throttle_max_requests=10'], 7302)
R['thr1'] = run('-Dzookeeper.request_throttle_max_requests=1', ['-Dzookeeper.request_throttle_max_requests=1'], 7303)
print()
print('== 二:RequestThrottler 线程与相关指标的名字(mntr 里含 throttle 的键)')
n = Node('z26b', 7304).start(); keys = sorted(k for k in kv(n.four('mntr')) if 'throttl' in k); print('  ', keys[:12]); R['keys'] = keys[:12]
print('  线程:', [x for x in threads(n) if 'Throttl' in x]); n.stop(); save('z26', R)
