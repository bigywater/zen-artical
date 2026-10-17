import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r52'); R = {}
A = Node(7152, name='a52'); B = Node(7153, name='b52', conf={'replicaof': '127.0.0.1 7152'}); Cn = Node(7154, name='c52', conf={'replicaof': '127.0.0.1 7152'})
A.start(); B.start(); Cn.start()
a, b, cc = A.c(), B.c(), Cn.c()
wait_link(b); wait_link(cc)
for i in range(1000): a.do('SET', f'k{i}', i)
time.sleep(0.3)
def rep(c, name):
    i = info(c, 'replication')
    return f'{name}: role={i["role"]:<6} replid={i["master_replid"][:8]}… replid2={i["master_replid2"][:8] if i["master_replid2"].strip("0") else "0…"} offset={i["master_repl_offset"]:>6} second_offset={i["second_repl_offset"]}'
def st(c, name):
    s = repl_stats(c); return f'{name}: sync_full={s["sync_full"]} sync_partial_ok={s["sync_partial_ok"]}'
print('== 一:A 是主库,B、C 是从库:三者的 replication ID 和 offset')
for c, nme in ((a, 'A'), (b, 'B'), (cc, 'C')): print(rep(c, nme))
print(st(a, 'A(主)'))
R['s1'] = [info(x, 'replication')['master_replid'] for x in (a, b, cc)]
print()
print('== 二:提升 B 为新主库(REPLICAOF NO ONE):B 换了新 replid,旧的存进 replid2')
oldA = info(a, 'replication')['master_replid']; offB = info(b, 'replication')['master_repl_offset']
b.do('REPLICAOF', 'NO', 'ONE')
for c, nme in ((a, 'A'), (b, 'B')): print(rep(c, nme))
iB = info(b, 'replication')
print(f'B 的 replid2 == A 的旧 replid:{iB["master_replid2"] == oldA};second_repl_offset = {iB["second_repl_offset"]}(提升时 offset {offB} + 1)')
R['s2'] = dict(same=iB['master_replid2'] == oldA, second=int(iB['second_repl_offset']), off=int(offB))
print()
print('== 三:C 改跟随 B——不需要重新全量同步')
sB0 = repl_stats(b)
cc.do('REPLICAOF', '127.0.0.1', 7153); wait_link(cc)
sB1 = repl_stats(b)
print(st(b, 'B(新主)'), f' (变化: full +{sB1["sync_full"]-sB0["sync_full"]}, partial_ok +{sB1["sync_partial_ok"]-sB0["sync_partial_ok"]})')
print('B 的日志:'); [print('  ', l.split('* ',1)[-1][:150]) for l in logtail(B, 'partial resynchronization')]
print(rep(cc, 'C'))
R['s3'] = [sB1['sync_full'] - sB0['sync_full'], sB1['sync_partial_ok'] - sB0['sync_partial_ok']]
print()
print('== 四:B 上写入,C 跟得上;旧主 A 也以从库身份重新加入 B——同样是部分重同步')
for i in range(500): b.do('SET', f'n{i}', i)
sB0 = repl_stats(b)
a.do('REPLICAOF', '127.0.0.1', 7153); wait_link(a); time.sleep(0.3)
sB1 = repl_stats(b)
print(f'A 重新加入之后 B: full +{sB1["sync_full"]-sB0["sync_full"]}, partial_ok +{sB1["sync_partial_ok"]-sB0["sync_partial_ok"]}')
print('dbsize A/B/C:', a.do('DBSIZE'), b.do('DBSIZE'), cc.do('DBSIZE'))
R['s4'] = [sB1['sync_full'] - sB0['sync_full'], sB1['sync_partial_ok'] - sB0['sync_partial_ok']]
for c, nme in ((a, 'A'), (b, 'B'), (cc, 'C')): print(rep(c, nme))
print()
print('== 五:一个毫无关系的新节点 D 挂到 B:replid 对不上,只能全量同步')
D = Node(7155, name='d52').start(); d = D.c(); d.do('SET', 'x', 1)
sB0 = repl_stats(b); d.do('REPLICAOF', '127.0.0.1', 7153); wait_link(d); sB1 = repl_stats(b)
print(f'B: full +{sB1["sync_full"]-sB0["sync_full"]}, partial_ok +{sB1["sync_partial_ok"]-sB0["sync_partial_ok"]}')
R['s5'] = [sB1['sync_full'] - sB0['sync_full'], sB1['sync_partial_ok'] - sB0['sync_partial_ok']]
save('r52', R); cleanup([A, B, Cn, D])
