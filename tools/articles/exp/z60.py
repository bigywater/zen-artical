import sys, os, time, json, re, subprocess, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z60'); R = {}
def heap(n):
    subprocess.run(['/usr/bin/jcmd', str(n.p.pid), 'GC.run'], capture_output=True); r = subprocess.run(['/usr/bin/jcmd', str(n.p.pid), 'GC.heap_info'], capture_output=True, text=True).stdout
    return int(re.search(r'used (\d+)K', r).group(1)) / 1024
def measure(N, size, conns=0, watches=0, port=7300):
    n = Node(f'z60-{N}-{size}-{conns}', port, xmx=512, conf={'snapCount': 100000000, 'maxClientCnxns': 5000}).start(); z = client(f'127.0.0.1:{port}', timeout=30)
    base = heap(n)
    for s in range(0, N, 5000):
        rs = [z.create_async(f'/d/k{i:07d}' if False else f'/k{i:07d}', b'v' * size) for i in range(s, min(N, s + 5000))]; [r.get() for r in rs]
    cl = []
    for i in range(conns):
        c = client(f'127.0.0.1:{port}', timeout=30); cl.append(c)
        for j in range(watches // max(conns, 1)): c.get(f'/k{(i * (watches // max(conns, 1)) + j) % N:07d}', watch=lambda e: None)
    h = heap(n); z.stop(); [c.stop() for c in cl]; n.stop(); (n.dir / 'zk.log').rename(n.dir / 'zk0.log'); n.start(wipe=False)
    snap = max((p.stat().st_size for p in (n.dir / 'data' / 'version-2').iterdir() if p.name.startswith('snapshot.')), default=0) / 1048576; n.stop()
    return dict(N=N, size=size, heap=h - base, snap=snap)
print('== 一:用三组实测数据拟合「堆 = a × znode 数 + b × 数据总字节」,再预测一个没测过的配置并实测验证')
pts = [measure(50000, 100, port=7300), measure(50000, 1000, port=7301), measure(150000, 100, port=7302)]
for p in pts: print(f'  {p["N"]:>7} 个 znode × {p["size"]:>4} 字节:堆增量 {p["heap"]:6.1f} MiB;快照 {p["snap"]:6.1f} MiB')
R['pts'] = pts
rows = [(p['N'], p['N'] * p['size'], p['heap']) for p in pts]
s11 = sum(x * x for x, _, _ in rows); s12 = sum(x * y for x, y, _ in rows); s22 = sum(y * y for _, y, _ in rows); t1 = sum(x * h for x, _, h in rows); t2 = sum(y * h for _, y, h in rows)
det = s11 * s22 - s12 * s12; a = (t1 * s22 - t2 * s12) / det; b = (s11 * t2 - s12 * t1) / det
print(f'  拟合:每个 znode 约 {a * 1048576:.0f} 字节的固定开销,每个数据字节约 {b * 1048576:.2f} 字节(最小二乘,只有 3 个数据点,只用来估数量级)'); R['coef'] = (a * 1048576, b * 1048576)
print()
print('== 二:预测并验证:100000 个 znode × 500 字节')
pred = a * 100000 + b * 100000 * 500; m = measure(100000, 500, port=7303)
print(f'  预测堆增量 {pred:.1f} MiB;实测 {m["heap"]:.1f} MiB;误差 {abs(pred - m["heap"]) / m["heap"] * 100:.1f}%;快照文件 {m["snap"]:.1f} MiB'); R['pred'] = dict(pred=pred, real=m['heap'], snap=m['snap'])
print()
print('== 三:连接与 watch 要另算(第 18 篇测过):再加 300 个连接 × 每个 20 个 watch,堆又增加多少')
m2 = measure(50000, 100, conns=300, watches=6000, port=7304); print(f'  同样 50000 × 100 字节的树,加 300 个连接和 6000 个 watch:堆增量 {m2["heap"]:.1f} MiB(没有连接时 {pts[0]["heap"]:.1f} MiB,多了 {m2["heap"] - pts[0]["heap"]:.1f} MiB)'); R['conn'] = dict(with_conn=m2['heap'], without=pts[0]['heap'])
save('z60', R)
