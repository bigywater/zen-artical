import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r113'); R = {}
n = Node(8220, name='r113', conf={'client-output-buffer-limit': ['normal 10mb 5mb 3', 'replica 256mb 64mb 60', 'pubsub 32mb 8mb 60']}).start(); c = n.c()
print('== 一:默认类别与格式:CONFIG GET client-output-buffer-limit(本实验已把 normal 改成 10mb 硬限 / 5mb 软限 / 3 秒)')
print(' ', c.do('CONFIG', 'GET', 'client-output-buffer-limit')[1])
c.do('SET', 'v1mb', 'x' * 1024 * 1024)
def clients(): return [dict(kv_.split('=', 1) for kv_ in l.split() if '=' in kv_) for l in c.do('CLIENT', 'LIST').splitlines()]
def bad_reader(sndbuf=4096):
    s = socket.create_connection(('127.0.0.1', 8220)); s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, sndbuf); return s
st0 = int(info(c, 'stats')['client_output_buffer_limit_disconnections'])
print()
print('== 二:硬限制(10 MB):不读取的客户端连续发 GET(每个回复 1 MB),累计到多少时被断开')
s = bad_reader(); sent = 0; t0 = time.perf_counter(); dead = None
try:
    while sent < 200:
        s.sendall(C.enc(['GET', 'v1mb'])); sent += 1; time.sleep(0.01)
        if int(info(c, 'stats')['client_output_buffer_limit_disconnections']) > st0: dead = sent; break
except Exception as e: dead = f'{sent}({type(e).__name__})'
print(f'  发送到第 {dead} 个 GET 时被服务器断开(client_output_buffer_limit_disconnections {st0} → {info(c, "stats")["client_output_buffer_limit_disconnections"]})')
R['hard'] = dead
log = [l.split('# ', 1)[-1].split('* ', 1)[-1] for l in n.log().splitlines() if 'output buffer' in l.lower()]
print('  日志:', (log[-1][:200] if log else '(无)'))
print()
print('== 三:软限制(5 MB 且持续 3 秒):输出缓冲保持在 5–10 MB 之间,持续 3 秒以上才断开')
st1 = int(info(c, 'stats')['client_output_buffer_limit_disconnections'])
s = bad_reader(); 
for _ in range(7): s.sendall(C.enc(['GET', 'v1mb']))
t0 = time.perf_counter(); gone = None
while time.perf_counter() - t0 < 10:
    ok = [x for x in clients() if x.get('cmd') == 'get']
    if not ok: gone = time.perf_counter() - t0; break
    time.sleep(0.1)
om = None
print(f'  发 7 个 GET(约 7 MB,在 5 MB 与 10 MB 之间):{("约 %.1f 秒后被断开" % gone) if gone else "10 秒内没有被断开"}(disconnections {st1} → {info(c, "stats")["client_output_buffer_limit_disconnections"]})')
R['soft'] = gone
print()
print('== 四:「读得慢」的客户端:每 0.2 秒读 100 KB,服务器输出缓冲是否会一直涨?')
s = bad_reader(65536); 
for _ in range(3): s.sendall(C.enc(['GET', 'v1mb']))
seen = []
for i in range(6):
    time.sleep(0.2); s.settimeout(0.05)
    try: s.recv(102400)
    except Exception: pass
    f = [x for x in clients() if x.get('cmd') == 'get']; seen.append(int(f[0]['omem']) if f else -1)
print('  每 0.2 秒读一点之后的 omem(字节):', seen); R['slow'] = seen
save('r113', R); cleanup([n])
