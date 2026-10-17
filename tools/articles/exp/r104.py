import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r104'); R = {}
n = Node(8080, name='r104').start(); c0 = n.c()
c0.do('HSET', 'h', 'f1', 'v1', 'f2', 'v2'); c0.do('SADD', 's', 'a', 'b'); c0.do('ZADD', 'z', 1.5, 'm'); c0.do('SET', 'str', 'hello')
def raw(sock, *args, t=0.3):
    sock.sendall(C.enc(args)); time.sleep(0.05); sock.settimeout(t); out = b''
    try:
        while True:
            d = sock.recv(65536)
            if not d: break
            out += d
            if len(d) < 65536: break
    except socket.timeout: pass
    return out
show = lambda b: b.decode('utf-8', 'replace').replace('\r\n', '⏎')
print('== 一:同样的命令,RESP2(默认)与 RESP3(HELLO 3)返回的原始字节')
s2 = socket.create_connection(('127.0.0.1', 8080)); s3 = socket.create_connection(('127.0.0.1', 8080))
h = raw(s3, 'HELLO', '3'); 
print('  HELLO 3 的回复(前 160 字节):', show(h)[:160])
rows = []
for cmd in (('HGETALL', 'h'), ('SMEMBERS', 's'), ('ZSCORE', 'z', 'm'), ('GET', 'nosuch'), ('ZRANGE', 'z', 0, -1, 'WITHSCORES'), ('HELLO',)):
    if cmd == ('HELLO',): continue
    a, b = raw(s2, *cmd), raw(s3, *cmd)
    print(f'  {" ".join(map(str, cmd)):<26} RESP2: {show(a):<46}  RESP3: {show(b)}')
    rows.append((' '.join(map(str, cmd)), show(a), show(b)))
R['rows'] = rows
print()
print('== 二:各类型前缀字节(RESP3 新增):% map、~ set、, double、_ null、# boolean、= verbatim string、> push、( big number')
for cmd in (('INFO', 'server'),):
    b = raw(s3, *cmd); print('  INFO 在 RESP3 下的首字节:', repr(b[:12]), '(= 表示 verbatim string,带 "txt:" 格式标记)')
    R['info3'] = repr(b[:14])
print()
print('== 三:大回复的字节数对比(100 个字段的 HGETALL)')
for i in range(100): c0.do('HSET', 'big', f'field{i}', f'value{i}')
a, b = raw(s2, 'HGETALL', 'big', t=1), raw(s3, 'HGETALL', 'big', t=1)
print(f'  RESP2 {len(a)} 字节;RESP3 {len(b)} 字节;差 {len(a)-len(b)} 字节(RESP3 用一个 %100 头代替 *200 头;元素本身的编码相同)')
R['size'] = (len(a), len(b))
print()
print('== 四:RESP3 的 Push:客户端缓存追踪(CLIENT TRACKING on)时,key 被改动服务器主动推送失效消息(带 > 前缀,不用等命令回复)')
raw(s3, 'CLIENT', 'TRACKING', 'on'); raw(s3, 'GET', 'str')
c0.do('SET', 'str', 'changed'); time.sleep(0.1); s3.settimeout(0.5); p = s3.recv(4096)
print('  另一个连接改了 str 之后,这个连接收到:', show(p)); R['push'] = show(p)
print()
print('== 五:同一个连接里,HELLO 2 可以切回 RESP2')
b = raw(s3, 'HELLO', '2'); print('  HELLO 2 回复的第一段:', show(b)[:60])
r = raw(s3, 'HGETALL', 'h'); print('  之后 HGETALL h:', show(r))
R['back'] = show(r)
save('r104', R); cleanup([n])
