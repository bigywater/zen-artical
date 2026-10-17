import sys, os, subprocess, shutil, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, http.client, aiohttp, asyncio, urllib3, warnings; warnings.filterwarnings('ignore')
from curl_cffi import requests as cr
tee('p14')
d = pdir('p14')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
cap = []
def srv_fn(c, a):
    raw = read_request(c)
    head = raw.split(b'\r\n\r\n')[0].decode('latin1')
    cap.append(head)
    body = b'<html>ok</html>'; c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: %d\r\nConnection: close\r\n\r\n' % len(body) + body)
def parse(head):
    lines = head.split('\r\n'); return lines[0], [tuple(l.split(':', 1)) if ':' in l else (l, '') for l in lines[1:]]
def chrome_run(U):
    """启动 headless Chrome 访问 U;服务器收到第一个请求后结束这批 Chrome 进程(用独一无二的 --user-data-dir 精确定位,不碰用户自己的 Chrome)。"""
    ud = f'{d}/chrome_{os.getpid()}'
    p = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-proxy-server', '--no-first-run', '--disable-extensions', '--disable-component-update',
                          '--disable-background-networking', f'--user-data-dir={ud}', '--dump-dom', U], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    n0 = len(cap)
    for _ in range(300):
        if len(cap) > n0 or p.poll() is not None: break
        time.sleep(0.1)
    time.sleep(0.5)
    out = subprocess.run(['pgrep', '-f', f'user-data-dir={ud}'], capture_output=True, text=True).stdout.split()
    for pid in out:
        try: os.kill(int(pid), 15)
        except Exception: pass
    time.sleep(0.5)
    for pid in subprocess.run(['pgrep', '-f', f'user-data-dir={ud}'], capture_output=True, text=True).stdout.split():
        try: os.kill(int(pid), 9)
        except Exception: pass
    return p

def grab(fn, wait=0.4):
    n0 = len(cap); fn(); time.sleep(wait)
    new = cap[n0:]
    return new[0] if new else None

env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
with RawSrv(srv_fn) as srv:
    U = srv.url('/')
    async def aio():
        async with aiohttp.ClientSession() as s:
            async with s.get(U) as r: await r.read()
    clients = [
        ('requests', lambda: requests.get(U)),
        ('urllib3', lambda: urllib3.PoolManager().request('GET', U)),
        ('http.client', lambda: (lambda c: (c.request('GET', '/'), c.getresponse().read()))(http.client.HTTPConnection('127.0.0.1', srv.port))),
        ('aiohttp', lambda: asyncio.run(aio())),
        ('curl 命令行', lambda: subprocess.run(['curl', '-s', U], env=env, capture_output=True)),
        ('wget', lambda: subprocess.run(['wget', '-q', '-O', '-', U], env=env, capture_output=True)),
        ('curl_cffi', lambda: cr.get(U)),
        ('Node 的 fetch', lambda: subprocess.run(['node', '-e', f'fetch("{U}").then(r=>r.text())'], env=env, capture_output=True)),
        ('Chrome(headless)', lambda: chrome_run(U)),
    ]
    heads = {}
    for name, fn in clients:
        try: heads[name] = grab(fn, 0.4)
        except Exception as e: heads[name] = None; print('  ', name, '失败', type(e).__name__)

    print('== 一:同一个 GET / 请求,各客户端发出的原始请求行和头(服务器是套接字服务器,按收到的字节原样记录)')
    sigs = {}
    for name, h in heads.items():
        if not h: print(f'  {name}:(没有收到请求)'); continue
        first, hs = parse(h)
        print(f'  {name}:{first}')
        for k, v in hs:
            v = v.strip(); v = v if len(v) <= 48 else v[:45] + '...'
            print(f'      {k}: {v.replace(str(srv.port), "<端口>")}')
        sigs[name] = [k for k, _ in hs]

    print('== 二:只看头名的顺序和大小写(每个客户端一行)')
    for name, ks in sigs.items(): print(f'  {name}:{", ".join(ks)}')
    low = {n: tuple(k.lower() for k in ks) for n, ks in sigs.items()}
    exact = {n: tuple(ks) for n, ks in sigs.items()}
    print(f'  {len(sigs)} 个客户端里,头名(忽略大小写)的顺序彼此不同的有 {len(set(low.values()))} 种;区分大小写后有 {len(set(exact.values()))} 种')
    same = [n for n in low if list(low.values()).count(low[n]) > 1]
    print(f'  顺序完全相同(忽略大小写)的客户端:{same if same else "无"}')
    print(f'  Host 头是第一个头的客户端:{[n for n, ks in sigs.items() if ks and ks[0].lower() == "host"]}')
    print(f'  头名全是小写的客户端:{[n for n, ks in sigs.items() if all(k == k.lower() for k in ks)]}')

    print('== 三:requests 里自己加的头:顺序和大小写会怎样(服务器收到的原始头名)')
    def req_with(**kw):
        h = grab(lambda: requests.get(U, **kw), 0.3); return [k + (': ' + v.strip() if k in ('User-Agent', 'user-agent', 'Accept-Encoding', 'x-a', 'X-A') else '') for k, v in parse(h)[1]]
    print(f'  默认:{req_with()}')
    print(f'  headers={{"x-custom": "1", "User-Agent": "my"}}:{req_with(headers={"x-custom": "1", "User-Agent": "my"})}')
    print(f'  headers={{"user-agent": "my"}}(小写名字覆盖默认的 User-Agent):{req_with(headers={"user-agent": "my"})}')
    print(f'  headers={{"Accept": "text/html", "User-Agent": "my", "Accept-Encoding": "gzip"}}(想改顺序):{req_with(headers={"Accept": "text/html", "User-Agent": "my", "Accept-Encoding": "gzip"})}')
    print(f'  headers={{"User-Agent": None}}(去掉默认头):{req_with(headers={"User-Agent": None})}')
    print(f'  headers={{"Connection": None, "Accept-Encoding": None, "Accept": None}}:{req_with(headers={"Connection": None, "Accept-Encoding": None, "Accept": None})}')
    s = requests.Session(); s.headers.clear()
    print(f'  Session.headers.clear() 后只加 Accept:{[k + (": " + v.strip() if k in ("User-Agent", "Accept-Encoding") else "") for k, v in parse(grab(lambda: (s.headers.update({"Accept": "*/*"}), s.get(U)), 0.3))[1]]}')
    print(f'  同时给出 "X-A" 和 "x-a" 两个同名头(大小写不同):{req_with(headers={"X-A": "1", "x-a": "2"})}')
purge()
