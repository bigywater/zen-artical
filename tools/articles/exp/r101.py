import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r101'); R = {}
n = Node(8040, name='r101', conf={'enable-debug-command': 'yes'}).start(); c = n.c()
def run_cli(args, secs, inject=None):
    p = subprocess.Popen(['redis-cli', '-p', '8040'] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if inject: threading.Thread(target=inject).start()
    time.sleep(secs); p.send_signal(signal.SIGINT)
    try: out = p.communicate(timeout=5)[0].decode(errors='replace')
    except Exception: p.kill(); out = p.communicate()[0].decode(errors='replace')
    return out
import pty
def run_pty(args, secs, inject=None):
    m, sl = pty.openpty()
    p = subprocess.Popen(['redis-cli', '-p', '8040'] + args, stdout=sl, stderr=sl, close_fds=True); os.close(sl)
    if inject: threading.Thread(target=inject).start()
    buf = b''; t0 = time.time()
    while time.time() - t0 < secs:
        r, _, _ = select.select([m], [], [], 0.2)
        if r:
            try: buf += os.read(m, 65536)
            except OSError: break
    p.send_signal(signal.SIGINT)
    try: p.wait(3)
    except Exception: p.kill()
    return buf.decode(errors='replace')
def last(out): 
    s = [x for x in re.split(r'[\r\n]+', out) if 'min:' in x]; return s[-1].strip() if s else out[-200:]
print('== 一:redis-cli --latency:每秒发很多 PING,打印 min / max / avg / 次数;空闲实例,运行 4 秒')
o = run_cli(['--latency'], 4); print('  最后一行:', last(o)); R['idle'] = last(o)
print()
print('== 二:同样的命令,但期间制造 3 次 200 ms 的阻塞(DEBUG SLEEP 0.2):max 会捕获它们,avg 几乎不动')
def inj():
    time.sleep(1.0)
    for _ in range(3): n.c().do('DEBUG', 'SLEEP', 0.2); time.sleep(0.6)
o = run_cli(['--latency'], 5, inj); print('  最后一行:', last(o)); R['spike'] = last(o)
print()
print('== 三:--latency-history:每 15 秒一行的历史(这里用 -i 1 每 1 秒一行,运行 5 秒)')
def inj2():
    time.sleep(2.0); n.c().do('DEBUG', 'SLEEP', 0.15)
o = run_pty(['--latency-history', '-i', '1'], 6.5, inj2)
clean = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '\n', o)
segs = [x.strip() for x in clean.splitlines() if 'min:' in x]
rows = []; cur = None
for sgm in segs:
    m_ = re.search(r'\((\d+) samples\)', sgm); k = int(m_.group(1))
    if cur is not None and k == 1: rows.append(cur)
    cur = sgm
if cur: rows.append(cur)
lines = rows
for i_, l in enumerate(lines[:6]): print(f'  窗口 {i_+1}(每个窗口结束时的一行): {l}')
R['history'] = lines[:6]
print()
print('== 四:--latency-dist:延迟分布(每种颜色块表示一个区间;文本模式只看区间与计数)—— 运行 3 秒,输出的最后一屏')
o = run_pty(['--latency-dist', '-i', '1'], 3.5); txt = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', o); L = [x for x in txt.splitlines() if x.strip()]
for l in L[-8:]: print('  ', l[:120])
print()
print('== 五:--intrinsic-latency 3:测「这台机器本身」不做任何 Redis 工作时的最大调度延迟(不连接服务器)')
t = time.perf_counter(); r = subprocess.run(['redis-cli', '--intrinsic-latency', '3'], capture_output=True, text=True, timeout=30); txt = (r.stdout + r.stderr)
L = [x.strip() for x in re.split(r'[\r\n]+', txt) if x.strip()]; print('  ', L[-2] if len(L) > 1 else L); print('  ', L[-1]); R['intrinsic'] = L[-2:]
save('r101', R); cleanup([n])
