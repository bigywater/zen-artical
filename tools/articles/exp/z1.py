import sys, os, time, json, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z1'); R = {}
n = Node('z1', 7300).start()
z = client('127.0.0.1:7300')
print('== 一:ZooKeeper 是「小数据、强顺序」的协调服务:先看它的上限 —— 单个 znode 的数据大小(默认 jute.maxbuffer ≈ 1 MiB)')
res = []
for kb in (1, 512, 1000, 1023, 1024, 2048):
    try: z.create(f'/big{kb}', b'x' * kb * 1024); res.append((kb, 'OK'))
    except Exception as e: res.append((kb, type(e).__name__))
    if not z.connected: z.stop(); z = client('127.0.0.1:7300')
for kb, r in res: print(f'  创建 {kb:>5} KiB 的 znode → {r}')
R['size'] = res
print()
print('== 二:写、读的速度(单机、同步调用,一次一个请求;小 znode 100 字节)')
v = b'v' * 100; N = 1000
t0 = time.perf_counter()
for i in range(N): z.create(f'/w{i}', v)
tw = time.perf_counter() - t0
t0 = time.perf_counter()
for i in range(N * 5): z.get(f'/w{i % N}')
tr = time.perf_counter() - t0
print(f'  同步写 {N} 次:{N / tw:7.0f} 次/秒({tw / N * 1000:.2f} ms/次)'); print(f'  同步读 {N * 5} 次:{N * 5 / tr:7.0f} 次/秒({tr / (N * 5) * 1000:.2f} ms/次)')
R['sync'] = dict(w=N / tw, r=N * 5 / tr)
t0 = time.perf_counter(); rs = [z.create_async(f'/a{i}', v) for i in range(5000)]; [r.get() for r in rs]; ta = time.perf_counter() - t0
print(f'  异步(流水线)写 5000 次:{5000 / ta:7.0f} 次/秒'); R['async_w'] = 5000 / ta
print()
print('== 三:顺序保证:每个写都有全局递增的 zxid;两个 znode 的 czxid 先后与创建顺序一致')
z.create('/o1', b'1'); z.create('/o2', b'2'); z.create('/o3', b'3')
zx = [z.get(p)[1].czxid for p in ('/o1', '/o2', '/o3')]
print('  /o1 /o2 /o3 的 czxid:', [hex(x) for x in zx], '严格递增:', zx == sorted(zx) and len(set(zx)) == 3)
print('  zxid 从服务端怎么看(四字命令 srvr 里的 Zxid):', n.srvr().get('zxid')); R['zxid'] = zx
print()
print('== 四:和数据库的差别:没有查询语言,只能按路径取 / 列子节点;服务端把整棵树放在内存里(mntr)')
m = kv(n.four('mntr'))
print('  znode 数 zk_znode_count =', m.get('zk_znode_count'), '| 近似数据大小 zk_approximate_data_size =', m.get('zk_approximate_data_size'), '字节 | zk_watch_count =', m.get('zk_watch_count'))
R['mntr'] = {k: m.get(k) for k in ('zk_znode_count', 'zk_approximate_data_size')}
z.stop(); n.stop(); save('z1', R)
