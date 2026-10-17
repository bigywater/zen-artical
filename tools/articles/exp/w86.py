import sys, os, re, struct, threading, statistics, errno, ssl, asyncio, datetime, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
import dpkt
from aioquic.asyncio.client import connect
from aioquic.asyncio.server import serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import HeadersReceived, DataReceived
from aioquic.quic.configuration import QuicConfiguration
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
tee('w86'); reset()
HOST = 'example.com'; IP = '104.20.23.154'
class C(QuicConnectionProtocol):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.h3 = H3Connection(self._quic); self.ev = asyncio.Queue()
    def quic_event_received(self, e):
        for x in self.h3.handle_event(e): self.ev.put_nowait(x)
async def h3_get(host, port, path='/', ticket=None, save=None, verify=True, timeout=8):
    cfg = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN, session_ticket=ticket)
    if save is not None: cfg.session_ticket_handler = lambda t: save.append(t)
    if not verify: cfg.verify_mode = ssl.CERT_NONE
    if host == IP: cfg.server_name = HOST
    t0 = time.time()
    async with connect(host, port, configuration=cfg, create_protocol=C, wait_connected=True) as c:
        t1 = time.time(); sid = c._quic.get_next_available_stream_id()
        c.h3.send_headers(sid, [(b':method', b'GET'), (b':scheme', b'https'), (b':authority', HOST.encode()), (b':path', path.encode())], end_stream=True); c.transmit()
        t2 = None; n = 0; st = None
        while True:
            e = await asyncio.wait_for(c.ev.get(), timeout)
            if isinstance(e, HeadersReceived): st = dict(e.headers).get(b':status'); t2 = time.time()
            if isinstance(e, DataReceived):
                n += len(e.data)
                if e.stream_ended: break
        t3 = time.time(); resumed = getattr(c._quic.tls, 'session_resumed', None); early = getattr(c._quic.tls, 'early_data_accepted', None)
        if save is not None:
            for _ in range(30):
                if save: break
                await asyncio.sleep(0.1)
        await asyncio.sleep(0.3)
        return dict(hs=(t1 - t0) * 1000, ttfb=(t2 - t1) * 1000, total=(t3 - t0) * 1000, status=st, n=n, resumed=resumed, early=early)
def run(co): return asyncio.run(co)

print('== 一:对 example.com 的 HTTP/3 请求:建立 QUIC 连接(握手)和取回首页要多久?和 TCP + TLS 1.3 + HTTP/2 比。各 5 次')
h3 = []
for i in range(5):
    try: h3.append(run(h3_get(IP, 443)))
    except Exception as e: print('  失败', repr(e)[:60])
def h2_time():
    ctx = ssl.create_default_context(); ctx.set_alpn_protocols(['h2']); t0 = time.time(); s = socket.create_connection((IP, 443), timeout=8); t1 = time.time(); ss = ctx.wrap_socket(s, server_hostname=HOST); t2 = time.time()
    import h2.connection, h2.config, h2.events
    c = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True)); c.initiate_connection(); ss.sendall(c.data_to_send()); sid = 1
    c.send_headers(sid, [(':method', 'GET'), (':path', '/'), (':scheme', 'https'), (':authority', HOST)], end_stream=True); ss.sendall(c.data_to_send()); got = False; ss.settimeout(6); t3 = None
    while not got:
        d = ss.recv(65536)
        if not d: break
        for e in c.receive_data(d):
            if isinstance(e, h2.events.ResponseReceived) and t3 is None: t3 = time.time()
            if isinstance(e, h2.events.StreamEnded): got = True
        ss.sendall(c.data_to_send())
    ss.close(); return (t1 - t0) * 1000, (t2 - t1) * 1000, (t3 - t2) * 1000
h2r = [h2_time() for _ in range(5)]
if h3:
    print(f'  HTTP/3:ALPN h3,握手(到可发请求)逐次 {[round(x["hs"]) for x in h3]} ms,中位 {statistics.median(x["hs"] for x in h3):.0f};请求发出到首字节 中位 {statistics.median(x["ttfb"] for x in h3):.0f} ms;总计 中位 {statistics.median(x["total"] for x in h3):.0f} ms;状态 {h3[0]["status"]},{h3[0]["n"]} 字节')
print(f'  HTTP/2:TCP 握手 中位 {statistics.median(x[0] for x in h2r):.0f} ms + TLS 握手 中位 {statistics.median(x[1] for x in h2r):.0f} ms + 请求到首字节 中位 {statistics.median(x[2] for x in h2r):.0f} ms;总计 中位 {statistics.median(sum(x) for x in h2r):.0f} ms')

