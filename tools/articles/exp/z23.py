import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z23'); R = {}
n = Node('z23', 7300, xmx=256).start(); z = client('127.0.0.1:7300', timeout=30)
NAME = lambda i: f'child-{i:034d}'
print('== 一:一个父节点下的子节点越多,get_children 越慢,超过响应大小上限直接失败(子节点名 40 个字符)')
print(f'  {"子节点数":>8} {"创建用时 s":>11} {"get_children ms":>16} {"结果":<20}')
R['rows'] = []; made = 0; z.create('/big', b'')
for target in (1000, 10000, 20000, 25000, 30000):
    t0 = time.perf_counter(); rs = [z.create_async(f'/big/{NAME(i)}', b'') for i in range(made, target)]; [r.get() for r in rs]; made = target; tc = time.perf_counter() - t0
    xs = []; res = '成功'
    for _ in range(5):
        t1 = time.perf_counter()
        try: z.get_children('/big'); xs.append((time.perf_counter() - t1) * 1000)
        except Exception as e: res = type(e).__name__; break
        if not z.connected: break
    if not z.connected or res != '成功':
        z.stop(); z = client('127.0.0.1:7300', timeout=30)
    R['rows'].append((target, tc, statistics.median(xs) if xs else None, res)); print(f'  {target:>8} {tc:>11.1f} {(statistics.median(xs) if xs else float("nan")):>16.1f} {res:<20}')
print()
print('== 二:分层(分片)可以绕开上限:同样 30000 个 znode 分到 100 个父节点下,每个父节点 300 个子节点')
t0 = time.perf_counter()
for p in range(100):
    z.create(f'/shard{p:03d}', b''); rs = [z.create_async(f'/shard{p:03d}/{NAME(i)}', b'') for i in range(300)]; [r.get() for r in rs]
tc = time.perf_counter() - t0
xs = []
for p in range(100): t1 = time.perf_counter(); z.get_children(f'/shard{p:03d}'); xs.append((time.perf_counter() - t1) * 1000)
print(f'  创建用时 {tc:.1f} s;100 个父节点各 get_children 的中位延迟 {statistics.median(xs):.2f} ms、最大 {max(xs):.2f} ms'); R['shard'] = dict(med=statistics.median(xs), mx=max(xs))
m = kv(n.four('mntr')); print('  服务端 zk_znode_count =', m.get('zk_znode_count'))
print()
print('== 三:删除一个有大量子节点的父节点:delete 失败(Node not empty),要先逐个删子节点')
try: z.delete('/shard000'); r = '成功'
except Exception as e: r = type(e).__name__
print('  delete /shard000(有 300 个子节点)→', r)
t0 = time.perf_counter(); z.delete('/shard001', recursive=True); print(f'  kazoo delete(recursive=True) 删除 300 个子节点 + 父节点用时 {(time.perf_counter() - t0) * 1000:.0f} ms'); R['del'] = r
print()
print('== 四:同一个 /big(30000 个子节点,响应约 1.3 MiB)用官方 Java 客户端 ls:客户端按 jute.maxbuffer 检查响应大小')
o = cli(7300, 'ls /big', timeout=60)[0]; first = o.splitlines()[0][:120] if o else '(无输出)'; print('  ls /big →', first, '|', len(o), '字符输出'); R['java_ls'] = first
o2 = cli(7300, 'ls /big', timeout=60, jvm=['-Djute.maxbuffer=4194304'])[0]; print('  加 -Djute.maxbuffer=4194304 后 ls /big → 输出', len(o2), '字符,开头', o2[:40].replace(chr(10), ' ')); R['java_ls_big'] = len(o2)
z.stop(); n.stop(); save('z23', R)
