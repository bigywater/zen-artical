import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r99'); R = {}
n = Node(8020, name='r99', conf={'latency-tracking': 'yes'}).start(); c = n.c()
c.do('CONFIG', 'RESETSTAT')
print('== 一:执行一组已知次数的命令,再看 INFO commandstats(calls 应该精确)')
for i in range(1000): c.do('SET', f'k{i}', i)
for i in range(3000): c.do('GET', f'k{i % 1000}')
for i in range(500): c.do('INCR', 'cnt')
for i in range(20): c.do('KEYS', 'k1*')
for i in range(10): c.do('HGET', 'k1', 'f', raise_err=False)          # WRONGTYPE:失败
for i in range(5): c.do('EVAL', 'return 1', 0)
cs = info(c, 'commandstats')
for k in ('cmdstat_set', 'cmdstat_get', 'cmdstat_incr', 'cmdstat_keys', 'cmdstat_hget', 'cmdstat_eval'): print(f'  {k:<14} {cs.get(k)}')
R['cs'] = {k: cs.get(k) for k in ('cmdstat_set', 'cmdstat_get', 'cmdstat_incr', 'cmdstat_keys', 'cmdstat_hget', 'cmdstat_eval')}
print()
print('== 二:字段含义:calls 次数,usec 累计微秒,usec_per_call 平均,rejected_calls 被拒绝(参数错误/无权限等)的次数,failed_calls 执行失败的次数')
for _ in range(7): c.do('GET', raise_err=False)          # 参数个数错误
for _ in range(3): c.do('SET', 'k', raise_err=False)
cs = info(c, 'commandstats')
print('  ', 'cmdstat_get:', cs['cmdstat_get']); print('  ', 'cmdstat_set:', cs['cmdstat_set']); print('  ', 'cmdstat_hget:', cs['cmdstat_hget'])
print()
print('== 三:LATENCY 直方图(Redis 7 起):INFO latencystats 每个命令的 p50 / p99 / p99.9 分位数(微秒)')
ls = info(c, 'latencystats')
for k in ('latency_percentiles_usec_set', 'latency_percentiles_usec_get', 'latency_percentiles_usec_keys'): print(f'  {k}: {ls.get(k)}')
R['ls'] = {k: ls.get(k) for k in ('latency_percentiles_usec_set', 'latency_percentiles_usec_get', 'latency_percentiles_usec_keys')}
print()
print('== 四:usec_per_call 不含网络与排队:KEYS 的平均耗时远大于 GET;并且和客户端测到的往返不同')
def rt(cmd, k=300):
    t = time.perf_counter()
    for _ in range(k): c.do(*cmd)
    return (time.perf_counter() - t) / k * 1e6
g, kk = rt(['GET', 'k1']), rt(['KEYS', 'k1*'], 100)
cs = info(c, 'commandstats')
def upc(name): return float(re.search(r'usec_per_call=([\d.]+)', cs[f'cmdstat_{name}']).group(1))
print(f'  客户端测得往返:GET {g:.1f} µs,KEYS {kk:.1f} µs;服务器统计的 usec_per_call:GET {upc("get"):.2f},KEYS {upc("keys"):.2f}')
R['rt'] = dict(get=g, keys=kk, upc_get=upc('get'), upc_keys=upc('keys'))
print()
print('== 五:CONFIG RESETSTAT 清零')
sh(c, 'CONFIG', 'RESETSTAT'); print('  之后 cmdstat_set:', info(c, 'commandstats').get('cmdstat_set'), ' cmdstat_config|resetstat:', info(c, 'commandstats').get('cmdstat_config|resetstat'))
save('r99', R); cleanup([n])
