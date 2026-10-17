import sys, os, time, json, re, subprocess, signal, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z90'); R = {}
n = Node('z90', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); z = client('127.0.0.1:7300')
for p in ('/tasks', '/claims', '/done'): z.ensure_path(p)
lf = ZDATA / 'z90' / 'w.log'; lf.parent.mkdir(exist_ok=True); lf.write_text(''); W = str(HERE / 'procs' / 'claimw.py'); C = str(HERE / 'procs' / 'cron.py')
def ev(): return [(float(l.split(' ', 2)[0]), l.split(' ', 2)[1], l.split(' ', 2)[2]) for l in lf.read_text().splitlines() if l.strip()]
print('== 一:没有 master:300 个任务放在 /tasks,5 个 worker 进程各自抢 —— 抢占方式是创建 /claims/<任务>(临时节点),只有一个能成功')
for i in range(300): z.create(f'/tasks/job{i:03d}', b'')
ps = [subprocess.Popen([sys.executable, W, '7300', f'W{i}', str(lf)]) for i in range(5)]
t0 = time.time()
while time.time() - t0 < 60 and len(z.get_children('/done')) < 300: time.sleep(0.1)
el = time.time() - t0; e = ev(); starts = collections.Counter(x[2].split()[1] for x in e if x[2].startswith('START')); per = collections.Counter(x[1] for x in e if x[2].startswith('START'))
print(f'  完成 {len(z.get_children("/done"))} / 300,用时 {el:.1f} s;执行次数 >1 的任务:{[k for k, v in starts.items() if v > 1]};各 worker 抢到的任务数 {dict(sorted(per.items()))}')
R['race'] = dict(done=len(z.get_children('/done')), dup=[k for k, v in starts.items() if v > 1], per=dict(per), s=el)
print()
print('== 二:worker 在执行任务中途被 kill -9:放一个耗时 3 s 的任务 slow00,杀掉抢到它的 worker,看它什么时候被别的 worker 接走重做')
z.create('/tasks/slow00', b''); t0 = time.time()
while not any(x[2] == 'START slow00' for x in ev()) and time.time() - t0 < 10: time.sleep(0.02)
e = ev(); first = [x for x in e if x[2] == 'START slow00'][0]; victim = int(first[1][1:]); tk = time.time(); ps[victim].kill()
while time.time() - tk < 20 and not any(x[2] == 'END slow00' for x in ev()): time.sleep(0.05)
e = ev(); s2 = [x for x in e if x[2] == 'START slow00']; en = [x for x in e if x[2] == 'END slow00']
print(f'  第一次 START 由 {first[1]} 开始;我在 START 后 {tk - first[0]:.1f} s 时 kill -9 它')
print(f'  第二次 START(接手者):{s2[1][1]},在 kill 后 {s2[1][0] - tk:.1f} s;END 在 kill 后 {en[0][0] - tk:.1f} s,由 {en[0][1]} 完成;/done/slow00 的写入者 = {z.get("/done/slow00")[0].decode()}')
print(f'  slow00 一共 START {len(s2)} 次、END {len(en)} 次 —— 至少一次执行:被杀的那一次做了一半,任务必须幂等')
R['crash'] = dict(starts=len(s2), ends=len(en), takeover=s2[1][0] - tk, end=en[0][0] - tk)
for p in ps: p.kill()
print()
print('== 三:定时任务单实例执行:3 个实例都想「每秒执行一次」同一个任务,抢 /cron/tick-<k>(持久节点,谁先 create 成功谁执行),共 25 个 tick;第 10 秒 kill -9 其中执行最多的一个')
lf.write_text(''); t_start = time.time() + 3
cps = [subprocess.Popen([sys.executable, C, '7300', f'N{i}', str(lf), str(t_start), '25']) for i in range(3)]
time.sleep(t_start - time.time() + 10); cnt = collections.Counter(x[1] for x in ev() if x[2].startswith('RUN')); victim = cnt.most_common(1)[0][0]; cps[int(victim[1])].kill(); print(f'  kill -9 {victim}(前 10 个 tick 它执行了 {cnt[victim]} 次)')
time.sleep(17); e = [x for x in ev() if x[2].startswith('RUN')]
ticks = collections.Counter(int(x[2].split()[1]) for x in e); missing = [k for k in range(25) if k not in ticks]; dup = [k for k, v in ticks.items() if v > 1]
print(f'  25 个 tick:被执行的 {len(ticks)} 个,漏掉 {missing},重复执行 {dup};各实例执行数 {dict(sorted(collections.Counter(x[1] for x in e).items()))}')
lat = [x[0] - (t_start + int(x[2].split()[1])) for x in e]; print(f'  执行时刻相对 tick 整点的偏差(ms):中位 {sorted(lat)[len(lat)//2]*1000:.0f},最大 {max(lat)*1000:.0f}')
R['cron'] = dict(ran=len(ticks), missing=missing, dup=dup, med=sorted(lat)[len(lat) // 2] * 1000, mx=max(lat) * 1000, victim=victim)
for p in cps: p.kill()
z.stop(); n.stop(); save('z90', R); os._exit(0)
