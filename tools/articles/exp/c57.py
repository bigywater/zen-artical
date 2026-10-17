import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c57')
img('python:3.12-alpine', 'alpine:3.20')
purge()
def vm(cmd):
    rc, o = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', cmd, raw=True)
    return o.strip()
SRV = '''import http.server,socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
socketserver.TCPServer(("0.0.0.0",8000),H).serve_forever()'''
print('== 一:iptables nat 表里,docker 加了什么规则(Docker Engine 29.8.2)')
print('  虚拟机的 iptables 版本:' + vm('iptables -V'))
base = set(vm('iptables -t nat -S').splitlines())
masq = [l for l in base if '172.17.0.0/16' in l or 'docker0' in l]
print('  默认 bridge(docker0,172.17.0.0/16)相关的 nat 规则:'); [print('    ' + l) for l in sorted(masq)]
P = free_port(9830)
dk('run', '-d', '--name', 'bwlab-c57srv', *LAB, '-p', f'{P}:8000', 'python:3.12-alpine', 'python', '-u', '-c', SRV); time.sleep(1.2)
after = set(vm('iptables -t nat -S').splitlines())
new = sorted(after - base)
print(f'  发布端口 -p {P}:8000 之后,nat 表新增的规则:'); [print('    ' + l) for l in new]
sip = out('inspect', '--format', '{{.NetworkSettings.Networks.bridge.IPAddress}}', 'bwlab-c57srv')
print('  filter 表(FORWARD / DOCKER)里新增的与这个端口相关的规则:' + ' ; '.join(l for l in vm('iptables -S DOCKER').splitlines() if sip in l or str(P) in l) or '(没有)')
print('== 二:conntrack 表里,一次出站连接是怎么被转换的')
dk('run', '-d', '--name', 'bwlab-c57c', *LAB, 'alpine:3.20', 'sh', '-c', '(sleep 8) | nc -w 9 github.com 443'); time.sleep(3)
cip = out('inspect', '--format', '{{.NetworkSettings.Networks.bridge.IPAddress}}', 'bwlab-c57c')
ct = [l for l in vm('cat /proc/net/nf_conntrack').splitlines() if f'src={cip}' in l and 'dport=443' in l]
for l in ct[:2]:
    f = l.split()
    print('    ' + ' '.join(x for x in f if not x.startswith(('zone', 'use=', 'mark='))).replace(cip, '<容器IP>')[:260])
print('== 三:发布端口的流量走的是 DNAT 规则,还是别的路径')
import urllib.request
def cnt():
    for l in vm('iptables -t nat -L DOCKER -v -n -x').splitlines():
        if f'dpt:{P}' in l: return int(l.split()[0])
    return -1
c0 = cnt()
print(f'  虚拟机里谁在监听发布端口 {P}:' + vm(f"ss -ltnp | grep :{P} | awk '{{print $1, $4, $6}}'"))
for _ in range(3): urllib.request.urlopen(f'http://127.0.0.1:{P}/', timeout=5).read()
c1 = cnt()
print(f'  Mac 上 curl 127.0.0.1:{P} 3 次之后,DNAT 规则的包计数:{c0} → {c1}')
for _ in range(3): dk('run', '--rm', *LAB, 'alpine:3.20', 'sh', '-c', f'wget -q -O /dev/null -T 3 http://172.17.0.1:{P}/')
c2 = cnt()
print(f'  另一个容器经 172.17.0.1:{P} 访问 3 次之后,DNAT 规则的包计数:{c1} → {c2}')
print('== 四:conntrack 表的容量与超时')
print('  nf_conntrack_max = ' + vm('cat /proc/sys/net/netfilter/nf_conntrack_max') + ';当前 count 约 ' + vm('cat /proc/sys/net/netfilter/nf_conntrack_count') + '(虚拟机里还有其它容器的连接)')
for k in ('tcp_timeout_established', 'tcp_timeout_time_wait', 'udp_timeout', 'udp_timeout_stream'):
    print(f'  nf_conntrack_{k} = ' + vm(f'cat /proc/sys/net/netfilter/nf_conntrack_{k}') + ' 秒')
dk('rm', '-f', 'bwlab-c57c')
rm_after = set(vm('iptables -t nat -S').splitlines())
dk('rm', '-f', 'bwlab-c57srv'); time.sleep(1)
final = set(vm('iptables -t nat -S').splitlines())
print(f'  删除服务容器之后,刚才新增的 {len(new)} 条 nat 规则还在吗?' + ('还在' if any(n in final for n in new) else '都没了'))
purge()
