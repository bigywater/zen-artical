import sys, os, re, struct, collections, statistics, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w28'); reset()
def raws(path): return [(ts, ip.raw) for ts, ip in read_pcap(path)]
def sc(k_): return sysout('sysctl', k_).strip()

print('== 一:UDP 头只有 8 字节:源端口、目的端口、长度、校验和。在 lo0 上发三种数据报,解码线上的头')
r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', 0)); port = r.getsockname()[1]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('127.0.0.1', 0)); sp = s.getsockname()[1]
with Cap(f'udp port {port}', iface='lo0', write=True) as c:
    for pl in (b'hello', b'', b'x' * 1000): s.sendto(pl, ('127.0.0.1', port))
    time.sleep(0.4)
for ts, r_ in raws(c.pcap):
    ihl = (r_[0] & 15) * 4; u = r_[ihl:ihl + 8]; a, b, ln, ck = struct.unpack('>HHHH', u); tl_ = struct.unpack('>H', r_[2:4])[0]
    print(f'  头 {u.hex(" ", 2)}:源端口 {a}(= 发送套接字的 {sp}:{a == sp}),目的端口 {b},长度 {ln} = 8 + 载荷 {ln - 8},校验和字段 0x{ck:04x};IP 总长 {tl_} = {ihl} + {ln}')
print('  载荷为 0 字节的数据报也是合法的:UDP 长度 8,对方 recvfrom 会收到一个空的数据报')
r.settimeout(1); got = [r.recvfrom(2000)[0] for _ in range(3)]
print(f'  接收方三次 recvfrom 得到的长度:{[len(g) for g in got]}——每次 recvfrom 对应发送方的一次 sendto(UDP 保留报文边界)')

print('== 二:报文边界与截断:UDP 每次 recvfrom 取走一个完整的数据报,缓冲区小了多出的部分直接丢掉;对比 TCP 流会把几次发送合并')
r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', 0)); r.settimeout(1); a_ = r.getsockname()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for pl in (b'A' * 10, b'B' * 20, b'C' * 30): s.sendto(pl, a_)
time.sleep(0.2)
print(f'  连发 10、20、30 字节三个数据报:接收方 3 次 recvfrom 分别拿到 {[len(r.recvfrom(100)[0]) for _ in range(3)]} 字节')
s.sendto(b'D' * 20, a_); time.sleep(0.1)
d1, an, fl, ad = r.recvmsg(5)
print(f'  再发一个 20 字节的数据报,接收方只给 5 字节的缓冲区:recvmsg 得到 {len(d1)} 字节,MSG_TRUNC 标志 {"置位" if fl & socket.MSG_TRUNC else "未置位"};再收一次:', end='')
try: r.recvfrom(100); print('又拿到数据')
except socket.timeout: print('什么也没有——剩下的 15 字节被丢掉了')
ls = socket.socket(); ls.bind(('127.0.0.1', 0)); ls.listen(); pt = ls.getsockname()[1]
cl = socket.socket(); cl.connect(('127.0.0.1', pt)); sv, _ = ls.accept()
for pl in (b'A' * 10, b'B' * 20, b'C' * 30): cl.sendall(pl)
time.sleep(0.2); sv.settimeout(1)
print(f'  TCP 同样发 10、20、30 字节:接收方一次 recv 拿到 {len(sv.recv(1000))} 字节(三次发送被合并成一个字节流,边界没有了)')

print('== 三:“无连接”的实际含义:一问一答的完整交换,UDP 和 TCP 各要多少个包、多少个往返;再用 netlab 给回环加 20 ms 单向延迟,看第一次请求到收到应答的时间')
pu = lab_port(); eu = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); eu.bind(('127.0.0.1', pu))
pt_ = lab_port()
while pt_ == pu: pt_ = lab_port()
et = socket.socket(); et.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); et.bind(('127.0.0.1', pt_)); et.listen(50)
def udp_srv():
    while True:
        d, a = eu.recvfrom(2000); eu.sendto(d, a)
def tcp_srv():
    while True:
        cn, _ = et.accept()
        def h(cn=cn):
            d = cn.recv(2000); cn.sendall(d); cn.close()
        threading.Thread(target=h, daemon=True).start()
threading.Thread(target=udp_srv, daemon=True).start(); threading.Thread(target=tcp_srv, daemon=True).start()
def udp_rt():
    c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); c.settimeout(3); t0 = time.time(); c.sendto(b'ping', ('127.0.0.1', pu)); c.recvfrom(100); dt = time.time() - t0; c.close(); return dt
