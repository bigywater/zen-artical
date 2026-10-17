import sys, os, re, struct, threading, statistics, errno, ssl, asyncio, datetime, math; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]  # exp/ 下有旧文件 h2.py,会遮住 h2 库
from netl import *
import h2.connection, h2.config, h2.events, h2.settings, hpack
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
tee('w85'); reset()
# 自签名证书(只给本机服务器用)
key = ec.generate_private_key(ec.SECP256R1()); name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
cert = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=2)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), False).sign(key, hashes.SHA256())
CF, KF = str(WT / 'w85_cert.pem'), str(WT / 'w85_key.pem')
open(CF, 'wb').write(cert.public_bytes(serialization.Encoding.PEM)); open(KF, 'wb').write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))

# ---- 本机 HTTP/2 服务器(h2 库 + asyncio + TLS) ----
class H2Srv(asyncio.Protocol):
    max_streams = 100
    def connection_made(self, tr):
        self.tr = tr; self.conn = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=False, header_encoding='utf-8')); self.conn.initiate_connection()
        self.conn.update_settings({h2.settings.SettingCodes.MAX_CONCURRENT_STREAMS: self.max_streams}); self.tr.write(self.conn.data_to_send()); self.waiters = {}
    def data_received(self, data):
        try: evs = self.conn.receive_data(data)
        except Exception: self.tr.close(); return
        for e in evs:
            if isinstance(e, h2.events.RequestReceived):
                hd = dict(e.headers); asyncio.ensure_future(self.handle(e.stream_id, hd.get(':path', '/')))
            elif isinstance(e, (h2.events.WindowUpdated, h2.events.RemoteSettingsChanged)):
                for ev in list(self.waiters.values()): ev.set()
        self.tr.write(self.conn.data_to_send())
    async def handle(self, sid, path):
        q = dict(x.split('=') for x in path.split('?', 1)[1].split('&')) if '?' in path else {}
        size = int(q.get('size', 1000)); delay = int(q.get('delay', 0))
        if delay: await asyncio.sleep(delay / 1000)
        self.conn.send_headers(sid, [(':status', '200'), ('content-length', str(size))]); self.tr.write(self.conn.data_to_send())
        ev = self.waiters.setdefault(sid, asyncio.Event()); sent = 0; blob = b'x' * 16384
        while sent < size:
            w = min(self.conn.local_flow_control_window(sid), size - sent, self.conn.max_outbound_frame_size, 16384)
            if w <= 0: ev.clear(); await ev.wait(); continue
            self.conn.send_data(sid, blob[:w]); sent += w; self.tr.write(self.conn.data_to_send())
        self.conn.end_stream(sid); self.tr.write(self.conn.data_to_send()); self.waiters.pop(sid, None)
sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); sctx.load_cert_chain(CF, KF); sctx.set_alpn_protocols(['h2'])
loop = asyncio.new_event_loop(); srv_port = lab_port()
def run_srv():
    asyncio.set_event_loop(loop); s = loop.run_until_complete(loop.create_server(H2Srv, '127.0.0.1', srv_port, ssl=sctx)); loop.run_forever()
threading.Thread(target=run_srv, daemon=True).start(); time.sleep(0.5)
# ---- 本机 HTTP/1.1 服务器(同样的 /bulk?size&delay) ----
def h1srv(port, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def h(c):
        c.settimeout(10); buf = b''
        try:
            while True:
                while b'\r\n\r\n' not in buf:
                    d = c.recv(65536)
                    if not d: return
                    buf += d
                head, buf = buf.split(b'\r\n\r\n', 1); path = head.split()[1].decode(); q = dict(x.split('=') for x in path.split('?', 1)[1].split('&')) if '?' in path else {}
                if int(q.get('delay', 0)): time.sleep(int(q['delay']) / 1000)
                c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n' % int(q.get('size', 1000)) + b'x' * int(q.get('size', 1000)))
        except Exception: pass
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
h1port = lab_port(); h1stop = [False]; h1srv(h1port, h1stop)

# ---- 客户端 ----
def h2_client(init_win=65535, conn_win=None, auto_ack=True):
    cctx = ssl.create_default_context(); cctx.check_hostname = False; cctx.verify_mode = ssl.CERT_NONE; cctx.set_alpn_protocols(['h2'])
    s = socket.create_connection(('127.0.0.1', srv_port)); ss = cctx.wrap_socket(s, server_hostname='localhost'); ss.settimeout(10)
    c = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True)); c.initiate_connection()
    c.update_settings({h2.settings.SettingCodes.INITIAL_WINDOW_SIZE: init_win})
    if conn_win: c.increment_flow_control_window(conn_win - 65535)
    ss.sendall(c.data_to_send()); return ss, c
