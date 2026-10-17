import sys, os, time, json, re, threading, subprocess, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.recipe.barrier import Barrier, DoubleBarrier
tee('z83'); R = {}
n = Node('z83', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); z = client('127.0.0.1:7300')
print('== 一:Barrier(栅栏):10 个等待者调用 wait() 阻塞,控制者 remove() 之后同时放行')
cl = [client('127.0.0.1:7300') for _ in range(10)]; ctl = Barrier(z, '/bar'); ctl.create(); woke = []
print('  /bar 存在:', z.exists('/bar') is not None, '(Barrier 的「关上」就是这个 znode 存在)')
def w(i):
    b = Barrier(cl[i], '/bar'); b.wait(); woke.append(time.time())
ths = [threading.Thread(target=w, args=(i,)) for i in range(10)]; [t.start() for t in ths]; time.sleep(1.0)
print(f'  1 秒后仍被挡住的等待者数 = {10 - len(woke)}')
t0 = time.time(); ctl.remove(); [t.join() for t in ths]
sp = (max(woke) - t0) * 1000; mn = (min(woke) - t0) * 1000
print(f'  remove() 之后 10 个都被唤醒:最早 {mn:.1f} ms,最晚 {sp:.1f} ms')
R['barrier'] = dict(blocked=10 - 0, first=mn, last=sp)
print('  已经移除后再来的等待者:wait() 立即返回:', end=' '); t0 = time.time(); Barrier(z, '/bar').wait(); print(f'{(time.time()-t0)*1000:.1f} ms')
print()
print('== 二:DoubleBarrier(双栅栏):5 个参与者,都 enter 之后才一起开始,都 leave 之后才一起结束。第 5 个迟到 2 秒')
lg = []
def part(i, late):
    c = client('127.0.0.1:7300'); b = DoubleBarrier(c, '/dbar', 5, identifier=f'p{i}')
    time.sleep(late); t_in = time.time(); b.enter(); t_ent = time.time(); time.sleep(0.2 * (i + 1)); t_lv = time.time(); b.leave(); t_out = time.time()
    lg.append((i, t_in, t_ent, t_lv, t_out)); c.stop()
T0 = time.time(); ths = [threading.Thread(target=part, args=(i, 2.0 if i == 4 else 0)) for i in range(5)]; [t.start() for t in ths]; [t.join() for t in ths]
lg.sort()
for i, t_in, t_ent, t_lv, t_out in lg: print(f'  p{i}: 调用 enter {t_in-T0:4.1f}s → 实际进入 {t_ent-T0:4.1f}s;干活 {(i+1)*0.2:.1f}s,调用 leave {t_lv-T0:4.1f}s → 实际离开 {t_out-T0:4.1f}s')
R['double'] = [dict(i=i, call_enter=round(a-T0, 2), enter=round(b-T0, 2), call_leave=round(c-T0, 2), leave=round(d-T0, 2)) for i, a, b, c, d in lg]
print(f'  进入时刻最大差 {(max(x[2] for x in lg)-min(x[2] for x in lg))*1000:.0f} ms;离开时刻最大差 {(max(x[4] for x in lg)-min(x[4] for x in lg))*1000:.0f} ms')
print()
print('== 三:同一个路径再来一轮(可重用):')
lg2 = []
def part2(i):
    c = client('127.0.0.1:7300'); b = DoubleBarrier(c, '/dbar', 5, identifier=f'p{i}'); b.enter(); b.leave(); lg2.append(i); c.stop()
ths = [threading.Thread(target=part2, args=(i,)) for i in range(5)]; [t.start() for t in ths]; [t.join(15) for t in ths]
print(f'  第二轮完成的参与者数 = {len(lg2)} / 5;/dbar 剩余子节点 = {z.get_children("/dbar")}')
R['reuse'] = len(lg2)
print()
print('== 四:参与者没到齐:只来了 4 个,enter() 会怎样')
res = []
def part3(i):
    c = client('127.0.0.1:7300'); b = DoubleBarrier(c, '/dbar3', 5, identifier=f'q{i}'); t0 = time.time()
    try: b.enter(); res.append('进入')
    except Exception as e: res.append(type(e).__name__)
    c.stop()
ths = [threading.Thread(target=part3, args=(i,)) for i in range(4)]; [t.start() for t in ths]; time.sleep(4); 
print(f'  4 个都还在等(没有 timeout 参数的 enter 会永远阻塞):已返回 {len(res)} 个;/dbar3 子节点 {len(z.get_children("/dbar3"))} 个')
R['short'] = len(z.get_children('/dbar3'))
print('  kazoo 的 DoubleBarrier.enter() 没有 timeout 参数,没人来就一直等。')
print()
print('== 五:参与者 enter 之后被 kill -9:其余参与者 leave() 要等多久')
lf = ZDATA / 'z83' / 'db.log'; lf.parent.mkdir(exist_ok=True); lf.write_text(''); P = str(HERE / 'procs' / 'dbar.py')
ps = [subprocess.Popen([sys.executable, P, '7300', f'r{i}', '3', str(lf), 'die_after_enter' if i == 2 else 'ok']) for i in range(3)]
t0 = time.time()
while time.time() - t0 < 10 and sum('ENTERED' in l for l in lf.read_text().splitlines()) < 3: time.sleep(0.05)
tk = time.time(); ps[2].kill(); 
while time.time() - tk < 20 and sum('LEFT' in l for l in lf.read_text().splitlines()) < 2: time.sleep(0.05)
L = [l.split() for l in lf.read_text().splitlines()]; lv = [float(l[0]) - tk for l in L if l[2] == 'LEFT']
print(f'  3 个参与者全部 ENTERED 后 kill -9 其中一个,另外两个 LEFT 的时刻(相对 kill): {[f"{x:.1f}s" for x in lv]}(会话超时 3 s)')
R['crash_leave'] = [round(x, 1) for x in lv]
for p in ps: p.kill()
z.stop(); n.stop(); save('z83', R); os._exit(0)
