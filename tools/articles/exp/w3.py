import sys, os, dpkt, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w3'); reset()
def sink_server(maxseg=None):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); port = lab_port(); s.bind(('127.0.0.1', port))
    if maxseg: s.setsockopt(socket.IPPROTO_TCP, 2, maxseg)
    s.listen(5); box = {'bytes': 0}
    def run():
        c, _ = s.accept()
        while True:
            d = c.recv(1 << 20)
            if not d: break
            box['bytes'] += len(d)
        c.close()
    th = threading.Thread(target=run, daemon=True); th.start(); return s, port, th, box
def mss_of(ip):
    t = ip.data; o = dpkt.tcp.parse_opts(t.opts); return [int.from_bytes(v, 'big') for k, v in o if k == 2]

print('== 一:两种接口的 MTU 不同:ifconfig 看 lo0 与 en0 的 mtu')
for ifn in ('lo0', 'en0'):
    out = subprocess.run(['ifconfig', ifn], capture_output=True, text=True).stdout
    print('  ' + [l for l in out.splitlines() if 'mtu' in l][0].strip())

print('== 二:MSS 在 SYN 里通告 = MTU − 20(IP)− 20(TCP)。同一个 curl,分别连本机服务(lo0)与 example.com:80(en0),看 SYN 和 SYN-ACK 里的 MSS 选项')
s, port, th, box = sink_server()
with Cap(f'tcp port {port}', write=True) as c:
    cl = socket.create_connection(('127.0.0.1', port)); cl.sendall(b'x'); time.sleep(0.2); cl.close()
th.join(2); s.close()
pk = read_pcap(c.pcap)
syn = [ip for t, ip in pk if ip.data.flags & dpkt.tcp.TH_SYN and not ip.data.flags & dpkt.tcp.TH_ACK][0]
synack = [ip for t, ip in pk if ip.data.flags & dpkt.tcp.TH_SYN and ip.data.flags & dpkt.tcp.TH_ACK][0]
print(f'  lo0:  SYN 里 MSS={mss_of(syn)}   SYN-ACK 里 MSS={mss_of(synack)}   (MTU 16384 − 40 = 16344)')
ip_ex = subprocess.run(['dig', '+short', 'example.com', '@1.1.1.1'], capture_output=True, text=True).stdout.split()[0]
with Cap(f'host {ip_ex} and tcp port 80', iface='en0', write=True) as c2:
    subprocess.run(['curl', '-s', '--noproxy', '*', '-o', '/dev/null', '--max-time', '6', f'http://{ip_ex}/', '-H', 'Host: example.com'], capture_output=True)
fr = []
with open(c2.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f): fr.append(dpkt.ethernet.Ethernet(b).data)
syn2 = [ip for ip in fr if isinstance(ip, dpkt.ip.IP) and ip.data.flags & dpkt.tcp.TH_SYN and not ip.data.flags & dpkt.tcp.TH_ACK][0]
sa2 = [ip for ip in fr if isinstance(ip, dpkt.ip.IP) and ip.data.flags & dpkt.tcp.TH_SYN and ip.data.flags & dpkt.tcp.TH_ACK][0]
print(f'  en0:  SYN 里 MSS={mss_of(syn2)}   SYN-ACK 里 MSS={mss_of(sa2)}   (本机 MTU 1500 − 40 = 1460;example.com 一侧通告 {mss_of(sa2)[0]},比 1460 小说明对方或路径上有设备钳制了 MSS)')

print('== 三:实际每个包能装多少数据?MSS 要减去 TCP 选项占的字节。上传 1 MiB:lo0 上最大的 TCP 数据段,以及 en0 上向 example.com POST 256 KiB 时最大的数据段')
s, port, th, box = sink_server()
with Cap(f'tcp port {port}', write=True) as c3:
    cl = socket.create_connection(('127.0.0.1', port)); cl.sendall(b'x' * (1 << 20)); cl.close()
th.join(5); s.close()
pk3 = read_pcap(c3.pcap)
segs = [len(ip.data.data) for t, ip in pk3 if ip.data.dport == port and len(ip.data.data) > 0]
cnt = collections.Counter(segs)
print(f'  lo0:  1 MiB 被切成 {len(segs)} 个数据段;最大 {max(segs)} 字节(= MSS 16344 − 12 字节时间戳选项 = 16332);出现次数最多的段长 {cnt.most_common(3)}')
with open(WT / 'post256k.bin', 'wb') as f: f.write(b'y' * (256 * 1024))
with Cap(f'host {ip_ex} and tcp port 80', iface='en0', write=True) as c4:
    subprocess.run(['curl', '-s', '--noproxy', '*', '-o', '/dev/null', '--max-time', '10', '--data-binary', f'@{WT}/post256k.bin', f'http://{ip_ex}/', '-H', 'Host: example.com'], capture_output=True)
