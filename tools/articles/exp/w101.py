import sys, os, re, struct, threading, statistics, errno, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
import socks, requests
import dns.message
tee('w101'); reset()
REP = {0: '成功', 1: '一般性 SOCKS 服务器故障', 2: '规则集不允许', 3: '网络不可达', 4: '主机不可达', 5: '连接被拒绝', 6: 'TTL 过期', 7: '不支持的命令', 8: '不支持的地址类型'}
log = []
def recvn(s, n):
    b = b''
    while len(b) < n:
        d = s.recv(n - len(b))
        if not d: raise EOFError()
        b += d
    return b
def relay(a, b):
    try:
        while True:
            r, _, _ = select.select([a, b], [], [], 10)
            if not r: break
            for s in r:
                d = s.recv(65536)
                if not d: return
                (b if s is a else a).sendall(d)
    except Exception: pass
def handle(c, auth):
    ent = {}; log.append(ent)
    try:
        c.settimeout(10); ver, n = recvn(c, 2); methods = list(recvn(c, n)); ent['methods'] = methods
        if auth:
            if 2 not in methods: c.sendall(b'\x05\xff'); return
            c.sendall(b'\x05\x02'); v, ul = recvn(c, 2); u = recvn(c, ul); pl = recvn(c, 1)[0]; p = recvn(c, pl); ok = (u == b'alice' and p == b'pa55')
            c.sendall(b'\x01' + (b'\x00' if ok else b'\x01')); ent['auth'] = (u.decode(), '成功' if ok else '失败')
            if not ok: return
        else:
            if 0 not in methods: c.sendall(b'\x05\xff'); return
            c.sendall(b'\x05\x00')
        ver, cmd, rsv, atyp = recvn(c, 4)
        if atyp == 1: addr = socket.inet_ntoa(recvn(c, 4))
        elif atyp == 3: l = recvn(c, 1)[0]; addr = recvn(c, l).decode()
        elif atyp == 4: addr = socket.inet_ntop(socket.AF_INET6, recvn(c, 16))
        else: c.sendall(b'\x05\x08\x00\x01' + bytes(6)); ent['reply'] = 8; return
        port = struct.unpack('>H', recvn(c, 2))[0]; ent.update(cmd=cmd, atyp=atyp, addr=addr, port=port)
        if cmd == 1:
            try:
                t0 = time.time(); o = socket.create_connection((addr, port), timeout=5); ent['connect_ms'] = (time.time() - t0) * 1000; bnd = o.getsockname()
                c.sendall(b'\x05\x00\x00\x01' + socket.inet_aton(bnd[0]) + struct.pack('>H', bnd[1])); ent['reply'] = 0; relay(c, o)
            except ConnectionRefusedError: c.sendall(b'\x05\x05\x00\x01' + bytes(6)); ent['reply'] = 5
            except socket.gaierror: c.sendall(b'\x05\x04\x00\x01' + bytes(6)); ent['reply'] = 4
            except Exception: c.sendall(b'\x05\x01\x00\x01' + bytes(6)); ent['reply'] = 1
        elif cmd == 3:
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.bind(('127.0.0.1', 0)); up = u.getsockname()[1]
            c.sendall(b'\x05\x00\x00\x01' + socket.inet_aton('127.0.0.1') + struct.pack('>H', up)); ent['reply'] = 0; ent['udp_port'] = up; u.settimeout(0.5); client_addr = None; tcp_closed = [False]
            def watch():
                try:
                    while c.recv(100): pass
                except Exception: pass
                tcp_closed[0] = True
            threading.Thread(target=watch, daemon=True).start(); out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); out.settimeout(3)
            while not tcp_closed[0]:
                try: d, a = u.recvfrom(65535)
                except socket.timeout: continue
                client_addr = a; frag = d[2]; at = d[3]
                if at == 1: ip = socket.inet_ntoa(d[4:8]); pt = struct.unpack('>H', d[8:10])[0]; data = d[10:]
                else: continue
                ent.setdefault('udp', []).append((ip, pt, len(data), frag)); out.sendto(data, (ip, pt))
                try: r, ra = out.recvfrom(65535); u.sendto(b'\x00\x00\x00\x01' + socket.inet_aton(ra[0]) + struct.pack('>H', ra[1]) + r, client_addr)
                except socket.timeout: pass
        else: c.sendall(b'\x05\x07\x00\x01' + bytes(6)); ent['reply'] = 7
    except Exception as e: ent['err'] = type(e).__name__
    finally:
        try: c.close()
        except Exception: pass