print('== 二:QUIC 在线路上长什么样:抓 en0 上一次 HTTP/3 请求的 UDP 包(目的 example.com 的 443),逐个看方向、大小、包头形式')
def qinfo(p):
    b = p[0]; 
    if b & 0x80:
        typ = {0: 'Initial', 1: '0-RTT', 2: 'Handshake', 3: 'Retry'}[(b >> 4) & 3]; ver = struct.unpack('>I', p[1:5])[0]; dl = p[5]; return f'长包头 {typ} 版本 0x{ver:08x} DCID {dl} 字节'
    return '短包头(1-RTT)'
with Cap(f'udp port 443 and host {IP}', iface='en0', write=True, snaplen=2000) as c:
    r = run(h3_get(IP, 443)); time.sleep(0.5)
pk = []
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(buf)
        if e.type != 0x0800: continue
        ip = e.data; u = ip.data; pk.append((ts, 'C→S' if ip.dst == socket.inet_aton(IP) else 'S→C', bytes(u.data)))
t0 = pk[0][0]
print(f'  整个请求在线上:{len(pk)} 个 UDP 数据报,{sum(len(p[2]) for p in pk)} 字节(UDP 载荷);客户端→服务器 {sum(1 for p in pk if p[1] == "C→S")} 个 / {sum(len(p[2]) for p in pk if p[1] == "C→S")} 字节;服务器→客户端 {sum(1 for p in pk if p[1] == "S→C")} 个 / {sum(len(p[2]) for p in pk if p[1] == "S→C")} 字节')
for ts, d, p in pk[:12]: print(f'    +{(ts - t0) * 1000:7.1f} ms  {d}  {len(p):>5} 字节  {qinfo(p)}')
fi = pk[0][2]; print(f'  客户端第一个数据报 {len(fi)} 字节(规范要求 Initial 所在的数据报至少 1200 字节,故意填充,防止 QUIC 服务器被拿来做流量放大);版本 0x{struct.unpack(">I", fi[1:5])[0]:08x} = QUIC v1')

print('== 三:会话恢复与 0-RTT:第一次连接保存 session ticket;第二次带着 ticket 连。握手耗时对比,以及 TLS 报告的“恢复了会话”“0-RTT 被接受”(各 4 次)')
tick = []
first = run(h3_get(IP, 443, save=tick)); time.sleep(0.5)
print(f'  第一次(完整握手):握手 {first["hs"]:.0f} ms,收到 {len(tick)} 个 session ticket;resumed = {first["resumed"]}')
res = []
for i in range(4):
    try: res.append(run(h3_get(IP, 443, ticket=tick[-1] if tick else None)))
    except Exception as e: print('  失败', repr(e)[:60])
fulls = [run(h3_get(IP, 443)) for _ in range(4)]
if res: print(f'  带 ticket 恢复:握手 逐次 {[round(x["hs"]) for x in res]} ms,中位 {statistics.median(x["hs"] for x in res):.0f};resumed = {res[0]["resumed"]},early_data_accepted = {res[0]["early"]};总计中位 {statistics.median(x["total"] for x in res):.0f} ms')
print(f'  完整握手对照:握手 逐次 {[round(x["hs"]) for x in fulls]} ms,中位 {statistics.median(x["hs"] for x in fulls):.0f};总计中位 {statistics.median(x["total"] for x in fulls):.0f} ms')

print('== 四:丢包下 HTTP/3 与 HTTP/2 谁更好?本机服务器(自签名证书),netlab 每方向 50 ms、丢包 3%。同时取 10 个 100 KB 的资源:HTTP/2 一条 TCP 连接,HTTP/3 一条 QUIC 连接,各 4 次')
key = ec.generate_private_key(ec.SECP256R1()); name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
cert = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=2)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), False).sign(key, hashes.SHA256())
CF, KF = str(WT / 'w86_cert.pem'), str(WT / 'w86_key.pem'); open(CF, 'wb').write(cert.public_bytes(serialization.Encoding.PEM)); open(KF, 'wb').write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
SIZE = 100000
class H3Srv(QuicConnectionProtocol):
    def __init__(self, *a, **k): super().__init__(*a, **k); self.h3 = None
    def quic_event_received(self, e):
        if self.h3 is None: self.h3 = H3Connection(self._quic)
        for x in self.h3.handle_event(e):
            if isinstance(x, HeadersReceived):
                self.h3.send_headers(x.stream_id, [(b':status', b'200'), (b'content-length', str(SIZE).encode())]); self.h3.send_data(x.stream_id, b'x' * SIZE, end_stream=True); self.transmit()
