import sys, os, re, struct, threading, statistics, errno, ssl, base64, select, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import requests
tee('w83'); reset()
PUB = '104.20.23.154'
seen = []
def sni_of(b):
    try:
        if b[0] != 0x16: return None
        p = 43; sid = b[p]; p += 1 + sid; cs = struct.unpack('>H', b[p:p + 2])[0]; p += 2 + cs; cm = b[p]; p += 1 + cm; el = struct.unpack('>H', b[p:p + 2])[0]; p += 2; end = p + el
        while p < end:
            t, l = struct.unpack('>HH', b[p:p + 4]); p += 4
            if t == 0: return b[p + 5:p + 5 + struct.unpack('>H', b[p + 3:p + 5])[0]].decode()
            p += l
    except Exception: return None
def relay(a, b, stats):
    socks = [a, b]
    try:
        while True:
            r, _, _ = select.select(socks, [], [], 8)
            if not r: break
            for s in r:
                d = s.recv(65536)
                if not d: return
                o = b if s is a else a; o.sendall(d)
                stats['up' if s is a else 'down'] += len(d)
                if s is a and 'first' not in stats: stats['first'] = d[:64]; stats['sni'] = sni_of(d)
    except Exception: pass
def proxy(port, stop, auth=False, deny=()):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def h(c):
        try:
            c.settimeout(10); buf = b''
            while b'\r\n\r\n' not in buf: buf += c.recv(65536)
            head, _, rest = buf.partition(b'\r\n\r\n'); lines = head.split(b'\r\n'); meth, target, ver = lines[0].decode().split(' ', 2)
            hd = {l.split(b':', 1)[0].decode().lower(): l.split(b':', 1)[1].strip().decode() for l in lines[1:] if b':' in l}
            rec = {'line': lines[0].decode(), 'headers': list(hd), 'auth': hd.get('proxy-authorization'), 'up': 0, 'down': 0}; seen.append(rec)
            if auth and not hd.get('proxy-authorization'):
                c.sendall(b'HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: Basic realm="w83"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'); rec['result'] = '407'; return
            if meth == 'CONNECT':
                host, _, p = target.rpartition(':'); rec['host'] = host
                if host in deny: c.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'); rec['result'] = '403'; return
                try: o = socket.create_connection((host, int(p)), timeout=4)
                except Exception: c.sendall(b'HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'); rec['result'] = '502'; return
                c.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n'); rec['result'] = '200'
                relay(c, o, rec); o.close()
            else:
                u = re.match(r'http://([^/:]+)(?::(\d+))?(/.*)?', target); host, p, path = u.group(1), int(u.group(2) or 80), u.group(3) or '/'
                rec['host'] = host; o = socket.create_connection((host, p), timeout=6)
                fwd = f'{meth} {path} {ver}\r\n'.encode() + b'\r\n'.join(l for l in lines[1:] if not l.lower().startswith((b'proxy-', b'connection:'))) + b'\r\nConnection: close\r\nVia: 1.1 w83proxy\r\n\r\n'
                o.sendall(fwd + rest); resp = b''
                while True:
                    d = o.recv(65536)
                    if not d: break
                    resp += d
                c.sendall(resp); rec['result'] = resp.split(b'\r\n', 1)[0].decode(); rec['down'] = len(resp); o.close()
        except Exception as e: seen.append({'err': repr(e)[:50]})
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
pp = lab_port(); stop = [False]; proxy(pp, stop)
PX = {'http': f'http://127.0.0.1:{pp}', 'https': f'http://127.0.0.1:{pp}'}

print('== 一:HTTP 代理看到的明文请求:客户端把请求发给代理,请求行写成绝对形式(完整 URL)。代理转发给 example.com:80。看代理收到的请求行与头部,和直连时的请求行对比')
seen.clear(); s = requests.get('http://example.com/', proxies=PX, timeout=10, headers={'User-Agent': 'w83', 'Accept-Encoding': 'identity'})
rec = seen[0]
print(f'  客户端经代理发出的请求行:{rec["line"]}')
print(f'  直连时的请求行是:GET / HTTP/1.1(origin-form,只有路径);经代理变成了 absolute-form,因为代理需要知道要连哪台主机')
print(f'  代理收到的头部名字:{rec["headers"]};代理转发请求时加了 Via: 1.1 w83proxy,去掉了 Proxy-* 和原来的 Connection 头(改成 Connection: close);最终客户端拿到 {s.status_code},{len(s.content)} 字节')
print(f'  代理能看到什么:完整 URL、全部头部(包括 Cookie / Authorization 等)和整个消息体——明文 HTTP 对代理是完全透明的')

print('== 二:HTTPS 经代理:CONNECT 隧道。客户端先对代理发 CONNECT example.com:443,代理回 200 后就只是在两个套接字之间搬字节,TLS 握手是客户端与 example.com 端到端完成的。看代理能看到什么')
seen.clear()
with requests.Session() as sess:
    s = sess.get('https://example.com/', proxies=PX, timeout=15, headers={'User-Agent': 'w83', 'Accept-Encoding': 'identity'})
