import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r100'); R = {}
def bench(port, n=200000, batch=2000):
    c = C(port); t = time.perf_counter()
    for i in range(0, n, batch): c.pipeline([['SET', f'k{i+j}', 'x' * 20] for j in range(batch)])
    return n / (time.perf_counter() - t)
print('== 一:MONITOR 对吞吐的影响(管道 SET 20 万条,每种 3 次取中位)')
n = Node(8030, name='r100').start()
base = statistics.median(bench(8030) for _ in range(3))
print(f'  没有 MONITOR:{base/1000:.0f}k 条/秒')
# 一个及时读取的 MONITOR 客户端
mon = subprocess.Popen(['redis-cli', '-p', '8030', 'monitor'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
def drain(): 
    while mon.stdout.read(1 << 16): pass
th = threading.Thread(target=drain, daemon=True); th.start(); time.sleep(0.5)
withm = statistics.median(bench(8030) for _ in range(3))
print(f'  有一个及时读取的 MONITOR 客户端:{withm/1000:.0f}k 条/秒(降低 {(1-withm/base)*100:.0f}%)')
mon.kill(); mon.wait(); time.sleep(0.3)
R['tp'] = dict(base=base, mon=withm)
print()
print('== 二:MONITOR 客户端不读取(卡住)时,服务器为它缓冲的输出会涨到多大:normal 客户端的输出缓冲默认没有上限')
print('  CONFIG GET client-output-buffer-limit →', n.c().do('CONFIG', 'GET', 'client-output-buffer-limit')[1])
s = socket.create_connection(('127.0.0.1', 8030)); s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096); s.sendall(C.enc(['MONITOR']))
time.sleep(0.3); c = n.c(); m0 = int(info(c, 'memory')['used_memory'])
rows = []
for k in range(1, 6):
    bench(8030, 200000)
    i_ = info(c, 'memory'); cl = [l for l in c.do('CLIENT', 'LIST').splitlines() if 'cmd=monitor' in l]
    om = int(re.search(r'omem=(\d+)', cl[0]).group(1)) if cl else 0
    rows.append((k * 200000, int(i_['used_memory']) - m0, om)); print(f'  已执行 {k*200000:>8} 条命令:used_memory 比开始时多 {(int(i_["used_memory"])-m0)/1e6:6.1f} MB,该 MONITOR 连接的 omem = {om/1e6:6.1f} MB')
R['omem'] = rows
s.close(); time.sleep(0.5)
print(f'  关闭这个连接后 used_memory 比开始多 {(int(info(c, "memory")["used_memory"])-m0)/1e6:.1f} MB')
print()
print('== 三:MONITOR 看到什么(每条命令一行:时间戳 [库 客户端地址] "命令" 参数…)')
mon = subprocess.Popen(['redis-cli', '-p', '8030', 'monitor'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True); time.sleep(0.5)
c = n.c(); c.do('SET', 'hello', 'world'); c.do('GET', 'hello'); c.do('AUTH', 'x', 'secretpw', raise_err=False); c.do('EVAL', "return redis.call('INCR','n')", 0); time.sleep(0.5)
mon.terminate(); out_ = mon.stdout.read().splitlines()
for l in out_[:8]: print('  ', l[:150])
R['sample'] = out_[:8]
save('r100', R); cleanup([n])
