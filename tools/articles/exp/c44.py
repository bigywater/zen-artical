import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c44')
img('alpine:3.20')
purge()
CAPS = "chown dac_override dac_read_search fowner fsetid kill setgid setuid setpcap linux_immutable net_bind_service net_broadcast net_admin net_raw ipc_lock ipc_owner sys_module sys_rawio sys_chroot sys_ptrace sys_pacct sys_admin sys_boot sys_nice sys_resource sys_time sys_tty_config mknod lease audit_write audit_control setfcap mac_override mac_admin syslog wake_alarm block_suspend audit_read perfmon bpf checkpoint_restore".split()
SH = r'''
echo "CapEff=$(grep CapEff /proc/self/status | cut -f2)"
grep -E '^(Seccomp|NoNewPrivs):' /proc/self/status | tr '\n\t' '  '; echo
echo "/dev 条目数 $(ls /dev | wc -l);块设备 $(ls /dev | grep -c -E '^(vd|sd|nvme|loop)')"
if grep -q ' /proc/sys ' /proc/mounts; then echo "/proc/sys 有单独的挂载,选项:$(grep ' /proc/sys ' /proc/mounts | awk '{print $4}' | cut -d, -f1)"; else echo "/proc/sys 没有单独的挂载(随 /proc:$(grep ' /proc ' /proc/mounts | head -1 | awk '{print $4}' | cut -d, -f1))"; fi
echo "/sys 挂载选项:$(grep ' /sys ' /proc/mounts | awk '{print $4}' | cut -d, -f1)"
mount -t tmpfs none /mnt >/tmp/m.err 2>&1; echo "mount -t tmpfs 退出码 $?:$(head -1 /tmp/m.err)"
'''
def run(label, opts):
    rc, o = dk('run', '--rm', *LAB, *opts, 'alpine:3.20', 'sh', '-c', SH)
    L = o.strip().splitlines()
    cap = int(L[0].split('=')[1], 16)
    names = [CAPS[i] for i in range(len(CAPS)) if cap >> i & 1]
    print(f'  {label}:')
    print(f'    capability {len(names)} 个({"含" if "sys_admin" in names else "不含"} sys_admin,{"含" if "sys_module" in names else "不含"} sys_module,{"含" if "sys_rawio" in names else "不含"} sys_rawio)')
    for l in L[1:]: print('    ' + l)
print('== 一:默认 与 --privileged 的差别(Docker Engine 29.8.2)')
run('默认', [])
run('--privileged', ['--privileged'])
print('== 二:更小的授权:只加 SYS_ADMIN 能做多少')
run('--cap-add SYS_ADMIN', ['--cap-add', 'SYS_ADMIN'])
print('== 三:特权容器能看到虚拟机的磁盘设备(只读 2 个字节,不修改任何内容)')
RAW = "ls /dev | grep -E '^vd' | tr '\\n' ' '; echo; if [ -e /dev/vda1 ]; then head -c 1082 /dev/vda1 | tail -c 2 | od -An -tx1; else echo 不存在; fi"
rc, o = dk('run', '--rm', *LAB, '--privileged', 'alpine:3.20', 'sh', '-c', RAW)
print('  --privileged:/dev/vd* = ' + o.strip().splitlines()[0] + ';读 /dev/vda1 偏移 1080 处的 2 个字节 = ' + o.strip().splitlines()[1].strip() + '(ext4 超级块的魔数是 53 ef)')
rc, o = dk('run', '--rm', *LAB, 'alpine:3.20', 'sh', '-c', RAW)
print('  默认:/dev/vd* = ' + (o.strip().splitlines()[0] or '(没有)') + ';/dev/vda1:' + o.strip().splitlines()[-1].strip())
print('== 四:--privileged 包含哪些变化(docker inspect)')
n = 'bwlab-c44'
dk('run', '-d', '--name', n, *LAB, '--privileged', 'alpine:3.20', 'sleep', '30')
print(f'  HostConfig.Privileged = {out("inspect", "--format", "{{.HostConfig.Privileged}}", n)};CapAdd = {out("inspect", "--format", "{{.HostConfig.CapAdd}}", n)};SecurityOpt = {out("inspect", "--format", "{{.HostConfig.SecurityOpt}}", n)}')
dk('rm', '-f', n)
purge()
