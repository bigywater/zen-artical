import sys, os, time, json, re, statistics, threading, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z53'); R = {}
def v2(nd): return nd.dir / 'data' / 'version-2'
def snaps(nd): return sorted((p for p in v2(nd).iterdir() if p.name.startswith('snapshot.')), key=lambda p: int(p.name.split('.')[1], 16))
print('== 一:快照什么时候做:snapCount=1000,写 12000 个 znode,相邻两个快照之间的事务数')
n = Node('z53a', 7300, conf={'snapCount': 1000}).start(); z = client('127.0.0.1:7300')
rs = [z.create_async(f'/n{i}', b'x') for i in range(12000)]; [r.get() for r in rs]; time.sleep(1)
zs = [int(p.name.split('.')[1], 16) for p in snaps(n)]; d = [b - a for a, b in zip(zs, zs[1:])]
print(f'  共 {len(zs)} 个快照;相邻间隔(事务数):{d}'); print(f'  最小 {min(d)} / 最大 {max(d)}(都落在 snapCount/2 = 500 到 snapCount = 1000 之间:{all(500 <= x <= 1000 for x in d[1:])})'); R['intervals'] = d
z.stop(); n.stop()
print()
print('== 二:快照要多久、多大(树里 N 个 znode,每个数据 200 字节;停机重启时会写一份新快照,日志里有耗时)')
print(f'  {"znode 数":>9} {"快照文件":>10} {"耗时 ms":>8} {"文件 MiB":>9}')
R['sizes'] = []
for N in (10000, 50000, 200000):
    n = Node(f'z53b{N}', 7301, xmx=256, conf={'snapCount': 10000000}).start(); z = client('127.0.0.1:7301')
    for s in range(0, N, 5000):
        rs = [z.create_async(f'/n{i}', b'v' * 200) for i in range(s, min(N, s + 5000))]; [r.get() for r in rs]
    z.stop(); n.stop(); (n.dir / 'zk.log').rename(n.dir / 'zk0.log'); n.start(wipe=False)
    m = [re.search(r'Snapshot taken in (\d+) ms', l) for l in n.log().splitlines()]; ms = [int(x.group(1)) for x in m if x][0]
    big = max(snaps(n), key=lambda p: p.stat().st_size); R['sizes'].append((N, ms, big.stat().st_size / 1048576)); print(f'  {N:>9} {big.name:>10} {ms:>8} {big.stat().st_size / 1048576:>9.1f}')
    n.stop()
print()
print('== 三:快照不阻塞写:后台连续写触发多次快照(snapCount=20000,树里已有 100000 个 znode),同时前台测同步写延迟;对照:不触发快照')
def run(snapcount):
    n = Node(f'z53c{snapcount}', 7302, xmx=256, conf={'snapCount': snapcount}).start(); z = client('127.0.0.1:7302'); w = client('127.0.0.1:7302')
    for s in range(0, 100000, 5000):
        rs = [z.create_async(f'/base{i}', b'v' * 200) for i in range(s, s + 5000)]; [r.get() for r in rs]
    stop = threading.Event()
    def bg():
        i = 0
        while not stop.is_set():
            rs = [z.create_async(f'/bg{i + j}', b'v' * 200) for j in range(500)]; [r.get() for r in rs]; i += 500
    t = threading.Thread(target=bg); nb = len(n.log().splitlines()); t.start(); xs = []; t0 = time.perf_counter()
    while time.perf_counter() - t0 < 12:
        a = time.perf_counter(); w.create(f'/fg{len(xs)}', b'x'); xs.append((time.perf_counter() - a) * 1000)
    stop.set(); t.join(); ns = sum(1 for l in n.log().splitlines()[nb:] if 'Snapshot taken' in l); xs.sort()
    r = dict(snaps=ns, p50=xs[len(xs) // 2], p99=xs[int(len(xs) * 0.99)], mx=xs[-1], n=len(xs)); z.stop(); w.stop(); n.stop(); return r
a = run(20000); b = run(100000000)
print(f'  触发快照({a["snaps"]} 次):前台同步写 p50 {a["p50"]:.2f} ms / p99 {a["p99"]:.2f} ms / 最大 {a["mx"]:.1f} ms;不触发快照:p50 {b["p50"]:.2f} / p99 {b["p99"]:.2f} / 最大 {b["mx"]:.1f} ms'); R['block'] = dict(with_snap=a, without=b)
print()
print('== 四:快照压缩 zookeeper.snapshot.compression.method=gz:同样 100000 个 znode 的快照大小与耗时')
def comp(method):
    jvm = [f'-Dzookeeper.snapshot.compression.method={method}'] if method else []
    n = Node(f'z53d{method or "none"}', 7303, xmx=256, jvm=jvm, conf={'snapCount': 10000000}).start(); z = client('127.0.0.1:7303')
    for s in range(0, 100000, 5000):
        rs = [z.create_async(f'/n{i}', b'v' * 200) for i in range(s, s + 5000)]; [r.get() for r in rs]
    z.stop(); n.stop(); (n.dir / 'zk.log').rename(n.dir / 'zk0.log'); n.start(wipe=False)
    ms = [int(m.group(1)) for l in n.log().splitlines() for m in [re.search(r'Snapshot taken in (\d+) ms', l)] if m][0]
    big = max(snaps(n), key=lambda p: p.stat().st_size); n.stop(); return big.name, big.stat().st_size / 1048576, ms
for m in (None, 'gz'):
    nm, sz, ms = comp(m); R['comp_' + (m or 'none')] = dict(name=nm, mib=sz, ms=ms); print(f'  压缩方式 {m or "默认(CHECKED)":<14} 文件 {nm:<16} {sz:>6.1f} MiB  写快照 {ms} ms')
save('z53', R)
