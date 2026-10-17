import sys, os, re, time, subprocess, json, socket, http.client, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c76')
img('alpine:3.20')
purge()
SOCK = os.path.expanduser('~/.docker/run/docker.sock')
class U(http.client.HTTPConnection):
    def __init__(self): super().__init__('localhost'); 
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX); self.sock.connect(SOCK)
def api(method, path, body=None, timeout=30):
    c = U(); c.timeout = timeout
    h = {'Content-Type': 'application/json'} if body is not None else {}
    c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
    r = c.getresponse(); data = r.read(); hd = dict(r.getheaders()); c.close()
    return r.status, hd, data
print('== 一:Engine API 就是 unix socket 上的 HTTP(Docker Engine 29.8.2,Mac 上的 socket 路径 ~/.docker/run/docker.sock)')
st, h, b = api('GET', '/_ping'); print(f'  GET /_ping → {st};正文 {b.decode()!r};响应头 Api-Version = {h.get("Api-Version")},Docker-Experimental = {h.get("Docker-Experimental")},Ostype = {h.get("Ostype")}')
st, h, b = api('GET', '/version'); v = json.loads(b)
print(f'  GET /version → {st};Version={v["Version"]} ApiVersion={v["ApiVersion"]} MinAPIVersion={v["MinAPIVersion"]} Os={v["Os"]} Arch={v["Arch"]} GoVersion={v["GoVersion"]}')
st, h, b = api('GET', '/info'); inf = json.loads(b); print(f'  GET /info → {st};{len(inf)} 个顶层字段;NCPU={inf["NCPU"]} Containers={inf["Containers"]} Driver={inf["Driver"]} CgroupVersion={inf.get("CgroupVersion")}')
print('== 二:用 API 创建、启动、读日志、删除一个容器')
st, h, b = api('POST', '/containers/create?name=bwlab-c76', {'Image': 'alpine:3.20', 'Cmd': ['sh', '-c', 'echo hello-from-api; echo err-from-api >&2'], 'Labels': {'bwlab': '1'}})
cid = json.loads(b).get('Id', '')
print(f'  POST /containers/create → {st};返回 Id = {cid[:12]}…(共 {len(cid)} 个字符);Warnings = {json.loads(b).get("Warnings")}')
st, h, b = api('POST', f'/containers/{cid}/start'); print(f'  POST /containers/<id>/start → {st}(无正文:{len(b)} 字节)')
st, h, b = api('POST', f'/containers/{cid}/wait'); print(f'  POST /containers/<id>/wait → {st};{b.decode().strip()}')
st, h, b = api('GET', f'/containers/{cid}/logs?stdout=1&stderr=1')
print(f'  GET /containers/<id>/logs → {st};Content-Type = {h.get("Content-Type")};正文 {len(b)} 字节;前 16 字节(十六进制):{b[:16].hex(" ")}')
frames = []; i = 0
while i + 8 <= len(b):
    t, ln = b[i], struct.unpack('>I', b[i + 4:i + 8])[0]; frames.append(({1: 'stdout', 2: 'stderr'}.get(t, t), b[i + 8:i + 8 + ln].decode().strip())); i += 8 + ln
print(f'  按 8 字节帧头拆开:{frames}')
st, h, b = api('GET', f'/containers/{cid}/json'); j = json.loads(b); print(f'  GET /containers/<id>/json → {st};State.Status={j["State"]["Status"]} ExitCode={j["State"]["ExitCode"]}')
st, h, b = api('DELETE', f'/containers/{cid}'); print(f'  DELETE /containers/<id> → {st}')
st, h, b = api('GET', f'/containers/{cid}/json'); print(f'  再 GET → {st};{json.loads(b)}')
print('== 三:API 版本号写在路径里')
for ver in ('v1.40', 'v1.24', 'v1.12', 'v1.54', 'v9.99'):
    st, h, b = api('GET', f'/{ver}/containers/json'); print(f'  GET /{ver}/containers/json → {st};{b.decode().strip()[:110] if st != 200 else "返回 " + str(len(json.loads(b))) + " 个容器"}')
print('== 四:docker CLI 发出的就是这些请求吗?用一个代理 socket 转发并记录')
import threading, tempfile
tmp = tempfile.mkdtemp(); psock = os.path.join(tmp, 'p.sock'); reqs = []
srv = socket.socket(socket.AF_UNIX); srv.bind(psock); srv.listen(5)
def pump(a, b_, log=None):
    try:
        while True:
            d = a.recv(65536)
            if not d: break
            if log is not None:
                for ln in re.findall(rb'(?m)^(?:GET|POST|HEAD|DELETE|PUT) \S+ HTTP/1\.1', d): log.append(ln.decode(errors='replace'))
            b_.sendall(d)
    except Exception: pass
    try: b_.shutdown(socket.SHUT_WR)
    except Exception: pass
def serve():
    while True:
        try: c, _ = srv.accept()
        except Exception: return
        u = socket.socket(socket.AF_UNIX); u.connect(SOCK)
        line = []
        threading.Thread(target=pump, args=(c, u, line), daemon=True).start(); threading.Thread(target=pump, args=(u, c), daemon=True).start()
        reqs.append(line)
threading.Thread(target=serve, daemon=True).start()
r = subprocess.run(['docker', '-H', f'unix://{psock}', 'run', '--rm', *LAB, 'alpine:3.20', 'echo', 'via-proxy'], capture_output=True, text=True, timeout=120)
time.sleep(0.5)
print(f'  docker -H unix://<代理> run --rm alpine echo via-proxy:输出 {r.stdout.strip()!r}')
seen = [x for l in reqs for x in l]
print(f'  代理记录到 {len(reqs)} 个连接、共 {len(seen)} 个请求(按连接分组列出,不严格按时间):')
for l in seen: print('    ' + re.sub(r'[0-9a-f]{64}', '<64位ID>', l)[:110])
srv.close(); shutil.rmtree(tmp, ignore_errors=True)
purge()
