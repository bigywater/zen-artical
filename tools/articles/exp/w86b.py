import sys, os, re, struct, threading, statistics, ssl, asyncio, datetime, time, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
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
import h2.connection, h2.config, h2.events, h2.settings
tee('w86b'); reset()
CURL = '/opt/homebrew/opt/curl/bin/curl'; CADDY = '/opt/homebrew/bin/caddy'
key = ec.generate_private_key(ec.SECP256R1()); name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
cert = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=2)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), False).sign(key, hashes.SHA256())
CF, KF = str(WT / 'w86_cert.pem'), str(WT / 'w86_key.pem'); open(CF, 'wb').write(cert.public_bytes(serialization.Encoding.PEM)); open(KF, 'wb').write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
SIZE = 100000
class C(QuicConnectionProtocol):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.h3 = H3Connection(self._quic); self.ev = asyncio.Queue()
    def quic_event_received(self, e):
        for x in self.h3.handle_event(e): self.ev.put_nowait(x)
class H3Srv(QuicConnectionProtocol):
    def __init__(self, *a, **k): super().__init__(*a, **k); self.h3 = None
    def quic_event_received(self, e):
        if self.h3 is None: self.h3 = H3Connection(self._quic)
        for x in self.h3.handle_event(e):
            if isinstance(x, HeadersReceived):
                self.h3.send_headers(x.stream_id, [(b':status', b'200'), (b'content-length', str(SIZE).encode())]); self.h3.send_data(x.stream_id, b'x' * SIZE, end_stream=True); self.transmit()
TICKETS = {}
p_a = lab_port(); p_c = lab_port(); p_a2 = lab_port()
async def servers():
    qc = QuicConfiguration(is_client=False, alpn_protocols=H3_ALPN); qc.load_cert_chain(CF, KF)
    await serve('127.0.0.1', p_a, configuration=qc, create_protocol=H3Srv, session_ticket_fetcher=TICKETS.get, session_ticket_handler=lambda t: TICKETS.__setitem__(t.ticket, t))
    while True: await asyncio.sleep(3600)
threading.Thread(target=lambda: asyncio.run(servers()), daemon=True).start(); time.sleep(1)

print('== 五:0-RTT 实测(本机自己的 aioquic 服务端,开了 session ticket 与 early data;netlab 每个方向 50 ms,往返 100 ms)。先完整握手一次拿 session ticket,然后量三种连法从开始连接到收到响应头、响应体收完各要多久,各 6 次:A 完整握手(不带 ticket);B 带 ticket 恢复会话、等握手完成再发请求;C 带 ticket 的 0-RTT,握手没完成就把请求发出去')
async def get(ticket=None, zero_rtt=False, save=None):
    cfg = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN, verify_mode=ssl.CERT_NONE, session_ticket=ticket)
    t0 = time.time()
    async with connect('127.0.0.1', p_a, configuration=cfg, create_protocol=C, wait_connected=not zero_rtt, session_ticket_handler=(lambda t: save.append(t)) if save is not None else None) as c:
        sid = c._quic.get_next_available_stream_id()
        c.h3.send_headers(sid, [(b':method', b'GET'), (b':scheme', b'https'), (b':authority', b'localhost'), (b':path', b'/')], end_stream=True); c.transmit()
        th = None
        while True:
            e = await asyncio.wait_for(c.ev.get(), 20)
            if isinstance(e, HeadersReceived) and th is None: th = time.time()
            if isinstance(e, DataReceived) and e.stream_ended: break
        t3 = time.time(); tls = c._quic.tls
        if save is not None:
            for _ in range(30):
                if save: break
                await asyncio.sleep(0.1)
        await asyncio.sleep(0.3)
        return dict(head=(th - t0) * 1000, total=(t3 - t0) * 1000, resumed=tls.session_resumed, early=tls.early_data_accepted)