import h2.connection, h2.config, h2.events, h2.settings
class H2Srv(asyncio.Protocol):
    def connection_made(self, tr):
        self.tr = tr; self.conn = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=False, header_encoding='utf-8')); self.conn.initiate_connection(); self.tr.write(self.conn.data_to_send()); self.ev = asyncio.Event()
    def data_received(self, data):
        for e in self.conn.receive_data(data):
            if isinstance(e, h2.events.RequestReceived): asyncio.ensure_future(self.handle(e.stream_id))
            elif isinstance(e, h2.events.WindowUpdated): self.ev.set()
        self.tr.write(self.conn.data_to_send())
    async def handle(self, sid):
        self.conn.send_headers(sid, [(':status', '200'), ('content-length', str(SIZE))]); sent = 0
        while sent < SIZE:
            w = min(self.conn.local_flow_control_window(sid), SIZE - sent, 16384)
            if w <= 0: self.ev.clear(); await self.ev.wait(); continue
            self.conn.send_data(sid, b'x' * w); sent += w; self.tr.write(self.conn.data_to_send())
        self.conn.end_stream(sid); self.tr.write(self.conn.data_to_send())
p3 = lab_port(); p2 = lab_port()
async def servers():
    qc = QuicConfiguration(is_client=False, alpn_protocols=H3_ALPN); qc.load_cert_chain(CF, KF)
    await serve('127.0.0.1', p3, configuration=qc, create_protocol=H3Srv)
    sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); sctx.load_cert_chain(CF, KF); sctx.set_alpn_protocols(['h2'])
    await asyncio.get_running_loop().create_server(H2Srv, '127.0.0.1', p2, ssl=sctx)
    while True: await asyncio.sleep(3600)
def srv_thread():
    asyncio.run(servers())
threading.Thread(target=srv_thread, daemon=True).start(); time.sleep(1)
async def h3_many(n=10):
    cfg = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN, verify_mode=ssl.CERT_NONE); t0 = time.time()
    async with connect('127.0.0.1', p3, configuration=cfg, create_protocol=C, wait_connected=True) as c:
        sids = []
        for i in range(n):
            sid = c._quic.get_next_available_stream_id(); c.h3.send_headers(sid, [(b':method', b'GET'), (b':scheme', b'https'), (b':authority', b'localhost'), (b':path', b'/')], end_stream=True); sids.append(sid)
        c.transmit(); done = {}; got = {s: 0 for s in sids}
        while len(done) < n:
            e = await asyncio.wait_for(c.ev.get(), 25)
            if isinstance(e, DataReceived):
                got[e.stream_id] += len(e.data)
                if e.stream_ended: done[e.stream_id] = (time.time() - t0) * 1000
        return (time.time() - t0) * 1000, sorted(done.values())
def h2_many(n=10):
    cctx = ssl.create_default_context(); cctx.check_hostname = False; cctx.verify_mode = ssl.CERT_NONE; cctx.set_alpn_protocols(['h2']); t0 = time.time()
    s = socket.create_connection(('127.0.0.1', p2)); ss = cctx.wrap_socket(s, server_hostname='localhost'); ss.settimeout(30)
    c = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True)); c.initiate_connection(); c.increment_flow_control_window((1 << 24) - 65535); c.update_settings({h2.settings.SettingCodes.INITIAL_WINDOW_SIZE: 1 << 22}); ss.sendall(c.data_to_send()); sids = []
    for i in range(n):
        sid = c.get_next_available_stream_id(); c.send_headers(sid, [(':method', 'GET'), (':path', '/'), (':scheme', 'https'), (':authority', 'localhost')], end_stream=True); sids.append(sid)
    ss.sendall(c.data_to_send()); done = {}
    while len(done) < n:
        d = ss.recv(65536)
        if not d: break
        for e in c.receive_data(d):
            if isinstance(e, h2.events.DataReceived): c.acknowledge_received_data(e.flow_controlled_length, e.stream_id)
            if isinstance(e, h2.events.StreamEnded): done[e.stream_id] = (time.time() - t0) * 1000
        ss.sendall(c.data_to_send())
    ss.close(); return (time.time() - t0) * 1000, sorted(done.values())
rows = {}
for loss in (0, 3):
    with lossy(loss=loss, delay=50, bw=0):
        r3 = []; r2 = []
        for i in range(4):
            try: r3.append(run(h3_many()))
            except Exception as e: print('  h3 失败', repr(e)[:50])
            try: r2.append(h2_many())
            except Exception as e: print('  h2 失败', repr(e)[:50])
        rows[loss] = (r3, r2)
print('    丢包率    协议      总耗时(ms)逐次                      中位     第一个流完成 中位   最后一个流完成 中位')
for loss, (r3, r2) in rows.items():
    for nm, r in (('HTTP/2', r2), ('HTTP/3', r3)):
        if r: print(f'    {loss}%       {nm}   {[round(x[0]) for x in r]}   {statistics.median(x[0] for x in r):>6.0f}   {statistics.median(x[1][0] for x in r):>8.0f}        {statistics.median(x[1][-1] for x in r):>8.0f}')
