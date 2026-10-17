import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c40')
img('python:3.12-alpine')
purge()
PROBE = r'''
import os, socket, sys, errno
CAPS = "chown dac_override dac_read_search fowner fsetid kill setgid setuid setpcap linux_immutable net_bind_service net_broadcast net_admin net_raw ipc_lock ipc_owner sys_module sys_rawio sys_chroot sys_ptrace sys_pacct sys_admin sys_boot sys_nice sys_resource sys_time sys_tty_config mknod lease audit_write audit_control setfcap mac_override mac_admin syslog wake_alarm block_suspend audit_read perfmon bpf checkpoint_restore".split()
def caps(field):
    for l in open("/proc/self/status"):
        if l.startswith(field):
            v = int(l.split()[1], 16); return [CAPS[i] for i in range(len(CAPS)) if v >> i & 1]
def t(f):
    try: f(); return "成功"
    except OSError as e: return errno.errorcode.get(e.errno, str(e.errno))
mode = sys.argv[1]
if mode == "caps":
    for f in ("CapEff", "CapBnd"): c = caps(f); print("%s(%d 个):%s" % (f, len(c), " ".join(c)))
else:
    open("/tmp/f", "w").close()
    def bind80():
        s = socket.socket(); s.bind(("0.0.0.0", 80)); s.close()
    def raw():
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP); s.close()
    print("uid=%d  chown 文件给 uid 1234:%s  绑定 80 端口:%s  创建 ICMP raw socket:%s  mknod 设备文件:%s  读别的用户 0600 的文件:%s" % (
        os.getuid(), t(lambda: os.chown("/tmp/f", 1234, 1234)), t(bind80), t(raw), t(lambda: os.mknod("/tmp/dev", 0o600 | 0o20000, os.makedev(1, 3))),
        t(lambda: open("/secret").close())))
'''
d = ctx('c40', {'p.py': PROBE, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY p.py /p.py\nRUN echo s > /secret && chown 1234:1234 /secret && chmod 600 /secret\nENTRYPOINT ["python","/p.py"]\n'})
rc, o = build(d, 'bwlab-c40', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
print('== 一:默认容器的 capability(Docker Engine 29.8.2,root 用户)')
rc, o = dk('run', '--rm', *LAB, 'bwlab-c40', 'caps')
for l in o.strip().splitlines(): print('  ' + l)
print('== 二:root 用户在不同 capability 配置下能做什么')
for label, opts in (('默认', []), ('--cap-drop ALL', ['--cap-drop', 'ALL']), ('--cap-drop ALL --cap-add CHOWN', ['--cap-drop', 'ALL', '--cap-add', 'CHOWN']), ('--cap-drop NET_RAW', ['--cap-drop', 'NET_RAW']), ('--cap-drop MKNOD', ['--cap-drop', 'MKNOD'])):
    rc, o = dk('run', '--rm', *LAB, *opts, 'bwlab-c40', 'try')
    print(f'  {label}:{o.strip()}')
print('== 三:普通用户(uid 1000)绑定 80 端口')
rc, o = dk('run', '--rm', *LAB, '--user', '1000', 'bwlab-c40', 'try'); print(f'  默认:{o.strip()}')
rc, o = dk('run', '--rm', *LAB, '--user', '1000', '--cap-drop', 'NET_BIND_SERVICE', 'bwlab-c40', 'try'); print(f'  --user 1000 --cap-drop NET_BIND_SERVICE:{o.strip()}')
rc, o = dk('run', '--rm', *LAB, '--user', '1000', '--sysctl', 'net.ipv4.ip_unprivileged_port_start=1024', 'bwlab-c40', 'try'); print(f'  --user 1000 --sysctl net.ipv4.ip_unprivileged_port_start=1024:{o.strip()}')
rc, o = dk('run', '--rm', *LAB, '--user', '1000', 'bwlab-c40', 'caps'); print('  uid 1000 的 capability:' + ' / '.join(o.strip().splitlines()))
rc, o = dk('run', '--rm', *LAB, 'bwlab-c40', 'caps', '--cap-add', 'ALL'); 
rc, o = dk('run', '--rm', *LAB, '--cap-add', 'SYS_ADMIN', 'bwlab-c40', 'caps'); print('  --cap-add SYS_ADMIN 后 CapEff 个数:' + o.strip().splitlines()[0].split(':')[0])
purge()