def serve(port, stop, auth=False):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=handle, args=(c, auth), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
port = lab_port(); stop = [False]; serve(port, stop)
tgt_port = lab_port(); ts = socket.socket(); ts.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ts.bind(('127.0.0.1', tgt_port)); ts.listen(8)
threading.Thread(target=lambda: [(lambda c: (c.sendall(b'hello from target\n'), c.close()))(ts.accept()[0]) for _ in range(20)], daemon=True).start()

print('== 一:SOCKS5 握手的每个字节(RFC 1928)。客户端:问候(版本 5,支持的认证方法列表)→ 服务器选一个方法 → 客户端发请求(命令 + 目标地址类型 + 地址 + 端口)→ 服务器回复(状态码 + 绑定地址)。手工连本机 SOCKS5 服务器,CONNECT 到本机的一个目标服务')
s = socket.create_connection(('127.0.0.1', port)); g = bytes([5, 1, 0]); s.sendall(g); r1 = recvn(s, 2)
req = bytes([5, 1, 0, 1]) + socket.inet_aton('127.0.0.1') + struct.pack('>H', tgt_port); s.sendall(req); r2 = recvn(s, 10); data = s.recv(100); s.close()
hx = lambda b: ' '.join(f'{x:02x}' for x in b)
print(f'  客户端问候 {hx(g)}:05 = 版本;01 = 1 种方法;00 = “无需认证”')
print(f'  服务器选择 {hx(r1)}:05;00 = 选定“无需认证”(ff 表示没有可接受的方法)')
print(f'  客户端请求 {hx(req)}:05 版本 | 01 = CONNECT | 00 保留 | 01 = 地址类型 IPv4 | {hx(req[4:8])} = 127.0.0.1 | {hx(req[8:])} = 端口 {tgt_port}')
print(f'  服务器回复 {hx(r2)}:05 | {r2[1]:02x} = {REP[r2[1]]} | 00 保留 | 01 = IPv4 | {hx(r2[4:8])}:{struct.unpack(">H", r2[8:])[0]} = 服务器一侧出站连接的本地地址与端口(BND.ADDR / BND.PORT)')
print(f'  之后这条 TCP 连接就是一根透明的管子:收到目标发来的 {data!r}')
print(f'  整个握手共 2 个往返:问候 / 选择 1 个往返,请求 / 回复 1 个往返(共 {len(g) + len(req)} 字节上行,{len(r1) + len(r2)} 字节下行)')

print('== 二:域名由谁解析?socks5://(客户端本地解析成 IP,请求里放 IPv4)与 socks5h://(把域名原样交给代理,请求里 ATYP = 3)。用 requests + PySocks 访问 example.com,看代理服务器收到的请求里地址类型')
for scheme in ('socks5', 'socks5h'):
    log.clear()
    try: r = requests.get('http://example.com/', proxies={'http': f'{scheme}://127.0.0.1:{port}'}, timeout=15); ok = f'{r.status_code},{len(r.content)} 字节'
    except Exception as e: ok = type(e).__name__
    e = [x for x in log if x.get('addr')][-1] if any(x.get('addr') for x in log) else {}
    AT = {1: 'IPv4', 3: '域名', 4: 'IPv6'}
    print(f'  {scheme}://:代理收到 CMD={e.get("cmd")}(1=CONNECT),ATYP={e.get("atyp")}({AT.get(e.get("atyp"), "?")}),地址 {e.get("addr")!r},端口 {e.get("port")};代理连目标用时 {e.get("connect_ms", 0):.0f} ms;客户端最终 {ok}')
print('  socks5:本机先做 DNS 解析(本机 DNS 查询可能被污染 / 泄露),代理只看到 IP;socks5h:域名交给代理去解析,本机不发 DNS 查询——这是隐私和绕开本地 DNS 的关键区别')

print('== 三:用户名密码认证(RFC 1929)与各种错误答复')
stop[0] = True; time.sleep(0.4); port2 = lab_port(); stop2 = [False]; serve(port2, stop2, auth=True)
def try_auth(user, pw, methods=(0, 2)):
    s = socket.create_connection(('127.0.0.1', port2)); s.sendall(bytes([5, len(methods)]) + bytes(methods)); r = recvn(s, 2)
    if r[1] == 0xff: s.close(); return '服务器答复 05 ff:没有可接受的认证方法'
    s.sendall(b'\x01' + bytes([len(user)]) + user.encode() + bytes([len(pw)]) + pw.encode()); a = recvn(s, 2); s.close(); return f'选定方法 {r[1]:02x}(02 = 用户名/密码);认证答复 {hx(a)}({"成功" if a[1] == 0 else "失败"})'
