import sys, os, time, json, re, subprocess, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z93'); R = {}
n = Node('z93', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start()
CUR = HERE.parent / 'curator'; CP = f'{CUR}/lib/*:{CUR}'; J_ = ['java', '-Dfile.encoding=UTF-8', '-Dstdout.encoding=UTF-8', '-cp', CP]
r = subprocess.run(J_ + ['Z93'], capture_output=True, text=True, timeout=200); out_ = r.stdout.rstrip(); print(out_)
if r.returncode: print('EXIT', r.returncode, r.stderr[-800:])
R['stdout'] = out_
print()
print('== 五:持有者所在的 JVM 被冻结(SIGSTOP,模拟长时间 GC)超过会话超时(3 s)')
lh = ZDATA / 'z93' / 'h.log'; lh.parent.mkdir(exist_ok=True); lw = ZDATA / 'z93' / 'w.log'
hp = subprocess.Popen(J_ + ['Holder', '7300', '12000'], stdout=open(lh, 'w'), stderr=subprocess.DEVNULL)
t0 = time.time()
while 'ACQUIRED' not in lh.read_text() and time.time() - t0 < 20: time.sleep(0.05)
t_stop = time.time(); hp.send_signal(signal.SIGSTOP)
wp = subprocess.Popen(J_ + ['Waiter', '7300'], stdout=open(lw, 'w'), stderr=subprocess.DEVNULL)
while 'WAITER_ACQUIRED' not in lw.read_text() and time.time() - t_stop < 20: time.sleep(0.05)
t_w = time.time() - t_stop
print(f'  持有者被冻结 {t_w:.1f} s 后,另一个进程 Waiter 拿到了同一把锁(会话超时 3 s)')
R['waiter_s'] = t_w
time.sleep(3); hp.send_signal(signal.SIGCONT); hp.wait(30)
L = lh.read_text().strip().splitlines(); print('  持有者解冻后的日志:'); [print('    ' + re.sub(r'^\d+ ', '', l)) for l in L]
R['holder_log'] = [re.sub(r'^\d+ ', '', l) for l in L]
n.stop(); save('z93', R); os._exit(0)
