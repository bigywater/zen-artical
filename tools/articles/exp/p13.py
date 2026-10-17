import sys, os, struct, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, socket, warnings; warnings.filterwarnings('ignore')
tee('p13')
d = pdir('p13'); CERT = make_cert(d)

def _nxt(cur):
    for a in getattr(cur, 'args', ()):
        if isinstance(a, BaseException): return a
    r = getattr(cur, 'reason', None)
    if isinstance(r, BaseException): return r
    return cur.__cause__ or cur.__context__

def chain(e):
    """沿着 args / reason / __cause__ 把嵌套的异常类名列出来,最后给出最内层异常的消息。"""
    names, seen, cur = [], set(), e
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur)); names.append(type(cur).__name__); last = cur; cur = _nxt(cur)
    return ' → '.join(names), str(last)[:80].replace('\r', '\\r').replace('\n', '\\n')

def rst(c):
    c.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); c.close()
def wait_data(c, t=3):
    select.select([c], [], [], t)

def s_close_after_read(c, a): read_request(c)
def s_close_unread(c, a): wait_data(c); time.sleep(0.05)   # 请求字节已到,但不读直接关
def s_rst_after_read(c, a): read_request(c); rst(c)
def s_partial_header(c, a): read_request(c); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Le')
def s_garbage(c, a): read_request(c); c.sendall(b'hello world\r\n\r\n')
def s_bad_status(c, a): read_request(c); c.sendall(b'HTTP/1.1 abc OK\r\nContent-Length: 0\r\n\r\n')
def s_long_header(c, a): read_request(c); c.sendall(b'HTTP/1.1 200 OK\r\nX-Long: ' + b'a' * 70000 + b'\r\nContent-Length: 0\r\n\r\n')
def s_many_headers(c, a): read_request(c); c.sendall(b'HTTP/1.1 200 OK\r\n' + b''.join(b'X-%d: v\r\n' % i for i in range(150)) + b'Content-Length: 0\r\n\r\n')
def s_short_body(c, a): read_request(c); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n' + b'x' * 100)
def s_rst_mid_body(c, a): read_request(c); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n' + b'x' * 100); time.sleep(0.1); rst(c)
def s_plain_answers_tls(c, a): c.settimeout(3); c.recv(4096); c.sendall(b'HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')

rows = []
def case(label, fn, scheme='http', **kw):
    with RawSrv(fn) as srv:
        url = f'{scheme}://127.0.0.1:{srv.port}/'
        try:
            r = requests.get(url, timeout=5, **kw); res = ('(无异常)', f'状态 {r.status_code}', '', '')
        except Exception as e:
            names, msg = chain(e)
            res = (type(e).__name__, names, msg, ('是' if isinstance(e, requests.exceptions.ConnectionError) else '否') + '/' + ('是' if isinstance(e, requests.exceptions.Timeout) else '否'))
    rows.append((label, res)); return res

print('== 一:服务器端的各种异常行为 → requests 抛什么(两个"是/否"依次表示:被 except ConnectionError 抓到吗 / 被 except Timeout 抓到吗)')
s = socket.socket(); s.bind(('127.0.0.1', 0)); refused_port = s.getsockname()[1]; s.close()
for label, fn in (
    ('没有任何服务在监听(端口被拒绝)', None),
    ('收到请求后,读完并正常关闭连接(FIN)', s_close_after_read),
    ('请求字节到达后,不读直接关闭(缓冲区有未读数据,系统发 RST)', s_close_unread),
    ('读完请求后,设 SO_LINGER=0 强制关闭(RST)', s_rst_after_read),
    ('只发了半截响应头就关闭', s_partial_header),
    ('回了不是 HTTP 的内容', s_garbage),
    ('状态行里状态码不是数字', s_bad_status),
    ('一条响应头长度 70000 字节', s_long_header),
    ('响应头 150 个', s_many_headers),
    ('Content-Length: 1000 只发 100 字节就关闭', s_short_body),
    ('Content-Length: 1000 发 100 字节后发 RST', s_rst_mid_body),
):
    if fn is None:
        try: requests.get(f'http://127.0.0.1:{refused_port}/', timeout=5); res = ('(无异常)', '', '', '')
        except Exception as e:
            names, msg = chain(e); res = (type(e).__name__, names, msg, ('是' if isinstance(e, requests.exceptions.ConnectionError) else '否') + '/' + ('是' if isinstance(e, requests.exceptions.Timeout) else '否'))
        rows.append((label, res))
    else: res = case(label, fn)
    r = rows[-1][1]
    print(f'  {label}')
    print(f'      requests 抛出:{r[0]};内部链:{r[1]};最内层:{r[2]};ConnectionError/Timeout = {r[3]}')

with RawSrv(s_partial_header) as srv:
    r = requests.get(f'http://127.0.0.1:{srv.port}/', timeout=5)
    print(f'  (细看"只发了半截响应头就关闭":requests 没有报错,r.status_code={r.status_code},收到的响应头={dict(r.headers)},r.content={r.content!r})')
print('== 二:协议不匹配')
res = case('https:// 去连一个只会说明文 HTTP 的服务器', s_plain_answers_tls, scheme='https', verify=False)
print(f'  https:// 去连明文 HTTP 服务器:抛 {res[0]};内部链 {res[1]};最内层 {res[2]};ConnectionError/Timeout = {res[3]}')
with Srv(tls=CERT) as sv:
    try: requests.get(f'http://127.0.0.1:{sv.port}/', timeout=5); res = ('(无异常)', '', '', '')
    except Exception as e:
        names, msg = chain(e); res = (type(e).__name__, names, msg, ('是' if isinstance(e, requests.exceptions.ConnectionError) else '否') + '/' + ('是' if isinstance(e, requests.exceptions.Timeout) else '否'))
    print(f'  http:// 去连一个 TLS 服务器:抛 {res[0]};内部链 {res[1]};最内层 {res[2]};ConnectionError/Timeout = {res[3]}')
    try: requests.get(sv.url('/'), timeout=5); res = ('(无异常)', '', '', '')
    except Exception as e:
        names, msg = chain(e); res = (type(e).__name__, names, msg, ('是' if isinstance(e, requests.exceptions.ConnectionError) else '否') + '/' + ('是' if isinstance(e, requests.exceptions.Timeout) else '否'))
    print(f'  https:// 连自签名证书的服务器且 verify=True:抛 {res[0]};内部链 {res[1]};最内层 {res[2]};ConnectionError/Timeout = {res[3]}')

print('== 三:这些异常的类继承关系(requests.exceptions)')
import inspect
for n in ('ConnectionError', 'ConnectTimeout', 'ReadTimeout', 'SSLError', 'ProxyError', 'ChunkedEncodingError', 'ContentDecodingError', 'TooManyRedirects', 'InvalidURL'):
    c = getattr(requests.exceptions, n); print(f'  {n}:' + ' → '.join(k.__name__ for k in c.__mro__[:-2]))
purge()
