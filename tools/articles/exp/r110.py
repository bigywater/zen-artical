import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r110'); R = {}
n = Node(8180, name='r110', conf={'notify-keyspace-events': 'Ex'}).start(); c = n.c()
print('== 一:默认值与 INFO 里的 hz / configured_hz')
sh(c, 'CONFIG', 'GET', 'hz'); sh(c, 'CONFIG', 'GET', 'dynamic-hz')
i = info(c, 'server'); print('  INFO server: hz =', i['hz'], ' configured_hz =', i['configured_hz'])
print()
print('== 二:hz 决定后台任务(过期扫描等)每秒跑几次:同样的 PX 300 key,量 expired 事件比 300 ms 晚多少(空闲实例,20 次,中位 / 最大)')
print(f'{"hz":>5} {"事件延迟 中位 ms":>16} {"最大 ms":>9}')
R['exp'] = {}
for hz in (1, 10, 100):
    c.do('CONFIG', 'SET', 'hz', hz); time.sleep(1.2)
    s = C(8180); s.do('SUBSCRIBE', '__keyevent@0__:expired'); D = []
    for k in range(20):
        t0 = time.perf_counter(); c.do('SET', f'e{hz}:{k}', 'v', 'PX', 300)
        while not s.avail(0.005): pass
        s.read(); D.append((time.perf_counter() - t0) * 1000 - 300)
    s.close(); R['exp'][hz] = (statistics.median(D), max(D)); print(f'{hz:>5} {statistics.median(D):>16.1f} {max(D):>9.1f}')
c.do('CONFIG', 'SET', 'hz', 10)
print()
print('== 三:空闲实例的 CPU:INFO 里 used_cpu_sys + used_cpu_user 在 10 秒内的增量(秒),每个 hz 一个新实例')
print(f'{"hz":>5} {"10 秒内 CPU 秒":>14} {"折合每秒 ms":>12}')
R['cpu'] = {}
for hz in (10, 100, 500):
    m = Node(8191, name=f'r110c{hz}', conf={'hz': hz, 'dynamic-hz': 'no'}).start(); mc = m.c(); time.sleep(1)
    def cpu(): i = info(mc, 'cpu'); return float(i['used_cpu_sys']) + float(i['used_cpu_user'])
    a = cpu(); time.sleep(10); b = cpu(); R['cpu'][hz] = b - a; print(f'{hz:>5} {b-a:>14.3f} {(b-a)/10*1000:>12.2f}')
    cleanup([m]); time.sleep(0.5)
print()
print('== 四:dynamic-hz yes:连接的客户端很多时,实际 hz 自动升高(configured_hz 不变)')
d = Node(8192, name='r110d', conf={'hz': 10, 'dynamic-hz': 'yes'}).start(); dc = d.c(); socks = []
print(f'{"已连接客户端":>10} {"hz":>5} {"configured_hz":>14}')
R['dyn'] = []
for target in (1, 100, 500, 2000, 4000):
    while len(socks) < target - 1: socks.append(socket.create_connection(('127.0.0.1', 8192)))
    time.sleep(1.5); i = info(dc, 'server'); cl = info(dc, 'clients')['connected_clients']
    print(f'{cl:>10} {i["hz"]:>5} {i["configured_hz"]:>14}'); R['dyn'].append((int(cl), int(i['hz']), int(i['configured_hz'])))
for s in socks: s.close()
save('r110', R); cleanup([n, d])
