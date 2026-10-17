import sys, os, time, json, re, subprocess, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z62'); R = {}
GC = ZDATA / 'z62' / 'gc.log'; GC.parent.mkdir(parents=True, exist_ok=True); GC.write_text('')
n = Node('z62', 7300, xmx=300, jvm=['-XX:+UseSerialGC', f'-Xlog:gc:file={GC}'], conf={'jvm.pause.monitor': 'true', 'jvm.pause.info-threshold.ms': 50, 'jvm.pause.warn-threshold.ms': 200, 'snapCount': 100000000}).start()
z = client('127.0.0.1:7300', timeout=30)
print('== 一:先把堆填到 ~110 MiB(100000 个 znode × 500 字节),再用串行 GC 的 Full GC 制造真实的停顿')
for s in range(0, 100000, 5000):
    rs = [z.create_async(f'/k{i:07d}', b'v' * 500) for i in range(s, s + 5000)]; [r.get() for r in rs]
w = client('127.0.0.1:7300', timeout=30); lat = []; stop = threading.Event()
def bg():
    i = 0
    while not stop.is_set():
        t = time.perf_counter(); w.create(f'/bg{i}', b'x'); lat.append(((time.perf_counter() - t) * 1000, time.perf_counter())); i += 1
th = threading.Thread(target=bg); th.start(); time.sleep(1)
marks = []
for i in range(6): marks.append(time.perf_counter()); subprocess.run(['/usr/bin/jcmd', str(n.p.pid), 'GC.run'], capture_output=True); time.sleep(1.5)
stop.set(); th.join()
gc = [l for l in GC.read_text().splitlines() if 'Pause Full' in l]; pauses = [float(re.search(r'([\d.]+)ms$', l).group(1)) for l in gc if re.search(r'([\d.]+)ms$', l)]
base = statistics.median(x for x, t in lat if all(abs(t - m) > 1 for m in marks)); mx = max(x for x, t in lat)
print(f'  GC 日志里的 Full GC 停顿(ms):{pauses};普通写延迟中位 {base:.2f} ms,压测期间最大写延迟 {mx:.1f} ms'); R['gc'] = dict(pauses=pauses, base=base, max_lat=mx)
print('  GC 日志示例:', gc[-1] if gc else '(无)'); R['gc_line'] = gc[-1] if gc else None
print()
print('== 二:ZooKeeper 自带的 JvmPauseMonitor(zoo.cfg 里 jvm.pause.monitor=true,阈值调到 info 50 ms / warn 200 ms)')
L = [re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l)[:130] for l in n.log().splitlines() if 'pause' in l.lower() and 'JVM' in l]
print(f'  日志里 JVM 停顿相关的行共 {len(L)} 条,例:'); [print('   ', l) for l in L[:3]]; R['pm'] = L[:3]
m = kv(n.four('mntr')); print('  mntr:zk_max_jvm_pause_time_ms =', m.get('zk_max_jvm_pause_time_ms'), '| zk_avg_jvm_pause_time_ms =', m.get('zk_avg_jvm_pause_time_ms'), '| zk_cnt_jvm_pause_time_ms =', m.get('zk_cnt_jvm_pause_time_ms')); R['mntr'] = {k: m.get(k) for k in ('zk_max_jvm_pause_time_ms', 'zk_avg_jvm_pause_time_ms', 'zk_cnt_jvm_pause_time_ms')}
w.stop(); z.stop(); n.stop(); save('z62', R)