def tcp_rt():
    t0 = time.time(); c = socket.create_connection(('127.0.0.1', pt_), timeout=3); c.sendall(b'ping'); c.recv(100); dt = time.time() - t0
    c.close(); return dt
with Cap(f'udp port {pu}', iface='lo0', write=True) as cu: udp_rt(); time.sleep(0.3)
with Cap(f'tcp port {pt_}', iface='lo0', write=True) as ct: tcp_rt(); time.sleep(0.5)
nu = len(raws(cu.pcap)); nt = len(raws(ct.pcap))
bu = sum(struct.unpack('>H', r_[2:4])[0] for _, r_ in raws(cu.pcap)); bt = sum(struct.unpack('>H', r_[2:4])[0] for _, r_ in raws(ct.pcap))
print(f'  一次 4 字节的请求 / 应答:UDP {nu} 个包({bu} 字节 IP 包);TCP(连接 + 请求 + 应答 + 关闭){nt} 个包({bt} 字节)')
base_u = statistics.median(udp_rt() for _ in range(20)); base_t = statistics.median(tcp_rt() for _ in range(20))
with lossy(loss=0, delay=20, bw=0):
    du = statistics.median(udp_rt() for _ in range(10)); dt_ = statistics.median(tcp_rt() for _ in range(10))
print(f'  没有延迟:UDP 一问一答 {base_u * 1e6:.0f} µs、TCP(含建立连接){base_t * 1e6:.0f} µs')
print(f'  单向 20 ms(往返 40 ms):UDP 一问一答 {du * 1000:.1f} ms(≈ 1 个往返)、TCP 含建立连接 {dt_ * 1000:.1f} ms(≈ 2 个往返:先三次握手,再请求应答)')

print('== 四:端口:临时端口的范围与分配方式(创建 1000 个 UDP 套接字不指定端口,看系统给的端口号),以及同一个端口被几个套接字绑定的规则')
print('  ' + sc('net.inet.ip.portrange.first') + ';' + sc('net.inet.ip.portrange.last') + ';' + sc('net.inet.ip.portrange.hifirst') + ';' + sc('net.inet.ip.portrange.hilast'))
ss = []; ports = []
for i in range(1000):
    x = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); x.bind(('127.0.0.1', 0)); ports.append(x.getsockname()[1]); ss.append(x)
steps = sum(1 for a, b in zip(ports, ports[1:]) if b == a + 1)
print(f'  1000 个不指定端口的 UDP 套接字:端口范围 {min(ports)} ~ {max(ports)},互不相同的 {len(set(ports))} 个,相邻两个恰好 +1 的只有 {steps} 个(随机分配,不是顺序递增)')
for x in ss: x.close()
a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); a.bind(('0.0.0.0', 0)); pp = a.getsockname()[1]
res = []
for nm, addr, opt in (('再绑 0.0.0.0 同一端口', '0.0.0.0', None), ('再绑 127.0.0.1 同一端口', '127.0.0.1', None), ('SO_REUSEADDR 后再绑 0.0.0.0', '0.0.0.0', socket.SO_REUSEADDR), ('SO_REUSEPORT 后再绑 0.0.0.0', '0.0.0.0', socket.SO_REUSEPORT)):
    b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if opt:
        if opt == socket.SO_REUSEPORT: a.close(); a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); a.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1); a.bind(('0.0.0.0', pp))
        b.setsockopt(socket.SOL_SOCKET, opt, 1)
    try: b.bind((addr, pp)); res.append(f'{nm}:成功')
    except OSError as e: res.append(f'{nm}:失败({e.strerror})')
print('  第一个套接字绑 0.0.0.0:' + str(pp) + ';' + ';'.join(res))

print('== 五:UDP 数据报的大小上限:协议上限 65507 字节(65535 − 20 − 8),但系统还有自己的限制(sysctl)')
for k_ in ('net.inet.udp.maxdgram', 'net.inet.udp.recvspace', 'net.inet.udp.checksum'): print('  ' + sc(k_))
r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', 0)); r.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20); r.settimeout(1); a_ = r.getsockname()
for bigsnd in (False, True):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if bigsnd: s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
    out = []
    for n in (9216, 9217, 65507, 65508):
        try: s.sendto(b'z' * n, a_); out.append(f'{n} 字节:发送成功')
        except OSError as e: out.append(f'{n} 字节:{e.strerror}')
    print(f'  {"调大 SO_SNDBUF 到 1 MiB 后" if bigsnd else "默认发送缓冲区"}:' + ';'.join(out))
while True:
    try: r.recvfrom(70000)
    except socket.timeout: break
