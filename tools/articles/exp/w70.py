import sys, os, re, struct, threading, statistics, errno, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dns.message, dns.query, dns.rdatatype, dns.flags, dns.rcode, dns.exception, dns.edns
import dpkt
tee('w70'); reset()
R = '1.1.1.1'
def udp(server, m, tmo=3):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(tmo); t0 = time.time()
    try: s.sendto(m.to_wire(), (server, 53)); d, _ = s.recvfrom(65535); return d, (time.time() - t0) * 1000
    except socket.timeout: return None, None
    finally: s.close()
def tcp_query(server, m, tmo=4, sock=None):
    own = sock is None
    t0 = time.time()
    if own: sock = socket.create_connection((server, 53), timeout=tmo)
    t1 = time.time(); w = m.to_wire(); sock.sendall(struct.pack('!H', len(w)) + w)
    hdr = b''
    while len(hdr) < 2: hdr += sock.recv(2 - len(hdr))
    n = struct.unpack('!H', hdr)[0]; buf = b''
    while len(buf) < n: buf += sock.recv(n - len(buf))
    t2 = time.time()
    if own: sock.close()
    return buf, (t1 - t0) * 1000, (t2 - t1) * 1000, sock
def mkm(name, t, edns=-1, payload=1232, do=False, rd=True):
    m = dns.message.make_query(name, t, use_edns=edns if edns >= 0 else False, payload=payload, want_dnssec=do)
    if not rd: m.flags &= ~dns.flags.RD
    return m
def retry(f, n=3):
    for i in range(n):
        r = f()
        if r and r[0]: return r
    return (None, None)

print('== 一:不带 EDNS0 的 DNS 报文走 UDP 最多 512 字节。根区的 DNSKEY 记录集比这大:不带 EDNS0 问 UDP,看是否被截断(TC),再用 TCP 重问')
m = mkm('.', 'DNSKEY')
d, t = retry(lambda: udp(R, m))
r = dns.message.from_wire(d, ignore_trailing=True) if d else None
if r: print(f'  UDP(无 EDNS0):响应 {len(d)} 字节,标志 {dns.flags.to_text(r.flags)},回答 {sum(len(x) for x in r.answer)} 条;TC 位 = {bool(r.flags & dns.flags.TC)}({"被截断:服务器放不下就只回头部和问题,让客户端改用 TCP" if r.flags & dns.flags.TC else "没有截断"})')
d2, tc, tq, _ = tcp_query(R, m); r2 = dns.message.from_wire(d2)
print(f'  TCP 重问:响应 {len(d2)} 字节,标志 {dns.flags.to_text(r2.flags)},回答 {sum(len(x) for x in r2.answer)} 条(DNSKEY);建立连接 {tc:.0f} ms + 查询往返 {tq:.0f} ms')

print('== 二:EDNS0 的 OPT 伪记录:它放在附加区,名字是根(00),类型 41,“类”字段被借来放 UDP 载荷大小,“TTL”字段被借来放扩展 RCODE / 版本 / 标志(DO 位 = 要求 DNSSEC 数据)')
m = mkm('example.com', 'A', edns=0, payload=1232, do=True); w = m.to_wire()
print(f'  查询 {len(w)} 字节;末尾 11 字节就是 OPT:{w[-11:].hex(" ")}')
print(f'    00 = 名字(根);{struct.unpack("!H", w[-10:-8])[0]} = 类型 OPT(41);{struct.unpack("!H", w[-8:-6])[0]} = 通告的 UDP 载荷大小;{w[-6]:02x} = 扩展 RCODE,{w[-5]:02x} = EDNS 版本,{struct.unpack("!H", w[-4:-2])[0]:04x} = 标志(最高位 DO = {bool(struct.unpack("!H", w[-4:-2])[0] & 0x8000)});{struct.unpack("!H", w[-2:])[0]} = RDLENGTH(选项总长)')
d, t = retry(lambda: udp(R, m)); r = dns.message.from_wire(d)
opt = r.opt
print(f'  响应 {len(d)} 字节;响应里的 OPT:{"有" if opt else "无"},服务器通告的 UDP 载荷大小 = {r.payload},DO 位回显 = {bool(r.ednsflags & 0x8000)},选项 {[o.otype for o in (opt[0].options if opt else [])]}')
for pl in (512, 1232, 4096):
    m = mkm('example.com', 'A', edns=0, payload=pl); d, t = retry(lambda: udp(R, m)); print(f'  通告 payload={pl}:响应 {len(d)} 字节,服务器回的 payload = {dns.message.from_wire(d).payload}')

