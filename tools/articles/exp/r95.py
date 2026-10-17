import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'r91.py')).read().split("print('== 主库通过")[0].replace("tee('r91')", "tee('r95')")
exec(src)
print('== 一:INFO replication 里每个从库的 lag 字段(距上次 REPLCONF ACK 的秒数):冻结一个从库,每秒读一次')
M = Node(7990, name='r95m', conf={'repl-diskless-sync-delay': 0}).start()
reps = [Node(7991 + i, name=f'r95r{i}', conf={'replicaof': '127.0.0.1 7990', 'repl-diskless-sync-delay': 0}).start() for i in range(2)]
[wait_link(r.c()) for r in reps]; time.sleep(2)
c = M.c(); print('  冻结前:', [l.split(',')[-2:] for l in [info(c, 'replication')['slave0'], info(c, 'replication')['slave1']]])
reps[0].p.send_signal(signal.SIGSTOP); L = []
for s in range(7):
    time.sleep(1); i_ = info(c, 'replication'); L.append((s + 1, [x.split('lag=')[1].split(',')[0] for x in (i_['slave0'], i_['slave1'])]))
    print(f'  冻结后 {s+1} s:slave0 lag = {L[-1][1][0]},slave1 lag = {L[-1][1][1]}')
R = {'lag': L}
reps[0].p.send_signal(signal.SIGCONT); cleanup([M] + reps); time.sleep(1)
print()
print('== 二:防脑裂:同样的 sentinel 分区实验(第 91 篇),旧主库加上 min-replicas-to-write 1、min-replicas-max-lag 3')
r0 = J_ = None
r = run({'min-replicas-to-write': 1, 'min-replicas-max-lag': 3}, 'min-replicas')
R['guard'] = r
print(f'  sentinel 切换 {r["switch"]:.1f} s;客户端 A(直连旧主库)共 {r["okA"]} 次写入被回复 OK,其中分区期间 {r["okA_split"]} 次;失败 {r["errA"]} 次 {r["errs"]}')
print(f'  最终在新主库上还在的 {r["kept"]} 条,丢失 {r["lost"]} 条')
import json
json.dump(R, open(os.path.join(HERE, 'out', 'r95.json'), 'w'), ensure_ascii=False, indent=1)
