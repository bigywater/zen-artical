import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k82')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k82')
CAPS = ['CHOWN','DAC_OVERRIDE','DAC_READ_SEARCH','FOWNER','FSETID','KILL','SETGID','SETUID','SETPCAP','LINUX_IMMUTABLE','NET_BIND_SERVICE','NET_BROADCAST','NET_ADMIN','NET_RAW','IPC_LOCK','IPC_OWNER','SYS_MODULE','SYS_RAWIO','SYS_CHROOT','SYS_PTRACE','SYS_PACCT','SYS_ADMIN','SYS_BOOT','SYS_NICE','SYS_RESOURCE','SYS_TIME','SYS_TTY_CONFIG','MKNOD','LEASE','AUDIT_WRITE','AUDIT_CONTROL','SETFCAP','MAC_OVERRIDE','MAC_ADMIN','SYSLOG','WAKE_ALARM','BLOCK_SUSPEND','AUDIT_READ','PERFMON','BPF','CHECKPOINT_RESTORE']
def decode(h): v = int(h, 16); return [CAPS[i] for i in range(len(CAPS)) if v >> i & 1]
def pod(name, sc='', csc='', cmd='[sleep, "3600"]', vols='', vm='', extra=''):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n{sc}{extra}  containers:\n  - name: c\n    image: busybox:1.36\n    imagePullPolicy: IfNotPresent\n    command: {cmd}\n{csc}{vm}{vols}---\n'
def ex(p_, cmd): return k('exec', p_, '-n', NS, '--', 'sh', '-c', cmd)[1].strip()
def up_(*names):
    for n in names: k('wait', '--for=condition=Ready', f'pod/{n}', '-n', NS, '--timeout=60s')
print(f'集群 {cn};securityContext 决定容器进程用哪个用户、哪些组、拥有哪些能力、卷里的文件归谁')

print('== 一:runAsUser / runAsGroup / fsGroup / supplementalGroups')
VOL = '  volumes: [{name: data, emptyDir: {}}]\n'; VM = '    volumeMounts: [{name: data, mountPath: /data}]\n'
k('apply', '-f', '-', input=pod('default', vols=VOL, vm=VM) + pod('user', sc='  securityContext: {runAsUser: 1000, runAsGroup: 3000, fsGroup: 2000, supplementalGroups: [4000, 5000]}\n', vols=VOL, vm=VM))
up_('default', 'user')
for n in ('default', 'user'):
    print(f'  Pod {n}:id → {ex(n, "id")};emptyDir /data 的权限 → {ex(n, "stat -c \'%a %U:%G (uid:gid=%u:%g)\' /data")}')
    print(f'    在 /data 里新建文件:{ex(n, "touch /data/f 2>&1 && stat -c \'%a %u:%g\' /data/f")};进程 /proc/1/status 的 Groups:{ex(n, "grep Groups /proc/1/status")}')

print('== 二:能力(capabilities)——默认有哪些,drop / add 之后变成什么')
k('apply', '-f', '-', input=pod('caps-default') + pod('caps-drop', csc='    securityContext: {capabilities: {drop: [ALL]}}\n') + pod('caps-add', csc='    securityContext: {capabilities: {add: [NET_ADMIN]}}\n') + pod('caps-priv', csc='    securityContext: {privileged: true}\n'))
up_('caps-default', 'caps-drop', 'caps-add', 'caps-priv')
for n in ('caps-default', 'caps-drop', 'caps-add', 'caps-priv'):
    h = ex(n, "grep CapEff /proc/1/status | awk '{print $2}'"); cs = decode(h)
    print(f'  {n}:CapEff={h} → {len(cs)} 个' + (f':{cs}' if len(cs) < 20 else ':(几乎全部,41 个里的 %d 个)' % len(cs)))
print(f'  default 里 chown 别人的文件:{ex("caps-default", "touch /tmp/x && chown 1234 /tmp/x && echo 成功")};drop ALL 里:{ex("caps-drop", "touch /tmp/x && chown 1234 /tmp/x 2>&1 | head -1")}')
print(f'  default 里创建网卡 ip link add:{ex("caps-default", "ip link add d0 type dummy 2>&1 | head -1") or "成功"};add NET_ADMIN 里:{ex("caps-add", "ip link add d0 type dummy 2>&1 | head -1") or "成功"}')
print(f'  privileged 里 mount tmpfs:{ex("caps-priv", "mkdir -p /m && mount -t tmpfs t /m 2>&1 && echo 成功")};default 里:{ex("caps-default", "mkdir -p /m && mount -t tmpfs t /m 2>&1 | head -1")}')
k('apply', '-f', '-', input=pod('port80-user', sc='  securityContext: {runAsUser: 1000}\n', csc='    securityContext: {capabilities: {drop: [ALL]}}\n', cmd='[sh, -c, "timeout 2 nc -l -p 80; echo \\"nc 退出码 $?\\"; sleep 3600"]'))
up_('port80-user'); time.sleep(3)
rc, o = k('logs', 'port80-user', '-n', NS); print(f'  非 root(uid 1000)+ drop ALL,监听 80 端口:{o.strip().splitlines()[-1] if o.strip() else "?"}(nc 退出码 143 表示被 timeout 终止=监听成功;1 才是失败)')
print(f'    该节点上 net.ipv4.ip_unprivileged_port_start={ex("port80-user", "cat /proc/sys/net/ipv4/ip_unprivileged_port_start")}(容器运行时把它设成了 0,所以不需要 NET_BIND_SERVICE)')

print('== 三:allowPrivilegeEscalation 与 readOnlyRootFilesystem')
k('apply', '-f', '-', input=pod('noesc', csc='    securityContext: {allowPrivilegeEscalation: false}\n') + pod('ro', csc='    securityContext: {readOnlyRootFilesystem: true}\n', vols=VOL, vm=VM))
up_('noesc', 'ro')
print(f'  默认:NoNewPrivs={ex("caps-default", "grep NoNewPrivs /proc/1/status | awk \'{print $2}\'")};allowPrivilegeEscalation=false:NoNewPrivs={ex("noesc", "grep NoNewPrivs /proc/1/status | awk \'{print $2}\'")}')
print(f'  readOnlyRootFilesystem:写 /tmp → {ex("ro", "touch /tmp/x 2>&1 | head -1")};写挂载的卷 /data → {ex("ro", "touch /data/x 2>&1 && echo 成功")}')

print('== 四:runAsNonRoot——镜像是 root 就根本起不来')
k('apply', '-f', '-', input=pod('nonroot', csc='    securityContext: {runAsNonRoot: true}\n') + pod('nonroot-uid', sc='  securityContext: {runAsNonRoot: true, runAsUser: 1000}\n')); time.sleep(8)
p = kj('get', 'pod', 'nonroot', '-n', NS); w = (p['status'].get('containerStatuses') or [{}])[0].get('state', {}).get('waiting', {})
print(f'  runAsNonRoot: true,但 busybox 镜像默认是 root:phase={p["status"]["phase"]};容器状态 {w.get("reason")}:{w.get("message", "")[:120]}')
print(f'  runAsNonRoot: true + runAsUser: 1000:phase={kj("get", "pod", "nonroot-uid", "-n", NS)["status"]["phase"]};id → {ex("nonroot-uid", "id")}')
k('delete', 'ns', NS, '--wait=false')
