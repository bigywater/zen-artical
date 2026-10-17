import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c70')
img('python:3.12-alpine', 'alpine:3.20')
purge()
def stats(n):
    rc, o = dk('stats', '--no-stream', '--format', '{{json .}}', n, timeout=60)
    return json.loads(o.strip().splitlines()[-1])
print('== 一:docker stats 的字段与 CPU 百分比(Docker Engine 29.8.2)')
n = 'bwlab-c70a'
BURN = 'import multiprocessing as mp,time\ndef f():\n    while True: pass\nif __name__=="__main__":\n    for _ in range(2): mp.Process(target=f,daemon=True).start()\n    time.sleep(60)'
dk('run', '-d', '--name', n, *LAB, 'python:3.12-alpine', 'python', '-c', BURN); time.sleep(3)
s = stats(n)
print('  一行 JSON 的字段:' + str(sorted(s.keys())))
print(f'  2 个满负荷进程:CPUPerc={s["CPUPerc"]} MemUsage={s["MemUsage"]} MemPerc={s["MemPerc"]} NetIO={s["NetIO"]} BlockIO={s["BlockIO"]} PIDs={s["PIDs"]}')
def cpu_usec(n): return int(dk('exec', n, 'sh', '-c', "grep usage_usec /sys/fs/cgroup/cpu.stat | cut -d' ' -f2")[1])
a = cpu_usec(n); t0 = time.time(); time.sleep(3); b = cpu_usec(n); el = time.time() - t0
print(f'  自己从 cgroup 的 cpu.stat 算:{(b - a) / 1e6 / el * 100:.0f}% (CPU 时间增量 ÷ 墙钟时间;满 1 个 CPU = 100%)')
print(f'  虚拟机 CPU 数 = {out("info", "--format", "{{.NCPU}}")}:docker stats 的 CPUPerc 可以超过 100% (每个核 100%)')
dk('rm', '-f', n)
print('== 二:MEM USAGE 和 cgroup 的 memory.current 不是一回事(页缓存)')
n = 'bwlab-c70b'
dk('run', '-d', '--name', n, *LAB, '--memory', '512m', 'alpine:3.20', 'sleep', '120'); time.sleep(1)
def cg(n):
    o = dk('exec', n, 'sh', '-c', 'cat /sys/fs/cgroup/memory.current; cat /sys/fs/cgroup/memory.stat')[1].splitlines()
    st = dict(l.split() for l in o[1:])
    return int(o[0]) / 1048576, int(st['anon']) / 1048576, int(st['inactive_file']) / 1048576
A = stats(n)['MemUsage']
dk('exec', n, 'sh', '-c', 'dd if=/dev/zero of=/f.bin bs=1M count=200 2>/dev/null; sync')
B = stats(n)['MemUsage']
cur, anon, inact = cg(n)
print(f'  docker stats 的 MemUsage:写 200 MiB 文件前 {A},写完 {B}')
print(f'  写完之后从 cgroup 读(这次读本身用了一个 docker exec 进程,会多出几 MiB):memory.current={cur:.1f} MiB,其中 anon={anon:.1f} MiB、inactive_file={inact:.1f} MiB')
print(f'  对比:cgroup 的 memory.current 增加了约 200 MiB(页缓存),而 docker stats 只增加了 {B},所以 MemUsage 不含页缓存')
dk('rm', '-f', n)
print('== 三:NetIO / BlockIO 与内核计数器')
n = 'bwlab-c70c'
dk('run', '-d', '--name', n, *LAB, 'alpine:3.20', 'sleep', '120'); time.sleep(1)
r0 = int(dk('exec', n, 'cat', '/sys/class/net/eth0/statistics/rx_bytes')[1]); t0_ = int(dk('exec', n, 'cat', '/sys/class/net/eth0/statistics/tx_bytes')[1])
dk('exec', n, 'ping', '-c', '20', '-s', '1000', '-i', '0.1', '-q', '172.17.0.1')
r1 = int(dk('exec', n, 'cat', '/sys/class/net/eth0/statistics/rx_bytes')[1]); t1_ = int(dk('exec', n, 'cat', '/sys/class/net/eth0/statistics/tx_bytes')[1])
s = stats(n)
print(f'  eth0 的 rx/tx 增量:{r1 - r0} / {t1_ - t0_} 字节;启动以来累计 rx={r1} tx={t1_};docker stats NetIO = {s["NetIO"]}')
dk('exec', n, 'sh', '-c', 'dd if=/dev/zero of=/b.bin bs=1M count=50 oflag=direct 2>/dev/null')
print(f'  写 50 MiB(oflag=direct)后 docker stats BlockIO = {stats(n)["BlockIO"]}')
dk('rm', '-f', n)
purge()
