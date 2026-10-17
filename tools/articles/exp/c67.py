import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c67')
img('alpine:3.20', 'python:3.12-alpine')
purge()
RECV = '''import socket,sys,json,zlib,gzip
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.bind(("127.0.0.1",int(sys.argv[1]))); s.settimeout(float(sys.argv[2]))
n=0
try:
    while True:
        d,a=s.recvfrom(65535); n+=1
        try: t=gzip.decompress(d).decode() if d[:2]==b"\\x1f\\x8b" else (zlib.decompress(d).decode() if d[:1]==b"\\x78" else d.decode(errors="replace"))
        except Exception: t=d.decode(errors="replace")
        print("PKT", t.replace("\\n"," ⏎ ")[:400], flush=True)
except socket.timeout:
    print("共收到 %d 个 UDP 包" % n, flush=True)'''
d = ctx('c67', {'r.py': RECV, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY r.py /r.py\nENTRYPOINT ["python","-u","/r.py"]\n'})
rc, o = build(d, 'bwlab-c67', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
print('== 一:这个 Docker 有哪些日志驱动(Docker Engine 29.8.2)')
print('  docker info 的 Plugins.Log = ' + out('info', '--format', '{{.Plugins.Log}}'))
print('== 二:--log-driver none')
n = 'bwlab-c67a'
dk('run', '-d', '--name', n, *LAB, '--log-driver', 'none', 'alpine:3.20', 'sh', '-c', 'echo hello-none; sleep 30'); time.sleep(1)
rc, o = dk('logs', n); print(f'  docker logs 退出码 {rc};{o.strip()[:120]}')
dk('rm', '-f', n)
print('== 三:发送到 UDP 接收端的 gelf 与 syslog(接收端是 --network host 的容器,即虚拟机的 127.0.0.1)')
P = free_port(9860)
def recv(secs=6):
    rn = f'bwlab-c67r{P}'
    dk('rm', '-f', rn)
    dk('run', '-d', '--name', rn, *LAB, '--network', 'host', 'bwlab-c67', str(P), str(secs)); time.sleep(1)
    return rn
for drv, opts in (('gelf', ['--log-opt', f'gelf-address=udp://127.0.0.1:{P}']), ('syslog', ['--log-opt', f'syslog-address=udp://127.0.0.1:{P}', '--log-opt', 'syslog-format=rfc5424', '--log-opt', 'tag=c67-demo'])):
    rn = recv(6)
    n = 'bwlab-c67-' + drv
    rc, o = dk('run', '-d', '--name', n, *LAB, '--log-driver', drv, *opts, 'alpine:3.20', 'sh', '-c', f'echo hello-{drv}; echo err-{drv} >&2; sleep 20')
    print(f'  --log-driver {drv}:docker run 退出码 {rc}')
    time.sleep(7)
    r = dk('logs', rn)[1].strip().splitlines()
    print(f'    接收端:{r[-1]}')
    for l in r[:-1][:2]: print('    ' + l[:330])
    rc, o = dk('logs', n); print(f'    docker logs {n}:退出码 {rc};{o.strip().replace(chr(10), " ⏎ ")[:120]}')
    dk('rm', '-f', n, rn)
print('== 四:目标不可达时')
n = 'bwlab-c67-bad'
rc, o = dk('run', '-d', '--name', n, *LAB, '--log-driver', 'gelf', '--log-opt', 'gelf-address=tcp://127.0.0.1:1', 'alpine:3.20', 'echo', 'x')
print(f'  gelf-address=tcp://127.0.0.1:1(没人监听):docker run 退出码 {rc};{[l for l in o.splitlines() if "docker:" in l or "rror" in l][0][:200] if rc else "(成功)"}')
rc, o = dk('run', '-d', '--name', n + '2', *LAB, '--log-driver', 'gelf', '--log-opt', f'gelf-address=udp://127.0.0.1:{free_port(9870)}', 'alpine:3.20', 'sh', '-c', 'echo to-nowhere; sleep 5')
print(f'  gelf 用 UDP 发往没人监听的端口:docker run 退出码 {rc}(UDP 不需要对方在线)')
purge()
