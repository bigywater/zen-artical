import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r92'); R = {}
st = SentinelSet(7960, 2, 7980, 3, quorum=2, down_after=3000, name='s92'); M = st.nodes[0]
sh(st.sents[0].c(), 'SENTINEL', 'GET-MASTER-ADDR-BY-NAME', 'mymaster')
stop = threading.Event(); res = {}
def worker(name, mode):
    log = []; addr = ('127.0.0.1', 7960); c = None; subaddr = [addr]
    if mode == 'sub':
        def listen():
            s = C(7981, timeout=60); s.do('SUBSCRIBE', '+switch-master')
            while not stop.is_set():
                if s.avail(0.1):
                    m = s.read()
                    if m[0] == 'message': p = m[2].split(); subaddr[0] = (p[3], int(p[4]))
        threading.Thread(target=listen, daemon=True).start()
    while not stop.is_set():
        t = time.perf_counter()
        try:
            if c is None: c = C(addr[1], timeout=1)
            r = c.do('SET', 'k', 1, raise_err=False)
            if r == 'OK': log.append((t, 'OK', addr[1]))
            else: log.append((t, str(r)[:30], addr[1])); raise ConnectionError('readonly/err')
        except Exception as e:
            log.append((t, type(e).__name__, addr[1])); c = None
            if mode == 'sentinel':       # 每次失败都问 sentinel
                try:
                    a = st.sents[1].c().do('SENTINEL', 'GET-MASTER-ADDR-BY-NAME', 'mymaster'); addr = (a[0], int(a[1]))
                except Exception: pass
            elif mode == 'sub': addr = subaddr[0]
            time.sleep(0.05)
        time.sleep(0.01)
    res[name] = log
ths = [threading.Thread(target=worker, args=(n, m)) for n, m in (('固定地址', 'fixed'), ('失败后问 sentinel', 'sentinel'), ('订阅 +switch-master', 'sub'))]
[t.start() for t in ths]; time.sleep(1.5)
t0 = time.perf_counter(); M.kill9()
while time.perf_counter() - t0 < 40 and st.addr(0) == ('127.0.0.1', 7960): time.sleep(0.05)
tsw = time.perf_counter() - t0
time.sleep(5); stop.set(); [t.join() for t in ths]
print(f'== kill -9 主库,三个客户端(每 10 ms 一次 SET)的对比;sentinel 完成切换 {tsw:.1f} s')
print(f'{"客户端策略":<20} {"kill 后失败次数":>13} {"首次失败(ms)":>12} {"恢复(首次成功于新主库,ms)":>26}')
R['tsw'] = tsw; R['c'] = {}
for n, log in res.items():
    after = [x for x in log if x[0] >= t0]; fails = [x for x in after if x[1] != 'OK']
    rec = next((x for x in after if x[1] == 'OK' and x[2] != 7960), None)
    ff = (fails[0][0] - t0) * 1000 if fails else None
    print(f'{n:<16} {len(fails):>13} {ff:>12.0f} {((rec[0]-t0)*1000 if rec else float("nan")):>26.0f}' if rec else f'{n:<16} {len(fails):>13} {ff:>12.0f} {"从未恢复":>26}')
    R['c'][n] = dict(fails=len(fails), first_fail=ff, recovered=(rec[0] - t0) if rec else None, top=collections.Counter(x[1] for x in fails).most_common(2))
print('  各客户端失败的错误类型:', {n: v['top'] for n, v in R['c'].items()})
save('r92', R); st.cleanup()
