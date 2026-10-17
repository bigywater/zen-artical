import sys, time, random, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r41'); R = {}
n = Node(7141).start(); c = n.c()
for i in range(1, 13): c.do('XADD', 's', f'{i}-0', 'job', f'j{i}')
print('== 一:创建消费组的起点:$ 只看之后的新消息;0 从头开始')
sh(c, 'XGROUP', 'CREATE', 's', 'gnew', '$')
sh(c, 'XGROUP', 'CREATE', 's', 'gall', '0')
sh(c, 'XGROUP', 'CREATE', 'nokey', 'g', '$', raise_err=False) if False else None
sh(c, 'XGROUP', 'CREATE', 'nokey', 'g', '$')
sh(c, 'XGROUP', 'CREATE', 'nokey', 'g', '$', 'MKSTREAM')
sh(c, 'XGROUP', 'CREATE', 's', 'gall', '0')
print()
print('== 二:同一个组里的 3 个消费者轮流读,每人每次 1 条,消息不重复')
got = {'c1': [], 'c2': [], 'c3': []}
seq = ['c1', 'c2', 'c3', 'c1', 'c1', 'c2', 'c3', 'c3', 'c2', 'c1', 'c2', 'c3']
for who in seq:
    r = c.do('XREADGROUP', 'GROUP', 'gall', who, 'COUNT', 1, 'STREAMS', 's', '>')
    got[who].append(r[0][1][0][0])
for k, v in got.items(): print(k, v)
R['got'] = got; R['seq'] = seq
sh(c, 'XREADGROUP', 'GROUP', 'gall', 'c1', 'COUNT', 1, 'STREAMS', 's', '>')
print('(读完了,再读一次返回 nil)')
print()
print('== 三:不同的组各自独立,都能读到全部消息')
r = c.do('XREADGROUP', 'GROUP', 'gnew', 'x', 'STREAMS', 's', '>')
print('gnew(创建于 $):', r)
c.do('XADD', 's', '13-0', 'job', 'j13')
r = c.do('XREADGROUP', 'GROUP', 'gnew', 'x', 'STREAMS', 's', '>'); print('XADD 一条之后 gnew 读到:', r)
print()
print('== 四:XINFO GROUPS / CONSUMERS')
sh(c, 'XINFO', 'GROUPS', 's')
sh(c, 'XINFO', 'CONSUMERS', 's', 'gall')
print()
print('== 五:消费者不用预先创建,第一次读就自动出现;也可以显式 XGROUP CREATECONSUMER')
sh(c, 'XGROUP', 'CREATECONSUMER', 's', 'gall', 'c9')
sh(c, 'XGROUP', 'CREATECONSUMER', 's', 'gall', 'c9')
sh(c, 'XGROUP', 'DESTROY', 's', 'gnew')
sh(c, 'XGROUP', 'DESTROY', 's', 'gnew')
save('r41', R); cleanup([n])
