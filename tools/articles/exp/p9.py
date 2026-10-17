import sys, os, subprocess, select, base64, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, socket
tee('p9')
_orig = socket.getaddrinfo
socket.getaddrinfo = lambda host, *a, **k: _orig('127.0.0.1' if isinstance(host, str) and host.endswith('.test') else host, *a, **k)
d = pdir('p9'); CERT, KEY = make_cert(d, san='DNS:secure.example.test,IP:127.0.0.1')

class Proxy:
    """最小的转发代理:记录它能看到的一切。require_auth 不为空时要求 Proxy-Authorization。"""
    def __init__(self, require_auth=None):
        self.events = []; self.auth = require_auth
        self.srv = RawSrv(self.handle)
        self.url = f'http://127.0.0.1:{self.srv.port}'
    def __enter__(self): self.srv.__enter__(); return self
    def __exit__(self, *a): self.srv.stop()
    def handle(self, c, addr):
        raw = read_request(c)
        head, _, rest = raw.partition(b'\r\n\r\n')
        lines = head.decode('latin1').split('\r\n'); first = lines[0]
        hd = [tuple(l.split(': ', 1)) for l in lines[1:] if ': ' in l]
        ev = dict(first=first, hdrs=hd, c2s=0, s2c=0, c2s_head=b'')
        self.events.append(ev)
        if self.auth:
            pa = next((v for k, v in hd if k.lower() == 'proxy-authorization'), None)
            if pa != 'Basic ' + base64.b64encode(self.auth.encode()).decode():
                c.sendall(b'HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: Basic realm="p"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'); ev['status'] = 407; return
        method, target, _ = first.split(' ', 2)
        if method == 'CONNECT':
            host, port = target.rsplit(':', 1)
            o = socket.create_connection(('127.0.0.1', int(port)))
            c.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n'); ev['status'] = 200
            if rest: o.sendall(rest); ev['c2s'] += len(rest); ev['c2s_head'] += rest
            c.settimeout(None)
            socks = [c, o]
            while True:
                r, _, _ = select.select(socks, [], [], 2.0)
                if not r: break
                done = False
                for s in r:
                    data = s.recv(65536)
                    if not data: done = True; break
                    if s is c: o.sendall(data); ev['c2s'] += len(data); ev['c2s_head'] += data
                    else: c.sendall(data); ev['s2c'] += len(data)
                if done: break
            o.close()
        else:
            u = urllib.parse.urlsplit(target)
            o = socket.create_connection(('127.0.0.1', u.port or 80))
            path = (u.path or '/') + ('?' + u.query if u.query else '')
            fwd = [f'{method} {path} HTTP/1.1'] + [f'{k}: {v}' for k, v in hd if not k.lower().startswith('proxy-') and k.lower() != 'connection'] + ['Connection: close', '', '']
            o.sendall('\r\n'.join(fwd).encode()); ev['status'] = 'forwarded'
            while True:
                data = o.recv(65536)
                if not data: break
                c.sendall(data); ev['s2c'] += len(data)
            o.close()

def origin(h): h.reply(200, b'hello from origin')

print('== 一:HTTP 地址经代理:代理能看到完整的请求(路径、查询串、Cookie、自定义头)')
with Srv(origin) as sv, Proxy() as px:
    url = f'http://plain.example.test:{sv.port}/secret/path?token=abc123'
    r = requests.get(url, proxies={'http': px.url}, headers={'Cookie': 'sid=SESSION42', 'X-Api-Key': 'KEY99'})
    ev = px.events[-1]
    print(f'  客户端得到:{r.status_code} {r.text!r}')
    print(f'  代理收到的第一行(注意是完整 URL,不是只有路径):{ev["first"].replace(str(sv.port), "<端口>")}')
    print(f'  代理收到的头:{[(k, v.replace(str(sv.port), "<端口>")) for k, v in ev["hdrs"]]}')
    print(f'  源站收到的路径:{sv.log[-1]["path"]};源站收到的头:{[k for k, _ in sv.log[-1]["hdrs"]]}')

