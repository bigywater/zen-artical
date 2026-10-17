import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c50')
img('alpine:3.20')
purge()
def aliases(n, net): return out('inspect', '--format', '{{json (index .NetworkSettings.Networks "%s").Aliases}}' % net, n)
def resolve(frm, name):
    rc, o = dk('exec', frm, 'nslookup', name)
    return [l.split()[-1] for l in o.splitlines() if l.startswith('Address') and '#' not in l], rc
for net in ('bwlab-c50n1', 'bwlab-c50n2'): dk('network', 'create', '--label', 'bwlab=1', net)
print('== 一:容器在网络里的别名(Docker Engine 29.8.2)')
dk('run', '-d', '--name', 'bwlab-c50a', *LAB, '--network', 'bwlab-c50n1', '--network-alias', 'web', '--network-alias', 'www', 'alpine:3.20', 'sleep', '300')
cid = out('inspect', '--format', '{{.Id}}', 'bwlab-c50a')[:12]
print(f'  --network-alias web --network-alias www 的容器,Aliases = {aliases("bwlab-c50a", "bwlab-c50n1")}(容器 ID 前 12 位是 {cid})')
dk('run', '-d', '--name', 'bwlab-c50plain', *LAB, '--network', 'bwlab-c50n1', 'alpine:3.20', 'sleep', '300')
print(f'  不带 --network-alias 的容器 Aliases = {aliases("bwlab-c50plain", "bwlab-c50n1")}')
print(f'  默认 bridge 上的容器 Aliases = ' + (lambda: (dk("run", "-d", "--name", "bwlab-c50def", *LAB, "alpine:3.20", "sleep", "300"), aliases("bwlab-c50def", "bridge"))[1])())
print('== 二:别名按网络生效')
dk('network', 'connect', '--alias', 'api', 'bwlab-c50n2', 'bwlab-c50a')
print(f'  docker network connect --alias api bwlab-c50n2:n1 里的 Aliases = {aliases("bwlab-c50a", "bwlab-c50n1")};n2 里的 Aliases = {aliases("bwlab-c50a", "bwlab-c50n2")}')
dk('run', '-d', '--name', 'bwlab-c50b', *LAB, '--network', 'bwlab-c50n2', 'alpine:3.20', 'sleep', '300')
for frm, nm in (('bwlab-c50plain', 'web'), ('bwlab-c50plain', 'api'), ('bwlab-c50b', 'api'), ('bwlab-c50b', 'web')):
    a, rc = resolve(frm, nm)
    print(f'  {frm.replace("bwlab-c50", "")}(在 {"n1" if frm == "bwlab-c50plain" else "n2"})解析 {nm}:' + (str(a[1:]) if a and rc == 0 else '解析失败'))
print('== 三:几个容器共用一个别名')
for i in (1, 2, 3):
    dk('run', '-d', '--name', f'bwlab-c50s{i}', *LAB, '--network', 'bwlab-c50n1', '--network-alias', 'db', 'alpine:3.20', 'sleep', '300')
ips = sorted(out('inspect', '--format', '{{(index .NetworkSettings.Networks "bwlab-c50n1").IPAddress}}', f'bwlab-c50s{i}') for i in (1, 2, 3))
a, rc = resolve('bwlab-c50plain', 'db')
print(f'  3 个容器的 IP:{ips};解析别名 db 得到:{sorted(a[1:])}')
seen = []
for _ in range(6):
    a, rc = resolve('bwlab-c50plain', 'db'); seen.append(a[1] if len(a) > 1 else '-')
print(f'  连续 6 次解析,返回的第一个地址:{seen}')
print('== 四:断开网络之后别名消失')
dk('network', 'disconnect', 'bwlab-c50n2', 'bwlab-c50a')
a, rc = resolve('bwlab-c50b', 'api'); print(f'  docker network disconnect 后,n2 里解析 api:' + (str(a[1:]) if a and rc == 0 else '解析失败'))
dk('rm', '-f', 'bwlab-c50s2')
a, rc = resolve('bwlab-c50plain', 'db'); print(f'  删掉 s2 之后,解析 db 得到:{sorted(a[1:])}')
purge()
