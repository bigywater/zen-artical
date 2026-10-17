import sys, os, threading, http.server, dpkt, math; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w1'); reset()
PORT = lab_port()
BODY = b'hello world\n'
seen = {}
class H(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def do_GET(self):
        if self.path == '/big': body = b'x' * (1 << 20)
        else: body = BODY
        self.send_response(200); self.send_header('Content-Length', str(len(body))); self.send_header('Content-Type', 'text/plain'); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
def hexd(b, n=64):
    out = []
    for i in range(0, min(len(b), n), 16):
        c = b[i:i + 16]; out.append(f'    {i:04x}  ' + ' '.join(f'{x:02x}' for x in c).ljust(48) + ' ' + ''.join(chr(x) if 32 <= x < 127 else '.' for x in c))
    return '\n'.join(out)

print('== 一:应用层看到的就是一段文本:curl 发出的 HTTP 请求(用一个原始 TCP 服务端把它收到的字节原样打出来)')
raw = socket.socket(); raw.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); P2 = lab_port(); raw.bind(('127.0.0.1', P2)); raw.listen(1)
box = []
def acc():
    c, _ = raw.accept(); box.append(c.recv(4096)); c.sendall(b'HTTP/1.1 200 OK\\r\\nContent-Length: 0\\r\\n\\r\\n'.replace(b'\\\\r\\\\n', b'\\r\\n')); c.close()
th = threading.Thread(target=acc); th.start()
subprocess.run(['curl', '-s', '--noproxy', '*', f'http://127.0.0.1:{P2}/hello'], capture_output=True); th.join(3)
req = box[0]
print(f'  收到 {len(req)} 字节: {req!r}')

print('== 二:同一个请求在 lo0 上抓到的包:逐层拆开,标出每层头占多少字节')
with Cap(f'tcp port {PORT}', write=True, verbose=1) as c:
    subprocess.run(['curl', '-s', '--noproxy', '*', f'http://127.0.0.1:{PORT}/hello'], capture_output=True)
pk = read_pcap(c.pcap)
data_pk = [(ts, ip) for ts, ip in pk if ip.data.dport == PORT and len(ip.data.data) > 0][0]
ts, ip = data_pk; tcp = ip.data
print(f'  这个会话共抓到 {len(pk)} 个包(握手 3 + 请求 1 + 响应 1 + 挥手若干 + ACK……),其中携带请求的是:')
print(f'  lo0 链路层头: 4 字节(地址族 AF_INET=2,小端存放),没有 MAC 地址')
print(f'  IPv4 头: {ip.hl * 4} 字节  版本={ip.v} 头长={ip.hl}x4 TOS={ip.tos} 总长={ip.len} id={ip.id} 标志=DF({bool(ip.df)}) TTL={ip.ttl} 协议={ip.p}(TCP) 校验和=0x{ip.sum:04x} {ip.src[0]}.{ip.src[1]}.{ip.src[2]}.{ip.src[3]} → {ip.dst[0]}.{ip.dst[1]}.{ip.dst[2]}.{ip.dst[3]}')
print(f'  TCP 头: {tcp.off * 4} 字节  源端口=客户端临时端口 目的端口={tcp.dport} seq 相对=1 标志={"PSH " if tcp.flags & dpkt.tcp.TH_PUSH else ""}{"ACK" if tcp.flags & dpkt.tcp.TH_ACK else ""} 窗口={tcp.win} 选项长度={tcp.off * 4 - 20} 字节')
print(f'  应用数据(HTTP 请求): {len(tcp.data)} 字节')
print(f'  合计: 4(lo0) + {ip.hl * 4}(IP) + {tcp.off * 4}(TCP) + {len(tcp.data)}(HTTP) = {4 + ip.hl * 4 + tcp.off * 4 + len(tcp.data)} 字节;头部开销占 {(ip.hl * 4 + tcp.off * 4) / (ip.len) * 100:.0f}% (IP 总长 {ip.len})')
print('  这个包的前 64 字节(从 IP 头开始):'); print(hexd(ip.raw, 64))

