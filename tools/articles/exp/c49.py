import sys, os, re, time, subprocess, json, socket, urllib.request; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c49')
img('python:3.12-alpine')
purge()
SERVE = '''import http.server,socketserver,sys,socket
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"hello from container\\n")
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address=True
import threading
def udp():
    u=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.bind(("0.0.0.0",9000))
    while True:
        d,a=u.recvfrom(100); u.sendto(b"udp-echo:"+d,a)
threading.Thread(target=udp,daemon=True).start()
socketserver.TCPServer(("0.0.0.0",8000),H).serve_forever()'''
d = ctx('c49', {'s.py': SERVE, 'Dockerfile': 'FROM python:3.12-alpine\nEXPOSE 8000/tcp 9000/udp\nCOPY s.py /s.py\nCMD ["python","-u","/s.py"]\n'})
rc, o = build(d, 'bwlab-c49', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def get(url):
    try:
        return urllib.request.urlopen(url, timeout=3).read().decode().strip()
    except Exception as e: return type(e).__name__ + ':' + str(getattr(e, 'reason', e))[:50]
lan = None
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('10.255.255.255', 1)); lan = s.getsockname()[0]; s.close()
except Exception: pass
P1, P2 = free_port(9780), free_port(9790)
print('== 一:-p 的几种写法(Docker Engine 29.8.2,macOS 上访问)')
dk('run', '-d', '--name', 'bwlab-c49a', *LAB, '-p', f'{P1}:8000', 'bwlab-c49'); time.sleep(1.2)
dk('run', '-d', '--name', 'bwlab-c49b', *LAB, '-p', f'127.0.0.1:{P2}:8000', 'bwlab-c49'); time.sleep(1.2)
print(f'  -p {P1}:8000:docker port → {out("port", "bwlab-c49a", "8000")};docker ps 的 PORTS 列 → {out("ps", "--filter", "name=bwlab-c49a", "--format", "{{.Ports}}")}')
print(f'    Mac 访问 127.0.0.1:{P1} → {get(f"http://127.0.0.1:{P1}/")}')
print(f'    Mac 用局域网地址访问 <本机局域网IP>:{P1} → {get(f"http://{lan}:{P1}/") if lan else "(没有局域网地址)"}')
print(f'  -p 127.0.0.1:{P2}:8000:docker port → {out("port", "bwlab-c49b", "8000")}')
print(f'    Mac 访问 127.0.0.1:{P2} → {get(f"http://127.0.0.1:{P2}/")}')
print(f'    Mac 用局域网地址访问 <本机局域网IP>:{P2} → {get(f"http://{lan}:{P2}/") if lan else "(没有局域网地址)"}')
print('== 二:-P(大写)把 EXPOSE 的端口映射到随机端口')
dk('run', '-d', '--name', 'bwlab-c49c', *LAB, '-P', 'bwlab-c49'); time.sleep(1.2)
pc = out('port', 'bwlab-c49c')
print(f'  docker port → {pc.replace(chr(10), " ; ")}')
hp = re.search(r'8000/tcp -> [\d.:\[\]]*:(\d+)', pc).group(1)
print(f'  随机的宿主机端口 {hp}(落在 32768 以上吗?{int(hp) >= 32768}),Mac 访问 → {get(f"http://127.0.0.1:{hp}/")}')
print('== 三:UDP 端口映射')
P3 = free_port(9800)
dk('run', '-d', '--name', 'bwlab-c49d', *LAB, '-p', f'{P3}:9000/udp', 'bwlab-c49'); time.sleep(1.2)
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.settimeout(3); u.sendto(b'ping', ('127.0.0.1', P3))
try: print(f'  Mac 发 UDP "ping" 到 127.0.0.1:{P3} → {u.recvfrom(100)[0].decode()}')
except Exception as e: print(f'  Mac 发 UDP 到 127.0.0.1:{P3} → {type(e).__name__}')
print(f'  只写 -p {P3}:9000(不带 /udp)时 docker port → ' + (lambda: (dk("run", "-d", "--name", "bwlab-c49e", *LAB, "-p", f"{free_port(9810)}:9000", "bwlab-c49"), out("port", "bwlab-c49e"))[1])())
print('== 四:Mac 上是谁在监听这个端口')
r = subprocess.run(['lsof', '-nP', f'-iTCP:{P1}', '-sTCP:LISTEN'], capture_output=True, text=True)
print('  lsof -iTCP:%d -sTCP:LISTEN:' % P1 + (' | '.join(' '.join(l.split()[:2]) for l in r.stdout.strip().splitlines()[1:]) or '(没有输出)'))
print(f'  虚拟机里有这个端口在监听吗?' + subprocess.run(['docker', 'run', '--rm', '--privileged', '--pid=host', 'alpine:3.20' if False else 'python:3.12-alpine', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', f'ss -ltn | grep :{P1} | head -1 | cut -c1-80'], capture_output=True, text=True).stdout.strip())
print('== 五:端口被占用时')
P4 = free_port(9820)
dk('run', '-d', '--name', 'bwlab-c49f', *LAB, '-p', f'{P4}:8000', 'bwlab-c49'); time.sleep(1)
rc, o = dk('run', '-d', '--name', 'bwlab-c49g', *LAB, '-p', f'{P4}:8000', 'bwlab-c49')
print(f'  同一个宿主机端口再映射一次:退出码 {rc};{[l for l in o.splitlines() if "docker:" in l][0][:140]}')
print(f'  失败的容器处于什么状态?{out("inspect", "--format", "{{.State.Status}}", "bwlab-c49g")}')
purge()
