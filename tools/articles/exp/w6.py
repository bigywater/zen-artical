import sys, os, dpkt, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w6'); reset()
ME = '192.168.9.100'
print('== 一:lo0 接口和路由:本机地址(包括 en0 的地址)的路由指向哪个接口?')
out = sysout('ifconfig', 'lo0')
for l in out.splitlines():
    l = l.strip()
    if l.startswith(('inet', 'lo0', 'options')): print('  ' + l[:110])
for ip in ('127.0.0.1', ME, '192.168.11.1'):
    r = sysout('route', '-n', 'get', ip)
    d = {k.strip(): v.strip() for k, v in (l.split(':', 1) for l in r.splitlines() if ':' in l)}
    print(f'  route get {ip:<14}→ interface={d.get("interface")} gateway={d.get("gateway", "(直连)")}')
print('  注意:发往本机自己 en0 地址的包,路由表里的出口也是 lo0——不是 en0')

print('== 二:证明一下:连本机自己的 en0 地址 192.168.9.100 的端口,同时在 lo0 和 en0 上抓包')
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); P = lab_port(); srv.bind(('0.0.0.0', P)); srv.listen(5)
with Cap(f'tcp port {P}', iface='lo0', write=True) as a, Cap(f'tcp port {P}', iface='en0', write=True) as b:
    cl = socket.create_connection((ME, P)); s, _ = srv.accept(); cl.sendall(b'ping'); s.recv(10); cl.close(); s.close()
pk = read_pcap(a.pcap)
print(f'  连接 {ME}:{P}:lo0 上抓到 {len(pk)} 个包,源 / 目的地址是 {pk[0][1].src[0]}.{pk[0][1].src[1]}.{pk[0][1].src[2]}.{pk[0][1].src[3]} → {pk[0][1].dst[0]}.{pk[0][1].dst[1]}.{pk[0][1].dst[2]}.{pk[0][1].dst[3]};en0 上抓到 {b.count} 个包')
print('  地址是 en0 的,包却在 lo0 上走:内核发现目的地址属于自己,直接环回,不经过网卡')

print('== 三:127.0.0.0/8 整段都是回环?在 macOS 上,只有 127.0.0.1 配在 lo0 上。服务端监听 0.0.0.0,客户端分别连 127.0.0.1、127.0.0.2、127.1.2.3')
for ip in ('127.0.0.1', '127.0.0.2', '127.1.2.3'):
    try:
        c = socket.create_connection((ip, P), timeout=2); s, _ = srv.accept(); print(f'  连 {ip}:成功(服务端看到对端 {s.getpeername()[0]})'); c.close(); s.close()
    except Exception as e: print(f'  连 {ip}:{type(e).__name__}: {e}')
print('  对比 Linux:整个 127.0.0.0/8 默认都路由到 lo,连 127.0.0.2 直接成功;macOS 需要先给 lo0 加别名(ifconfig lo0 alias 127.0.0.2,要 root),本机没做')

print('== 四:延迟:ping 回环、ping 自己的 en0 地址、ping 网关(真实的一跳),各 20 次的平均往返时间')
for label, ip in (('127.0.0.1', '127.0.0.1'), (f'本机自己的 en0 地址 {ME}', ME), ('网关 192.168.11.1', '192.168.11.1')):
    r = subprocess.run(['ping', '-c', '20', '-i', '0.2', ip], capture_output=True, text=True).stdout.splitlines()
    print(f'  {label}: ' + r[-1].replace('round-trip min/avg/max/stddev =', 'min/avg/max/stddev ='))

print('== 五:回环里走哪条路更快:TCP(127.0.0.1)、UDP、Unix 域套接字——1 字节乒乓 20000 次的平均往返时间,以及单向灌 1 GiB 的吞吐')
import tempfile
def pingpong_tcp(n=20000):
    s = socket.socket(); s.bind(('127.0.0.1', 0)); s.listen(1); port = s.getsockname()[1]
    def srv():
        c, _ = s.accept(); c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        while True:
            d = c.recv(1)
            if not d: break
            c.sendall(d)
    threading.Thread(target=srv, daemon=True).start()
    c = socket.create_connection(('127.0.0.1', port)); c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    t0 = time.perf_counter()
    for _ in range(n): c.sendall(b'x'); c.recv(1)
    e = time.perf_counter() - t0; c.close(); return e / n * 1e6
def pingpong_udp(n=20000):
    a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); a.bind(('127.0.0.1', 0)); b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); b.bind(('127.0.0.1', 0))
    def srv():
        while True:
            d, ad = a.recvfrom(10)
            if not d: break
            a.sendto(d, ad)
    threading.Thread(target=srv, daemon=True).start()
    t0 = time.perf_counter()
    for _ in range(n): b.sendto(b'x', a.getsockname()); b.recvfrom(10)
    e = time.perf_counter() - t0; a.sendto(b'', a.getsockname()); return e / n * 1e6
def pingpong_unix(n=20000):
    path = tempfile.mktemp(dir='/tmp'); s = socket.socket(socket.AF_UNIX); s.bind(path); s.listen(1)
    def srv():
        c, _ = s.accept()
        while True:
            d = c.recv(1)
            if not d: break
            c.sendall(d)
    threading.Thread(target=srv, daemon=True).start()
    c = socket.socket(socket.AF_UNIX); c.connect(path)
    t0 = time.perf_counter()
    for _ in range(n): c.sendall(b'x'); c.recv(1)
    e = time.perf_counter() - t0; c.close(); os.unlink(path); return e / n * 1e6
for name, fn in (('TCP 127.0.0.1', pingpong_tcp), ('UDP 127.0.0.1', pingpong_udp), ('Unix 域套接字', pingpong_unix)):
    xs = [fn() for _ in range(3)]
    print(f'  {name:<14} 1 字节乒乓平均往返 {median(xs):.1f} µs')
def bulk_tcp(mib=1024):
    s = socket.socket(); s.bind(('127.0.0.1', 0)); s.listen(1); port = s.getsockname()[1]; got = [0]
    def srv():
        c, _ = s.accept()
        while True:
            d = c.recv(1 << 20)
            if not d: break
            got[0] += len(d)
    th = threading.Thread(target=srv, daemon=True); th.start()
    c = socket.create_connection(('127.0.0.1', port)); buf = b'x' * (1 << 20); t0 = time.perf_counter()
    for _ in range(mib): c.sendall(buf)
    c.close(); th.join(); return mib / (time.perf_counter() - t0)
def bulk_unix(mib=1024):
    path = tempfile.mktemp(dir='/tmp'); s = socket.socket(socket.AF_UNIX); s.bind(path); s.listen(1); got = [0]
    def srv():
        c, _ = s.accept()
        while True:
            d = c.recv(1 << 20)
            if not d: break
            got[0] += len(d)
    th = threading.Thread(target=srv, daemon=True); th.start()
    c = socket.socket(socket.AF_UNIX); c.connect(path); buf = b'x' * (1 << 20); t0 = time.perf_counter()
    for _ in range(mib): c.sendall(buf)
    c.close(); th.join(); os.unlink(path); return mib / (time.perf_counter() - t0)
for name, fn in (('TCP 127.0.0.1', bulk_tcp), ('Unix 域套接字', bulk_unix)):
    xs = [fn() for _ in range(3)]
    print(f'  {name:<14} 单向灌 1 GiB 吞吐 {median(xs):.0f} MiB/s')