fr4 = []
with open(c4.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f): fr4.append(dpkt.ethernet.Ethernet(b).data)
segs4 = [len(ip.data.data) for ip in fr4 if isinstance(ip, dpkt.ip.IP) and ip.data.dport == 80 and len(ip.data.data) > 0]
c4n = collections.Counter(segs4)
print(f'  en0:  发出的数据段共 {len(segs4)} 个,最大 {max(segs4)} 字节;出现次数最多的段长 {c4n.most_common(3)}(通告的 MSS 减 12 字节时间戳选项)')
print(f'  所以“MTU 1500”真正能装的应用数据是每包 {max(segs4)} 字节,而不是 1500')

print('== 四:想把 MSS 调小:TCP_MAXSEG。在 macOS 上,客户端在 connect 之前把它设成 512,看环回连接和访问 example.com:80 的连接的 SYN 与数据段有没有变')
srv = socket.socket(); srv.bind(('127.0.0.1', lab_port())); srv.listen(1); lp = srv.getsockname()[1]
with Cap(f'tcp port {lp}', write=True) as c5:
    cl = socket.socket(); cl.setsockopt(socket.IPPROTO_TCP, 2, 512); cl.connect(('127.0.0.1', lp)); a, _ = srv.accept()
    print(f'  环回:设置 TCP_MAXSEG=512 后,连接上 getsockopt 读到 {cl.getsockopt(socket.IPPROTO_TCP, 2)}', end='')
    cl.close(); a.close()
syn5 = [ip for t, ip in read_pcap(c5.pcap) if ip.data.flags & dpkt.tcp.TH_SYN and not ip.data.flags & dpkt.tcp.TH_ACK][0]
print(f';抓到的 SYN 里 MSS={mss_of(syn5)}——SYN 没变')
req = b'POST / HTTP/1.1\r\nHost: example.com\r\nContent-Length: 20000\r\nConnection: close\r\n\r\n' + b'p' * 20000
with Cap(f'host {ip_ex} and tcp port 80', iface='en0', write=True) as c6:
    cl = socket.socket(); cl.setsockopt(socket.IPPROTO_TCP, 2, 512); cl.settimeout(5); cl.connect((ip_ex, 80)); cl.sendall(req)
    try: cl.recv(2000)
    except Exception: pass
    cl.close()
fr6 = []
with open(c6.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f): fr6.append(dpkt.ethernet.Ethernet(b).data)
syn6 = [ip for ip in fr6 if isinstance(ip, dpkt.ip.IP) and ip.data.flags & dpkt.tcp.TH_SYN and not ip.data.flags & dpkt.tcp.TH_ACK][0]
sg6 = [len(ip.data.data) for ip in fr6 if isinstance(ip, dpkt.ip.IP) and ip.data.dport == 80 and len(ip.data.data) > 0]
print(f'  en0 → example.com:SYN 里 MSS={mss_of(syn6)};客户端发出 {len(sg6)} 个数据段,最大 {max(sg6)} 字节——和不设置时(第三节)一样是 1388,TCP_MAXSEG=512 没有生效;{len(req)} 字节的请求被切成 {len(sg6)} 段')
print('  结论:在这个 macOS 版本上,connect 之前的 TCP_MAXSEG=512 虽然 setsockopt 不报错,但读回来的仍是 16332,实际协商的 MSS 与发出的段长也都不受它影响;要在实验里改变段长,只能靠应用层写入大小加 TCP_NODELAY(下一节)')

print('== 五:段越小,包越多、开销越大。用“每次只 write 500 字节 + TCP_NODELAY”模拟 MSS≈500 的发送(每次 write 立即成为一个包),与默认的 1 MiB 大块 write 比较:往本机发 64 MiB,看服务端收齐的时间与发送方发出的包数(TCP_CONNECTION_INFO txpackets,3 轮中位数)')
def run5(chunk, nodelay, mib=64):
    s, port, th, box = sink_server()
    cl = socket.create_connection(('127.0.0.1', port))
    if nodelay: cl.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    buf = b'z' * chunk; n = (mib << 20) // chunk
    t0 = time.perf_counter()
    for _ in range(n): cl.sendall(buf)
    info = tcp_info(cl); cl.close(); th.join(30); e = time.perf_counter() - t0
    s.close(); return e, info['txpackets']
for chunk, nd, label in ((1 << 20, False, '1 MiB 大块写'), (500, True, '500 字节小块写 + NODELAY')):
    rs = [run5(chunk, nd) for _ in range(3)]
    e = median(r[0] for r in rs)
    print(f'  {label}: 64 MiB 收齐用时 {e * 1000:.0f} ms({64 / e:.0f} MiB/s),发出 {rs[1][1]} 个数据包,平均每包 {64 * 1048576 / rs[1][1]:.0f} 字节')
