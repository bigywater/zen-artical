import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c86')
img('alpine:3.20', 'docker:dind')
purge()
N = 'bwlab-dind86'
def inner(cmd, timeout=120, ct=N):
    r = subprocess.run(['docker', 'exec', ct, 'sh', '-c', cmd], capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()
outer_n = len(out('ps', '-q').split())
print('== 一:Docker-in-Docker:容器里起一个自己的 dockerd(Docker Engine 29.8.2,镜像 docker:dind,版本见下)')
dk('run', '-d', '--name', N, *LAB, '--privileged', '--entrypoint', 'sh', 'docker:dind', '-c', 'sleep 3600'); time.sleep(1)
t0 = time.time()
inner('(dockerd > /tmp/dockerd.log 2>&1 &)')
for _ in range(120):
    if inner('docker info >/dev/null 2>&1')[0] == 0: break
    time.sleep(0.5)
ready = time.time() - t0
rc, o = inner('docker info --format "{{.ServerVersion}} storage={{.Driver}} cgroup={{.CgroupVersion}} containers={{.Containers}} images={{.Images}}"')
print(f'  不指定存储驱动直接起 dockerd,{ready:.1f} 秒后就绪:{o}')
print('  嵌套 dockerd 的启动日志里选存储驱动的行:' + ' | '.join(l[-110:] for l in inner('grep -i -E "storage|snapshotter|overlay" /tmp/dockerd.log | head -3')[1].splitlines()))
print(f'  外层 Docker 的容器数 {outer_n};嵌套的 docker ps 看到的容器数:{len(inner("docker ps -q")[1].split())}(嵌套的 docker 看不到外层的任何容器)')
p = subprocess.run(f'docker save alpine:3.20 | docker exec -i {N} docker load', shell=True, capture_output=True, text=True)
print('  嵌套的镜像库一开始是空的,需要自己 load/pull;load 之后:' + inner('docker images --format "{{.Repository}}:{{.Tag}}"')[1])
rc, o = inner('docker run -d --name inner1 alpine:3.20 sleep 120 && docker ps --format "{{.Names}} {{.Status}}"')
print('  嵌套里运行一个容器:' + o.replace('\n', ' '))
print('  外层 docker ps 能看到 inner1 吗?' + ('能' if 'inner1' in out('ps', '--format', '{{.Names}}') else '不能(它只存在于嵌套的 dockerd 里)'))
print('  嵌套容器的主进程在外层容器(dind 容器)里的进程列表中:' + inner('ps -o pid,args | grep "sleep 120" | grep -v grep | head -1')[1])
inner('docker rm -f inner1 >/dev/null 2>&1')
print('== 二:挂载宿主 socket(Docker-outside-of-Docker):共用同一个 dockerd')
dk('rm', '-f', N)
S2 = 'bwlab-dood86'
rc, o = dk('run', '-d', '--name', S2, *LAB, '-v', '/var/run/docker.sock:/var/run/docker.sock', '--entrypoint', 'sh', 'docker:dind', '-c', 'sleep 600')
print(f'  docker run -v /var/run/docker.sock:/var/run/docker.sock:退出码 {rc}')
time.sleep(1)
cnt = len(inner('docker ps -q', ct=S2)[1].split())
print(f'  这个容器里的 docker ps -q 看到 {cnt} 个容器;外层 docker ps -q 是 {len(out("ps", "-q").split())} 个——看到的是同一个 dockerd 管的所有容器(含 Docker Desktop 里别的项目的)')
print('  docker info 的 Name / ServerVersion / Driver:' + inner('docker info --format "{{.Name}} {{.ServerVersion}} {{.Driver}}"', ct=S2)[1])
rc, o = inner('docker run -d --name sibling86 --label bwlab=1 alpine:3.20 sleep 60', ct=S2)
print(f'  在容器里 docker run 一个 sibling86:退出码 {rc}')
print('  外层 docker ps 能看到 sibling86 吗?' + ('能(它是外层 dockerd 的兄弟容器,不是子容器)' if 'sibling86' in out('ps', '--format', '{{.Names}}') else '不能'))
dk('rm', '-f', 'sibling86', S2)
print('== 三:不加 --privileged 能起嵌套的 dockerd 吗')
N3 = 'bwlab-dind86np'
dk('run', '-d', '--name', N3, *LAB, '--entrypoint', 'sh', 'docker:dind', '-c', 'sleep 600'); time.sleep(1)
inner('(dockerd > /tmp/dockerd.log 2>&1 &)', ct=N3)
ok = False
for _ in range(30):
    if inner('docker info >/dev/null 2>&1', ct=N3)[0] == 0: ok = True; break
    time.sleep(0.5)
print(f'  不加 --privileged:15 秒内 dockerd 就绪了吗?{ok};dockerd 日志最后几行:' + ' | '.join(l[-130:] for l in inner('tail -3 /tmp/dockerd.log', ct=N3)[1].splitlines()))
print(f'  对比:DooD 不加 --privileged 就能用(上一节);DinD 在上一节用了 --privileged,嵌套 dockerd {ready:.1f} 秒就绪。')
dk('rm', '-f', N3)
purge()
