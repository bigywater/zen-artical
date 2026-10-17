import sys, os, time, json, re, threading, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z16'); R = {}
n = Node('z16', 7300).start(); z = client('127.0.0.1:7300'); w = client('127.0.0.1:7300')
print('== 一:一次性触发:另一个客户端连续写 200 次,带重新注册的 watcher 收到多少次通知?(callback 里重新 get + 重新注册)')
z.create('/hot', b'0'); notif = [0]; seen_vals = set(); lock = threading.Lock(); done = threading.Event()
def on_change(e):
    notif[0] += 1
    v, st = w.get('/hot', watch=on_change)
    seen_vals.add(int(v))
w.get('/hot', watch=on_change)
N = 200
def writer():
    for i in range(1, N + 1): z.set('/hot', str(i).encode())
t0 = time.perf_counter(); writer(); time.sleep(1.0)
final = int(w.get('/hot')[0])
print(f'  写了 {N} 次(终值 {final});收到通知 {notif[0]} 次;通过「通知后重新读取」看到的不同的值 {len(seen_vals)} 个')
print('  → 中间的变化被合并了:通知次数 < 写入次数,但最后一次读到的总是最新值(version 单调)'); R['coalesce'] = dict(writes=N, notif=notif[0], seen=len(seen_vals))
print()
print('== 二:持久 watch(3.6+,addWatch):注册一次,持续收到事件。用官方 CLI 的交互会话注册,另一个客户端修改')
z.create('/pw', b'0')
p = cli_session(7300); time.sleep(1.5)
p.stdin.write('addWatch -m PERSISTENT /pw\n'); p.stdin.flush(); time.sleep(0.8)
for i in range(3): z.set('/pw', f'v{i}'.encode()); time.sleep(0.2)
z.create('/pw/child', b''); time.sleep(0.4)
p.stdin.write('quit\n'); p.stdin.flush(); out_ = p.communicate(timeout=20)[0]
evs = [l.strip() for l in out_.splitlines() if l.startswith('WatchedEvent')]
print('  PERSISTENT 模式:3 次 set + 1 次 create 子节点 之后,CLI 收到的事件:'); [print('   ', l) for l in evs]; R['persistent'] = evs
z.delete('/pw/child'); z.delete('/pw')
print()
print('== 三:PERSISTENT_RECURSIVE:对整个子树')
z.create('/pr', b''); z.create('/pr/a', b'')
p = cli_session(7300); time.sleep(1.5)
p.stdin.write('addWatch -m PERSISTENT_RECURSIVE /pr\n'); p.stdin.flush(); time.sleep(0.8)
z.set('/pr/a', b'x'); z.create('/pr/a/b', b''); z.create('/pr/c', b''); z.delete('/pr/c'); time.sleep(0.5)
p.stdin.write('quit\n'); p.stdin.flush(); out_ = p.communicate(timeout=20)[0]
evs = [l.strip() for l in out_.splitlines() if l.startswith('WatchedEvent')]
print('  对 /pr 的递归持久 watch,收到:'); [print('   ', l) for l in evs]; R['recursive'] = evs
z.stop(); w.stop(); n.stop(); save('z16', R)
