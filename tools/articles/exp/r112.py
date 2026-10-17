import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r112'); R = {}
n = Node(8210, name='r112').start(); c = n.c()
def cl(name_flag=None):
    return [l for l in c.do('CLIENT', 'LIST').splitlines()]
def fields(l):
    return {kv_.split('=', 1)[0]: kv_.split('=', 1)[1] for kv_ in l.split() if '=' in kv_}
print('== 一:CLIENT LIST 里和缓冲区相关的字段(一个空闲连接)')
s = socket.create_connection(('127.0.0.1', 8210)); s.sendall(C.enc(['PING'])); s.recv(100); time.sleep(0.2)
me = [fields(l) for l in cl() if 'cmd=ping' in l][0]
for k in ('qbuf', 'qbuf-free', 'argv-mem', 'multi-mem', 'obl', 'oll', 'omem', 'tot-mem', 'rbs', 'rbp', 'tot-net-in', 'tot-net-out'): print(f'  {k:<10} {me.get(k)}')
R['idle'] = {k: me.get(k) for k in ('qbuf', 'qbuf-free', 'argv-mem', 'obl', 'oll', 'omem', 'tot-mem', 'rbs', 'rbp')}
print('  (qbuf 查询缓冲、obl 固定输出缓冲字节、oll 输出链表节点数、omem 输出缓冲总内存、rbs/rbp 读缓冲大小与峰值、tot-mem 整个客户端占用)')
print()
print('== 二:输出缓冲怎么涨:GET 一个 1 MB 的 value,但客户端不读')
c.do('SET', 'v1mb', 'x' * 1024 * 1024)
s2 = socket.create_connection(('127.0.0.1', 8210)); s2.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
rows = []
for k in (0, 1, 5, 20, 100):
    for _ in range(k - (rows[-1][0] if rows else 0)): s2.sendall(C.enc(['GET', 'v1mb']))
    time.sleep(0.3)
    l = [fields(x) for x in cl() if x and 'cmd=get' in x]
    f = l[0] if l else {}
    rows.append((k, int(f.get('omem', 0)), int(f.get('obl', 0)), int(f.get('oll', 0)), int(f.get('tot-mem', 0)))); print(f'  已发送 {k:>3} 个 GET(每个回复 1 MB),客户端不读:omem = {rows[-1][1]/1e6:6.1f} MB   (obl={rows[-1][2]} oll={rows[-1][3]})')
R['omem'] = rows
s2.close(); time.sleep(0.3)
print()
print('== 三:查询缓冲怎么涨:发一个大 SET 的前半部分(声明 50 MB,只发 10 MB),连接保持')
n.c().do('CONFIG', 'SET', 'proto-max-bulk-len', '100mb'); n.c().do('CONFIG', 'SET', 'client-query-buffer-limit', '1gb')
s3 = socket.create_connection(('127.0.0.1', 8210)); s3.sendall(b'*3\r\n$3\r\nSET\r\n$1\r\nk\r\n$52428800\r\n')
for i in range(10): s3.sendall(b'x' * (1024 * 1024))
time.sleep(0.5)
l = [fields(x) for x in cl() if 'qbuf=' in x and int(fields(x).get('qbuf', 0)) > 1000000]
f = l[0] if l else {}
print(f'  qbuf = {int(f.get("qbuf", 0))/1e6:.1f} MB,qbuf-free = {int(f.get("qbuf-free", 0))/1e6:.1f} MB,argv-mem = {int(f.get("argv-mem", 0))/1e6:.1f} MB,tot-mem = {int(f.get("tot-mem", 0))/1e6:.1f} MB')
R['qbuf'] = {k: int(f.get(k, 0)) for k in ('qbuf', 'qbuf-free', 'argv-mem', 'tot-mem')}
s3.close(); time.sleep(0.3)
print()
print('== 四:INFO clients / memory 里的汇总:mem_clients_normal、client_recent_max_input_buffer、client_recent_max_output_buffer')
s4 = [socket.create_connection(('127.0.0.1', 8210)) for _ in range(200)]
for x in s4: x.sendall(C.enc(['PING'])); 
time.sleep(0.5)
m = info(c, 'memory'); k = info(c, 'clients')
print(f'  200 个空闲连接:connected_clients = {k["connected_clients"]},mem_clients_normal = {int(m["mem_clients_normal"])/1e6:.2f} MB(平均每个连接 {int(m["mem_clients_normal"])/int(k["connected_clients"])/1024:.1f} KB)')
R['clients'] = dict(n=int(k['connected_clients']), mem=int(m['mem_clients_normal']))
save('r112', R); cleanup([n])
