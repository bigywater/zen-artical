import sys, os, re, struct, threading, statistics, errno, ctypes, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
def tfolab(*a):
    r = subprocess.run(['sudo', '-n', '/Library/netlab/tfolab', *map(str, a)], capture_output=True, text=True); return (r.stdout + r.stderr).strip()
libc = ctypes.CDLL('libc.dylib', use_errno=True)
class sa_endpoints(ctypes.Structure):
    _fields_ = [('sae_srcif', ctypes.c_uint), ('sae_srcaddr', ctypes.c_void_p), ('sae_srcaddrlen', ctypes.c_uint32), ('sae_dstaddr', ctypes.c_void_p), ('sae_dstaddrlen', ctypes.c_uint32)]
class iovec(ctypes.Structure): _fields_ = [('iov_base', ctypes.c_void_p), ('iov_len', ctypes.c_size_t)]
def sockaddr(host, port, scope=0):
    if ':' in host: return ctypes.create_string_buffer(struct.pack('!BBHI16sI', 28, socket.AF_INET6, port, 0, socket.inet_pton(socket.AF_INET6, host), 0)[:-4] + struct.pack('=I', scope), 28), 28
    return ctypes.create_string_buffer(struct.pack('!BBH4s8x', 16, socket.AF_INET, port, socket.inet_aton(host)), 16), 16
def connectx_data(s, host, port, data, scope=0, flags=2):
    dst, ln = sockaddr(host, port, scope); ep = sa_endpoints(0, None, 0, ctypes.addressof(dst), ln)
    buf = ctypes.create_string_buffer(data, len(data)); iov = iovec(ctypes.addressof(buf), len(data)); n = ctypes.c_size_t(0); cid = ctypes.c_uint(0)
    r = libc.connectx(s.fileno(), ctypes.byref(ep), 0, flags, ctypes.byref(iov), 1, ctypes.byref(n), ctypes.byref(cid))
    return r, ctypes.get_errno(), n.value
TFO = 0x105
def tcp_pkts(path, iface_en=False):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            if iface_en:
                e = dpkt.ethernet.Ethernet(buf)
                if e.type != 0x0800: continue
                ip = bytes(e.data)
            else: ip = bytes(buf[4:])
            if ip[0] >> 4 == 6:
                if ip[6] != 6: continue
                t = ip[40:]; tl_ = struct.unpack('>H', ip[4:6])[0]; ihl = 40; body = tl_
            else:
                if ip[9] != 6: continue
                ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]; body = tl_ - ihl
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); hl = (off >> 4) * 4; opts = []; optd = {}; o = t[20:hl]; i = 0
            while i < len(o):
                kd = o[i]
                if kd == 0: break
                if kd == 1: i += 1; continue
                ln = o[i + 1]; opts.append((kd, ln)); optd[kd] = bytes(o[i + 2:i + ln]); i += ln
            out.append(dict(ts=ts, sp=sp, dp=dp, seq=seq, ack=ack, fl=fl, plen=body - hl, opts=opts, optd=optd))
    return out
FLN = {0x02: 'SYN', 0x12: 'SYN+ACK', 0x10: 'ACK', 0x18: 'PSH+ACK', 0x11: 'FIN+ACK', 0x04: 'RST', 0x14: 'RST+ACK', 0x19: 'FIN+PSH+ACK'}
OPN = {2: 'MSS', 3: 'WS', 4: 'SACKok', 8: 'TS', 34: 'TFO', 5: 'SACK'}
def dd(P):
    seen = set(); out = []
    for p in P:
        key = (p['sp'], p['dp'], p['seq'], p['fl'], p['plen'])
        if key in seen: continue
        seen.add(key); out.append(p)
    return out
def show(P, port):
    t0 = P[0]['ts']
    for p in P:
        print(f'    +{(p["ts"] - t0) * 1000:7.2f} ms  {"C→S" if p["dp"] == port else "S→C"}  {FLN.get(p["fl"], hex(p["fl"])):<9} 载荷 {p["plen"]:>3} 字节  选项 {[OPN.get(k, k) for k, l in p["opts"]]}' + ('  ← TFO 选项长度 ' + str([l for k, l in p['opts'] if k == 34]) if any(k == 34 for k, l in p['opts']) else ''))
def syns(P, port): return [p for p in P if p['fl'] & 0x12 == 0x02 and p['dp'] == port]
def topt(p): return [l for k, l in p['opts'] if k == 34]

def server(host, port, tfo, n, scope=0):
    fam = socket.AF_INET6 if ':' in host else socket.AF_INET
    ls = socket.socket(fam); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ls.bind((host, port, 0, scope) if fam == socket.AF_INET6 else (host, port)); ls.listen()
    if tfo: ls.setsockopt(socket.IPPROTO_TCP, TFO, 1)
    ls.settimeout(5); res = []
    def run():
        for i in range(n):
            try:
                cn, _ = ls.accept(); cn.settimeout(2); d = cn.recv(100); res.append(d); cn.sendall(b'R' * 10); time.sleep(0.05); cn.close()
            except Exception as e: res.append(repr(e))
        ls.close()
    th = threading.Thread(target=run); th.start(); return th, res
def client(host, port, data, scope=0, tfo=True):
    fam = socket.AF_INET6 if ':' in host else socket.AF_INET
    k = socket.socket(fam)
    if tfo: connectx_data(k, host, port, data, scope)
    else: k.connect((host, port, 0, scope) if fam == socket.AF_INET6 else (host, port)); k.sendall(data)
    k.settimeout(3); k.recv(20); return k

