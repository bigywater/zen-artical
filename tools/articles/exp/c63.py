import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c63')
img('alpine:3.20')
purge()
P = 'bwlab-c63'
def comp(d, *args, timeout=180):
    r = subprocess.run(['docker', 'compose', '-p', P, '-f', str(d / 'compose.yaml'), *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, tidy(r.stdout + r.stderr)
def names(svc='worker'):
    return sorted(n.replace(P + '-', '') for n in out('ps', '-a', '--filter', f'name={P}-{svc}', '--format', '{{.Names}}').split())
def ids(svc='worker'):
    return {n.replace(P + '-', ''): out('inspect', '--format', '{{.Id}}', n)[:6] for n in out('ps', '-a', '--filter', f'name={P}-{svc}', '--format', '{{.Names}}').split()}
Y = '''services:
  worker:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 300
  client:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 300
'''
d = ctx('c63', {'compose.yaml': Y})
print('== 一:--scale 扩缩容(Docker Compose v5.5.1)')
comp(d, 'up', '-d', '--scale', 'worker=3'); i3 = ids(); print(f'  up -d --scale worker=3:{sorted(i3)}')
comp(d, 'up', '-d', '--scale', 'worker=1'); i1 = ids(); print(f'  再 --scale worker=1:剩下 {sorted(i1)};被保留的 worker-1 是原来那个吗?{i1.get("worker-1") == i3.get("worker-1")}')
comp(d, 'up', '-d', '--scale', 'worker=3'); i33 = ids(); print(f'  再 --scale worker=3:{sorted(i33)};worker-1 仍是原来的?{i33.get("worker-1") == i3.get("worker-1")};worker-2 是新建的(ID 变了)吗?{i33.get("worker-2") != i3.get("worker-2")}')
print('== 二:DNS 解析服务名得到所有副本')
r = dk('exec', f'{P}-client-1', 'nslookup', 'worker')[1]
addrs = sorted(l.split()[-1] for l in r.splitlines() if l.startswith('Address') and ':53' not in l)
real = sorted(out('inspect', '--format', '{{(index .NetworkSettings.Networks "bwlab-c63_default").IPAddress}}', n) for n in out('ps', '--filter', f'name={P}-worker', '--format', '{{.Names}}').split())
print(f'  client 解析 worker 得到 {addrs};3 个副本的真实 IP {real};一致吗?{addrs == real}')
comp(d, 'down', '-v', '-t', '1')
print('== 三:deploy.replicas')
Y2 = Y.replace('    command: sleep 300\n  client', '    command: sleep 300\n    deploy:\n      replicas: 2\n  client', 1)
d2 = ctx('c63b', {'compose.yaml': Y2})
comp(d2, 'up', '-d'); print(f'  deploy.replicas: 2,docker compose up -d:{names()}')
rc, o = comp(d2, 'up', '-d', '--scale', 'worker=4'); print(f'  命令行 --scale worker=4 覆盖 replicas:{names()}')
comp(d2, 'down', '-v', '-t', '1')
print('== 四:带端口映射时扩容')
for label, ports in (('固定宿主机端口 "9941:80"', '"9941:80"'), ('端口范围 "9942-9944:80"', '"9942-9944:80"'), ('只写容器端口 "80"', '"80"')):
    Y3 = Y.replace('    command: sleep 300\n  client', f'    command: sleep 300\n    ports: [{ports}]\n  client', 1)
    d3 = ctx('c63c', {'compose.yaml': Y3})
    rc, o = comp(d3, 'up', '-d', '--scale', 'worker=2')
    err = next((l.strip() for l in o.splitlines() if 'port' in l.lower() and ('allocated' in l.lower() or 'bind' in l.lower() or 'failed' in l.lower())), '')
    print(f'  {label} --scale worker=2:退出码 {rc};运行中的副本 {sorted(n for n in names() if out("inspect", "--format", "{{.State.Status}}", P + "-" + n) == "running")};{err[:110]}')
    comp(d3, 'down', '-v', '-t', '1')
print('== 五:container_name 与扩容')
Y4 = Y.replace('    image: alpine:3.20\n    labels: {bwlab: "1"}\n    command: sleep 300\n  client', '    image: alpine:3.20\n    container_name: bwlab-c63-fixed\n    labels: {bwlab: "1"}\n    command: sleep 300\n  client', 1)
d4 = ctx('c63d', {'compose.yaml': Y4})
rc, o = comp(d4, 'up', '-d', '--scale', 'worker=2'); print(f'  worker 设了 container_name,--scale worker=2:退出码 {rc};{o.strip().splitlines()[-1][:140]}')
comp(d4, 'down', '-v', '-t', '1')
purge()
