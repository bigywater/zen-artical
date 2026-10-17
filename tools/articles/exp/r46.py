import sys, time, random, os, json, subprocess, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r46'); R = {}
n = Node(7146).start(); c = n.c()
N = 100000
def mk(key, groups=True):
    c.do('DEL', key)
    if groups: c.do('XGROUP', 'CREATE', key, 'g', '0', 'MKSTREAM')
    for i in range(0, N, 5000): c.pipeline([['XADD', key, '*', 'job', 'x' * 100] for _ in range(5000)])
def mem(key): return c.do('MEMORY', 'USAGE', key, 'SAMPLES', 0)
def stat(key):
    d = kv(c.do('XINFO', 'STREAM', key)); return int(d['length']), int(d['radix-tree-keys']), mem(key)
print('== 一:消费并 XACK 之后,内存变了吗?(10 万条,每条值 100 字节)')
mk('a')
L0, K0, M0 = stat('a')
ids = [e[0] for e in c.do('XREADGROUP', 'GROUP', 'g', 'w', 'COUNT', N, 'STREAMS', 'a', '>')[0][1]]
L1, K1, M1 = stat('a')
for i in range(0, N, 5000): c.do('XACK', 'a', 'g', *ids[i:i+5000])
L2, K2, M2 = stat('a')
print(f'{"阶段":<22} {"XLEN":>7} {"radix-keys":>11} {"MEMORY USAGE":>13}')
print(f'{"写入完成":<22} {L0:>7} {K0:>11} {M0:>13}')
print(f'{"读取但未 ack":<22} {L1:>7} {K1:>11} {M1:>13}')
print(f'{"全部 XACK":<22} {L2:>7} {K2:>11} {M2:>13}')
R['ack'] = [[L0, K0, M0], [L1, K1, M1], [L2, K2, M2]]
print()
print('== 二:XDEL 隔一条删一条(删一半) vs XDEL 连续删前一半')
mk('alt', False); mk('front', False)
alt = c.do('XRANGE', 'alt', '-', '+', 'COUNT', N); front = c.do('XRANGE', 'front', '-', '+', 'COUNT', N)
for i in range(0, N, 5000):
    pass
ai = [e[0] for e in alt][::2]; fi = [e[0] for e in front][:N // 2]
for i in range(0, len(ai), 2000): c.do('XDEL', 'alt', *ai[i:i+2000])
for i in range(0, len(fi), 2000): c.do('XDEL', 'front', *fi[i:i+2000])
print(f'{"删除方式":<22} {"XLEN":>7} {"radix-keys":>11} {"MEMORY USAGE":>13}')
for name, k in (('隔一条删一条', 'alt'), ('连续删前一半', 'front')):
    l, kk, m = stat(k); print(f'{name:<22} {l:>7} {kk:>11} {m:>13}')
R['del'] = {k: stat(k) for k in ('alt', 'front')}
print('(基线:同样写入 10 万条、什么都没删时 MEMORY USAGE = %d)' % M0)
print()
print('== 三:XTRIM 按 MINID / MAXLEN 裁掉旧数据')
mk('t', False)
allids = [e[0] for e in c.do('XRANGE', 't', '-', '+', 'COUNT', N)]
mid = allids[N // 2]
r = c.do('XTRIM', 't', 'MINID', mid)
l, kk, m = stat('t'); print(f'XTRIM t MINID {mid} → 返回 {r};XLEN {l},radix-keys {kk},MEMORY USAGE {m}'); R['minid'] = [l, kk, m]
r = c.do('XTRIM', 't', 'MAXLEN', 0)
l, kk, m = stat('t'); print(f'XTRIM t MAXLEN 0 → 返回 {r};XLEN {l},radix-keys {kk},MEMORY USAGE {m}')
R['trim'] = [l, kk, m]
print()
print('== 四:XDEL 只是打标记:entries-added 不变,max-deleted-entry-id 前进')
d = kv(c.do('XINFO', 'STREAM', 'front'))
for k in ('length', 'entries-added', 'max-deleted-entry-id', 'first-entry'):
    v = d[k] if k != 'first-entry' else d[k][0]
    print(f'{k:>22} = {v}')
save('r46', R); cleanup([n])
