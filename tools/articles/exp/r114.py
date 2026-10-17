import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct, resource; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r114'); R = {}
print('== 一:默认值:maxclients、进程的文件描述符上限(ulimit -n)')
n = Node(8230, name='r114').start(); c = n.c()
sh(c, 'CONFIG', 'GET', 'maxclients')
i = info(c, 'clients'); print('  INFO clients: maxclients =', i.get('maxclients'), ' connected_clients =', i['connected_clients'])
print('  当前 shell 的 ulimit -n =', resource.getrlimit(resource.RLIMIT_NOFILE))
print('  redis 日志里关于 maxclients / 文件描述符的行:', [l.split('# ',1)[-1].split('* ',1)[-1][:170] for l in n.log().splitlines() if 'maxclients' in l.lower() or 'file descriptor' in l.lower() or 'open files' in l.lower()][:3])
cleanup([n]); time.sleep(0.5)
print()
print('== 二:maxclients 设成 100:第 101 个之后的连接会怎样')
n = Node(8230, name='r114b', conf={'maxclients': 100}).start(); c = n.c(); socks = []; rej = []
for k in range(120):
    try:
        s = socket.create_connection(('127.0.0.1', 8230), timeout=2); s.sendall(C.enc(['PING'])); s.settimeout(1); r = s.recv(100)
        if r.startswith(b'-'): rej.append((k + 1, r[:60])); s.close()
        else: socks.append(s)
    except Exception as e: rej.append((k + 1, type(e).__name__))
print(f'  尝试 120 个连接:成功 {len(socks) + 1}(含最初那个 c),被拒 {len(rej)};第一个被拒的是第 {rej[0][0] if rej else "-"} 个:{rej[0][1] if rej else ""}')
socks.pop().close(); time.sleep(0.3); c.close()
try: st = info(C(8230), 'stats'); print('  INFO stats rejected_connections =', st['rejected_connections'], ' total_connections_received =', st['total_connections_received'])
except Exception as e: print('  (INFO 也连不上了:', type(e).__name__, ')')
R['max'] = dict(ok=len(socks), rej=len(rej), first=rej[0][0] if rej else None, msg=str(rej[0][1]) if rej else '')
for s in socks: s.close()
cleanup([n]); time.sleep(0.5)
print()
print('== 三:timeout 2:空闲 2 秒的连接被服务器关闭')
n = Node(8230, name='r114c', conf={'timeout': 2}).start(); c = n.c()
s = socket.create_connection(('127.0.0.1', 8230)); s.sendall(C.enc(['PING'])); s.recv(100); t0 = time.perf_counter(); s.settimeout(10)
try: d = s.recv(10); gone = time.perf_counter() - t0
except Exception as e: d = None; gone = None
print(f'  空闲连接被关闭用了 {gone:.1f} 秒(对端读到 {d!r},即 EOF)' if gone else '  10 秒内没被关闭')
R['timeout'] = gone
c2 = n.c(); print('  统计:', info(c2, 'stats')['total_connections_received'], '个连接被接受过;connected_clients =', info(c2, 'clients')['connected_clients'])
cleanup([n]); time.sleep(0.5)
print()
print('== 四:每个连接占多少内存,以及文件描述符怎么算:开 1000 个空闲连接')
n = Node(8230, name='r114d').start(); c = n.c()
m0 = int(info(c, 'memory')['used_memory']); socks = [socket.create_connection(('127.0.0.1', 8230)) for _ in range(1000)]
for s in socks: s.sendall(C.enc(['PING']))
time.sleep(1); m1 = int(info(c, 'memory')['used_memory']); k = info(c, 'clients')
lsof = subprocess.run(['lsof', '-p', str(n.p.pid)], capture_output=True, text=True).stdout.splitlines()
print(f'  1000 个连接:connected_clients = {k["connected_clients"]},used_memory +{(m1-m0)/1e6:.1f} MB(每个连接约 {(m1-m0)/1000/1024:.1f} KB),Redis 进程打开的文件描述符 {len(lsof)-1} 个(lsof 行数)')
R['conn'] = dict(per=(m1 - m0) / 1000, fds=len(lsof) - 1)
for s in socks: s.close()
save('r114', R); cleanup([n])