with lossy(loss=0, delay=50, bw=0):
    saved = []
    r0 = asyncio.run(get(save=saved)); time.sleep(0.5)
    print(f'  第一次(完整握手,同时保存 session ticket):响应头 {r0["head"]:.0f} ms,收完 {r0["total"]:.0f} ms;收到 {len(saved)} 个 ticket;ticket 里 max_early_data_size = {saved[-1].max_early_data_size if saved else None}')
    res = {'A 完整握手': [], 'B 带 ticket,等握手完成': [], 'C 带 ticket,0-RTT': []}
    for i in range(6):
        res['A 完整握手'].append(asyncio.run(get()))
        res['B 带 ticket,等握手完成'].append(asyncio.run(get(ticket=saved[-1])))
        res['C 带 ticket,0-RTT'].append(asyncio.run(get(ticket=saved[-1], zero_rtt=True)))
for k, v in res.items():
    print(f'    {k:<24} 响应头 逐次 {[round(x["head"]) for x in v]} 中位 {statistics.median(x["head"] for x in v):.0f} ms;收完 中位 {statistics.median(x["total"] for x in v):.0f} ms;session_resumed = {v[0]["resumed"]},early_data_accepted = {v[0]["early"]}')
print('  (往返 100 ms:A、B 应当约等于 2 个往返——1 个等握手,1 个等响应;C 约等于 1 个往返)')

print('== 六:丢包下的 HTTP/3 与 HTTP/2 到底慢在协议还是实现?把 w86 第四节里的 “aioquic 客户端 + aioquic 服务端” 换成原生实现对照:客户端用 curl 8.22(ngtcp2 / nghttp3 / nghttp2,C 写的),服务端用 Caddy 2.11(Go 的 quic-go 与标准库 HTTP/2),交叉组合成 2×2。同样是同时取 10 个 100 KB 的资源,一条连接;netlab 每方向 50 ms,丢包 0% 和 3%,每格 4 次')
caddyfile = WT / 'Caddyfile'
caddyfile.write_text('{\n  admin off\n  skip_install_trust\n  auto_https disable_redirects\n  storage file_system %s\n}\nlocalhost:%d {\n  bind 127.0.0.1\n  tls internal\n  root * %s\n  file_server\n}\n' % (WT / 'caddydata' / 'store', p_c, WT / 'caddyroot'))
cenv = dict(os.environ, HOME=str(WT / 'caddydata'), XDG_DATA_HOME=str(WT / 'caddydata'), XDG_CONFIG_HOME=str(WT / 'caddydata'))
cad = subprocess.Popen([CADDY, 'run', '--config', str(caddyfile), '--adapter', 'caddyfile'], env=cenv, stdout=subprocess.DEVNULL, stderr=open(WT / 'caddy.log', 'wb'))
atexit.register(lambda: cad.terminate())
for _ in range(60):
    r = subprocess.run([CURL, '-sk', '--http2', '--resolve', f'localhost:{p_c}:127.0.0.1', '-o', '/dev/null', '-w', '%{http_code}', f'https://localhost:{p_c}/f.bin'], capture_output=True, text=True)
    if r.stdout.strip() == '200': break
    time.sleep(0.5)
else: print('  caddy 没起来', open(WT / 'caddy.log').read()[-300:]); sys.exit(1)
r = subprocess.run([CURL, '-sk', '--http3-only', '--resolve', f'localhost:{p_c}:127.0.0.1', '-o', '/dev/null', '-w', '%{http_code} %{http_version} %{size_download}', f'https://localhost:{p_c}/f.bin'], capture_output=True, text=True)
print('  自检:curl --http3-only 取 Caddy 的 100 KB 文件 →', r.stdout.strip(), '(状态码 / HTTP 版本 / 字节数)')

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
async def servers2():
    sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); sctx.load_cert_chain(CF, KF); sctx.set_alpn_protocols(['h2'])
    await asyncio.get_running_loop().create_server(H2Srv, '127.0.0.1', p_a2, ssl=sctx)
    while True: await asyncio.sleep(3600)
threading.Thread(target=lambda: asyncio.run(servers2()), daemon=True).start(); time.sleep(1)

async def h3_many(port, n=10):
    cfg = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN, verify_mode=ssl.CERT_NONE, server_name='localhost'); t0 = time.time()
    async with connect('127.0.0.1', port, configuration=cfg, create_protocol=C, wait_connected=True) as c:
        sids = []
        for i in range(n):
            sid = c._quic.get_next_available_stream_id(); c.h3.send_headers(sid, [(b':method', b'GET'), (b':scheme', b'https'), (b':authority', b'localhost'), (b':path', b'/f.bin')], end_stream=True); sids.append(sid)
        c.transmit(); done = {}
        while len(done) < n:
            e = await asyncio.wait_for(c.ev.get(), 40)
            if isinstance(e, DataReceived) and e.stream_ended: done[e.stream_id] = (time.time() - t0) * 1000
        return (time.time() - t0) * 1000, sorted(done.values())