print('  正确的用户名密码 →', try_auth('alice', 'pa55')); print('  错误的密码 →', try_auth('alice', 'wrong')); print('  只提供“无需认证”方法 →', try_auth('', '', methods=(0,)))
print('  注意:用户名和密码在 RFC 1929 里是明文传输的(只用于控制代理的访问,没有加密)')
stop2[0] = True; time.sleep(0.4)
stop = [False]; serve(port, stop)
def req_reply(atyp_bytes, cmd=1):
    s = socket.create_connection(('127.0.0.1', port)); s.sendall(b'\x05\x01\x00'); recvn(s, 2); s.sendall(bytes([5, cmd, 0]) + atyp_bytes); r = recvn(s, 10); s.close(); return r
closed = socket.socket(); closed.bind(('127.0.0.1', 0)); cp = closed.getsockname()[1]; closed.close()
for nm, ab, cmd in (('连接一个没有监听的端口', b'\x01' + socket.inet_aton('127.0.0.1') + struct.pack('>H', cp), 1), ('域名无法解析', b'\x03' + bytes([len('no-such-w101.invalid')]) + b'no-such-w101.invalid' + struct.pack('>H', 80), 1), ('不支持的命令(BIND = 2)', b'\x01' + socket.inet_aton('127.0.0.1') + struct.pack('>H', 80), 2), ('不支持的地址类型(0x09)', b'\x09' + bytes(6), 1)):
    try: r = req_reply(ab, cmd); print(f'  {nm}:回复 {hx(r)} → 状态码 {r[1]} = {REP.get(r[1], "?")}')
    except Exception as e: print(f'  {nm}:{type(e).__name__}')

print('== 四:UDP ASSOCIATE:SOCKS5 也能转发 UDP。客户端先用 TCP 控制连接发 UDP ASSOCIATE(命令 3),服务器回复它的 UDP 中继地址;之后每个 UDP 数据报前面加 SOCKS5 的 UDP 头(RSV 2 字节 + FRAG 1 字节 + ATYP + 地址 + 端口)。通过它发一个真实的 DNS 查询给 1.1.1.1:53')
tcp = socket.create_connection(('127.0.0.1', port)); tcp.sendall(b'\x05\x01\x00'); recvn(tcp, 2); tcp.sendall(bytes([5, 3, 0, 1]) + bytes(4) + struct.pack('>H', 0)); rr = recvn(tcp, 10); up = struct.unpack('>H', rr[8:])[0]
q = dns.message.make_query('example.com', 'A').to_wire(); hdr = b'\x00\x00\x00\x01' + socket.inet_aton('1.1.1.1') + struct.pack('>H', 53)
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.settimeout(5); t0 = time.time()
for i in range(3):
    try: u.sendto(hdr + q, ('127.0.0.1', up)); d, _ = u.recvfrom(65535); break
    except socket.timeout: d = None
dt = (time.time() - t0) * 1000
print(f'  UDP ASSOCIATE 回复 {hx(rr)}:状态 {rr[1]} = {REP[rr[1]]},服务器的 UDP 中继端口 {up}')
print(f'  UDP 数据报头(10 字节)= {hx(hdr)}:00 00 = RSV;00 = FRAG(0 = 不分片);01 = IPv4;01 01 01 01 = 1.1.1.1;00 35 = 端口 53;之后是 {len(q)} 字节的 DNS 查询')
if d: r = dns.message.from_wire(d[10:]); print(f'  收到 UDP 中继回来的数据报 {len(d)} 字节(前 10 字节是 SOCKS5 UDP 头,来源 {socket.inet_ntoa(d[4:8])}:{struct.unpack(">H", d[8:10])[0]}),里面的 DNS 响应:{[x.to_text() for rr_ in r.answer for x in rr_]};用时 {dt:.0f} ms')
else: print('  没有收到 UDP 中继回来的数据报')
tcp.close(); time.sleep(0.5)
print(f'  UDP 中继的生命周期绑定在 TCP 控制连接上:关掉 TCP 控制连接后,服务器就停止中继(服务器日志里记录了 {sum(len(x.get("udp", [])) for x in log)} 个被中继的 UDP 数据报)')
stop[0] = True
