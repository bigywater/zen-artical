import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c71')
img('alpine:3.20')
purge()
n = 'bwlab-c71'
dk('volume', 'create', '--label', 'bwlab=1', 'bwlab-c71v')
dk('run', '-d', '--name', n, *LAB, '-e', 'MODE=demo', '-p', '127.0.0.1:0:80', '-v', 'bwlab-c71v:/data', '--label', 'role=web', '--memory', '64m', 'alpine:3.20', 'sh', '-c', 'sleep 300')
time.sleep(1)
j = json.loads(out('inspect', n))[0]
print('== 一:docker inspect 的结构(Docker Engine 29.8.2)')
print(f'  容器 inspect 的顶层键({len(j)} 个):' + ' '.join(sorted(j.keys())))
for k in ('State', 'Config', 'HostConfig', 'NetworkSettings'):
    print(f'  {k} 下有 {len(j[k])} 个键')
print('  State 的键:' + ' '.join(sorted(j['State'].keys())))
ji = json.loads(out('inspect', 'alpine:3.20'))[0]
print(f'  镜像 inspect 的顶层键({len(ji)} 个):' + ' '.join(sorted(ji.keys())))
print('== 二:--format 的常用写法')
for label, f in (('进程 PID', '{{.State.Pid}}'), ('环境变量', '{{json .Config.Env}}'), ('标签', '{{json .Config.Labels}}'), ('挂载', '{{range .Mounts}}{{.Type}}:{{.Name}}->{{.Destination}} {{end}}'), ('端口映射', '{{json .NetworkSettings.Ports}}'), ('取端口 80/tcp 的第一个宿主机端口', '{{(index (index .NetworkSettings.Ports "80/tcp") 0).HostPort}}'), ('内存上限', '{{.HostConfig.Memory}}'), ('截取 ID 前 12 位', '{{printf "%.12s" .Id}}'), ('IP(bridge)', '{{(index .NetworkSettings.Networks "bridge").IPAddress}}')):
    o = out('inspect', '--format', f, n)
    print(f'  {label}:{f}  →  {o[:110]}'.replace(n, '<名>'))
rc, o = dk('inspect', '--format', '{{.NoSuchField}}', n); print(f'  不存在的字段:退出码 {rc};{o.strip().splitlines()[0][:130]}')
print('== 三:-s 显示可写层大小')
j0 = json.loads(out('inspect', '-s', n))[0]
dk('exec', n, 'sh', '-c', 'dd if=/dev/zero of=/w.bin bs=1M count=10 2>/dev/null; sync')
j1 = json.loads(out('inspect', '-s', n))[0]
print(f'  SizeRw:写 10 MiB 前 {j0.get("SizeRw")},写后 {j1.get("SizeRw")};SizeRootFs:{j0.get("SizeRootFs")} → {j1.get("SizeRootFs")}')
print(f'  不带 -s 时有 SizeRw 字段吗?{"SizeRw" in json.loads(out("inspect", n))[0]}')
print('== 四:同名的对象与 --type')
dk('tag', 'alpine:3.20', 'bwlab-c71-dup')
dk('create', '--name', 'bwlab-c71-dup', *LAB, 'alpine:3.20')
r = json.loads(out('inspect', 'bwlab-c71-dup'))
print(f'  容器和镜像都叫 bwlab-c71-dup(镜像是 docker tag 出来的):docker inspect bwlab-c71-dup 返回 {len(r)} 个对象,它是{"容器" if "State" in r[0] else "镜像"}')
print(f'  --type image:{out("inspect", "--type", "image", "--format", "{{.RepoTags}}", "bwlab-c71-dup")};--type container:{out("inspect", "--type", "container", "--format", "{{.Name}}", "bwlab-c71-dup")}')
rc, o = dk('inspect', 'no-such-thing'); print(f'  对象不存在:退出码 {rc};输出 {o.strip().splitlines()[-1][:90]}')
purge()
