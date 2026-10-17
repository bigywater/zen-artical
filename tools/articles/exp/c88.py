import sys, os, re, time, subprocess, json, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c88')
img('python:3.12-alpine')
purge()
SRV = '''import http.server,socketserver,socket
H = socket.gethostname()
class R(http.server.BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.send_header("Connection","close"); self.end_headers(); self.wfile.write(H.encode())
    def log_message(self,*a): pass
socketserver.ThreadingTCPServer.allow_reuse_address=True
socketserver.ThreadingTCPServer(("0.0.0.0",8000),R).serve_forever()'''
CLI = '''import socket,sys,urllib.request,collections,time,json
mode=sys.argv[1]; n=int(sys.argv[2])
if mode=="new":
    c=collections.Counter(); err=0
    for _ in range(n):
        try: c[urllib.request.urlopen("http://svc:8000/",timeout=2).read().decode()]+=1
        except Exception: err+=1
    print(json.dumps({"counts":sorted(c.values(),reverse=True),"names":len(c),"errors":err}))
elif mode=="order":
    seq=[]
    for _ in range(n):
        seq.append(socket.getaddrinfo("svc",8000,socket.AF_INET,socket.SOCK_STREAM)[0][4][0].split(".")[-1])
    print(" ".join(seq))
elif mode=="all":
    print(" ".join(sorted(a[4][0].split(".")[-1] for a in socket.getaddrinfo("svc",8000,socket.AF_INET,socket.SOCK_STREAM))))
elif mode=="use":
    ip=sys.argv[3]; c=collections.Counter(); err=0
    for _ in range(n):
        try: c[urllib.request.urlopen("http://%s:8000/"%ip,timeout=1).read().decode()]+=1
        except Exception: err+=1
    print(json.dumps({"counts":sorted(c.values(),reverse=True),"errors":err}))
elif mode=="cached":
    ip=socket.gethostbyname("svc"); c=collections.Counter(); err=0
    for _ in range(n):
        try: c[urllib.request.urlopen("http://%s:8000/"%ip,timeout=2).read().decode()]+=1
        except Exception: err+=1
    print(json.dumps({"ip_last_octet":ip.split(".")[-1],"counts":sorted(c.values(),reverse=True),"errors":err}))'''
d = ctx('c88', {'srv.py': SRV, 'cli.py': CLI, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY srv.py cli.py /\n'})
rc, o = build(d, 'bwlab-c88', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
dk('network', 'create', '--label', 'bwlab=1', 'bwlab-c88net')
for i in (1, 2, 3):
    dk('run', '-d', '--name', f'bwlab-c88s{i}', *LAB, '--network', 'bwlab-c88net', '--network-alias', 'svc', 'bwlab-c88', 'python', '-u', '/srv.py')
time.sleep(2)
ips = {i: out('inspect', '--format', '{{(index .NetworkSettings.Networks "bwlab-c88net").IPAddress}}', f'bwlab-c88s{i}').split('.')[-1] for i in (1, 2, 3)}
def cli(*a):
    rc, o = dk('run', '--rm', *LAB, '--network', 'bwlab-c88net', 'bwlab-c88', 'python', '/cli.py', *a, timeout=180); return o.strip().splitlines()[-1]
print('== 一:三个容器共用别名 svc,解析一次得到什么(Docker Engine 29.8.2)')
print(f'  三个后端的 IP 末段:{ips};getaddrinfo("svc") 返回的全部地址末段(排序后):{cli("all", "1")}')
print('== 二:连续解析 20 次,返回的第一个地址是谁(顺序规律)')
print(f'  第一个地址的末段序列:{cli("order", "20")}')
print('== 三:每次请求都重新解析并新建连接:300 个请求分给三个后端')
r = json.loads(cli('new', '300')); print(f'  各后端收到的请求数(从多到少):{r["counts"]};不同的响应者 {r["names"]} 个;错误 {r["errors"]}')
print('== 四:客户端只解析一次(缓存),之后一直用同一个 IP')
r = json.loads(cli('cached', '300')); print(f'  解析一次得到的 IP 末段 {r["ip_last_octet"]};300 个请求各后端收到:{r["counts"]};错误 {r["errors"]}')
print('== 五:停掉一个后端之后')
dk('stop', '-t', '1', 'bwlab-c88s2')
print(f'  解析 svc 得到的地址末段:{cli("all", "1")}(停掉的是末段 {ips[2]})')
r = json.loads(cli('new', '120')); print(f'  每次重新解析的客户端 120 个请求:各后端收到 {r["counts"]},错误 {r["errors"]}')
dead_ip = out('inspect', '--format', '{{(index .NetworkSettings.Networks "bwlab-c88net").IPAddress}}', 'bwlab-c88s2') or ('172.' + '?')
net_prefix = out('inspect', '--format', '{{(index .NetworkSettings.Networks "bwlab-c88net").IPAddress}}', 'bwlab-c88s1').rsplit('.', 1)[0]
dead = f'{net_prefix}.{ips[2]}'
t0 = time.time(); r = json.loads(cli('use', '20', dead)); print(f'  早先缓存了那个已停止后端的 IP 的客户端(模拟):20 个请求,各后端收到 {r["counts"]},错误 {r["errors"]}(20 个请求总共用时 {time.time() - t0:.1f} 秒,含启动容器的开销)')
purge()