def fetch_all(ss, c, sids, auto_ack=True, stall_after=None):
    done = set(); got = {s: 0 for s in sids}; t_done = {}; t0 = time.time()
    while len(done) < len(sids):
        try: d = ss.recv(65536)
        except socket.timeout: break
        if not d: break
        for e in c.receive_data(d):
            if isinstance(e, h2.events.DataReceived):
                got[e.stream_id] += len(e.data)
                if auto_ack: c.acknowledge_received_data(e.flow_controlled_length, e.stream_id)
            elif isinstance(e, h2.events.StreamEnded): done.add(e.stream_id); t_done[e.stream_id] = (time.time() - t0) * 1000
        ss.sendall(c.data_to_send())
    return got, t_done

print('== 一:多路复用:10 个请求,每个让服务器“思考”300 ms 再返回 20 KB。本机 netlab 每方向 50 ms(往返 100 ms)。三种做法的总耗时(含建立连接):HTTP/1.1 一条连接顺序发;HTTP/1.1 开 6 条连接并行(浏览器的传统做法);HTTP/2 一条连接 10 个流同时发')
N = 10
def h1_seq():
    t0 = time.time(); s = socket.create_connection(('127.0.0.1', h1port))
    for i in range(N):
        s.sendall(b'GET /bulk?size=20000&delay=300 HTTP/1.1\r\nHost: x\r\n\r\n'); buf = b''
        while b'\r\n\r\n' not in buf: buf += s.recv(65536)
        head, rest = buf.split(b'\r\n\r\n', 1)
        while len(rest) < 20000: rest += s.recv(65536)
    s.close(); return (time.time() - t0) * 1000
def h1_par(k=6):
    t0 = time.time(); q = list(range(N)); lock = threading.Lock()
    def w():
        s = socket.create_connection(('127.0.0.1', h1port))
        while True:
            with lock:
                if not q: break
                q.pop()
            s.sendall(b'GET /bulk?size=20000&delay=300 HTTP/1.1\r\nHost: x\r\n\r\n'); buf = b''
            while b'\r\n\r\n' not in buf: buf += s.recv(65536)
            head, rest = buf.split(b'\r\n\r\n', 1)
            while len(rest) < 20000: rest += s.recv(65536)
        s.close()
    th = [threading.Thread(target=w) for _ in range(k)]
    for t in th: t.start()
    for t in th: t.join()
    return (time.time() - t0) * 1000
def h2_mux():
    t0 = time.time(); ss, c = h2_client(conn_win=1 << 24, init_win=1 << 22); sids = []
    for i in range(N):
        sid = c.get_next_available_stream_id(); c.send_headers(sid, [(':method', 'GET'), (':path', '/bulk?size=20000&delay=300'), (':scheme', 'https'), (':authority', 'localhost')], end_stream=True); sids.append(sid)
    ss.sendall(c.data_to_send()); got, td = fetch_all(ss, c, sids); ss.close(); assert all(v == 20000 for v in got.values()), got
    return (time.time() - t0) * 1000, sorted(td.values())
with lossy(loss=0, delay=50, bw=0):
    a = statistics.median(h1_seq() for _ in range(2)); b = statistics.median(h1_par() for _ in range(2)); r = [h2_mux() for _ in range(2)]; cc = statistics.median(x[0] for x in r)
print(f'  HTTP/1.1 一条连接顺序发:{a:.0f} ms(≈ 握手 1 RTT + 10 × (1 RTT + 300 ms) = 100 + 10 × 400 = 4100 ms)')
print(f'  HTTP/1.1 6 条并行连接:{b:.0f} ms(10 个请求分两批:6 + 4,每批 1 RTT + 300 ms,加握手 100 ms ≈ 900 ms)')
print(f'  HTTP/2 一条连接:{cc:.0f} ms(含 TCP 握手 1 RTT + TLS 握手 1 RTT + 10 个流同时 1 RTT + 300 ms ≈ 600 ms);10 个流完成的时刻(ms,从发出请求起):{[round(x) for x in r[0][1]]}')

print('== 二:流量控制:服务器要发 1 MiB,客户端宣告的窗口只有 65535(默认),并且故意不确认(不发 WINDOW_UPDATE),看服务器发了多少就停了;然后补发 WINDOW_UPDATE,看继续')
ss, c = h2_client(init_win=65535); sid = c.get_next_available_stream_id()
c.send_headers(sid, [(':method', 'GET'), (':path', '/bulk?size=1048576'), (':scheme', 'https'), (':authority', 'localhost')], end_stream=True); ss.sendall(c.data_to_send()); got = 0; frames = 0; t0 = time.time(); ss.settimeout(1.5)
try:
    while True:
        d = ss.recv(65536)
        if not d: break
        for e in c.receive_data(d):
            if isinstance(e, h2.events.DataReceived): got += len(e.data); frames += 1
        ss.sendall(c.data_to_send())
