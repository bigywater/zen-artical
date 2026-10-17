import sys, os, re, struct, threading, statistics, errno, random, string, base64, http.client, ssl; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dns.message, dns.query, dns.rdatatype, dns.flags, dns.rcode, dns.exception
import dpkt
tee('w72'); reset()
ALI = '223.5.5.5'; ALI_NAME = 'dns.alidns.com'
ctx = ssl.create_default_context()
class DoHConn(http.client.HTTPSConnection):
    def __init__(self, timeout=6): super().__init__(ALI_NAME, 443, timeout=timeout, context=ctx)
    def connect(self):
        sk = socket.create_connection((ALI, 443), timeout=self.timeout); self.sock = ctx.wrap_socket(sk, server_hostname=ALI_NAME)
def rand(n=8): return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))
def answers(r): return sorted(x.to_text() for rr in r.answer for x in rr if rr.rdtype == dns.rdatatype.A) if r else None

print('== 一:加密 DNS 能不能连上:对常见公共解析器的 DoT(TCP 853)和 DoH(TCP 443)各试一次连接和 TLS 握手(超时 4 秒)')
tests = [('1.1.1.1', 853, 'one.one.one.one', 'Cloudflare DoT'), ('1.0.0.1', 853, 'one.one.one.one', 'Cloudflare DoT'), ('8.8.8.8', 853, 'dns.google', 'Google DoT'), ('9.9.9.9', 853, 'dns.quad9.net', 'Quad9 DoT'), ('94.140.14.14', 853, 'dns.adguard-dns.com', 'AdGuard DoT'), (ALI, 853, ALI_NAME, '阿里 DoT'), ('1.1.1.1', 443, 'one.one.one.one', 'Cloudflare DoH'), ('8.8.8.8', 443, 'dns.google', 'Google DoH'), ('9.9.9.9', 443, 'dns.quad9.net', 'Quad9 DoH'), (ALI, 443, ALI_NAME, '阿里 DoH'), ('104.20.23.154', 443, 'example.com', '对照:example.com 的 HTTPS')]
for ip, port, sni, nm in tests:
    t = time.time()
    try:
        s = socket.create_connection((ip, port), timeout=4); t1 = time.time()
        try: ss = ctx.wrap_socket(s, server_hostname=sni); print(f'  {nm:<22} {ip}:{port}:TCP 连上 {(t1 - t) * 1000:.0f} ms,TLS 握手成功 {(time.time() - t1) * 1000:.0f} ms({ss.version()})'); ss.close()
        except Exception as e: print(f'  {nm:<22} {ip}:{port}:TCP 连上 {(t1 - t) * 1000:.0f} ms,但 TLS 握手失败:{type(e).__name__}'); s.close()
    except Exception as e: print(f'  {nm:<22} {ip}:{port}:TCP 连接失败({type(e).__name__},{(time.time() - t) * 1000:.0f} ms)')
print('  结论只限于这台机器所在的网络:能握手的才能拿来做后面的对比,所以后面用阿里的 223.5.5.5(UDP 53、DoT、DoH 都通)')

print('== 二:同一个解析器 223.5.5.5 上,三种传输的耗时:普通 UDP 53、DoT(853)、DoH(443,HTTP/1.1 POST)。各 6 次;加密的分“新建连接的第一问”和“复用连接的后续问”')
def udp_q(name):
    m = dns.message.make_query(name, 'A'); t0 = time.time(); r = dns.query.udp(m, ALI, timeout=3); return r, (time.time() - t0) * 1000
res = {k: [] for k in ('UDP 53', 'DoT 新连接(TCP+TLS+查询)', 'DoT 复用连接', 'DoH 新连接(TCP+TLS+HTTP+查询)', 'DoH 复用连接', 'DoH 复用连接(按 IP 连,不发 SNI)')}
for i in range(6):
    r, t = udp_q('example.com'); res['UDP 53'].append(t)
    t0 = time.time(); s = socket.create_connection((ALI, 853), timeout=4); ss = ctx.wrap_socket(s, server_hostname=ALI_NAME); m = dns.message.make_query('example.com', 'A'); dns.query.tls(m, ALI, timeout=4, sock=ss, server_hostname=ALI_NAME); res['DoT 新连接(TCP+TLS+查询)'].append((time.time() - t0) * 1000)
    t0 = time.time(); dns.query.tls(dns.message.make_query('example.com', 'A'), ALI, timeout=4, sock=ss, server_hostname=ALI_NAME); res['DoT 复用连接'].append((time.time() - t0) * 1000); ss.close()
    t0 = time.time(); c = DoHConn(5); c.request('POST', '/dns-query', body=dns.message.make_query('example.com', 'A').to_wire(), headers={'Content-Type': 'application/dns-message', 'Accept': 'application/dns-message', 'Host': ALI_NAME}); rr = c.getresponse(); rr.read(); res['DoH 新连接(TCP+TLS+HTTP+查询)'].append((time.time() - t0) * 1000)
    t0 = time.time(); c.request('POST', '/dns-query', body=dns.message.make_query('example.com', 'A').to_wire(), headers={'Content-Type': 'application/dns-message', 'Accept': 'application/dns-message', 'Host': ALI_NAME}); rr = c.getresponse(); body = rr.read(); res['DoH 复用连接'].append((time.time() - t0) * 1000); c.close()
    c0 = http.client.HTTPSConnection(ALI, 443, timeout=5, context=ctx)
    for j in range(2):
        t0 = time.time(); c0.request('POST', '/dns-query', body=dns.message.make_query('example.com', 'A').to_wire(), headers={'Content-Type': 'application/dns-message', 'Accept': 'application/dns-message', 'Host': ALI_NAME}); c0.getresponse().read(); tt = (time.time() - t0) * 1000
    res['DoH 复用连接(按 IP 连,不发 SNI)'].append(tt); c0.close()
