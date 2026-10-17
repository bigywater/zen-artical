import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z13'); R = {}
n = Node('z13', 7300, conf={'tickTime': 1000}).start()
def mk(timeout=6):
    z = client('127.0.0.1:7300', timeout=timeout); st = []; t0 = [time.perf_counter()]
    z.add_listener(lambda s: st.append((round((time.perf_counter() - t0[0]) * 1000), str(s)))); return z, st, t0
print('== 一:服务端被暂停(SIGSTOP)2 秒,小于会话超时 6 秒:客户端怎么变化')
z, st, t0 = mk(); z.create('/eph1', b'', ephemeral=True); sid = z.client_id[0]; w = client('127.0.0.1:7300')
t0[0] = time.perf_counter(); n.pause(); time.sleep(2); n.resume(); time.sleep(3)
print('  状态变化:', st); print('  同一个会话:', z.client_id[0] == sid, '| 临时节点还在:', w.exists('/eph1') is not None); R['short'] = dict(states=st, same=z.client_id[0] == sid)
print()
print('== 二:暂停 9 秒,大于会话超时:恢复后会话过期')
z.stop(); z.close(); z, st, t0 = mk(); z.create('/eph2', b'', ephemeral=True); sid = z.client_id[0]; ev = []
w.exists('/eph2', watch=lambda e: ev.append((e.type, e.path)))
t0[0] = time.perf_counter(); n.pause(); time.sleep(9); n.resume(); time.sleep(4)
print('  状态变化:', st); print(f'  原会话 id {sid:#x} → 现在 {z.client_id[0]:#x};临时节点 /eph2 还在:', w.exists('/eph2') is not None)
R['long'] = dict(states=st, new_sid=z.client_id[0] != sid, ev=[(str(a), b) for a, b in ev])
print()
print('== 三:客户端自己被冻结(SIGSTOP 客户端进程)超过会话超时:服务端先把会话过期')
import subprocess
code = "import sys, time; sys.path.insert(0, '.')\nfrom zkl import client\nz = client('127.0.0.1:7300', timeout=6); z.create('/eph3', b'', ephemeral=True); print(z.client_id[0], flush=True); time.sleep(300)\n"
p = subprocess.Popen([sys.executable, '-c', code], cwd=HERE, stdout=subprocess.PIPE, text=True); p.stdout.readline(); time.sleep(0.5)
print('  客户端进程冻结前 /eph3 存在:', w.exists('/eph3') is not None); t1 = time.perf_counter(); p.send_signal(__import__('signal').SIGSTOP)
while w.exists('/eph3') and time.perf_counter() - t1 < 20: time.sleep(0.05)
gone = (time.perf_counter() - t1) * 1000; print(f'  冻结客户端后 /eph3 在 {gone:.0f} ms 后被服务端删除(会话超时 6000 ms)'); R['frozen_ms'] = gone
p.kill()
z.stop(); w.stop(); n.stop(); save('z13', R)