except socket.timeout: pass
print(f'  不确认时:服务器发出 {got} 字节({frames} 个 DATA 帧)就停了(初始流窗口 65535、连接窗口 65535;停了 1.5 秒也不动)')
ss.settimeout(10); c.increment_flow_control_window(1 << 20, sid); c.increment_flow_control_window(1 << 20); ss.sendall(c.data_to_send()); t1 = time.time(); fin = False
while not fin:
    d = ss.recv(65536)
    if not d: break
    for e in c.receive_data(d):
        if isinstance(e, h2.events.DataReceived): got += len(e.data)
        if isinstance(e, h2.events.StreamEnded): fin = True
    ss.sendall(c.data_to_send())
print(f'  补发 WINDOW_UPDATE(流 + 连接各 +1 MiB)后:又过 {(time.time() - t1) * 1000:.0f} ms 传完,总共 {got} 字节')
ss.close()
print('  窗口大小决定吞吐:往返 100 ms 时,下载 4 MiB,客户端宣告不同的初始流窗口(连接窗口放到 16 MiB)的耗时')
for w in (65535, 262144, 1 << 20, 4 << 20):
    with lossy(loss=0, delay=50, bw=0):
        ts = []
        for rep in range(2):
            ss, c = h2_client(init_win=w, conn_win=1 << 24); sid = c.get_next_available_stream_id(); t0 = time.time()
            c.send_headers(sid, [(':method', 'GET'), (':path', '/bulk?size=4194304'), (':scheme', 'https'), (':authority', 'localhost')], end_stream=True); ss.sendall(c.data_to_send()); fetch_all(ss, c, [sid]); ts.append(time.time() - t0); ss.close()
    t = statistics.mean(ts); print(f'    初始窗口 {w:>8} 字节:{t:5.2f} 秒,{4194304 / t / 1e6:6.2f} MB/s(窗口 ÷ RTT = {w / 0.1 / 1e6:6.2f} MB/s)')

print('== 三:HPACK 头部压缩的效果:同一个连接上连续发 10 个头部相同的请求(含一个 200 字节的 Cookie),看每个请求的头部块大小')
hd = [(':method', 'GET'), (':scheme', 'https'), (':path', '/api/items?page=1'), (':authority', 'example.com'), ('user-agent', 'Mozilla/5.0 (X11; Linux x86_64) w85-test'), ('accept', 'application/json'), ('accept-encoding', 'gzip, br'), ('cookie', 'session=' + 'a' * 192)]
plain = sum(len(k) + len(v) + 4 for k, v in hd)
enc = hpack.Encoder(); sizes = [len(enc.encode(hd)) for _ in range(10)]
print(f'  10 个相同请求的头部块大小(字节):{sizes};同样内容用 HTTP/1.1 文本写要 {plain} 字节左右(每个头部名字 + ": " + 值 + CRLF)')
print(f'  第 1 个 {sizes[0]} 字节(新头部要写出来,同时放进动态表),第 2 个起 {sizes[1]} 字节(只是引用动态表的索引),压缩到 {sizes[1] / plain:.1%}')
enc2 = hpack.Encoder(); enc2.header_table_size = 0
sizes2 = [len(enc2.encode(hd)) for _ in range(3)]
print(f'  把动态表关掉(HEADER_TABLE_SIZE = 0):{sizes2}——每次都得重新写出来(只剩霍夫曼编码和静态表的压缩)')
hd2 = hd[:-1] + [('cookie', 'session=' + 'b' * 192)]
print(f'  只改一个头部的值(换一个 200 字节的 Cookie):下一个请求的头部块 {len(enc.encode(hd2))} 字节(新的 Cookie 要整个重发,其余仍是引用)')
print('  对比真实服务器:对 example.com 连续在同一个连接上发 3 个请求,看响应 HEADERS 帧的头部块大小')
cctx = ssl.create_default_context(); cctx.set_alpn_protocols(['h2']); s = socket.create_connection(('104.20.23.154', 443), timeout=8); ss = cctx.wrap_socket(s, server_hostname='example.com'); ss.settimeout(4)
c = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True)); c.initiate_connection(); ss.sendall(c.data_to_send()); blks = []
for i in range(3):
    sid = c.get_next_available_stream_id(); c.send_headers(sid, [(':method', 'GET'), (':path', '/'), (':scheme', 'https'), (':authority', 'example.com'), ('user-agent', 'w85')], end_stream=True); ss.sendall(c.data_to_send()); fin = False; hlen = None
    while not fin:
        d = ss.recv(65536)
        if not d: break
        for e in c.receive_data(d):
            if isinstance(e, h2.events.ResponseReceived): hlen = sum(len(k) + len(v) for k, v in e.headers)
            if isinstance(e, h2.events.DataReceived): c.acknowledge_received_data(e.flow_controlled_length, e.stream_id)
            if isinstance(e, h2.events.StreamEnded): fin = True
        ss.sendall(c.data_to_send())
    blks.append(hlen)
print(f'  example.com 三次响应的头部(解码后名字+值总字节):{blks}(线上 HPACK 编码的字节数在上一篇里看到过是 160 字节左右;解码后的原始大小在这里)')
ss.close(); h1stop[0] = True