print('== 三:DNS over TCP 的帧格式:每条消息前加 2 字节的长度。测一次 TCP 查询的字节,以及耗时:UDP 一问一答;新建 TCP 连接的一问一答;同一 TCP 连接上的第二问')
m = mkm('example.com', 'A', edns=0)
w = m.to_wire(); print(f'  TCP 上发送的字节:{struct.pack("!H", len(w)).hex()} + {len(w)} 字节报文(前两个字节 {len(w):#06x} = {len(w)} 就是后面报文的长度)')
res = {'UDP': [], 'TCP 新连接(连接 + 查询)': [], 'TCP 复用连接的第 2 问': []}
for i in range(6):
    d, t = retry(lambda: udp(R, m))
    if t: res['UDP'].append(t)
    b, tc, tq, sk = tcp_query(R, m); res['TCP 新连接(连接 + 查询)'].append(tc + tq)
    sk = socket.create_connection((R, 53), timeout=4); tcp_query(R, m, sock=sk); b, a, tq2, _ = tcp_query(R, m, sock=sk); sk.close(); res['TCP 复用连接的第 2 问'].append(tq2)
    time.sleep(0.2)
for k, v in res.items(): print(f'  {k:<26}:{[round(x) for x in v]} ms,中位 {statistics.median(v):.0f} ms')
print(f'  到 1.1.1.1 的网络往返约 {statistics.median(res["UDP"]):.0f} ms:UDP 一个往返;TCP 新连接多一个握手往返(约 2 倍);复用连接的后续查询回到一个往返')

print('== 四:一次查询在线路上的包数和字节(抓 en0):UDP 一问一答 vs TCP 新连接一问一答')
def wirecount(fn):
    with Cap(f'host {R} and port 53', iface='en0', write=True, snaplen=200) as c:
        fn(); time.sleep(0.5)
    n = 0; byt = 0; out = []
    with open(c.pcap, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            if e.type != 0x0800: continue
            ip = e.data; n += 1; byt += ip.len; out.append(ip)
    return n, byt, out
m = mkm('example.com', 'A', edns=0)
def desc(ips):
    return [('→' if ip.dst == socket.inet_aton(R) else '←') + str(ip.len) + ('T' if ip.p == 6 else 'U') for ip in ips]
n, byt, ips = wirecount(lambda: retry(lambda: udp(R, m))); print(f'  UDP:{n} 个 IP 包,共 {byt} 字节(IP 层);逐包(→ 发出 / ← 收到,数字是 IP 包长):{desc(ips)}')
n, byt, ips = wirecount(lambda: tcp_query(R, m)); print(f'  TCP 新连接:{n} 个 IP 包,共 {byt} 字节(IP 层);逐包:{desc(ips)}')
fl = []
for i in range(3):
    n, byt, ips = wirecount(lambda: retry(lambda: udp(R, m))); fl.append((n, [x for x in desc(ips)]))
print(f'  再重复 UDP 3 次的包数:{[n for n, _ in fl]}(逐包 {[x for _, x in fl]})')

print('== 五:大响应与 IP 分片:对比三种情形(抓 en0):cloudflare.com 的 TXT 记录集通过 TCP 取回是 2649 字节,比以太网 UDP 能装的 1472 字节(MTU 1500 − IP 头 20 − UDP 头 8)大得多;microsoft.com 的 TXT 是 4689 字节')
for nm, pl in (('cloudflare.com', 4096), ('cloudflare.com', 1232), ('microsoft.com', 4096)):
    m = mkm(nm, 'TXT', edns=0, payload=pl)
    with Cap(f'host {R} and udp port 53', iface='en0', write=True, snaplen=2000) as c:
        d, t = retry(lambda: udp(R, m)); time.sleep(0.5)
    frags = []
    with open(c.pcap, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            if e.type != 0x0800: continue
            ip = e.data
            if ip.src == socket.inet_aton(R): frags.append((ip.off & 0x1fff, bool(ip.off & dpkt.ip.IP_MF), ip.len))
    r = dns.message.from_wire(d, ignore_trailing=True) if d else None
    print(f'  {nm} TXT,通告 payload={pl}:应用层收到 {len(d) if d else None} 字节,TC = {bool(r.flags & dns.flags.TC) if r else None},回答 {sum(len(x) for x in r.answer) if r else None} 条;线上来自 1.1.1.1 的 IP 包 {len(frags)} 个:{[("偏移%d" % (o * 8), "MF" if mf else "末片", ln) for o, mf, ln in frags]}')
print('  2020 年起的 “DNS flag day” 建议把 EDNS0 载荷大小设成 1232 左右(= IPv6 最小 MTU 1280 − 40 − 8),既避免分片,又足够容纳大多数响应;更大的交给 TCP')
