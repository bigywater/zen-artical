import sys, os, time, json, re, subprocess, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z95'); R = {}
n = Node('z95', 7300, xmx=512, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start()
CUR = HERE.parent / 'curator'; CP = f'{CUR}/lib/*:{CUR}'; J_ = ['java', '-Dfile.encoding=UTF-8', '-Dstdout.encoding=UTF-8', '-cp', CP]
r = subprocess.run(J_ + ['Z95'], capture_output=True, text=True, timeout=200); out_ = r.stdout.rstrip(); print(out_)
if r.returncode: print('EXIT', r.returncode, r.stderr[-800:])
R['stdout'] = out_
print()
print('== 三:缓存客户端与服务端之间的连接被切断 6 秒(会话超时 3 s),期间 ZooKeeper 里的值被改了:缓存返回什么、什么时候追上')
z = client('127.0.0.1:7300'); z.create('/cfg', b'v1'); px = Proxy(7310, 7300).start()
lf = ZDATA / 'z95' / 'p.log'; lf.parent.mkdir(exist_ok=True)
pp = subprocess.Popen(J_ + ['CacheProbe', '7310'], stdout=open(lf, 'w'), stderr=subprocess.DEVNULL)
def ev(): return [(int(l.split(' ', 2)[0]) / 1000, l.split(' ', 1)[1]) for l in lf.read_text().splitlines() if l.strip()]
t0 = time.time()
while not any('VAL v1' in x[1] for x in ev()) and time.time() - t0 < 20: time.sleep(0.05)
time.sleep(0.5); tb = time.time(); px.block(); time.sleep(0.3); z.set('/cfg', b'v2'); tu = time.time(); time.sleep(5.7); t_un = time.time(); px.unblock()
while not any('VAL v2' in x[1] for x in ev()) and time.time() - t_un < 30: time.sleep(0.05)
time.sleep(0.5)
rows = [(t - tb, m) for t, m in ev() if t >= tb - 0.1]
print(f'  切断(代理拒绝连接)发生在 +0.0 s;ZooKeeper 里 /cfg 在 +{tu - tb:.1f} s 被改成 v2;+{t_un - tb:.1f} s 恢复网络')
for t, m in rows: print(f'    +{t:5.1f}s  {m}')
v2 = [t for t, m in rows if m == 'VAL v2'][0]
print(f'  缓存在整个断开期间一直返回旧值 v1;恢复后 {v2 - (t_un - tb):.1f} s 看到 v2(服务端早在 {tu - tb:.1f} s 就已经是 v2)')
R['stale'] = dict(changed=tu - tb, unblock=t_un - tb, caught=v2, rows=[(round(t, 1), m) for t, m in rows])
pp.kill(); n.stop(); save('z95', R); os._exit(0)