print('== 三:换到真实以太网:访问 example.com 的 80 端口,在 en0 上抓包。多出一个 14 字节的以太网头(目的 MAC、源 MAC、EtherType)')
ipaddr = subprocess.run(['dig', '+short', 'example.com', '@1.1.1.1'], capture_output=True, text=True).stdout.split()[0]
with Cap(f'host {ipaddr} and tcp port 80', iface='en0', write=True) as c2:
    r = subprocess.run(['curl', '-s', '--noproxy', '*', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', '8', f'http://{ipaddr}/', '-H', 'Host: example.com'], capture_output=True, text=True)
import dpkt as _d
with open(c2.pcap, 'rb') as f:
    pc = _d.pcap.Reader(f); frames = [(t, _d.ethernet.Ethernet(b), len(b)) for t, b in pc]
req_f = [x for x in frames if isinstance(x[1].data, _d.ip.IP) and isinstance(x[1].data.data, _d.tcp.TCP) and x[1].data.data.dport == 80 and len(x[1].data.data.data) > 0][0]
t, eth, flen = req_f; ip3 = eth.data; tcp3 = ip3.data
mac = lambda b: ':'.join(f'{x:02x}' for x in b[:3]) + ':xx:xx:xx'
print(f'  curl 返回 HTTP {r.stdout};这个会话共抓到 {len(frames)} 帧')
print(f'  以太网头: 14 字节  目的 MAC={mac(eth.dst)}(默认网关) 源 MAC={mac(eth.src)}(本机) EtherType=0x{eth.type:04x}(IPv4)')
print(f'  IPv4 头: {ip3.hl * 4} 字节  TTL={ip3.ttl} 协议={ip3.p} 总长={ip3.len} 校验和=0x{ip3.sum:04x} 目的={ip3.dst[0]}.{ip3.dst[1]}.{ip3.dst[2]}.{ip3.dst[3]}')
print(f'  TCP 头: {tcp3.off * 4} 字节  目的端口={tcp3.dport} 选项长度={tcp3.off * 4 - 20} 字节;HTTP 请求 {len(tcp3.data)} 字节')
print(f'  整个帧: {flen} 字节 = 14 + {ip3.hl * 4} + {tcp3.off * 4} + {len(tcp3.data)};同一个请求在 lo0 上是 4 + 20 + 32 + {len(tcp.data)}')
syn = [x for x in frames if isinstance(x[1].data, _d.ip.IP) and x[1].data.data.flags & _d.tcp.TH_SYN and not x[1].data.data.flags & _d.tcp.TH_ACK][0]
opts = _d.tcp.parse_opts(syn[1].data.data.opts)
print(f'  en0 上 SYN 里的 MSS = ' + str([int.from_bytes(v, "big") for k, v in opts if k == 2]) + '(= 1500 − 20 − 20);lo0 上是 16344(= 16384 − 20 − 20)')

print('== 四:头部开销随数据量的变化:下载 1 MiB(Content-Length 1048576)时,lo0 上的包数、总字节与头部占比;并按以太网 MSS 1448(含时间戳选项)算出同样数据需要的帧数')
with Cap(f'tcp port {PORT}', write=True) as c3:
    subprocess.run(['curl', '-s', '--noproxy', '*', '-o', '/dev/null', f'http://127.0.0.1:{PORT}/big'], capture_output=True)
pk3 = read_pcap(c3.pcap)
resp = [(t, ip) for t, ip in pk3 if ip.data.sport == PORT and len(ip.data.data) > 0]
payload = sum(len(ip.data.data) for t, ip in resp)
print(f'  lo0:响应方向携带数据的包 {len(resp)} 个,应用数据共 {payload} 字节(含 HTTP 响应头);最大的一个包的 TCP 数据 {max(len(ip.data.data) for t, ip in resp)} 字节')
hdr = sum(4 + ip.hl * 4 + ip.data.off * 4 for t, ip in resp)
print(f'  这些包的头部合计 {hdr} 字节,占总字节的 {hdr / (hdr + payload) * 100:.2f}%')
N = math.ceil(payload / 1448); hdr_eth = N * (14 + 20 + 32)
print(f'  同样的 {payload} 字节放到 MSS=1448 的以太网上:需要 {N} 个帧,头部 {hdr_eth} 字节(每帧 14 + 20 + 32),占 {hdr_eth / (hdr_eth + payload) * 100:.2f}%(这是按公式算出来的,不是实测)')
small_total = sum(4 + ip_.len for t_, ip_ in pk); small_payload = sum(len(ip_.data.data) for t_, ip_ in pk)
print(f'  对比第二节那次只取 {len(BODY)} 字节响应体的小请求:{len(pk)} 个包共 {small_total} 字节(含 lo0 头),应用数据只有 {small_payload} 字节,占 {small_payload / small_total * 100:.0f}%——小请求里绝大部分字节是头部和握手')

print('== 五:自己拼一遍 IPv4 + TCP 头,和抓到的字节逐字节对照(校验和字段除外)')
import struct
ip_bytes = ip.raw
my_ip = struct.pack('!BBHHHBBH4s4s', (4 << 4) | 5, ip.tos, ip.len, ip.id, (0x4000 if ip.df else 0), ip.ttl, ip.p, 0, ip.src, ip.dst)
same_ip = my_ip[:10] == ip_bytes[:10] and my_ip[12:20] == ip_bytes[12:20]
print(f'  自己用 struct 拼出的 IPv4 头(校验和先填 0)与抓到的前 20 字节:除第 10~11 字节(校验和)外 {"完全相同" if same_ip else "不同"}')
def csum(b):
    if len(b) % 2: b += b'\\0'
    s = sum(struct.unpack('!%dH' % (len(b) // 2), b)); s = (s & 0xffff) + (s >> 16); s = (s & 0xffff) + (s >> 16); return ~s & 0xffff
print(f'  抓到的原始字节里 IP 校验和字段 = 0x{int.from_bytes(ip_bytes[10:12], "big"):04x}(环回口发送时没有填,tcpdump 提示 bad cksum);自己按反码求和算出来应该是 0x{csum(my_ip):04x}')
print('  所以在环回接口上看到的 “bad cksum” 不是出错:校验和被留空(校验和卸载),真正走网卡时才会填上')
srv.shutdown()
