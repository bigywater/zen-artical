import sys, os, re, struct, threading, statistics, errno, ssl; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt, dns.message, dns.query, dns.rdatatype
tee('w92'); reset()
HOST = 'example.com'; IP = '104.20.23.154'
def tls_conn(sni, alpn=None, ip=IP, verify=True):
    ctx = ssl.create_default_context()
    if not verify: ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    if alpn is not None: ctx.set_alpn_protocols(alpn)
    s = socket.create_connection((ip, 443), timeout=8); return ctx.wrap_socket(s, server_hostname=sni)

print('== 一:SNI 在 ClientHello 里是明文:抓 en0 上去 example.com 的一次 TLS 连接,在客户端发出的第一个包里和之后的包里搜 "example.com" 这串字节')
with Cap(f'tcp port 443 and host {IP}', iface='en0', write=True, snaplen=0) as c:
    ss = tls_conn(HOST, ['h2', 'http/1.1']); ss.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'); ss.recv(100); ss.close(); time.sleep(0.4)
pk = []
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(buf)
        if e.type != 0x0800 or not isinstance(e.data.data, dpkt.tcp.TCP) or not e.data.data.data: continue
        t = e.data.data; pk.append(('C→S' if t.dport == 443 else 'S→C', bytes(t.data)))
needle = HOST.encode()
for i, (d, p) in enumerate(pk[:10]):
    pos = p.find(needle)
    print(f'  第 {i + 1} 个有载荷的包 {d} {len(p):>5} 字节:{"含明文 example.com,偏移 %d" % pos if pos >= 0 else "没有明文 example.com"}')
hits = [(i, d) for i, (d, p) in enumerate(pk) if needle in p]
print(f'  整个连接里含明文 "{HOST}" 的包共 {len(hits)} 个(其中 C→S {sum(1 for _, d in hits if d == "C→S")} 个、S→C {sum(1 for _, d in hits if d == "S→C")} 个)——只有 ClientHello 一个;证书、Host 头、响应都在加密记录里')
print('  所以路径上的任何设备都能读出你要访问哪个站点,即使内容是加密的')

print('== 二:SNI 与 HTTP Host 头不一致会怎样(“域前置”):TLS 里用 SNI = example.com 连上,然后在 HTTP 请求里写别的 Host')
for hostname in ('example.com', 'example.org', 'www.iana.org', 'nonexistent-w92.example'):
    ss = tls_conn(HOST, ['http/1.1']); ss.sendall(f'GET / HTTP/1.1\r\nHost: {hostname}\r\nConnection: close\r\n\r\n'.encode()); buf = b''
    ss.settimeout(6)
    try:
        while True:
            d = ss.recv(65536)
            if not d: break
            buf += d
    except Exception: pass
    ss.close(); st = buf.split(b'\r\n', 1)[0].decode(errors='replace')[:40]; m = re.search(rb'<title>(.*?)</title>', buf, re.S)
    print(f'  SNI = example.com,Host: {hostname:<22}→ {st};页面标题 {m.group(1).decode(errors="replace")[:40] if m else "(无)"};{len(buf)} 字节')

print('== 三:ALPN 协商:客户端列出愿意说的协议(按偏好排序),服务器选一个或者拒绝。试几种列表')
for lst in (['h2', 'http/1.1'], ['http/1.1', 'h2'], ['h2'], ['http/1.1'], ['h3'], ['foo'], ['foo', 'http/1.1'], None):
    try:
        ss = tls_conn(HOST, lst); r = f'选定 {ss.selected_alpn_protocol()}'; ss.close()
    except ssl.SSLError as e: r = f'握手失败:{str(e)[:70]}'
    except Exception as e: r = f'失败 {type(e).__name__}'
    print(f'  客户端提供 {str(lst):<24}→ {r}')
print('  ALPN 列表的顺序:规范里是服务器按自己的偏好在客户端列表里挑一个,所以客户端把 http/1.1 写在前面不一定得到 http/1.1(看上面前两行)')

print('== 四:SNI 的隐私问题与 ECH:DNS 里的 HTTPS 记录(类型 65)可以带 ech 参数,让客户端把 ClientHello 里的 SNI 也加密。看几个站点的 HTTPS 记录里有没有 alpn / ech / ipv4hint')
for nm in ('example.com', 'cloudflare.com', 'www.python.org', 'github.com'):
    try:
        r = dns.query.udp(dns.message.make_query(nm, 'HTTPS'), '1.1.1.1', timeout=4)
        rr = [x for a in r.answer for x in a if a.rdtype == dns.rdatatype.HTTPS]
        if not rr: print(f'  {nm:<16}:没有 HTTPS 记录'); continue
        KN = {1: 'alpn', 2: 'no-default-alpn', 3: 'port', 4: 'ipv4hint', 5: 'ech', 6: 'ipv6hint'}; keys = sorted(KN.get(int(k), str(k)) for k in rr[0].params.keys())
        print(f'  {nm:<16}:HTTPS 记录参数 {keys};{"带 ech(可以加密 SNI)" if "ech" in keys else "没有 ech"}')
    except Exception as e: print(f'  {nm:<16}:查询失败 {type(e).__name__}')
print('  本机 Python 的 ssl 不支持 ECH,所以上面第一节看到的 SNI 仍然是明文;浏览器支持时,会先查 HTTPS 记录里的 ech 配置,把真实的 SNI 放在加密的 ClientHello 内层')
