import sys, os, re, struct, collections, ipaddress, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w34'); reset()
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
_t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); _t.connect((gw, 9)); ME = _t.getsockname()[0]; _t.close()
def cs(b):
    if len(b) % 2: b += b'\0'
    s = sum(struct.unpack('>%dH' % (len(b) // 2), b))
    while s >> 16: s = (s & 0xffff) + (s >> 16)
    return ~s & 0xffff
def mrc(code):
    """最大响应码 → 实际时间(单位 0.1 秒);≥128 用浮点格式"""
    if code < 128: return code
    exp = (code >> 4) & 7; mant = code & 15; return (mant | 0x10) << (exp + 3)
def enc_mrc(tenths):
    if tenths < 128: return tenths
    for exp in range(8):
        for mant in range(16):
            if ((mant | 0x10) << (exp + 3)) >= tenths: return 0x80 | (exp << 4) | mant
    return 0xff
def ip_pkt(src, dst, igmp):
    h = struct.pack('>BBHHHBBH4s4s', 0x46, 0xc0, 24 + len(igmp), 0, 0, 1, 2, 0, socket.inet_aton(src), socket.inet_aton(dst)) + bytes([0x94, 0x04, 0, 0])
    h = h[:10] + struct.pack('>H', cs(h)) + h[12:]
    return h + igmp
def wpcap(path, pkts):
    with open(path, 'wb') as f:
        f.write(struct.pack('<IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
        for i, ip in enumerate(pkts):
            dst = ip[16:20]; eth = bytes([1, 0, 0x5e, dst[1] & 0x7f, dst[2], dst[3]]) + bytes.fromhex('020000000001') + b'\x08\x00' + ip
            f.write(struct.pack('<IIII', 1, i * 1000, len(eth), len(eth)) + eth)
def msg(b, fill_cs_at=2):
    b = bytearray(b); b[fill_cs_at:fill_cs_at + 2] = b'\0\0'; b[fill_cs_at:fill_cs_at + 2] = struct.pack('>H', cs(bytes(b))); return bytes(b)

Q = '192.0.2.1'; H = '192.0.2.10'; G = '239.255.42.99'; S1 = '198.51.100.7'; S2 = '198.51.100.8'
print('== 一:IGMP 报文格式(手工构造,不是抓来的;地址为文档地址):v2 查询 8 字节、v3 查询 12 字节起、v2 报告 8 字节、v3 报告 8 字节头 + 每条记录 8 字节起。如何区分 v2 与 v3 查询:看 IGMP 部分的长度')
v2q = msg(struct.pack('>BBHI', 0x11, 100, 0, 0))
v3gq = msg(struct.pack('>BBHIBBH', 0x11, 100, 0, 0, 2, 125, 0))
v3gsq = msg(struct.pack('>BBHIBBH', 0x11, 100, 0, int.from_bytes(socket.inet_aton(G), 'big'), 2, 125, 2) + socket.inet_aton(S1) + socket.inet_aton(S2))
v2r = msg(struct.pack('>BBHI', 0x16, 0, 0, int.from_bytes(socket.inet_aton(G), 'big')))
def rec(rtype, grp, srcs): return struct.pack('>BBH4s', rtype, 0, len(srcs), socket.inet_aton(grp)) + b''.join(socket.inet_aton(x) for x in srcs)
v3r1 = msg(struct.pack('>BBHHH', 0x22, 0, 0, 0, 1) + rec(2, G, []), 2)
v3r2 = msg(struct.pack('>BBHHH', 0x22, 0, 0, 0, 2) + rec(1, G, [S1, S2]) + rec(2, '239.255.42.100', []), 2)
for nm, m, dst in (('v2 通用查询(最大响应 10 秒)', v2q, '224.0.0.1'), ('v3 通用查询', v3gq, '224.0.0.1'), ('v3 组-源查询(2 个源)', v3gsq, G), ('v2 成员报告', v2r, G), ('v3 报告(1 条记录:EXCLUDE 空 = 加入整个组)', v3r1, '224.0.0.22'), ('v3 报告(2 条记录:INCLUDE{S1,S2} + EXCLUDE{})', v3r2, '224.0.0.22')):
    print(f'    {nm:<38}IGMP 部分 {len(m):>3} 字节,校验和 0x{struct.unpack(">H", m[2:4])[0]:04x}(验算 {"通过" if cs(m) == 0 else "不通过"}),整个 IP 包 {24 + len(m)} 字节')
print(f'  v2 查询的“最大响应时间”字段是 1 字节、单位 0.1 秒(最大 25.5 秒);v3 的 8 位字段 ≥ 128 时用浮点格式:例如要表示 {enc_mrc(2000) and 200} 秒 = 2000 个 0.1 秒,编码成 0x{enc_mrc(2000):02x},解回来是 {mrc(enc_mrc(2000))}')
print('  v1 / v2 / v3 查询的区分:IGMP 部分长度 = 8 且最大响应时间 = 0 → v1;长度 = 8 且 ≠ 0 → v2;长度 ≥ 12 → v3')
print('  v3 报告发往 224.0.0.22(所有 IGMPv3 路由器),v2 报告发往被报告的组地址本身,v2 离开发往 224.0.0.2')

print('== 二:解码验证:把上面几个报文写成 pcap,用 tcpdump -vv 和 scapy 各解一遍,看是否与我构造的一致')
pc = str(WT / 'w34_igmp.pcap')
pk = [ip_pkt(Q, '224.0.0.1', v2q), ip_pkt(Q, '224.0.0.1', v3gq), ip_pkt(Q, G, v3gsq), ip_pkt(H, G, v2r), ip_pkt(H, '224.0.0.22', v3r1), ip_pkt(H, '224.0.0.22', v3r2)]
wpcap(pc, pk)
o = subprocess.run(['tcpdump', '-r', pc, '-nn', '-vv'], capture_output=True, text=True).stdout
for l in [x for x in o.splitlines() if 'igmp' in x.lower() or 'IGMP' in x]:
    print('  tcpdump: ' + ' '.join(l.split())[:200])
from scapy.all import IP, load_contrib
load_contrib('igmpv3'); load_contrib('igmp')
from scapy.contrib.igmpv3 import IGMPv3, IGMPv3mq, IGMPv3mr, IGMPv3gr
sc = []
for p in pk:
    x = IP(p); x2 = x.payload
    sc.append(f'{type(x2).__name__}')
print('  scapy 对这 6 个 IP 包解出的上层类型:' + ' / '.join(sc))
x = IP(pk[5])[IGMPv3mr]; print(f'  scapy 解出最后一个 v3 报告:记录数 {x.numgrp},记录类型 {[g.rtype for g in x.records]},组 {[g.maddr for g in x.records]},源 {[g.srcaddrs for g in x.records]}')

print('== 三:v3 报告的记录类型:当前状态报告(MODE_IS_INCLUDE=1 / MODE_IS_EXCLUDE=2)和状态变化报告(CHANGE_TO_INCLUDE=3 / CHANGE_TO_EXCLUDE=4 / ALLOW_NEW_SOURCES=5 / BLOCK_OLD_SOURCES=6);套接字操作怎么对应(计算 + 真实 setsockopt 的结果)')
TABLE = [('IP_ADD_MEMBERSHIP(任意源,加入)', '状态变化 CHANGE_TO_EXCLUDE{}(= 接收任何源)'), ('IP_DROP_MEMBERSHIP(离开)', '状态变化 CHANGE_TO_INCLUDE{}(= 不接收任何源 = 离开)'), ('IP_ADD_SOURCE_MEMBERSHIP(加入时只要某个源)', '状态变化 CHANGE_TO_INCLUDE{S}'), ('再加一个源 S2', 'ALLOW_NEW_SOURCES{S2}'), ('IP_BLOCK_SOURCE(任意源模式下屏蔽 S)', 'BLOCK_OLD_SOURCES{S} 或 CHANGE_TO_EXCLUDE{S}')]
for a, b in TABLE: print(f'    {a:<40}→ v3 报告里的记录:{b}')

print('== 四:本机的套接字源过滤是真的(内核按源地址过滤);发送方的源地址是本机 en0 的地址,接收方用不同的源过滤方式加入同一个组:只要这个源 / 只要别的源 / 屏蔽这个源 / 不过滤')
G4 = '239.255.42.99'; PORT0 = 34571
def mreqs(g, src, ifa): return socket.inet_aton(g) + socket.inet_aton(src) + socket.inet_aton(ifa)   # BSD 顺序:组、源、接口
def mkr(mode, srcaddr, port):
    r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('0.0.0.0', port)); r.settimeout(0.4)
    try:
        if mode == 'asm': r.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(G4) + socket.inet_aton(ME))
        elif mode == 'include': r.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_SOURCE_MEMBERSHIP, mreqs(G4, srcaddr, ME))
        elif mode == 'block':
            r.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(G4) + socket.inet_aton(ME)); r.setsockopt(socket.IPPROTO_IP, socket.IP_BLOCK_SOURCE, mreqs(G4, srcaddr, ME))
        return r, None
    except OSError as e: return None, f'{e.strerror}'
cfg = [('不过滤(任意源)', 'asm', None), ('只要本机地址这个源', 'include', ME), ('只要另一个源(198.51.100.7)', 'include', S1), ('任意源加入后屏蔽本机地址这个源', 'block', ME), ('任意源加入后屏蔽另一个源', 'block', S1)]
res = []; ig = []
for i, (nm, mode, sa) in enumerate(cfg):
    port = PORT0 + i
    with Cap('igmp', iface='en0', write=True) as c:
        r, err = mkr(mode, sa, port); time.sleep(0.2)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ME)); s.sendto(b'src-filter', (G4, port)); time.sleep(0.3)
        if err: res.append(f'{nm}:setsockopt 失败({err})')
        else:
            try: r.recvfrom(100); res.append(f'{nm}:收到')
            except socket.timeout: res.append(f'{nm}:没收到')
        if r: r.close()
        time.sleep(0.3)
    ig += [bytes(m.data) for m in [dpkt.ethernet.Ethernet(b) for ts, b in dpkt.pcap.Reader(open(c.pcap, 'rb'))] if m.type == 0x0800 and bytes(m.data)[9] == 2]
print('  每种过滤方式用独立的套接字、独立的端口依次测试。发送方源地址 = 本机 en0 地址,发一个数据报到该组;结果:\n    ' + '\n    '.join(res))
tp = collections.Counter(m[(m[0] & 15) * 4] for m in ig)
print(f'  这些加入 / 屏蔽 / 离开的过程中线上的 IGMP 报文共 {len(ig)} 个,类型分布:' + ';'.join(f'0x{k_:02x} × {v}' for k_, v in tp.items()) + '(0x16 = v2 报告,0x17 = v2 离开,0x22 = v3 报告)')
print('  这个网段上的查询者是 v2(见上一篇),本机对它按 v2 说话:v2 报文里没有“源”的概念,过滤信息只存在于本机内核里,并没有告诉路由器')
