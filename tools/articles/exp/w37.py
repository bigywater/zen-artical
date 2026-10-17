import sys, os, re, struct, collections, threading, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w37'); reset()
PUB = '104.20.23.154'
FL = [(0x80, 'CWR'), (0x40, 'ECE'), (0x20, 'URG'), (0x10, 'ACK'), (0x08, 'PSH'), (0x04, 'RST'), (0x02, 'SYN'), (0x01, 'FIN')]
def flags(f): return '+'.join(n for b, n in FL if f & b) or '无'
def tcps(path, lo=False):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            if lo: ip = bytes(buf[4:])
            else:
                e = dpkt.ethernet.Ethernet(buf)
                if e.type != 0x0800: continue
                ip = bytes(e.data)
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:tl_]
            sp, dp, seq, ack, off, fl, win, ck, urg = struct.unpack('>HHIIBBHHH', t[:20])
            out.append(dict(ts=ts, src=socket.inet_ntoa(ip[12:16]), dst=socket.inet_ntoa(ip[16:20]), sp=sp, dp=dp, seq=seq, ack=ack, doff=(off >> 4) * 4, rsv=off & 15, fl=fl, win=win, ck=ck, urg=urg, opts=t[20:(off >> 4) * 4], plen=len(t) - (off >> 4) * 4, raw=t[:20], ipraw=ip))
    return out
def parse_opts(o):
    out = []; i = 0
    while i < len(o):
        k = o[i]
        if k == 0: out.append(('EOL', b'')); break
        if k == 1: out.append(('NOP', b'')); i += 1; continue
        l = o[i + 1]; v = o[i + 2:i + l]
        nm = {2: 'MSS', 3: 'WScale', 4: 'SACK-permitted', 5: 'SACK', 8: 'Timestamps', 34: 'TFO'}.get(k, f'kind{k}')
        out.append((nm, v)); i += l
    return out

print('== 一:一次真实的 HTTP 请求(en0,example.com:80)的头几个包,逐个 TCP 头字段解码;序号用相对值(减去各自的初始序号)')
with Cap(f'tcp port 80 and host {PUB}', iface='en0', write=True) as c:
    k = socket.create_connection((PUB, 80), timeout=5); k.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'); k.settimeout(3)
    try:
        while k.recv(65536): pass
    except Exception: pass
    k.close(); time.sleep(0.4)
P = tcps(c.pcap); me = P[0]['sp']; isn_c = P[0]['seq']; isn_s = [p for p in P if p['fl'] & 0x12 == 0x12][0]['seq']
print('    #  方向   源端口→目的端口  相对序号  相对确认号  头长  标志        窗口    载荷  校验和')
for i, p in enumerate(P[:9], 1):
    d = '→' if p['sp'] == me else '←'
    rs = (p['seq'] - (isn_c if p['sp'] == me else isn_s)) & 0xffffffff; ra = (p['ack'] - (isn_s if p['sp'] == me else isn_c)) & 0xffffffff if p['fl'] & 0x10 else 0
    print(f'    {i:>2}  {d}   {"C" if p["sp"] == me else p["sp"]}→{"C" if p["dp"] == me else p["dp"]:<7}      {rs:>8}  {ra:>9}  {p["doff"]:>3}  {flags(p["fl"]):<10}  {p["win"]:>6}  {p["plen"]:>5}  0x{p["ck"]:04x}')
print(f'  整个连接共 {len(P)} 个包。每个包的头都是 20 字节固定部分 + 选项:源端口 2、目的端口 2、序号 4、确认号 4、数据偏移 4 位 + 保留 4 位(合 1 字节)、标志 1 字节(CWR ECE URG ACK PSH RST SYN FIN)、窗口 2、校验和 2、紧急指针 2')
syn = P[0]; print(f'  第 1 个包(SYN)的头 20 字节:{syn["raw"].hex(" ", 2)};数据偏移 = {syn["doff"] // 4}(×4 = {syn["doff"]} 字节),保留位 {syn["rsv"]},标志字节 0x{syn["fl"]:02x}')

print('== 二:选项:SYN 里的选项逐字节(MSS / NOP / 窗口缩放 / 时间戳 / SACK 允许 / EOL),以及数据包里的选项')
o = syn['opts']; print(f'  SYN 的选项 {len(o)} 字节:{o.hex(" ")}')
pos = 0
for nm, v in parse_opts(o):
    if nm in ('NOP', 'EOL'): print(f'    {nm}(1 字节,用来对齐 / 结束)')
    else:
        kind = {'MSS': 2, 'WScale': 3, 'SACK-permitted': 4, 'Timestamps': 8}.get(nm, 0)
        desc = ''
        if nm == 'MSS': desc = f'MSS = {struct.unpack(">H", v)[0]}'
        elif nm == 'WScale': desc = f'窗口缩放移位 {v[0]}(窗口字段 × 2^{v[0]})'
        elif nm == 'SACK-permitted': desc = '允许选择性确认'
        elif nm == 'Timestamps': desc = f'TSval = {struct.unpack(">I", v[:4])[0]},TSecr = {struct.unpack(">I", v[4:])[0]}'
        print(f'    {nm}(类型 {kind},长度 {len(v) + 2}):{desc}')