print('== 二:HTTPS 地址经代理:代理只看到 CONNECT host:port,之后是它看不懂的加密字节')
with Srv(origin, tls=(CERT, KEY)) as sv, Proxy() as px:
    url = f'https://secure.example.test:{sv.port}/secret/path?token=abc123'
    r = requests.get(url, proxies={'https': px.url}, verify=CERT, headers={'Cookie': 'sid=SESSION42', 'X-Api-Key': 'KEY99'})
    ev = px.events[-1]; blob = ev['c2s_head']
    print(f'  客户端得到:{r.status_code} {r.text!r}')
    print(f'  代理收到的第一行:{ev["first"].replace(str(sv.port), "<端口>")}')
    print(f'  代理收到的头:{[(k, v.replace(str(sv.port), "<端口>")) for k, v in ev["hdrs"]]}')
    print(f'  之后代理转发的字节:客户端→源站 {ev["c2s"]} 字节,源站→客户端 {ev["s2c"]} 字节')
    print(f'  客户端发来的第一个字节 = {blob[0]:#04x}(TLS 握手记录的类型是 0x16);代理能在其中看到主机名 secure.example.test(SNI 是明文):{b"secure.example.test" in blob}')
    for needle in (b'/secret/path', b'token=abc123', b'SESSION42', b'KEY99'):
        print(f'  代理看到的字节里出现 {needle.decode()!r}:{needle in blob}')
    print(f'  源站(TLS 服务器)收到的路径:{sv.log[-1]["path"]}')

print('== 三:代理要求认证(407):HTTP 地址与 HTTPS 地址在 requests 里的表现不同')
with Srv(origin) as sv, Srv(origin, tls=(CERT, KEY)) as sv2, Proxy(require_auth='alice:pw') as px:
    r = requests.get(f'http://plain.example.test:{sv.port}/', proxies={'http': px.url})
    print(f'  HTTP 地址,代理 URL 里没有账号:没有抛异常,r.status_code = {r.status_code}')
    try: requests.get(f'https://secure.example.test:{sv2.port}/', proxies={'https': px.url}, verify=CERT)
    except Exception as e: print(f'  HTTPS 地址,代理 URL 里没有账号:{type(e).__name__}:{str(e)[-90:]}')
    purl = px.url.replace('http://', 'http://alice:pw@')
    r = requests.get(f'http://plain.example.test:{sv.port}/', proxies={'http': purl}); h1 = px.events[-1]
    print(f'  HTTP 地址,代理 URL 带 alice:pw:{r.status_code};代理收到 Proxy-Authorization = {dict(h1["hdrs"]).get("Proxy-Authorization")}')
    r = requests.get(f'https://secure.example.test:{sv2.port}/', proxies={'https': purl}, verify=CERT); h2 = px.events[-1]
    print(f'  HTTPS 地址,代理 URL 带 alice:pw:{r.status_code};CONNECT 请求里 Proxy-Authorization = {dict(h2["hdrs"]).get("Proxy-Authorization")}')

print('== 四:代理设置从哪来:proxies= 参数、环境变量、NO_PROXY、trust_env=False')
CODE = r'''
import sys, requests
url = sys.argv[1]; mode = sys.argv[2]
s = requests.Session()
if mode == 'noenv': s.trust_env = False
r = s.get(url)
print(r.status_code)
'''
(d / 'c4.py').write_text(CODE)
with Srv(origin) as sv, Proxy() as px:
    url = f'http://plain.example.test:{sv.port}/x'
    base = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
    pyp = ["-c", "import socket; o=socket.getaddrinfo; socket.getaddrinfo=lambda h,*a,**k:o('127.0.0.1' if isinstance(h,str) and h.endswith('.test') else h,*a,**k); import runpy,sys; sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')"]
    def go(label, env, mode='env'):
        n0 = len(px.events); m0 = len(sv.log)
        o = subprocess.run([sys.executable, *pyp, str(d / 'c4.py'), url, mode], capture_output=True, text=True, env={**base, **env}, timeout=60)
        via = len(px.events) - n0
        print(f'  {label}:状态 {o.stdout.strip() or o.stderr.strip()[-60:]};经过代理的请求 {via} 个;源站一共收到 {len(sv.log) - m0} 个请求(经代理转发的也算)')
    go('设了 HTTP_PROXY', {'HTTP_PROXY': px.url})
    go('小写 http_proxy', {'http_proxy': px.url})
    go('HTTP_PROXY + NO_PROXY=.example.test', {'HTTP_PROXY': px.url, 'NO_PROXY': '.example.test'})
    go('HTTP_PROXY + NO_PROXY=plain.example.test', {'HTTP_PROXY': px.url, 'NO_PROXY': 'plain.example.test'})
    go('HTTP_PROXY + trust_env=False', {'HTTP_PROXY': px.url}, 'noenv')
    n0 = len(px.events); r = requests.get(url, proxies={'http': px.url}); print(f'  只在代码里传 proxies=:经过代理 {len(px.events) - n0} 个')
    n0 = len(px.events); r = requests.get(f'http://127.0.0.1:{sv.port}/x', proxies={'http': px.url}); print(f'  proxies= 传了代理,但目标是 127.0.0.1:经过代理 {len(px.events) - n0} 个(本进程 NO_PROXY={os.environ.get("NO_PROXY")})')
purge()
