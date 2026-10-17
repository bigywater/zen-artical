import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r89'); R = {}
st = SentinelSet(7740, 2, 7760, 3, quorum=2, down_after=3000, failover_timeout=10000, name='s89')
M = st.nodes[0]
mc = M.c()
for i in range(1000): mc.do('SET', f'k{i}', i)
time.sleep(0.5)
events = []; stop = threading.Event()
def sub(i):
    c = C(7760 + i, timeout=30); c.do('PSUBSCRIBE', '*')
    while not stop.is_set():
        if c.avail(0.1):
            m = c.read()
            if isinstance(m, list) and m[0] == 'pmessage': events.append((time.perf_counter(), i, m[2], m[3]))
ths = [threading.Thread(target=sub, args=(i,)) for i in range(3)]; [t.start() for t in ths]; time.sleep(0.5)
# 一个持续写的客户端:通过 sentinel 找主库
wr = []
def writer():
    i = 0
    while not stop.is_set():
        t = time.perf_counter()
        try:
            a = st.addr(1)
            c = C(a[1], timeout=1); r = c.do('SET', 'w', i, raise_err=False); c.close()
            wr.append((t, 'OK' if r == 'OK' else str(r)[:20], a[1]))
        except Exception as e:
            wr.append((t, type(e).__name__, None))
        i += 1; time.sleep(0.02)
tw = threading.Thread(target=writer); tw.start(); time.sleep(1.0)
t0 = time.perf_counter(); M.kill9()
while time.perf_counter() - t0 < 30:
    if st.addr(0) != ('127.0.0.1', 7740): break
    time.sleep(0.05)
tsw = time.perf_counter() - t0
time.sleep(3.0); stop.set(); [t.join() for t in ths]; tw.join()
print('== 一:kill -9 主库之后,sentinel 发布的事件(相对 kill 的毫秒;只列第一个 sentinel 看到的每种事件,共 3 个 sentinel 订阅)')
seen = set(); rows = []
for t, i, ch, msg in sorted(events):
    if ch.startswith('+sentinel') or ch in ('+sdown', '+odown') and False: pass
    key = (ch, msg.split(' ')[0] if ch in ('+sdown',) else ch)
    if (ch, i) in seen and ch in ('+vote-for-leader', '+sdown', '+odown', '+new-epoch'): pass
    line = f'  +{(t-t0)*1000:6.0f} ms  s{i}  {ch:<34} {msg[:80]}'
    if ch.startswith('+') or ch.startswith('-'):
        if ch in ('+sentinel', '+sentinel-address-switch', '+reboot') or ch.startswith('+sentinel'): continue
        rows.append((ch, i, (t - t0) * 1000, msg))
for ch, i, ms_, msg in rows: print(f'  +{ms_:6.0f} ms  s{i}  {ch:<34} {msg[:90]}')
R['events'] = rows; R['switch'] = tsw
print()
fails = [t for t, r, p in wr if t >= t0 and r != 'OK']
oks_after = [t for t, r, p in wr if t >= t0 and r == 'OK' and p != 7740]
print(f'== 二:写入客户端(每 20 ms 经 sentinel 找主库再 SET):kill 后 {len(fails)} 次失败;首次失败 {(min(fails)-t0)*1000:.0f} ms,首次在新主库上成功 {(min(oks_after)-t0)*1000:.0f} ms' if fails and oks_after else '== 二:写入客户端未观察到失败')
R['outage'] = dict(nfail=len(fails), first_fail=(min(fails) - t0) if fails else None, recovered=(min(oks_after) - t0) if oks_after else None)
print('   新主库地址(sentinel 眼中):', st.addr(0))
print()
print('== 三:新主库的选择与副本重新指向')
for n in st.nodes[1:]:
    try:
        i_ = info(n.c(), 'replication'); print(f'  {n.port}: role={i_["role"]}' + (f' master_port={i_.get("master_port")} link={i_.get("master_link_status")}' if i_['role'] == 'slave' else ''))
    except Exception as e: print(' ', n.port, 'down')
print()
print('== 四:旧主库重启之后:sentinel 把它变成新主库的从库')
t1 = time.perf_counter(); M.start(rewrite=False)
while time.perf_counter() - t1 < 30:
    try:
        i_ = info(M.c(), 'replication')
        if i_['role'] == 'slave' and i_.get('master_link_status') == 'up': break
    except Exception: pass
    time.sleep(0.05)
print(f'  旧主库 {M.port} 重启后 {(time.perf_counter()-t1)*1000:.0f} ms:role = {info(M.c(), "replication")["role"]},master_port = {info(M.c(), "replication").get("master_port")}')
R['rejoin'] = time.perf_counter() - t1
save('r89', R); st.cleanup()
