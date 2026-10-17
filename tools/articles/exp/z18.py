import sys, os, time, json, re, threading, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from concurrent.futures import ThreadPoolExecutor
tee('z18'); R = {}
n = Node('z18', 7300, xmx=256, conf={'maxClientCnxns': 2000}).start()
def heap():
    subprocess.run(['/usr/bin/jcmd', str(n.p.pid), 'GC.run'], capture_output=True)
    r = subprocess.run(['/usr/bin/jcmd', str(n.p.pid), 'GC.heap_info'], capture_output=True, text=True).stdout
    return int(re.search(r'used (\d+)K', r).group(1)) / 1024
def rss(): return int(subprocess.run(['ps', '-o', 'rss=', '-p', str(n.p.pid)], capture_output=True, text=True).stdout.strip()) / 1024
adm = client('127.0.0.1:7300'); adm.create('/w', b'')
for i in range(20000): pass
rs = [adm.create_async(f'/w/n{i:05d}', b'') for i in range(20000)]; [r.get() for r in rs]
base = (heap(), rss()); print('== 基线:20000 个空 znode(用来被 watch),没有额外连接:JVM 已用堆 %.1f MiB,RSS %.0f MiB' % base)
clients = []; lock = threading.Lock()
def mk(i):
    z = client('127.0.0.1:7300', timeout=20)
    with lock: clients.append(z)
print()
print('== 一:连接数的内存代价:新增 400 个空闲连接(没有 watch)')
with ThreadPoolExecutor(30) as ex: list(ex.map(mk, range(400)))
time.sleep(1); m = kv(n.four('mntr')); h1 = (heap(), rss())
print(f'  zk_num_alive_connections = {m["zk_num_alive_connections"]};JVM 已用堆 {h1[0]:.1f} MiB(+{h1[0] - base[0]:.1f}),RSS {h1[1]:.0f} MiB(+{h1[1] - base[1]:.0f})'); R['conn'] = dict(heap=h1[0] - base[0], rss=h1[1] - base[1], conns=m['zk_num_alive_connections'])
print()
print('== 二:watch 数量的内存代价:每个客户端对 50 个不同的 znode 注册 watch(400 × 50 = 20000 个 watch)')
def reg(i):
    z = clients[i]
    for j in range(50): z.get(f'/w/n{(i * 50 + j) % 20000:05d}', watch=lambda e: None)
with ThreadPoolExecutor(30) as ex: list(ex.map(reg, range(400)))
time.sleep(1); m = kv(n.four('mntr')); h2 = (heap(), rss())
print(f'  zk_watch_count = {m["zk_watch_count"]};JVM 已用堆 {h2[0]:.1f} MiB(比只有连接时 +{h2[0] - h1[0]:.1f}),RSS {h2[1]:.0f} MiB'); print('  wchs →', ' '.join(n.four('wchs').split()))
R['watch'] = dict(heap=h2[0] - h1[0], count=m['zk_watch_count'])
print()
print('== 三:同一个客户端对同一个路径注册多次 watch 会占用多少:对 /w/n00000 注册 100 次(同一连接)')
w0 = int(kv(n.four('mntr'))['zk_watch_count'])
for _ in range(100): clients[0].get('/w/n00000', watch=lambda e: None)
w1 = int(kv(n.four('mntr'))['zk_watch_count']); print(f'  zk_watch_count {w0} → {w1}(同一个连接对同一路径的重复注册只算 1 个)'); R['dup'] = (w0, w1)
for z in clients: z.stop()
adm.stop(); n.stop(); save('z18', R)
