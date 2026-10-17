import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c91')
img('python:3.12-alpine', 'alpine:3.20')
purge()
def df(opts):
    rc, o = dk('run', '--rm', *LAB, *opts, 'alpine:3.20', 'sh', '-c', "df -k /dev/shm | tail -1 | awk '{print $2}'; grep ' /dev/shm ' /proc/mounts | awk '{print $4}'")
    L = o.strip().splitlines(); return int(L[0]) // 1024, L[1]
print('== 一:/dev/shm 的大小(Docker Engine 29.8.2)')
for label, opts in (('默认', []), ('--shm-size 256m', ['--shm-size', '256m']), ('--shm-size 1g', ['--shm-size', '1g'])):
    sz, mo = df(opts); print(f'  {label}:/dev/shm 大小 {sz} MiB;挂载选项 {mo}')
print('  docker inspect 的 HostConfig.ShmSize(默认容器) = ' + (lambda: (dk("run", "-d", "--name", "bwlab-c91i", *LAB, "alpine:3.20", "sleep", "30"), out("inspect", "--format", "{{.HostConfig.ShmSize}}", "bwlab-c91i"))[1])() + ' 字节')
dk('rm', '-f', 'bwlab-c91i')
print('== 二:写满会怎样(用 dd 写文件)')
for label, opts, mb in (('默认 64 MiB,写 100 MiB', [], 100), ('--shm-size 128m,写 100 MiB', ['--shm-size', '128m'], 100)):
    rc, o = dk('run', '--rm', *LAB, *opts, 'alpine:3.20', 'sh', '-c', f'dd if=/dev/zero of=/dev/shm/f bs=1M count={mb} 2>&1 | tail -3; ls -l /dev/shm/f | awk "{{print \\$5}}"')
    print(f'  {label}:' + ' | '.join(l.strip() for l in o.strip().splitlines()))
print('== 三:用 mmap 写(Python multiprocessing.shared_memory):空间不够时不是报错而是被信号杀死')
PY = '''from multiprocessing import shared_memory
import sys, os
n = int(sys.argv[1]) << 20
s = shared_memory.SharedMemory(create=True, size=n, name="demo")
print("ftruncate 成功,大小 %d MiB(稀疏,还没占用)" % (n >> 20), flush=True)
b = s.buf
for off in range(0, n, 4096):
    b[off:off + 1] = b"x"
print("所有页都写完了", flush=True)'''
for label, opts in (('默认 64 MiB,共享内存 100 MiB', []), ('--shm-size 128m,共享内存 100 MiB', ['--shm-size', '128m'])):
    rc, o = dk('run', '--rm', *LAB, *opts, 'python:3.12-alpine', 'python', '-u', '-c', PY, '100')
    print(f'  {label}:退出码 {rc};输出:{" | ".join(l.strip() for l in o.strip().splitlines() if "resource_tracker" not in l and "warnings.warn" not in l)[:170]}')
print('== 四:/dev/shm 的占用算进容器的内存')
n = 'bwlab-c91m'
dk('run', '-d', '--name', n, *LAB, '--shm-size', '200m', 'alpine:3.20', 'sleep', '120'); time.sleep(1)
def cur(): return int(dk('exec', n, 'cat', '/sys/fs/cgroup/memory.current')[1]) / 1048576
a = cur(); dk('exec', n, 'sh', '-c', 'dd if=/dev/zero of=/dev/shm/f bs=1M count=80 2>/dev/null'); b_ = cur()
print(f'  往 /dev/shm 写 80 MiB:memory.current {a:.1f} → {b_:.1f} MiB(增加 {b_ - a:.1f} MiB)')
dk('rm', '-f', n)
rc, o = dk('run', '--name', 'bwlab-c91o', *LAB, '--memory', '64m', '--memory-swap', '64m', '--shm-size', '200m', 'alpine:3.20', 'sh', '-c', 'dd if=/dev/zero of=/dev/shm/f bs=1M count=120 2>&1 | tail -1; echo "dd 之后的退出码 $?"')
st = json.loads(out('inspect', '--format', '{{json .State}}', 'bwlab-c91o'))
print(f'  --memory 64m、--shm-size 200m,往 /dev/shm 写 120 MiB:docker run 退出码 {rc};输出:{o.strip().replace(chr(10), " | ")[:120]};容器 ExitCode={st["ExitCode"]} OOMKilled={st["OOMKilled"]}')
dk('rm', '-f', 'bwlab-c91o')
print('== 五:--ipc 共享 /dev/shm 之外的 IPC(System V),以及 /dev/shm 本身是否共享')
a_, b2 = 'bwlab-c91a', 'bwlab-c91b'
dk('run', '-d', '--name', a_, *LAB, '--ipc', 'shareable', 'alpine:3.20', 'sleep', '120')
dk('run', '-d', '--name', b2, *LAB, '--ipc', f'container:{a_}', 'alpine:3.20', 'sleep', '120'); time.sleep(1)
dk('exec', a_, 'sh', '-c', 'echo from-a > /dev/shm/hello')
print('  b 通过 --ipc container:a 加入 a 的 IPC 命名空间后,能读到 a 写在 /dev/shm 的文件吗?' + dk('exec', b2, 'sh', '-c', 'cat /dev/shm/hello 2>&1')[1].strip())
print('  两者的 IPC 命名空间相同吗?' + str(dk('exec', a_, 'readlink', '/proc/self/ns/ipc')[1].strip() == dk('exec', b2, 'readlink', '/proc/self/ns/ipc')[1].strip()))
dk('rm', '-f', a_, b2)
purge()
