import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r87'); R = {}
def flags_of(s):
    try: return sentinel_master(s.c())['flags']
    except Exception: return '?'
def watch(st, sents, secs, stopwhen=None):
    t0 = time.perf_counter(); tl = {i: {} for i in range(len(sents))}
    while time.perf_counter() - t0 < secs:
        for i, s in enumerate(sents):
            f = flags_of(s)
            if f not in tl[i]: tl[i][f] = time.perf_counter() - t0
        if stopwhen and stopwhen(): break
        time.sleep(0.02)
    return tl
def show(tl, ix):
    for i in ix: print(f'   sentinel{i}: ' + '  '.join(f'{k or "?"}@{v*1000:.0f}ms' for k, v in tl[i].items()))
print('== 一:quorum 2,3 个 sentinel,kill -9 主库:每个 sentinel 眼中主库 flags 的变化(相对 kill 的毫秒)')
st = SentinelSet(7700, 2, 7720, 3, quorum=2, down_after=3000, name='s87a'); M = st.nodes[0]
M.kill9(); tl = watch(st, st.sents, 12, stopwhen=lambda: st.addr(0) != ('127.0.0.1', 7700))
show(tl, range(3)); R['a'] = {str(i): tl[i] for i in tl}
print('   新主库地址:', st.addr(0)); st.cleanup(); time.sleep(1)
print()
print('== 二:quorum 3,但其中 1 个 sentinel 被冻结,kill -9 主库:只有 2 个 sentinel 能投「下线」,够不够')
st = SentinelSet(7700, 2, 7720, 3, quorum=3, down_after=3000, name='s87b'); M = st.nodes[0]
st.sents[2].p.send_signal(signal.SIGSTOP); M.kill9()
tl = watch(st, st.sents[:2], 12); show(tl, range(2)); print('   12 秒后主库地址:', st.addr(0), ' (未切换)')
R['b'] = {str(i): tl[i] for i in tl}; R['b_addr'] = list(st.addr(0))
print('   解冻第 3 个 sentinel 之后:')
st.sents[2].p.send_signal(signal.SIGCONT)
tl = watch(st, st.sents, 15, stopwhen=lambda: st.addr(0) != ('127.0.0.1', 7700)); show(tl, range(3))
print('   新主库地址:', st.addr(0)); R['b2'] = {str(i): tl[i] for i in tl}; st.cleanup(); time.sleep(1)
print()
print('== 三:quorum 1:任何一个 sentinel 觉得挂了就够')
st = SentinelSet(7700, 2, 7720, 3, quorum=1, down_after=3000, name='s87c'); M = st.nodes[0]
M.kill9(); tl = watch(st, st.sents, 12, stopwhen=lambda: st.addr(0) != ('127.0.0.1', 7700)); show(tl, range(3))
R['c'] = {str(i): tl[i] for i in tl}
save('r87', R); st.cleanup()
