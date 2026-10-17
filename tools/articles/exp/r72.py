import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r72'); R = {}
cl = Cluster(7360, 3, 1, name='c72'); time.sleep(1)
c0 = cl.nodes[0].c()
KS = lambda k: c0.do('CLUSTER', 'KEYSLOT', k)
print('== 一:同一个用户的几个 key,有 / 没有 hash tag')
for k in ('user1:profile', 'user1:orders', 'user1:cart', '{user1}:profile', '{user1}:orders', '{user1}:cart'): print(f'  {k:<18} → 槽 {KS(k)}')
print()
print('== 二:hash tag 的解析规则(服务器返回的槽位 vs 我用规则推断的「参与计算的部分」)')
cases = [('a{b}c', 'b'), ('{b}', 'b'), ('{}a', '{}a'), ('{a', '{a'), ('a}', 'a}'), ('{{a}}', '{a'), ('{a}{b}', 'a'), ('{a}}', 'a'), ('x{}{y}', 'x{}{y}'), ('a{b', 'a{b'), ('{a}b}c', 'a'), ('', '')]
print(f'{"key":<12} {"服务器槽位":>8} {"参与计算的部分":>16} {"推断槽位":>8} {"一致":>4}')
rows = []
for k, part in cases:
    s1 = KS(k); s2 = keyslot(part); rows.append((k, s1, part, s2)); print(f'{k!r:<12} {s1:>8} {part!r:>16} {s2:>8} {"✓" if s1 == s2 else "✗":>4}')
R['rules'] = rows
print()
print('== 三:一个 tag 只能落在一个槽里——10 万个 key 都用 {user1} 会怎样')
cc = CC([7360])
for i in range(100000): cc.do(f'{{user1}}:{i}', 'SET', f'{{user1}}:{i}', 1)
per = {}
for n in cl.nodes:
    c = n.c()
    if 'master' in c.do('ROLE')[0]: per[n.port] = c.do('DBSIZE')
print('各主库 DBSIZE:', per, '  CLUSTER COUNTKEYSINSLOT', keyslot('user1'), '=', C(slot_owner_map(c0)[keyslot('user1')]).do('CLUSTER', 'COUNTKEYSINSLOT', keyslot('user1')), '(向该槽的主库查询)')
R['hot'] = per
print()
print('== 四:折中——按 key 编号取模分成 64 个 tag({user1:0}…{user1:63}),仍保证「同一个 tag 内」可以多 key 操作')
for n in cl.nodes:
    n.c().do('FLUSHALL') if 'master' in n.c().do('ROLE')[0] else None
for i in range(100000): cc.do(f'{{user1:{i % 64}}}:{i}', 'SET', f'{{user1:{i % 64}}}:{i}', 1)
per2 = {}
for n in cl.nodes:
    c = n.c()
    if 'master' in c.do('ROLE')[0]: per2[n.port] = c.do('DBSIZE')
print('各主库 DBSIZE:', per2)
slots64 = set(keyslot(f'user1:{t}') for t in range(64))
print(f'64 个 tag 落在 {len(slots64)} 个不同的槽')
R['spread'] = per2
save('r72', R); cl.cleanup()
