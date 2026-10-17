import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r49'); R = {}
n = Node(7149, conf={'client-output-buffer-limit': ['pubsub 100kb 50kb 5']}).start(); c = n.c()

def sub(port, chan='ch'):
    s = C(port, timeout=5); s.do('SUBSCRIBE', chan); return s

print('== 一:没有订阅者时发布:PUBLISH 返回收到的订阅者数,消息不保存')
sh(c, 'PUBLISH', 'ch', 'm0')
s = sub(7149)
sh(c, 'PUBLISH', 'ch', 'm1')
print('订阅者收到:', s.read())
s.close(); time.sleep(0.2)
print('订阅者断开后再发布:'); sh(c, 'PUBLISH', 'ch', 'm2')
s = sub(7149); print('重新订阅:'); print('0.3 秒内收到:', s.read() if s.avail(0.3) else '什么都没有(m2 不会补发)'); s.close()
print()
print('== 二:订阅者掉线期间的窗口:每 10 ms 发一条,订阅者在第 100 条后断开 0.5 秒再重连')
c.do('DEL', 'seq')
recv = []; stop = threading.Event()
def reader():
    s = sub(7149, 'ch2')
    while not stop.is_set() and len(recv) < 100:
        if s.avail(0.05): recv.append(int(s.read()[2]))
    s.close(); time.sleep(0.5)
    s = sub(7149, 'ch2')
    while not stop.is_set():
        if s.avail(0.05): recv.append(int(s.read()[2]))
th = threading.Thread(target=reader); th.start(); time.sleep(0.2)
pc = n.c()
for i in range(1, 301):
    pc.do('PUBLISH', 'ch2', i); time.sleep(0.01)
time.sleep(0.3); stop.set(); th.join()
missing = sorted(set(range(1, 301)) - set(recv))
print(f'发布 300 条;订阅者收到 {len(recv)} 条;缺失 {len(missing)} 条,区间 {missing[0]}–{missing[-1]}(连续: {missing == list(range(missing[0], missing[-1]+1))})')
R['gap'] = dict(sent=300, got=len(recv), miss=len(missing), lo=missing[0], hi=missing[-1])
print()
print('== 三:订阅者太慢:输出缓冲区超过 client-output-buffer-limit pubsub 100kb 50kb 5 会被服务器断开')
slow = sub(7149, 'big'); slow.s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
pl = n.c()
payload = 'x' * 1000
st0 = info(pl, 'stats')['client_output_buffer_limit_disconnections']
sent = 0
for i in range(3000):
    r = pl.do('PUBLISH', 'big', payload); sent += 1
    if r == 0: break
print(f'发了 {sent} 条 1000 字节的消息;最后一次 PUBLISH 返回的订阅者数 = {r}')
time.sleep(0.3)
print('PUBSUB NUMSUB big:', pl.do('PUBSUB', 'NUMSUB', 'big'))
st1 = info(pl, 'stats')['client_output_buffer_limit_disconnections']
print(f'INFO stats client_output_buffer_limit_disconnections: {st0} → {st1}')
import re
print('服务器日志(节选):')
for l in n.log().splitlines():
    if 'output buffer' in l.lower():
        f = {k: (re.search(k + r'=(\S+)', l).group(1) if re.search(k + r'=(\S+)', l) else '?') for k in ('id', 'age', 'omem', 'tot-mem', 'cmd')}
        print('  ' + ' '.join(f'{k}={v}' for k, v in f.items()) + ' … scheduled to be closed ASAP for overcoming of output buffer limits.')
R['slow'] = dict(sent=sent, before=int(st0), after=int(st1))
print()
print('== 四:服务器重启:订阅关系和消息都不会保留')
s = sub(7149, 'ch3'); n.stop(); n.start(rewrite=False); c = n.c()
sh(c, 'PUBSUB', 'NUMSUB', 'ch3'); sh(c, 'PUBLISH', 'ch3', 'x')
try: s.s.settimeout(1); print('原订阅连接读到:', s.read())
except Exception as e: print('原订阅连接:', type(e).__name__, e)
save('r49', R); cleanup([n])
