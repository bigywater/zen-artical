import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r86'); R = {}
def flags_of(s): return sentinel_master(s.c())['flags']
print('== 一:主观下线(sdown):只让 1 个 sentinel 觉得主库不可达,quorum = 2 时能否触发故障转移?')
st = SentinelSet(7660, 2, 7680, 3, quorum=2, down_after=3000, name='s86a'); M = st.nodes[0]
print('  三个 sentinel 眼中主库的 flags:', [flags_of(s) for s in st.sents])
# 冻结主库,同时冻结另外两个 sentinel:只剩 sentinel0 能看到主库"没有回应"
t0 = time.perf_counter()
M.p.send_signal(signal.SIGSTOP); st.sents[1].p.send_signal(signal.SIGSTOP); st.sents[2].p.send_signal(signal.SIGSTOP)
c0 = st.sents[0].c(); first = {}
while time.perf_counter() - t0 < 9:
    f = flags_of(st.sents[0])
    if f not in first: first[f] = time.perf_counter() - t0
    time.sleep(0.02)
print(f'  主库被冻结,另外两个 sentinel 也被冻结;sentinel0 眼中主库 flags 的变化(相对冻结的毫秒):{ {k: round(v*1000) for k, v in first.items()} }')
print('  9 秒后主库地址仍是', st.addr(0), '(没有发生故障转移:sdown 只是「我认为它挂了」,不够触发)')
R['single'] = {k: v for k, v in first.items()}; R['single_addr'] = list(st.addr(0))
M.p.send_signal(signal.SIGCONT); [s.p.send_signal(signal.SIGCONT) for s in st.sents[1:]]
time.sleep(1); st.cleanup(); time.sleep(1)
print()
print('== 二:sdown 的判定时间取决于 down-after-milliseconds:分别设 1000 / 3000 / 6000 ms,冻结主库,量 sentinel 标出 s_down 的时间(每种 2 次)')
print(f'{"down-after":>11} {"s_down 出现(ms)":>20}')
R['da'] = {}
for k, da in enumerate((1000, 3000, 6000)):
    L = []
    for rep in range(2):
        st = SentinelSet(7660, 2, 7680, 3, quorum=2, down_after=da, name=f's86b{k}{rep}')
        M = st.nodes[0]; t0 = time.perf_counter(); M.p.send_signal(signal.SIGSTOP); seen = None
        while time.perf_counter() - t0 < da / 1000 + 6:
            if 's_down' in flags_of(st.sents[0]): seen = time.perf_counter() - t0; break
            time.sleep(0.01)
        L.append(seen); M.p.send_signal(signal.SIGCONT); st.cleanup(); time.sleep(1)
    R['da'][str(da)] = L
    print(f'{da:>11} {", ".join(f"{x*1000:.0f}" for x in L):>20}')
print()
print('== 三:主库进程活着,只是阻塞 6 秒不响应(DEBUG SLEEP):sentinel 怎么看')
st = SentinelSet(7660, 2, 7680, 3, quorum=2, down_after=3000, name='s86c', node_conf={'enable-debug-command': 'yes'}); M = st.nodes[0]
t0 = time.perf_counter()
threading.Thread(target=lambda: M.c(timeout=30).do('DEBUG', 'SLEEP', 6, raise_err=False)).start()
first = {}
while time.perf_counter() - t0 < 8:
    f = flags_of(st.sents[0])
    if f not in first: first[f] = time.perf_counter() - t0
    time.sleep(0.02)
print(f'  主库被 DEBUG SLEEP 6 阻塞(进程活着,只是 6 秒不响应),sentinel0 眼中 flags 变化:{ {k: round(v*1000) for k, v in first.items()} }')
R['sleep'] = {k: v for k, v in first.items()}
print('  6 秒后 sentinel 眼中主库:', flags_of(st.sents[0]), ' 主库地址:', st.addr(0))
save('r86', R); st.cleanup()