for k, v in res.items(): print(f'  {k:<32}:{[round(x, 1) for x in v]} ms,中位 {statistics.median(v):.1f} ms')
print(f'  DoH 响应:HTTP {rr.status},头 {[(k, v) for k, v in rr.getheaders() if k.lower() in ("content-type", "cache-control", "server")]};DNS 响应体 {len(body)} 字节;DNS 里 A 记录的 TTL = {[x.ttl for x in dns.message.from_wire(body).answer]}')

print('== 三:连接细节:DoT / DoH 用的 TLS 版本、套件、ALPN 和证书(对着 223.5.5.5)')
for port, alpn in ((853, ['dot']), (443, ['h2', 'http/1.1'])):
    c2 = ssl.create_default_context(); c2.set_alpn_protocols(alpn); s = socket.create_connection((ALI, port), timeout=4); ss = c2.wrap_socket(s, server_hostname=ALI_NAME); cert = ss.getpeercert()
    sans = [v for k, v in cert['subjectAltName']]
    print(f'  端口 {port}:{ss.version()},套件 {ss.cipher()[0]},ALPN 协商结果 {ss.selected_alpn_protocol()};证书主体 {dict(x[0] for x in cert["subject"]).get("commonName")},签发者 {dict(x[0] for x in cert["issuer"]).get("organizationName")},有效期 {cert["notBefore"]} ~ {cert["notAfter"]};SAN 共 {len(sans)} 项,含本 IP {ALI in sans}')
    ss.close()

print('== 四:路径上的观察者能看到什么(抓 en0):对一个随机的名字各问一次,在抓到的字节里搜这个名字')
def capture_find(fn, name):
    with Cap(f'host {ALI}', iface='en0', write=True, snaplen=2000) as c:
        fn(); time.sleep(0.6)
    n = 0; byt = 0; found = 0; sni = False; up = 0; down = 0
    with open(c.pcap, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            if e.type != 0x0800: continue
            ip = e.data; n += 1; byt += ip.len
            if ip.dst == socket.inet_aton(ALI): up += ip.len
            else: down += ip.len
            raw = bytes(buf)
            if name.split('.')[0].encode() in raw: found += 1
            if ALI_NAME.encode() in raw: sni = True
    return n, byt, found, sni, up, down
nm = rand() + '.example.com'
for label, fn in (('UDP 53', lambda: dns.query.udp(dns.message.make_query(nm, 'A'), ALI, timeout=3)),
                  ('DoT', lambda: dns.query.tls(dns.message.make_query(nm, 'A'), ALI, timeout=4, server_hostname=ALI_NAME)),
                  ('DoH', lambda: (lambda c: (c.request('POST', '/dns-query', body=dns.message.make_query(nm, 'A').to_wire(), headers={'Content-Type': 'application/dns-message', 'Host': ALI_NAME}), c.getresponse().read(), c.close()))(DoHConn(5)))):
    n, byt, found, sni, up, down = capture_find(fn, nm)
    print(f'  {label:<7}:{n} 个 IP 包,共 {byt} 字节(上行 {up} / 下行 {down});包含查询名字(随机的第一段标签)明文的包 {found} 个;包里能找到服务器名 "{ALI_NAME}"(TLS 的 SNI)的:{"是" if sni else "否"}')
print('  UDP 53 把名字原样暴露给路径上的任何设备;DoT / DoH 的名字被加密,但目标 IP、端口、TLS 的 SNI(服务器名)、包的大小和时间仍然可见')

print('== 五:同一个问题,不同传输,答案一样吗?www.bbc.co.uk 的 A 记录:发给 1.1.1.1 的 UDP 53(第 67 篇看到过异常)、发给 223.5.5.5 的 UDP 53、DoT、DoH')
def doh_q(name):
    c = DoHConn(6); t0 = time.time(); c.request('POST', '/dns-query', body=dns.message.make_query(name, 'A').to_wire(), headers={'Content-Type': 'application/dns-message', 'Accept': 'application/dns-message', 'Host': ALI_NAME}); b = c.getresponse().read(); c.close(); return dns.message.from_wire(b), (time.time() - t0) * 1000
def dot_q(name):
    t0 = time.time(); r = dns.query.tls(dns.message.make_query(name, 'A'), ALI, timeout=5, server_hostname=ALI_NAME); return r, (time.time() - t0) * 1000
for nm in ('www.bbc.co.uk', 'example.com'):
    print(f'  {nm}:')
    for label, f in (('1.1.1.1 UDP 53', lambda: (lambda m, t0: (dns.query.udp(m, '1.1.1.1', timeout=4), (time.time() - t0) * 1000))(dns.message.make_query(nm, 'A'), time.time())),
                     ('223.5.5.5 UDP 53', lambda: (lambda m, t0: (dns.query.udp(m, ALI, timeout=4), (time.time() - t0) * 1000))(dns.message.make_query(nm, 'A'), time.time())),
                     ('223.5.5.5 DoT', lambda: dot_q(nm)), ('223.5.5.5 DoH', lambda: doh_q(nm))):
        try: r, t = f(); print(f'    {label:<18}:{t:6.0f} ms,A 记录 {answers(r)}')
        except Exception as e: print(f'    {label:<18}:失败 {type(e).__name__}')
