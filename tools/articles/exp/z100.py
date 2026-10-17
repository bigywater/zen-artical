import sys, os, time, json, re, subprocess, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z100'); R = {}
n = Node('z100', 7300, xmx=512, conf={'tickTime': 1000, 'maxClientCnxns': 2000}).start()
def wc(): return int(kv(n.four('mntr'))['zk_watch_count'])
z = client('127.0.0.1:7300')
print('== 一:源码 WatchManager 用 Map<String, Set<Watcher>> 存 watch:同一连接对同一路径重复注册只算 1 个;不同连接各算 1 个;data watch 与 child watch 分属两个管理器')
z.create('/w', b'x'); b0 = wc()
for i in range(100): z.exists('/w', watch=lambda e: None)
print(f'  同一连接对 /w 注册 100 次 exists watch:zk_watch_count {b0} → {wc()}')
c2 = client('127.0.0.1:7300'); c2.exists('/w', watch=lambda e: None); print(f'  另一条连接注册 1 次:→ {wc()}')
z.get_children('/w', watch=lambda e: None); print(f'  同一连接再对 /w 注册 get_children(child watch):→ {wc()}')
R['dedupe'] = [wc()]
print()
print('== 二:触发即移除(triggerWatch 里的 iterator.remove()):')
got = []; z.create('/t', b'1'); z.get('/t', watch=lambda e: got.append(e.type)); b = wc(); z.set('/t', b'2'); time.sleep(0.3); print(f'  触发前 zk_watch_count={b},set 之后={wc()},回调收到 {got}')
c2.stop()
print()
print('== 三:连接关闭时 removeWatcher 是同步的:500 条连接,每条在 10 个不同节点上各注册一个 watch,全部关闭后 zk_watch_count 多久回到基线')
z.ensure_path('/m'); [z.create(f'/m/n{i}', b'') for i in range(10) if not z.exists(f'/m/n{i}')]
base = wc(); cs = []
for i in range(500):
    c = client('127.0.0.1:7300'); [c.exists(f'/m/n{k}', watch=lambda e: None) for k in range(10)]; cs.append(c)
peak = wc(); print(f'  基线 {base} → 500 条连接注册后 {peak}')
t_c = time.perf_counter(); [c.stop() for c in cs]; t_close = time.perf_counter() - t_c; t0 = time.perf_counter(); samples = []
while time.perf_counter() - t0 < 5:
    samples.append((time.perf_counter() - t0, wc()))
    if samples[-1][1] <= base: break
    time.sleep(0.02)
print(f'  500 次 close() 本身用了 {t_close:.1f} s;全部返回后第一次读到的 zk_watch_count = {samples[0][1]},{samples[-1][0]*1000:.0f} ms 内回到 {samples[-1][1]}(基线 {base})')
R['close'] = dict(base=base, peak=peak, ms=samples[-1][0] * 1000, end=samples[-1][1], first=samples[0][1], t_close=t_close)
print()
print('== 四:createNode 里父节点的 cversion 与 pzxid(源码:parent.stat.setCversion / setPzxid):建一个子节点后父节点 stat 的变化')
z.create('/par', b''); s0 = z.exists('/par'); z.create('/par/c', b''); s1 = z.exists('/par'); c_st = z.exists('/par/c'); z.delete('/par/c'); s2 = z.exists('/par')
print(f'  创建前 cversion={s0.cversion} pzxid={s0.pzxid:#x};创建 /par/c 后 cversion={s1.cversion} pzxid={s1.pzxid:#x}(子节点 czxid={c_st.czxid:#x});删除后 cversion={s2.cversion} pzxid={s2.pzxid:#x}')
R['cv'] = dict(c0=s0.cversion, c1=s1.cversion, c2=s2.cversion, pz1_eq_czxid=s1.pzxid == c_st.czxid)
print(f'  创建后 pzxid == 子节点 czxid:{s1.pzxid == c_st.czxid};cversion 每次 +1:{s1.cversion == s0.cversion + 1 and s2.cversion == s1.cversion + 1}')
print()
print('== 五:服务端 delete 时的 supress:同一连接对 /x 既注册 exists(data watch)又注册 get_children(child watch),与另一条只注册 exists 的连接相比,服务端发给它的字节数')
px1 = Proxy(7311, 7300).start(); px2 = Proxy(7312, 7300).start(); a = client('127.0.0.1:7311'); b = client('127.0.0.1:7312')
z.create('/x', b''); a.exists('/x', watch=lambda e: None); a.get_children('/x', watch=lambda e: None); b.exists('/x', watch=lambda e: None); time.sleep(0.5)
a0, b0 = px1.bytes_down, px2.bytes_down; z.delete('/x'); time.sleep(0.8); da, db = px1.bytes_down - a0, px2.bytes_down - b0
print(f'  delete /x 后服务端发给 A(data+child 两种 watch)的字节 {da},发给 B(只有 data watch)的字节 {db}(相等 → 只发了一个 NodeDeleted 通知,与 supress 一致)')
R['supress'] = dict(a=da, b=db); a.stop(); b.stop()
z.stop()
CUR = HERE.parent / 'curator'
print()
r = subprocess.run(['java', '-Dfile.encoding=UTF-8', '-Dstdout.encoding=UTF-8', '-cp', f'{CUR}/lib/*:{CUR}', 'Z100'], capture_output=True, text=True, timeout=100)
print(r.stdout.rstrip()); 
if r.returncode: print('EXIT', r.returncode, r.stderr[-600:])
R['java'] = r.stdout; n.stop(); save('z100', R); os._exit(0)
