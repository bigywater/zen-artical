import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c52')
img('python:3.12-alpine', 'alpine:3.20')
purge()
def vm(cmd):
    rc, o = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', cmd, raw=True)
    return o.strip()
MSS = '''import socket,sys
s=socket.create_connection((sys.argv[1],int(sys.argv[2])),timeout=5)
print("MSS =", s.getsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG))'''
SRV = '''import socket
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("0.0.0.0",7000)); s.listen(5)
while True:
    c,_=s.accept(); c.close()'''
print('== 一:默认的 MTU(Docker Engine 29.8.2,Docker Desktop)')
print('  虚拟机 eth0 / docker0 的 MTU:' + vm('echo $(cat /sys/class/net/eth0/mtu) $(cat /sys/class/net/docker0/mtu)'))
print('  默认 bridge 的网络选项 com.docker.network.driver.mtu = ' + out('network', 'inspect', 'bridge', '--format', '{{index .Options "com.docker.network.driver.mtu"}}'))
print('  默认容器里 eth0 的 MTU = ' + dk('run', '--rm', 'alpine:3.20', 'cat', '/sys/class/net/eth0/mtu')[1].strip())
print('== 二:自定义网络设置 MTU')
for mtu in (1400, 1280):
    dk('network', 'create', '--label', 'bwlab=1', '-o', f'com.docker.network.driver.mtu={mtu}', f'bwlab-c52n{mtu}')
    nid = out('network', 'inspect', f'bwlab-c52n{mtu}', '--format', '{{.Id}}')[:12]
    cm = dk('run', '--rm', '--network', f'bwlab-c52n{mtu}', 'alpine:3.20', 'cat', '/sys/class/net/eth0/mtu')[1].strip()
    print(f'  -o com.docker.network.driver.mtu={mtu}:容器里 eth0 的 MTU = {cm};虚拟机里这个网络的网桥 br-{nid[:4]}… 的 MTU = ' + vm(f'cat /sys/class/net/br-{nid}/mtu'))
print('== 三:MTU 影响 TCP 的 MSS(两个容器之间建立连接,读 TCP_MAXSEG)')
d = ctx('c52', {'mss.py': MSS, 'srv.py': SRV, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY mss.py srv.py /\n'})
rc, o = build(d, 'bwlab-c52', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
for net, label in (('bridge', '默认 bridge(MTU 65535)'), ('bwlab-c52n1400', '自定义网络 MTU 1400'), ('bwlab-c52n1280', '自定义网络 MTU 1280')):
    n = 'bwlab-c52srv'
    dk('run', '-d', '--name', n, *LAB, '--network', net, 'bwlab-c52', 'python', '/srv.py'); time.sleep(1)
    ip = out('inspect', '--format', '{{(index .NetworkSettings.Networks "%s").IPAddress}}' % net, n)
    rc, o = dk('run', '--rm', *LAB, '--network', net, 'bwlab-c52', 'python', '/mss.py', ip, '7000')
    print(f'  {label}:两个容器之间的 TCP {o.strip()}')
    dk('rm', '-f', n)
purge()
