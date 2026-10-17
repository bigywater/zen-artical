import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r97'); R = {}
n = Node(8010, name='r97', conf={'latency-monitor-threshold': 5, 'enable-debug-command': 'yes', 'appendonly': 'yes', 'appendfsync': 'always'}).start(); c = n.c()
sh(c, 'CONFIG', 'GET', 'latency-monitor-threshold')
print('\n== 一:制造几类延迟事件:慢命令(command)、fork、AOF 写 / fsync、过期')
for i in range(400000 // 5000): c.pipeline([['SET', f'k:{i*5000+j}', 'v'] for j in range(5000)])
for i in range(3): c.do('DEBUG', 'SLEEP', 0.03 + 0.03 * i)
c.do('KEYS', '*')
c.do('BGSAVE'); time.sleep(1.5)
c.do('BGREWRITEAOF'); time.sleep(2)
for i in range(400): c.do('SET', f'z{i}', 'x' * 100)
print('\n== 二:LATENCY LATEST:每个事件类型 [事件名, 最近一次的时间戳, 最近一次的毫秒数, 历史最大毫秒数]')
lat = c.do('LATENCY', 'LATEST'); print(fmt(lat)); R['latest'] = [(x[0], x[2], x[3]) for x in lat]
print('\n== 三:LATENCY HISTORY command(该事件最近的采样点:[时间戳, 毫秒数])')
h = c.do('LATENCY', 'HISTORY', 'command'); print(fmt(h)); R['history'] = h
print('\n== 四:LATENCY GRAPH command(ASCII 图)')
g = c.do('LATENCY', 'GRAPH', 'command'); print(g); R['graph'] = g
print('\n== 五:LATENCY DOCTOR(服务器生成的分析报告,原文)')
d = c.do('LATENCY', 'DOCTOR'); print(d); R['doctor_len'] = len(d)
print('\n== 六:LATENCY RESET 清除事件')
sh(c, 'LATENCY', 'RESET'); sh(c, 'LATENCY', 'LATEST')
print('\n== 七:阈值决定记不记录:latency-monitor-threshold = 0 表示关闭;调到 100 ms,再制造 50 ms 的慢命令就不会被记录')
c.do('CONFIG', 'SET', 'latency-monitor-threshold', 100); c.do('DEBUG', 'SLEEP', 0.05); print('  阈值 100 ms,DEBUG SLEEP 0.05 之后 LATENCY LATEST =', c.do('LATENCY', 'LATEST'))
c.do('DEBUG', 'SLEEP', 0.15); print('  再 DEBUG SLEEP 0.15 之后 LATENCY LATEST =', [(x[0], x[2]) for x in c.do('LATENCY', 'LATEST')])
save('r97', R); cleanup([n])