def h2_many(port, n=10):
    cctx = ssl.create_default_context(); cctx.check_hostname = False; cctx.verify_mode = ssl.CERT_NONE; cctx.set_alpn_protocols(['h2']); t0 = time.time()
    s = socket.create_connection(('127.0.0.1', port)); ss = cctx.wrap_socket(s, server_hostname='localhost'); ss.settimeout(40)
    c = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True)); c.initiate_connection(); c.increment_flow_control_window((1 << 24) - 65535); c.update_settings({h2.settings.SettingCodes.INITIAL_WINDOW_SIZE: 1 << 22}); sids = []
    for i in range(n):
        sid = c.get_next_available_stream_id(); c.send_headers(sid, [(':method', 'GET'), (':path', '/f.bin'), (':scheme', 'https'), (':authority', 'localhost')], end_stream=True); sids.append(sid)
    ss.sendall(c.data_to_send()); done = {}
    while len(done) < n:
        d = ss.recv(65536)
        if not d: break
        for e in c.receive_data(d):
            if isinstance(e, h2.events.DataReceived): c.acknowledge_received_data(e.flow_controlled_length, e.stream_id)
            if isinstance(e, h2.events.StreamEnded): done[e.stream_id] = (time.time() - t0) * 1000
        ss.sendall(c.data_to_send())
    ss.close(); return (time.time() - t0) * 1000, sorted(done.values())
def curl_many(flag, port, n=10):
    t0 = time.time()
    r = subprocess.run([CURL, '-sk', flag, '--resolve', f'localhost:{port}:127.0.0.1', '--parallel', '--parallel-immediate', '--parallel-max', str(n), '--max-time', '90', '-o', '/dev/null', '-w', '%{time_total} %{size_download}\n', f'https://localhost:{port}/f.bin?n=[1-{n}]'], capture_output=True, text=True)
    wall = (time.time() - t0) * 1000
    rows = [l.split() for l in r.stdout.strip().splitlines() if l.strip()]
    ok = [x for x in rows if len(x) == 2 and int(x[1]) == SIZE]
    if len(ok) != n: raise RuntimeError(f'curl 只完成 {len(ok)}/{n}')
    return wall, sorted(float(x[0]) * 1000 for x in ok)
async def noop(): pass
CASES = [('HTTP/3', 'aioquic 客户端 → aioquic 服务端', lambda: asyncio.run(h3_many(p_a))), ('HTTP/3', 'aioquic 客户端 → Caddy 服务端', lambda: asyncio.run(h3_many(p_c))),
         ('HTTP/3', 'curl 客户端 → aioquic 服务端', lambda: curl_many('--http3-only', p_a)), ('HTTP/3', 'curl 客户端 → Caddy 服务端', lambda: curl_many('--http3-only', p_c)),
         ('HTTP/2', 'python h2 客户端 → python h2 服务端', lambda: h2_many(p_a2)), ('HTTP/2', 'python h2 客户端 → Caddy 服务端', lambda: h2_many(p_c)),
         ('HTTP/2', 'curl 客户端 → python h2 服务端', lambda: curl_many('--http2', p_a2)), ('HTTP/2', 'curl 客户端 → Caddy 服务端', lambda: curl_many('--http2', p_c))]
print('    丢包率  协议      客户端 → 服务端                         总耗时(ms)逐次                    中位')
for loss in (0, 3):
    with lossy(loss=loss, delay=50, bw=0):
        for proto, nm, fn in CASES:
            rs = []
            for i in range(4):
                try: rs.append(fn()[0])
                except Exception as e: rs.append(None); print('    失败', nm, repr(e)[:80])
            ok = [x for x in rs if x]
            print(f'    {loss}%     {proto}   {nm:<38} {[round(x) if x else None for x in rs]}   {statistics.median(ok) if ok else float("nan"):>7.0f}')
cad.terminate()
