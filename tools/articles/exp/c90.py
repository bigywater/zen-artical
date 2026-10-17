import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c90')
img('alpine:3.20')
purge()
def vm(cmd):
    rc, o = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', cmd, raw=True)
    return o.strip()
def sysv(opts, *keys):
    rc, o = dk('run', '--rm', *LAB, *opts, 'alpine:3.20', 'sh', '-c', ' '.join(f'echo {k}=$(cat /proc/sys/{k.replace(".", "/")}); ' for k in keys))
    return rc, o.strip().replace('\n', ' ; ')
print('== 一:--sysctl 只改容器自己的命名空间(Docker Engine 29.8.2;只改容器内的值,不碰虚拟机的)')
keys = ['net.ipv4.ip_forward', 'net.core.somaxconn', 'net.ipv4.ip_local_port_range', 'kernel.shmmax']
print('  虚拟机里的当前值:' + vm(' '.join(f'echo {k}=$(cat /proc/sys/{k.replace(".", "/")}); ' for k in keys)).replace('\n', ' ; '))
print('  默认容器里的值:' + sysv([], *keys)[1])
rc, v = sysv(['--sysctl', 'net.ipv4.ip_forward=1', '--sysctl', 'net.core.somaxconn=1024', '--sysctl', 'net.ipv4.ip_local_port_range=40000 40100', '--sysctl', 'kernel.shmmax=1048576'], *keys)
print(f'  --sysctl net.ipv4.ip_forward=1 net.core.somaxconn=1024 net.ipv4.ip_local_port_range="40000 40100" kernel.shmmax=1048576:退出码 {rc};容器里 {v}')
print('  同一时刻虚拟机里的值(不应变):' + vm(' '.join(f'echo {k}=$(cat /proc/sys/{k.replace(".", "/")}); ' for k in keys)).replace('\n', ' ; '))
print('== 二:不在独立命名空间里的 sysctl 会被拒绝')
for k, v in (('vm.swappiness', '10'), ('kernel.panic', '1'), ('fs.file-max', '100000'), ('kernel.pid_max', '65536')):
    rc, o = dk('run', '--rm', *LAB, '--sysctl', f'{k}={v}', 'alpine:3.20', 'true')
    msg = next((l for l in o.splitlines() if 'sysctl' in l.lower() or 'docker:' in l), o)
    print(f'  --sysctl {k}={v}:退出码 {rc};{msg.strip()[:150]}')
print('== 三:与共享命名空间的模式冲突')
for label, opts in (('--network host + net.ipv4.ip_forward', ['--network', 'host', '--sysctl', 'net.ipv4.ip_forward=1']), ('--ipc host + kernel.shmmax', ['--ipc', 'host', '--sysctl', 'kernel.shmmax=1048576']), ('--network none + net.core.somaxconn', ['--network', 'none', '--sysctl', 'net.core.somaxconn=512'])):
    rc, o = dk('run', '--rm', *LAB, *opts, 'alpine:3.20', 'cat', '/proc/sys/net/core/somaxconn')
    msg = next((l for l in o.splitlines() if 'sysctl' in l.lower() or 'docker:' in l), o)
    msg = msg.split('runc create failed:')[-1].strip()
    print(f'  {label}:退出码 {rc};{msg[:170]}')
print('== 四:容器里直接写 /proc/sys')
rc, o = dk('run', '--rm', *LAB, 'alpine:3.20', 'sh', '-c', 'echo 1 > /proc/sys/net/ipv4/ip_forward 2>&1; echo "写 ip_forward 退出码 $?"; echo 20 > /proc/sys/vm/swappiness 2>&1; echo "写 swappiness 退出码 $?"; grep " /proc/sys " /proc/mounts | cut -d" " -f4 | cut -d, -f1')
print('  默认容器里:' + o.strip().replace('\n', ' ; '))
purge()
