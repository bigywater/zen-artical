import sys, os, re, time, subprocess, json, threading, http.server, socketserver; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c51')
img('alpine:3.20')
purge()
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'hello from the Mac\n')
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
P1, P2 = free_port(9840), free_port(9850)
s1 = socketserver.TCPServer(('127.0.0.1', P1), H); s2 = socketserver.TCPServer(('0.0.0.0', P2), H)
for s in (s1, s2): threading.Thread(target=s.serve_forever, daemon=True).start()
def wget(frm_opts, host, port):
    rc, o = dk('run', '--rm', *LAB, *frm_opts, 'alpine:3.20', 'sh', '-c', f'wget -q -O - -T 3 http://{host}:{port}/ 2>&1 | head -1')
    return o.strip()
print('== 一:host.docker.internal 解析到哪里(Docker Engine 29.8.2,Docker Desktop on macOS)')
for name in ('host.docker.internal', 'gateway.docker.internal', 'kubernetes.docker.internal', 'no.such.name.internal'):
    rc, o = dk('run', '--rm', *LAB, 'alpine:3.20', 'nslookup', name)
    a = [l.split()[-1] for l in o.splitlines() if l.startswith('Address') and '#' not in l]
    print(f'  nslookup {name}:退出码 {rc};地址 {a if a else "无"}')
print('  容器里的 /etc/hosts 有 host.docker.internal 吗?' + dk('run', '--rm', 'alpine:3.20', 'sh', '-c', 'grep -c docker.internal /etc/hosts')[1].strip() + ' 行')
print('== 二:容器访问 Mac 上的服务')
print(f'  Mac 上监听 127.0.0.1:{P1} 的服务:容器访问 host.docker.internal:{P1} → {wget([], "host.docker.internal", P1)}')
print(f'  Mac 上监听 0.0.0.0:{P2} 的服务:容器访问 host.docker.internal:{P2} → {wget([], "host.docker.internal", P2)}')
print(f'  容器访问 127.0.0.1:{P1}(容器自己的回环)→ {wget([], "127.0.0.1", P1) or "(没有输出)"}')
dk('network', 'create', '--label', 'bwlab=1', 'bwlab-c51net')
print(f'  自定义网络里的容器访问 host.docker.internal:{P1} → {wget(["--network", "bwlab-c51net"], "host.docker.internal", P1)}')
print('== 三:--add-host host.docker.internal:host-gateway 与不加的对比')
rc, o = dk('run', '--rm', *LAB, '--add-host', 'host.docker.internal:host-gateway', 'alpine:3.20', 'sh', '-c', 'grep docker.internal /etc/hosts')
print(f'  加 --add-host host.docker.internal:host-gateway 后 /etc/hosts 里:{o.strip()}')
print(f'  这时访问 host.docker.internal:{P1} → {wget(["--add-host", "host.docker.internal:host-gateway"], "host.docker.internal", P1)}')
print('== 四:--network host 的容器')
print(f'  --network host 的容器访问 host.docker.internal:{P1} → {wget(["--network", "host"], "host.docker.internal", P1)}')
s1.shutdown(); s2.shutdown()
purge()
