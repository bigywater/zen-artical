import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r111'); R = {}
n = Node(8200, name='r111').start(); c = n.c()
def mem():
    m = info(c, 'memory'); return {k: m.get(k) for k in ('used_memory', 'used_memory_rss', 'mem_fragmentation_ratio', 'mem_fragmentation_bytes', 'allocator_frag_ratio', 'allocator_frag_bytes', 'allocator_rss_ratio', 'mem_allocator', 'active_defrag_running')}
def show(tag, m):
    print(f'  {tag:<26} used_memory={int(m["used_memory"])/1e6:7.1f} MB  used_memory_rss={int(m["used_memory_rss"])/1e6:7.1f} MB  mem_fragmentation_ratio={m["mem_fragmentation_ratio"]}  allocator_frag_ratio={m["allocator_frag_ratio"]}')
print('== 一:这个 Redis 用的分配器')
print('  mem_allocator =', mem()['mem_allocator'])
print()
print('== 二:尝试开启主动碎片整理')
sh(c, 'CONFIG', 'SET', 'activedefrag', 'yes'); R['err'] = str(c.do('CONFIG', 'SET', 'activedefrag', 'yes', raise_err=False))
sh(c, 'MEMORY', 'PURGE')
print()
print('== 三:制造碎片:写入 100 万个 key(value 大小不一),随机删除其中 90%,看内存指标')
rnd = random.Random(4)
for i in range(0, 1000000, 10000): c.pipeline([['SET', f'k{i+j}', 'x' * rnd.randrange(20, 200)] for j in range(10000)])
m1 = mem(); show('写入 100 万个 key 后', m1)
keys = [f'k{i}' for i in range(1000000)]; rnd.shuffle(keys)
for i in range(0, 900000, 20000): c.pipeline([['DEL', k] for k in keys[i:i + 20000]])
time.sleep(1); m2 = mem(); show('随机删除 90% 之后', m2)
print(f'  used_memory 从 {int(m1["used_memory"])/1e6:.0f} MB 降到 {int(m2["used_memory"])/1e6:.0f} MB(-{(1-int(m2["used_memory"])/int(m1["used_memory"]))*100:.0f}%);used_memory_rss 从 {int(m1["used_memory_rss"])/1e6:.0f} MB 到 {int(m2["used_memory_rss"])/1e6:.0f} MB(-{(1-int(m2["used_memory_rss"])/int(m1["used_memory_rss"]))*100:.0f}%)')
R['m1'] = m1; R['m2'] = m2
print()
print('== 四:MEMORY DOCTOR 怎么说')
print(' ', c.do('MEMORY', 'DOCTOR')[:300].replace('\n', ' '))
R['doctor'] = c.do('MEMORY', 'DOCTOR')[:300]
save('r111', R); cleanup([n])
