import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r88'); R = {}
print('== quorum 1(一个 sentinel 就能宣布客观下线),但另外 2 个 sentinel 被冻结;kill -9 主库。它能不能发起并完成故障转移?')
st = SentinelSet(7780, 2, 7800, 3, quorum=1, down_after=3000, failover_timeout=8000, name='s88')
M = st.nodes[0]
events = []; stop = threading.Event()
def sub():
    c = C(7800, timeout=60); c.do('PSUBSCRIBE', '*')
    while not stop.is_set():
        if c.avail(0.1):
            m = c.read()
            if isinstance(m, list) and m[0] == 'pmessage': events.append((time.perf_counter(), m[2], m[3]))
th = threading.Thread(target=sub); th.start(); time.sleep(0.5)
st.sents[1].p.send_signal(signal.SIGSTOP); st.sents[2].p.send_signal(signal.SIGSTOP)
t0 = time.perf_counter(); M.kill9()
time.sleep(25); stop.set(); th.join()
rows = []
for t, ch, msg in events:
    if ch.startswith('+sentinel'): continue
    rows.append((ch, (t - t0) * 1000, msg)); print(f'  +{(t-t0)*1000:6.0f} ms  {ch:<34} {msg[:80]}')
print('  25 秒后 sentinel0 认为的主库地址:', st.addr(0), '(仍是旧主库:没有选出新主库)')
print('  主库仍是 7780 的 flags:', sentinel_master(st.sents[0].c())['flags'])
R['rows'] = rows; R['addr'] = list(st.addr(0))
lg = [l.split('# ', 1)[-1][:120] for l in st.sents[0].log().splitlines() if any(k in l for k in ('failover', 'vote', 'elected', 'try-failover', 'abort'))]
print('  sentinel0 日志(节选):'); [print('   ', l) for l in lg[:8]]
save('r88', R)
for s in st.sents[1:]: s.p.send_signal(signal.SIGCONT)
st.cleanup()
