import sys, os, re, time, subprocess, json, urllib.request; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c47')
img('python:3.12-alpine', 'alpine:3.20')
purge()
def vm(cmd):
    rc, o = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', cmd, raw=True)
    return o.strip()
print('== 一:--network host 看到的网络(Docker Engine 29.8.2,Docker Desktop on macOS)')
rc, o = dk('run', '--rm', *LAB, 'alpine:3.20', 'sh', '-c', 'ls /sys/class/net | tr "\\n" " "; echo; hostname'); L = o.strip().splitlines()
print(f'  默认容器的网卡:{L[0]};hostname = {L[1]}')
rc, o = dk('run', '--rm', *LAB, '--network', 'host', 'alpine:3.20', 'sh', '-c', 'ls /sys/class/net | tr "\\n" " " | cut -c1-200; hostname'); L = o.strip().splitlines()
print(f'  --network host 的容器的网卡:{L[0]};hostname = {L[1]}')
print(f'  虚拟机自己的网卡:{vm("ls /sys/class/net | tr '\\n' ' ' | cut -c1-200")};hostname = {vm("hostname")}')
c1 = dk('run', '--rm', *LAB, '--network', 'host', 'alpine:3.20', 'readlink', '/proc/self/ns/net')[1].strip()
c0 = dk('run', '--rm', *LAB, 'alpine:3.20', 'readlink', '/proc/self/ns/net')[1].strip()
print(f'  网络命名空间:默认容器 {c0};--network host 的容器 {c1};虚拟机 PID 1 的 {vm("readlink /proc/1/ns/net")}')
print('== 二:host 模式下 -p 端口映射')
rc, o = dk('run', '--rm', *LAB, '--network', 'host', '-p', '9711:80', 'alpine:3.20', 'true'); print(f'  --network host -p 9711:80:退出码 {rc};输出:{o.strip().splitlines()[0][:110] if o.strip() else "(无)"}')
print('== 三:在 host 模式容器里监听端口,谁能访问')
SERVE = 'import http.server,socketserver,sys\nsocketserver.TCPServer.allow_reuse_address=True\nh=http.server.SimpleHTTPRequestHandler\nwith socketserver.TCPServer(("0.0.0.0",int(sys.argv[1])),h) as s: print("listening",flush=True); s.serve_forever()'
P = free_port(9730 + int(time.time()) % 60)
n = 'bwlab-c47-h'
dk('run', '-d', '--name', n, *LAB, '--network', 'host', 'python:3.12-alpine', 'python', '-u', '-c', SERVE, str(P)); time.sleep(1.5)
print(f'  host 模式容器监听了 {P}:docker logs = {dk("logs", n)[1].strip()}')
print(f'  虚拟机里 ss 看到 {P} 在监听吗?{"是" if vm(f"ss -ltn | grep :{P}") else "否"}')
try:
    urllib.request.urlopen(f'http://127.0.0.1:{P}/', timeout=3); r = '成功'
except Exception as e: r = type(e).__name__ + ':' + str(e)[:60]
print(f'  Mac 宿主机 curl 127.0.0.1:{P}:{r}')
rc, o = dk('run', '--rm', *LAB, 'alpine:3.20', 'sh', '-c', f'wget -q -O /dev/null -T 3 http://172.17.0.1:{P}/ && echo 成功 || echo 失败')
print(f'  另一个默认 bridge 容器访问 172.17.0.1:{P}(虚拟机上 docker0 的地址):{o.strip()}')
print('== 四:两个 host 模式的容器绑定同一个端口')
n2 = 'bwlab-c47-h2'
rc, o = dk('run', '--name', n2, *LAB, '--network', 'host', 'python:3.12-alpine', 'python', '-u', '-c', SERVE, str(P))
print(f'  第二个 host 容器绑定同一个端口:退出码 {rc};{o.strip().splitlines()[-1][:100]}')
for nm in ('bwlab-c47-b1', 'bwlab-c47-b2'):
    dk('run', '-d', '--name', nm, *LAB, 'python:3.12-alpine', 'python', '-u', '-c', SERVE, '8000')
time.sleep(1.5)
print('  对比:两个默认 bridge 容器都监听容器内的 8000:' + ' / '.join(dk('logs', nm)[1].strip() for nm in ('bwlab-c47-b1', 'bwlab-c47-b2')))
purge()
