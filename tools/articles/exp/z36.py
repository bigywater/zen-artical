import sys, os, time, json, re, statistics, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z36'); R = {}
e = Ensemble('z36', 3, base=7300).start(); hosts = e.hosts()
print('== 一:选举期间客户端写和读不可用多久?一个写线程和一个读线程每 10 ms 一次,重复杀 leader 5 次,看最长连续失败的时间窗')
print(f'  {"次":>2} {"写不可用(ms)":>13} {"读不可用(ms)":>13} {"失败写次数":>10}')
R['runs'] = []
for r in range(5):
    z = client(hosts, timeout=10); z.ensure_path('/rw')
    stop = threading.Event(); wlog = []; rlog = []
    def writer():
        i = 0
        while not stop.is_set():
            t = time.perf_counter()
            try: z.create(f'/rw/w{r}-{i}', b''); ok = True
            except Exception: ok = False
            wlog.append((t, ok)); i += 1; time.sleep(0.01)
    def reader():
        while not stop.is_set():
            t = time.perf_counter()
            try: z.exists('/rw'); ok = True
            except Exception: ok = False
            rlog.append((t, ok)); time.sleep(0.01)
    tw = threading.Thread(target=writer); tr = threading.Thread(target=reader); tw.start(); tr.start(); time.sleep(1)
    ld = e.leader(); tk = time.perf_counter(); ld.kill(); time.sleep(8); stop.set(); tw.join(); tr.join()
    def window(log):
        # 从杀 leader 开始:最长的「两次成功之间」的间隔
        ok_ts = [t for t, ok in log if ok]; gaps = [(b - a) for a, b in zip(ok_ts, ok_ts[1:])]; return max(gaps) * 1000 if gaps else None
    wg, rg = window(wlog), window(rlog); nf = sum(1 for t, ok in wlog if not ok)
    R['runs'].append(dict(w=wg, r=rg, nfail=nf)); print(f'  {r + 1:>2} {wg:>13.0f} {rg:>13.0f} {nf:>10}')
    z.stop(); ld.start(wipe=False, wait=False); e.wait_quorum(); time.sleep(1.5)
w = [x['w'] for x in R['runs']]; rr = [x['r'] for x in R['runs']]
print(f'  写不可用中位 {statistics.median(w):.0f} ms(最小 {min(w):.0f} / 最大 {max(w):.0f});读不可用中位 {statistics.median(rr):.0f} ms'); R['med'] = dict(w=statistics.median(w), mn=min(w), mx=max(w), r=statistics.median(rr))
e.stop(); save('z36', R)
