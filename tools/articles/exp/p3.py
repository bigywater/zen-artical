import sys, os, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, urllib3
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
tee('p3')

def states(cport):
    """lsof 里本机端口为 cport 的 TCP 连接状态(客户端那一端)。"""
    o = subprocess.run(['lsof', '-nP', f'-iTCP:{cport}'], capture_output=True, text=True).stdout
    return sorted({m.group(1) for m in re.finditer(rf'127\.0\.0\.1:{cport}->\S+ \((\w+)\)', o)})

def ok(h): h.reply(200, b'ok')

print('== 一:服务器在连接空闲 1.0 秒后关掉它;客户端分别隔 0.2 秒和 1.5 秒再发下一个请求')
for gap in (0.2, 1.5):
    with Srv(ok, idle=1.0) as sv, requests.Session() as s:
        r1 = s.get(sv.url('/')); cport = list(sv.conns)[0]
        st_before = states(cport)
        time.sleep(gap)
        st_gap = states(cport)
        t0 = time.perf_counter(); r2 = s.get(sv.url('/')); dt = ms(t0)
        print(f'  间隔 {gap} 秒:第 2 个请求 {r2.status_code},服务器累计 {sv.n_conn} 条连接;客户端那端的套接字状态 发请求前 {st_before} → 等待之后 {st_gap};第 2 个请求耗时 {dt:.2f} ms')

print('== 二:客户端没有收到任何异常——urllib3 在复用连接前先检查它是不是已经被对端关掉了')
import inspect, urllib3.connectionpool as cp
src, start = inspect.getsourcelines(cp.HTTPConnectionPool._get_conn)
for i, l in enumerate(src):
    if 'is_connection_dropped' in l: print(f'  urllib3 {urllib3.__version__} connectionpool.py 第 {start + i} 行:{l.strip()}')
import urllib3.connection as uc
src, start = inspect.getsourcelines(uc.HTTPConnection.is_connected.fget)
print('  HTTPConnection.is_connected 的实现(urllib3 源码):')
for i, l in enumerate(src): print(f'    {start + i:>4} | {l.rstrip()}')
with Srv(ok, idle=0.5) as sv, requests.Session() as s:
    s.get(sv.url('/')); time.sleep(1.0)
    errs = 0; t0 = time.perf_counter()
    for _ in range(5):
        try: s.get(sv.url('/')); time.sleep(0.7)
        except Exception: errs += 1
    print(f'  服务器空闲 0.5 秒就关,客户端每隔 0.7 秒请求一次,共 6 次请求:异常 {errs} 次,服务器累计 {sv.n_conn} 条连接')

print('== 三:真正会出错的是竞态:服务器收到请求之后、回应之前把连接关了')
def drop_second(h):
    n = sv.conns.get(h.client_address[1], 0)
    if n >= 2:
        h.close_connection = True
        try: h.connection.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        h.connection.close(); return
    h.reply(200, b'ok')
for label, retry in (('默认(max_retries=0)', None), ('Retry(total=1)', Retry(total=1, backoff_factor=0))):
    with Srv(drop_second) as sv, requests.Session() as s:
        if retry: s.mount('http://', HTTPAdapter(max_retries=retry))
        s.get(sv.url('/'))
        try:
            r = s.get(sv.url('/')); res = f'成功 {r.status_code}'
        except Exception as e: res = f'{type(e).__name__}: {e}'
        print(f'  {label}:第 2 个请求(在复用的连接上被服务器直接断开)→ {res};服务器累计 {sv.n_conn} 条连接,收到 {len(sv.log)} 个请求')

print('== 四:服务器用 Keep-Alive: timeout=1 告诉客户端"我 1 秒后关",客户端会听吗')
def hint(h): h.reply(200, b'ok', headers={'Keep-Alive': 'timeout=1', 'Connection': 'keep-alive'})
with Srv(hint, idle=3.0) as sv, requests.Session() as s:
    r = s.get(sv.url('/')); print(f'  第 1 个响应头:Keep-Alive: {r.headers.get("Keep-Alive")}')
    time.sleep(2.0)
    r = s.get(sv.url('/'))
    print(f'  客户端等了 2.0 秒(超过 timeout=1,但服务器实际 3.0 秒才关)再请求:服务器累计 {sv.n_conn} 条连接 → 客户端{"没有" if sv.n_conn == 1 else ""}因为这个提示放弃旧连接')
purge()
