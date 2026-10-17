import sys, os, time, json, re, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z22'); R = {}
n = Node('z22', 7300, xmx=256).start(); z = client('127.0.0.1:7300')
print('== 一:不同 value 大小的同步写 / 读延迟(每种大小 30 次,中位数;单机)')
print(f'  {"大小":>8} {"写 ms":>8} {"读 ms":>8} {"写吞吐 MiB/s":>14}')
R['rows'] = []
for kb in (1, 10, 100, 500, 1000):
    v = b'x' * kb * 1024; z.create(f'/v{kb}', v); ws, rs = [], []
    for i in range(30):
        t0 = time.perf_counter(); z.set(f'/v{kb}', v); ws.append((time.perf_counter() - t0) * 1000)
    for i in range(30):
        t0 = time.perf_counter(); z.get(f'/v{kb}'); rs.append((time.perf_counter() - t0) * 1000)
    w, r = statistics.median(ws), statistics.median(rs); R['rows'].append((kb, w, r)); print(f'  {kb:>5} KiB {w:>8.2f} {r:>8.2f} {kb / 1024 / (w / 1000):>14.1f}')
print()
print('== 二:每次 set 都会写进事务日志:1000 次 set 一个 100 KiB 的 znode,数据目录增长')
def du(): return sum(p.stat().st_size for p in (n.dir / 'data' / 'version-2').iterdir() if p.name.startswith('snapshot.')), sum(p.stat().st_blocks * 512 for p in (n.dir / 'data' / 'version-2').iterdir() if p.name.startswith('log.'))
s0, l0 = du(); v = b'y' * 100 * 1024; z.create('/grow', v); t0 = time.perf_counter()
for i in range(1000): z.set('/grow', v)
dt = time.perf_counter() - t0; s1, l1 = du()
print(f'  1000 次 set(每次 100 KiB)用时 {dt:.1f} s;事务日志实际占盘增长 {(l1 - l0) / 1048576:.1f} MiB(≈ {1000 * 100 / 1024:.0f} MiB 的写入量);当前只有 1 个这样的 znode,内存里只占 100 KiB')
R['log'] = dict(mib=(l1 - l0) / 1048576, s=dt)
print()
print('== 三:对大 value 做 watch:一次修改触发的通知很小(事件不带数据),但接收者 get 要读整份')
got = []; w = client('127.0.0.1:7300'); w.get('/v1000', watch=lambda e: got.append(time.perf_counter())); t0 = time.perf_counter(); z.set('/v1000', b'z' * 1024 * 1000)
while not got: time.sleep(0.001)
t1 = time.perf_counter(); w.get('/v1000'); t2 = time.perf_counter()
print(f'  set 1000 KiB → 通知到达 {(got[0] - t0) * 1000:.1f} ms;通知后读取这 1000 KiB 用 {(t2 - t1) * 1000:.1f} ms'); R['watch'] = dict(notify=(got[0] - t0) * 1000, read=(t2 - t1) * 1000)
w.stop(); z.stop(); n.stop(); save('z22', R)