sa = [p for p in P if p['fl'] & 0x12 == 0x12][0]; print(f'  SYN-ACK 的选项 {len(sa["opts"])} 字节:' + '、'.join(n for n, _ in parse_opts(sa['opts'])))
data = [p for p in P if p['plen'] > 0][:2]; print('  带数据的包头长 ' + '、'.join(f'{p["doff"]} 字节(选项 {[n for n, _ in parse_opts(p["opts"])]})' for p in data))
print(f'  各种包的头长:{dict(collections.Counter(p["doff"] for p in P))}——SYN 的头最长(选项最多),之后只剩时间戳(NOP NOP + 10 字节 = 12 字节),头 32 字节')

print('== 三:标志位组合:在 lo0 上下载 1 MiB,统计所有包的标志组合,以及窗口字段的取值')
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(); port = srv.getsockname()[1]
def run():
    cn, _ = srv.accept(); cn.sendall(b'z' * (1 << 20)); cn.close()
threading.Thread(target=run, daemon=True).start()
with Cap(f'tcp port {port}', iface='lo0', write=True) as c2:
    k = socket.create_connection(('127.0.0.1', port)); n = 0
    while True:
        d = k.recv(1 << 20)
        if not d: break
        n += len(d)
    k.close(); time.sleep(0.4)
P2 = tcps(c2.pcap, lo=True)
cnt = collections.Counter(flags(p['fl']) for p in P2)
print(f'  下载 {n} 字节,lo0 上共 {len(P2)} 个 TCP 包;标志组合:' + ';'.join(f'{k_} × {v}' for k_, v in cnt.most_common()))
cs = [p for p in P2 if p['sp'] == port]; sc_ = [p for p in P2 if p['dp'] == port]
print(f'  窗口字段(16 位原始值):客户端发的 SYN {P2[0]["win"]},之后客户端的 ACK 里最小 {min(p["win"] for p in P2[2:] if p["dp"] == port)} / 最大 {max(p["win"] for p in P2[2:] if p["dp"] == port)};SYN 的窗口字段不缩放(窗口缩放选项只对后面的包有效)')
print(f'  服务端发出的数据包:载荷最大 {max(p["plen"] for p in cs)} 字节(= MSS 16344),PSH 位出现 {sum(1 for p in cs if p["fl"] & 8)} 次——PSH 只是提示接收方尽快交给应用,不改变传输')

print('== 四:紧急指针与 URG:send(..., MSG_OOB) 发 1 个“带外”字节,看 URG 标志和紧急指针;接收方用 MSG_OOB 收')
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(); port = srv.getsockname()[1]; got = {}
def run2():
    cn, _ = srv.accept(); cn.settimeout(2); time.sleep(0.5)
    try: got['oob'] = cn.recv(10, socket.MSG_OOB)
    except Exception as e: got['oob'] = repr(e)
    try: got['inband'] = cn.recv(100)
    except Exception as e: got['inband'] = repr(e)
    cn.close()
th = threading.Thread(target=run2); th.start()
with Cap(f'tcp port {port}', iface='lo0', write=True) as c3:
    k = socket.create_connection(('127.0.0.1', port)); k.sendall(b'abc'); time.sleep(0.1); k.send(b'!', socket.MSG_OOB); time.sleep(0.1); k.sendall(b'def'); th.join(3); k.close(); time.sleep(0.3)
P3 = tcps(c3.pcap, lo=True)
for p in P3:
    if p['fl'] & 0x20 or p['plen'] > 0: print(f'    {"客户端" if p["dp"] == port else "服务端"}发出:标志 {flags(p["fl"])},载荷 {p["plen"]} 字节,紧急指针字段 {p["urg"]}')
print(f'  接收方 recv(MSG_OOB) 拿到 {got.get("oob")!r};普通 recv 拿到 {got.get("inband")!r}')
print('  URG 标志置位时,紧急指针指向紧急数据的末尾(相对序号偏移);它几乎没有被实际用过,而且“带外数据”在各系统里语义不一致,RFC 6093 建议新应用不要使用')
