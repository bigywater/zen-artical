import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r105'); R = {}
n = Node(8090, name='r105', conf={'proto-max-bulk-len': '1mb', 'client-query-buffer-limit': '2mb'}).start()
def talk(payload, t=0.4, close_expect=False):
    s = socket.create_connection(('127.0.0.1', 8090)); s.sendall(payload); time.sleep(0.05); s.settimeout(t); out = b''
    try:
        while True:
            d = s.recv(65536)
            if not d: out += '<对端关闭连接>'.encode(); break
            out += d
    except socket.timeout: pass
    s.close(); return out.decode('utf-8', 'replace').replace('\r\n', '⏎')
def line(name, payload):
    o = talk(payload); print(f'  {name:<34} 发送: {payload[:60]!r:<68} 收到: {o[:120]}'); R.setdefault('rows', []).append((name, repr(payload[:60]), o[:120]))
print('== 一:两种请求格式:multibulk(标准)与 inline(telnet 风格)')
line('multibulk PING', b'*1\r\n$4\r\nPING\r\n')
line('inline PING', b'PING\r\n')
line('inline SET / GET(引号)', b'SET k "hello world"\r\nGET k\r\n')
print()
print('== 二:协议错误:服务器回错误并关闭连接')
line('multibulk 长度不是数字', b'*abc\r\n')
line('multibulk 长度为负', b'*-5\r\n')
line('bulk 长度不是数字', b'*1\r\n$x\r\nfoo\r\n')
line('multibulk 元素前缀不是 $', b'*1\r\n:3\r\nfoo\r\n')
line('bulk 长度超过 proto-max-bulk-len', b'*2\r\n$3\r\nSET\r\n$2000000\r\n')
line('bulk 长度声明 10 实际 3 + 结尾错', b'*1\r\n$10\r\nabc\r\n')
line('multibulk 元素数超过 1024*1024', b'*2000000\r\n')
line('inline 引号未闭合', b'SET k "abc\r\n')
print()
print('== 三:不完整的请求:服务器等待剩余部分,不会回复也不会报错;补全后才执行')
s = socket.create_connection(('127.0.0.1', 8090)); s.sendall(b'*3\r\n$3\r\nSET\r\n$1\r\nk\r\n$5\r\nhe'); time.sleep(0.5); s.settimeout(0.3)
try: r0 = s.recv(100)
except socket.timeout: r0 = '(0.5 秒内没有任何回复)'
s.sendall(b'llo\r\n'); time.sleep(0.1); s.settimeout(1); r1 = s.recv(100)
print('  发送到 "he" 就停:', r0, ' → 补上 "llo\\r\\n" 之后:', r1); R['partial'] = (repr(r0), repr(r1)); s.close()
print()
print('== 四:client-query-buffer-limit(这里设成 2 MB,proto-max-bulk-len 临时放宽到 100 MB):一个 5 MB 的 bulk 还没收完,查询缓冲就超限 → 服务器关闭连接')
n.c().do('CONFIG', 'SET', 'proto-max-bulk-len', '100mb')
s = socket.create_connection(('127.0.0.1', 8090)); s.sendall(b'*3\r\n$3\r\nSET\r\n$1\r\nk\r\n$5000000\r\n')
sent = 0
try:
    while sent < 5_000_000:
        s.sendall(b'x' * 100000); sent += 100000
    res = f'发送了 {sent} 字节,连接仍在'
except Exception as e: res = f'发送 {sent} 字节后:{type(e).__name__}'
try:
    s.settimeout(0.5); d = s.recv(200); res += f';服务器回:{d[:100]!r}'
except Exception as e: res += f';读:{type(e).__name__}'
n.c().do('CONFIG', 'SET', 'proto-max-bulk-len', '1mb')
print(' ', res); R['qbuf'] = res; s.close()
print('  服务器日志里的相关行:', [l.split('# ',1)[-1].split('* ',1)[-1][:170] for l in n.log().splitlines() if 'query buffer' in l.lower() or 'closing' in l.lower()][:3])
print()
print('== 五:解析大 bulk 的速度:一条 SET 带 N MB 的 value(本机),客户端一次发出')
n.c().do('CONFIG', 'SET', 'proto-max-bulk-len', '600mb'); n.c().do('CONFIG', 'SET', 'client-query-buffer-limit', '1gb')
for mb in (1, 10, 100, 500):
    c = n.c(); v = 'x' * (mb * 1024 * 1024); t = time.perf_counter(); c.do('SET', 'big', v); dt = (time.perf_counter() - t) * 1000; c.close()
    print(f'  {mb:>4} MB:SET 往返 {dt:.0f} ms({mb/dt*1000:.0f} MB/s)'); R.setdefault('big', []).append((mb, dt))
save('r105', R); cleanup([n])
