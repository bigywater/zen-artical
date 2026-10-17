import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c45')
img('python:3.12-alpine', 'alpine:3.20')
purge()
PROBE = r'''
import os, errno, sys, stat
def op(path, flags):
    try:
        fd = os.open(path, flags); os.close(fd); return "成功"
    except OSError as e: return errno.errorcode.get(e.errno, str(e.errno))
def info(path):
    try:
        st = os.stat(path); return "%s %d:%d" % (stat.filemode(st.st_mode), os.major(st.st_rdev), os.minor(st.st_rdev))
    except OSError as e: return "不存在"
for a in sys.argv[1:]:
    print("%s:%s;O_RDONLY→%s;O_WRONLY→%s" % (a, info(a), op(a, os.O_RDONLY), op(a, os.O_WRONLY)))
'''
d = ctx('c45', {'p.py': PROBE, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY p.py /p.py\nENTRYPOINT ["python","/p.py"]\n'})
rc, o = build(d, 'bwlab-c45', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def go(label, opts, *paths):
    rc, o = dk('run', '--rm', *LAB, *opts, 'bwlab-c45', *paths)
    print(f'  {label}:')
    for l in o.strip().splitlines(): print('    ' + l)
print('== 一:默认容器的 /dev 与 --device 加进去的设备(Docker Engine 29.8.2)')
go('默认', [], '/dev/fuse', '/dev/net/tun', '/dev/loop7', '/dev/zero')
go('--device /dev/fuse --device /dev/net/tun', ['--device', '/dev/fuse', '--device', '/dev/net/tun'], '/dev/fuse', '/dev/net/tun', '/dev/loop7')
print('== 二:--device 的权限后缀 r / w / m,以及改名映射')
go('--device /dev/loop7:/dev/mydisk:r(只读)', ['--device', '/dev/loop7:/dev/mydisk:r'], '/dev/mydisk', '/dev/loop7')
go('--device /dev/loop7:/dev/mydisk:rw(读写,不能 mknod)', ['--device', '/dev/loop7:/dev/mydisk:rw'], '/dev/mydisk')
go('--device /dev/zero:/dev/myzero', ['--device', '/dev/zero:/dev/myzero'], '/dev/myzero')
print('== 三:容器里自己 mknod 一个设备文件,能用吗')
MK = "mknod /tmp/myfuse c 10 229; echo mknod 退出码 $?; python /p.py /tmp/myfuse"
rc, o = dk('run', '--rm', *LAB, '--entrypoint', 'sh', 'bwlab-c45', '-c', MK); print('  默认(有 MKNOD capability):' + ' | '.join(l.strip() for l in o.strip().splitlines()))
rc, o = dk('run', '--rm', *LAB, '--device-cgroup-rule', 'c 10:229 rwm', '--entrypoint', 'sh', 'bwlab-c45', '-c', MK); print("  加 --device-cgroup-rule 'c 10:229 rwm':" + ' | '.join(l.strip() for l in o.strip().splitlines()))
rc, o = dk('run', '--rm', *LAB, '--device-cgroup-rule', 'c 10:229 r', '--entrypoint', 'sh', 'bwlab-c45', '-c', MK); print("  加 --device-cgroup-rule 'c 10:229 r'(只读):" + ' | '.join(l.strip() for l in o.strip().splitlines()))
print('== 四:docker inspect 里记录的设备')
n = 'bwlab-c45-i'
dk('run', '-d', '--name', n, *LAB, '--device', '/dev/fuse', '--device', '/dev/loop7:/dev/mydisk:r', '--device-cgroup-rule', 'c 10:229 rwm', 'alpine:3.20', 'sleep', '30')
print('  HostConfig.Devices = ' + out('inspect', '--format', '{{json .HostConfig.Devices}}', n))
print('  HostConfig.DeviceCgroupRules = ' + out('inspect', '--format', '{{json .HostConfig.DeviceCgroupRules}}', n))
dk('rm', '-f', n)
purge()
