import sys, time, random, os, json, subprocess, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r45'); R = {}
n = Node(7145).start(); c = n.c()
for i in range(1, 11): c.do('XADD', 's', f'{i}-0', 'job', f'j{i}')
c.do('XGROUP', 'CREATE', 's', 'g', '0')
c.do('XREADGROUP', 'GROUP', 'g', 'A', 'COUNT', 10, 'STREAMS', 's', '>')
time.sleep(0.6)
print('== 一:A 读了 10 条没 ack;B 用 XAUTOCLAIM 每次最多认领 3 条,靠游标翻页')
cur = '0-0'; rounds = []
while True:
    r = c.do('XAUTOCLAIM', 's', 'g', 'B', 500, cur, 'COUNT', 3)
    ids = [e[0] for e in r[1]]
    print(f'游标 {cur:>5} → 下一个游标 {r[0]:>5}  认领 {ids}  已删除 {r[2]}')
    rounds.append(dict(cur=cur, nxt=r[0], ids=ids))
    if r[0] == '0-0': break
    cur = r[0]
R['rounds'] = rounds
print()
print('== 二:认领之后 idle 归零、投递次数 +1,所以马上再来一轮什么都认领不到')
sh(c, 'XPENDING', 's', 'g', '-', '+', 3)
sh(c, 'XAUTOCLAIM', 's', 'g', 'C', 500, '0-0', 'COUNT', 3)
print()
print('== 三:JUSTID:只转移所有权,不返回消息体,也不增加投递次数')
time.sleep(0.6)
sh(c, 'XAUTOCLAIM', 's', 'g', 'C', 500, '0-0', 'COUNT', 3, 'JUSTID')
sh(c, 'XPENDING', 's', 'g', '-', '+', 3)
print()
print('== 四:PEL 里的消息被 XDEL 了:XAUTOCLAIM 把它从 PEL 里清掉,并在第三个元素里告诉你')
time.sleep(0.6)
sh(c, 'XDEL', 's', '4-0', '5-0')
sh(c, 'XAUTOCLAIM', 's', 'g', 'D', 500, '0-0', 'COUNT', 10)
sh(c, 'XPENDING', 's', 'g')
print()
print('== 五:翻页的调用次数')
print(f'10 条 pending,COUNT 3:{len(R["rounds"])} 次 XAUTOCLAIM 调用扫完(最后一次返回游标 0-0)')
save('r45', R); cleanup([n])