time.sleep(1)
rec = seen[0]
print(f'  客户端发给代理的第一行:{rec["line"]};代理回复 {rec.get("result")} Connection Established;之后客户端 {s.status_code},收到 {len(s.content)} 字节')
print(f'  代理中转的字节:客户端→服务器 {rec["up"]} 字节,服务器→客户端 {rec["down"]} 字节(都是 TLS 密文)')
print(f'  代理在转发的第一批字节里看到的 TLS ClientHello 里的 SNI(服务器名,明文)= {rec.get("sni")};它看不到 URL 路径、头部、Cookie 和消息体')
print(f'  客户端校验的证书是 example.com 自己的(不是代理的):requests 成功且没有证书错误——说明隧道是端到端的 TLS')

print('== 三:CONNECT 多花的时间:代理与客户端之间加每方向 50 ms 延迟(netlab 作用在 lo0 的 9400–9499 端口,即客户端↔代理这一段;代理↔example.com 是真实网络)。直连与经代理访问 https://example.com/ 的耗时(各 4 次)')
def timed(proxies):
    t0 = time.time(); requests.get('https://example.com/', proxies=proxies, timeout=15, headers={'Accept-Encoding': 'identity'}); return (time.time() - t0) * 1000
direct = [timed(None) for _ in range(4)]
with lossy(loss=0, delay=50, bw=0):
    via = [timed(PX) for _ in range(4)]
print(f'  直连:{[round(x) for x in direct]} ms,中位 {statistics.median(direct):.0f} ms')
print(f'  经代理(客户端↔代理 往返 100 ms):{[round(x) for x in via]} ms,中位 {statistics.median(via):.0f} ms')
print(f'  经代理多出 {statistics.median(via) - statistics.median(direct):.0f} ms(中位数之差)')
def phases(via_proxy, delay_on):
    out = {}
    t0 = time.time()
    if via_proxy:
        s = socket.create_connection(('127.0.0.1', pp), timeout=10); out['连到代理'] = time.time() - t0; t1 = time.time()
        s.sendall(b'CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n'); b_ = b''
        while b'\r\n\r\n' not in b_: b_ += s.recv(4096)
        out['CONNECT 往返'] = time.time() - t1
    else:
        s = socket.create_connection((PUB, 443), timeout=10); out['TCP 连到源站'] = time.time() - t0
    t2 = time.time(); ss = ssl.create_default_context().wrap_socket(s, server_hostname='example.com'); out['TLS 握手'] = time.time() - t2
    t3 = time.time(); ss.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\nAccept-Encoding: identity\r\n\r\n'); d = ss.recv(65536); out['HTTP 请求到首字节'] = time.time() - t3; ss.close()
    return out
def med(rows):
    return {k: statistics.median(r[k] for r in rows) * 1000 for k in rows[0]}
d_ph = med([phases(False, False) for _ in range(3)])
with lossy(loss=0, delay=50, bw=0):
    p_ph = med([phases(True, True) for _ in range(3)])
print('  直连各阶段(中位 ms):' + ';'.join(f'{k} {v:.0f}' for k, v in d_ph.items()) + f';合计 {sum(d_ph.values()):.0f}')
print('  经代理各阶段(中位 ms):' + ';'.join(f'{k} {v:.0f}' for k, v in p_ph.items()) + f';合计 {sum(p_ph.values()):.0f}')
print('  对照:TLS 握手和 HTTP 请求这两个阶段,经代理的耗时比直连多出的部分,就是隧道里多经过的那一段 100 ms 往返(客户端↔代理)')

print('== 四:代理的各种答复:403(被策略禁止)、502(代理连不上目标)、407(要求认证)和客户端的反应')
stop[0] = True; pp2 = lab_port(); stop2 = [False]; proxy(pp2, stop2, auth=False, deny=('blocked.example',)); P2 = {'http': f'http://127.0.0.1:{pp2}', 'https': f'http://127.0.0.1:{pp2}'}
for nm, url in (('CONNECT 到被禁止的主机', 'https://blocked.example/'), ('CONNECT 到连不上的目标(127.0.0.1:9)', 'https://127.0.0.1:9/')):
    seen.clear()
    try: requests.get(url, proxies=P2, timeout=8); out = '成功(意外)'
    except Exception as e: out = f'{type(e).__name__}:{re.sub(r"(Max retries.*?Caused by )", "", str(e))[:90]}'
    print(f'  {nm}:代理返回 {seen[0].get("result") if seen else "?"};客户端 → {out}')
stop2[0] = True; pp3 = lab_port(); stop3 = [False]; proxy(pp3, stop3, auth=True); P3 = {'http': f'http://127.0.0.1:{pp3}', 'https': f'http://127.0.0.1:{pp3}'}
seen.clear()
try: requests.get('http://example.com/', proxies=P3, timeout=8); out = '成功'
except Exception as e: out = type(e).__name__
r = requests.get('http://example.com/', proxies=P3, timeout=8)
print(f'  代理要求认证:不带凭据 → 状态 {r.status_code},Proxy-Authenticate = {r.headers.get("proxy-authenticate")}')
seen.clear(); P4 = {k: f'http://user:pass@127.0.0.1:{pp3}' for k in ('http', 'https')}
r = requests.get('http://example.com/', proxies=P4, timeout=10, headers={'Accept-Encoding': 'identity'})
print(f'  带上凭据(Proxy-Authorization: Basic …)→ 状态 {r.status_code};代理收到的 Proxy-Authorization = {seen[-1].get("auth")}(Basic 只是 base64 编码:{base64.b64decode(seen[-1]["auth"].split()[1]).decode()},不是加密)')
stop3[0] = True
