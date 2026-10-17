import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c36')
img('python:3.12-alpine')
purge()
ALLOC = r'''
import os, sys, time
step = 10
chunks = []
mx = int(sys.argv[1])
def rd(f):
    try: return open(f).read().strip()
    except Exception: return "?"
try:
    for i in range(mx // step):
        chunks.append(bytearray(os.urandom(step << 20)))
        print("已分配 %d MiB(memory.current=%.0f MiB,swap.current=%.0f MiB)" % ((i + 1) * step, int(rd("/sys/fs/cgroup/memory.current")) / 1048576, int(rd("/sys/fs/cgroup/memory.swap.current")) / 1048576), flush=True)
        time.sleep(0.05)
except MemoryError:
    print("MemoryError", flush=True)
print("完成,共 %d MiB" % (len(chunks) * step), flush=True)
'''
d = ctx('c36', {'a.py': ALLOC, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY a.py /a.py\nENTRYPOINT ["python","-u","/a.py"]\n'})
rc, o = build(d, 'bwlab-c36', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def rd(opts):
    rc, o = dk('run', '--rm', *LAB, *opts, '--entrypoint', 'sh', 'bwlab-c36', '-c', 'echo memory.max=$(cat /sys/fs/cgroup/memory.max) memory.swap.max=$(cat /sys/fs/cgroup/memory.swap.max)')
    return o.strip()
print('== 一:--memory 与 --memory-swap 在 cgroup 里变成什么(Docker Engine 29.8.2)')
vm_swap = dk('run', '--rm', *LAB, 'bwlab-c36', '0')  # warm
rc, o = dk('run', '--rm', *LAB, '--entrypoint', 'sh', 'bwlab-c36', '-c', "grep -E 'MemTotal|SwapTotal' /proc/meminfo | tr -s ' ' | tr '\\n' ';'")
print('  虚拟机的 /proc/meminfo:' + o.strip())
for label, opts in (('不限制', []), ('--memory 64m', ['--memory', '64m']), ('--memory 64m --memory-swap 64m', ['--memory', '64m', '--memory-swap', '64m']), ('--memory 64m --memory-swap 128m', ['--memory', '64m', '--memory-swap', '128m']), ('--memory 64m --memory-swap -1', ['--memory', '64m', '--memory-swap', '-1'])):
    print(f'  {label}:{rd(opts)}')
print('== 二:分配 200 MiB(每次 10 MiB,真正写入),在不同限制下会怎样')
def alloc(label, opts):
    n = 'bwlab-c36-' + str(abs(hash(label)) % 10**6)
    rc, o = dk('run', '--name', n, *LAB, *opts, 'bwlab-c36', '200', timeout=120)
    s = json.loads(out('inspect', '--format', '{{json .State}}', n))
    lines = [l for l in o.strip().splitlines() if l.startswith('已分配')]
    last = lines[-1] if lines else '(无输出)'
    print(f'  {label}:最后一条输出「{last}」;ExitCode={s["ExitCode"]} OOMKilled={s["OOMKilled"]}')
    dk('rm', '-f', n)
alloc('不限制', [])
alloc('--memory 64m', ['--memory', '64m'])
alloc('--memory 64m --memory-swap 64m', ['--memory', '64m', '--memory-swap', '64m'])
alloc('--memory 64m --memory-swap 128m', ['--memory', '64m', '--memory-swap', '128m'])
alloc('--memory 64m --memory-swap -1', ['--memory', '64m', '--memory-swap', '-1'])
print('== 三:--memory-reservation(软限制)与 docker stats 里的 LIMIT')
n = 'bwlab-c36-stats'
dk('run', '-d', '--name', n, *LAB, '--memory', '64m', '--memory-reservation', '32m', '--entrypoint', 'sleep', 'bwlab-c36', '60'); time.sleep(1)
print(f'  memory.high / memory.low 等:{dk("exec", n, "sh", "-c", "echo high=$(cat /sys/fs/cgroup/memory.high) low=$(cat /sys/fs/cgroup/memory.low) max=$(cat /sys/fs/cgroup/memory.max)")[1].strip()}')
print(f'  docker stats --no-stream:{out("stats", "--no-stream", "--format", "{{.MemUsage}} 占 {{.MemPerc}}", n)}')
dk('rm', '-f', n)
purge()
