import sys, os, re, struct, ipaddress, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w21'); reset()
DRY = os.environ.get('DRY') == '1'
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
_t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); _t.connect((gw, 9)); ME = _t.getsockname()[0]; _t.close()
MYMAC = [l.split()[1] for l in sysout('ifconfig', 'en0').splitlines() if l.strip().startswith('ether ')][0]
MT = {1: 'DISCOVER', 2: 'OFFER', 3: 'REQUEST', 4: 'DECLINE', 5: 'ACK', 6: 'NAK', 7: 'RELEASE', 8: 'INFORM'}
OPT = {1: '子网掩码', 3: '路由器(网关)', 6: 'DNS 服务器', 12: '主机名', 15: '域名', 26: '接口 MTU', 28: '广播地址', 51: '租约时间', 53: '报文类型', 54: '服务器标识', 55: '请求的参数列表', 57: '最大报文长度', 58: 'T1(续租时间)', 59: 'T2(重新绑定时间)', 61: '客户端标识', 50: '请求的地址', 255: '结束', 119: '域搜索列表', 95: 'LDAP', 252: 'WPAD', 43: '厂商特定'}
def mac(b): return ':'.join('%02x' % x for x in b)
def dec(p):
    """解码 DHCP/BOOTP 载荷"""
    if len(p) < 240: return None
    op, ht, hl, hops, xid, secs, flags, ci, yi, si, gi = struct.unpack('>BBBBIHH4s4s4s4s', p[:28])
    d = dict(op=op, htype=ht, hlen=hl, hops=hops, xid=xid, secs=secs, flags=flags, ciaddr=socket.inet_ntoa(ci), yiaddr=socket.inet_ntoa(yi), siaddr=socket.inet_ntoa(si), giaddr=socket.inet_ntoa(gi), chaddr=mac(p[28:28 + hl]), cookie=p[236:240].hex(), opts={}, length=len(p), optorder=[])
    i = 240
    while i < len(p):
        t = p[i]
        if t == 255: break
        if t == 0: i += 1; continue
        l = p[i + 1]; d['opts'][t] = p[i + 2:i + 2 + l]; d['optorder'].append(t); i += 2 + l
    return d
def u32(b): return struct.unpack('>I', b)[0]
def cls(ip_):
    a = ipaddress.ip_address(ip_)
    if ip_ == '0.0.0.0': return '0.0.0.0'
    if ip_ == '255.255.255.255': return '255.255.255.255(受限广播)'
    if ip_ == ME: return '本机 en0 地址'
    if ip_ == gw: return '默认网关'
    return '同网段的其它地址' if a in ipaddress.ip_network(ipaddress.ip_interface(ME + '/22').network) else '其它地址'

print('== 一:本机当前的 DHCP 租约(ipconfig getpacket en0 给出的最后一个 DHCP 应答):BOOTP 固定头 + 选项,逐项解码')
pk = sysout('ipconfig', 'getpacket', 'en0')
print('  ' + '\n  '.join(priv(l) for l in pk.splitlines() if l.strip())[:2200])
def hx(name):
    m = re.search(name + r' \(uint32\): 0x([0-9a-f]+)', pk); return int(m.group(1), 16) if m else None
lease, t1, t2 = hx('lease_time'), hx('renewal_t1_time_value'), hx('rebinding_t2_time_value')
print(f'  租约时间 {lease} 秒({lease / 60:.0f} 分钟);T1(开始续租)= {t1} 秒;T2(开始向任何服务器广播请求)= {t2} 秒')
print(f'  T1 / 租约 = {t1 / lease:.3f},T2 / 租约 = {t2 / lease:.3f}(规范建议的默认值是 0.5 和 0.875)')
print('  这个应答的 ciaddr 不是 0.0.0.0:' + ('是' if not re.search(r'ciaddr = 0\.0\.0\.0', pk) else '否') + ' —— ciaddr 非 0 说明它回应的是一次续租(客户端已有地址时发的 REQUEST),而不是首次获取')

print('== 二:发一次真实的 DHCPDISCOVER(广播 → 服务器回 OFFER):用一个随机的本地管理 MAC 作为 chaddr,不发后续 REQUEST,所以不会真正占用地址;只抓服务器回的 OFFER')
fakemac = bytes([0x02, 0x00, 0x5e]) + bytes(random.getrandbits(8) for _ in range(3))
xid = random.getrandbits(32)
opts = bytes([53, 1, 1]) + bytes([61, 7, 1]) + fakemac + bytes([12, 10]) + b'netlab-w21' + bytes([55, 8, 1, 3, 6, 15, 28, 51, 58, 59]) + bytes([57, 2]) + struct.pack('>H', 1500) + bytes([255])
disc = struct.pack('>BBBBIHH4s4s4s4s', 1, 1, 6, 0, xid, 0, 0x8000, b'\0' * 4, b'\0' * 4, b'\0' * 4, b'\0' * 4) + fakemac + b'\0' * 10 + b'\0' * 64 + b'\0' * 128 + bytes([0x63, 0x82, 0x53, 0x63]) + opts
print(f'  DISCOVER 共 {len(disc)} 字节:固定头 236 + magic cookie 4 + 选项 {len(opts)};op=1(BOOTREQUEST),xid=0x{xid:08x},flags=0x8000(广播标志:请服务器用广播回应),chaddr={fakemac.hex(":")[:8]}:xx:xx:xx(本地管理位 MAC)')
print('  选项:' + ';'.join(f'{t}={OPT.get(t, "?")}' for t in (53, 61, 12, 55, 57)))
offer = None
if not DRY:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    with Cap('udp port 67 or udp port 68', iface='en0', write=True) as c:
        t0 = time.time(); s.sendto(disc, ('255.255.255.255', 67)); time.sleep(3)
    allp = []
    for ts, ip in read_pcap(c.pcap):
        r_ = ip.raw; ihl = (r_[0] & 15) * 4; payload = r_[ihl + 8:]
        d = dec(payload)
        if d: allp.append((ts, r_, d))
    mine = [x for x in allp if x[2]['xid'] == xid]
    print(f'  3 秒内在 en0 上抓到 {len(allp)} 个 DHCP 包,其中 xid 与我的 DISCOVER 相同的 {len(mine)} 个(其余是别的设备的 DHCP 流量,只统计个数)')
    for ts, r_, d in mine:
        ihl = (r_[0] & 15) * 4; sp, dp = struct.unpack('>HH', r_[ihl:ihl + 4]); mtp = d['opts'].get(53, b'\0')[0]
        print(f'    +{(ts - t0) * 1000:7.1f} ms  {MT.get(mtp, mtp)}  UDP {sp} → {dp},IP 源 {cls(socket.inet_ntoa(r_[12:16]))} → 目的 {cls(socket.inet_ntoa(r_[16:20]))},IP 总长 {struct.unpack(">H", r_[2:4])[0]},DHCP 载荷 {d["length"]} 字节')
        if mtp == 2:
            offer = d
            print(f'      OFFER 内容:yiaddr = {cls(d["yiaddr"])}(给我的地址),siaddr = {cls(d["siaddr"])},chaddr 是我伪造的:{d["chaddr"] == fakemac.hex(":")},flags=0x{d["flags"]:04x}')
            o = d['opts']
            print(f'      选项(顺序 {d["optorder"]}):租约 {u32(o[51])} 秒' + (f',T1={u32(o[58])}' if 58 in o else ',无 T1 选项') + (f',T2={u32(o[59])}' if 59 in o else ',无 T2 选项') + f',子网掩码 {socket.inet_ntoa(o[1])},路由器 {len(o[3]) // 4} 个,DNS {len(o[6]) // 4} 个,服务器标识 {cls(socket.inet_ntoa(o[54]))}')
    if not offer: print('  没有收到 OFFER(服务器可能没有回应这个伪造的客户端,或回应是单播而本机抓不到)')
    print('  没有发 REQUEST,所以没有完成 DORA 的后两步,也没有占用这个地址;下一节用 scapy 交叉解码')

print('== 三:自己解码 vs scapy 解码:同一个 DHCP 包(上面抓到的 OFFER;抓不到时用 ipconfig getpacket 对应的 ACK 的 DISCOVER 自己拼的包),比较两种解码得到的选项')
from scapy.all import BOOTP, DHCP
src_pkt = disc if offer is None else None
if offer is not None:
    for ts, r_, d in mine:
        if d['opts'].get(53, b'\0')[0] == 2: raw_payload = r_[(r_[0] & 15) * 4 + 8:]; break
else: raw_payload = disc
sp_ = BOOTP(raw_payload); dh = sp_[DHCP].options if DHCP in sp_ else []
mine_d = dec(raw_payload)
sc_types = [o[0] for o in dh if isinstance(o, tuple)]
print(f'  自己解码出的选项编号:{mine_d["optorder"]}')
print(f'  scapy 解码出的选项名:{[o[0] for o in dh if isinstance(o, tuple)]}')
print(f'  选项个数:自己 {len(mine_d["optorder"])} / scapy {len(sc_types)};scapy 看到的 xid 0x{sp_.xid:08x} 与自己的 0x{mine_d["xid"]:08x}{"一致" if sp_.xid == mine_d["xid"] else "不一致"};op={sp_.op},chaddr 前 6 字节一致:{mac(bytes(sp_.chaddr[:6])) == mine_d["chaddr"]}')
print(f'  DHCP 包总长 {len(raw_payload)} 字节 = 固定头 236 + cookie 4 + 选项 {len(raw_payload) - 240};BOOTP 的 sname(64 字节)和 file(128 字节)两个字段在 DHCP 里基本空着:非 0 字节数 sname {sum(1 for b in raw_payload[44:108] if b)}、file {sum(1 for b in raw_payload[108:236] if b)}')

print('== 四:租约时间线(计算)与本机真实续租(被动抓包):T1 / T2 / 租约到期的时间点,以及被动抓包里是否抓到了本机的续租 REQUEST 和 ACK')
print(f'  按 ipconfig 给出的值:租约 {lease} 秒:在 T1={t1} 秒时(约 {t1 / 60:.1f} 分钟)向原服务器单播 REQUEST 续租;若没回应,到 T2={t2} 秒({t2 / 60:.1f} 分钟)改为广播 REQUEST;到 {lease} 秒({lease / 60:.0f} 分钟)租约过期就要放弃这个地址、重新从 DISCOVER 开始')
pas = '/Users/w/Desktop/zen/tools/articles/wtmp/dhcp_passive.pcap'
if os.path.exists(pas) and not DRY:
    import dpkt
    t_start = float(open('/Users/w/Desktop/zen/tools/articles/wtmp/dhcp_passive.start').read()); evs = []; others = 0
    with open(pas, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            if e.type != 0x0800: continue
            r_ = bytes(e.data); ihl = (r_[0] & 15) * 4; d = dec(r_[ihl + 8:])
            if not d: continue
            if d['chaddr'] == MYMAC:
                evs.append((ts, d, socket.inet_ntoa(r_[12:16]), socket.inet_ntoa(r_[16:20]), mac(e.dst) == 'ff:ff:ff:ff:ff:ff'))
            else: others += 1
    dur = (evs[-1][0] if evs else t_start) - t_start
    print(f'  被动抓包(从 {time.strftime("%H:%M:%S", time.localtime(t_start))} 起约 30 分钟):属于本机 MAC 的 DHCP 报文 {len(evs)} 个,其它设备的 {others} 个(只统计个数)')
    for ts, d, s_, d_, bc in evs:
        mtp = d['opts'].get(53, b'\0')[0]
        print(f'    起点后 {ts - t_start:7.1f} s  {MT.get(mtp, mtp):<8} xid=0x{d["xid"]:08x}  IP {cls(s_)} → {cls(d_)}  {"以太网目的 MAC 广播" if bc else "以太网单播"}  ciaddr={"0.0.0.0" if d["ciaddr"] == "0.0.0.0" else "本机地址"}')
    req = [x for x in evs if x[1]['opts'].get(53, b'\0')[0] == 3]
    if len(req) >= 2: print(f'  两次 REQUEST 之间的间隔:{[round(req[i + 1][0] - req[i][0], 1) for i in range(len(req) - 1)]} 秒(T1 = {t1} 秒)')
    elif req: print(f'  只抓到 1 次续租 REQUEST,发生在起点后 {req[0][0] - t_start:.1f} 秒')
    else: print('  这 30 分钟里没有抓到本机的续租报文')
else: print('  (被动抓包文件不存在或为干跑,略过)')

print('== 五:DHCP 给的配置和系统实际生效的是否一致:子网掩码 / 路由器 / DNS / 广播地址 与 ifconfig、route、scutil 的比较')
ifc = sysout('ifconfig', 'en0')
nm = re.search(r'netmask (0x[0-9a-f]+)', ifc).group(1); bc = re.search(r'broadcast ([\d.]+)', ifc).group(1)
mask_pk = re.search(r'subnet_mask \(ip\): ([\d.]+)', pk).group(1); mask_if = socket.inet_ntoa(struct.pack('>I', int(nm, 16)))
router_pk = re.search(r'router \(ip_mult\): \{([\d., ]+)\}', pk).group(1).split(', ')
dns_pk = re.search(r'domain_name_server \(ip_mult\): \{([\d., ]+)\}', pk).group(1).split(', ')
bc_pk = re.search(r'broadcast_address \(ip\): ([\d.]+)', pk).group(1)
scd = sysout('scutil', '--dns')
dns_sys = []
for l in scd.splitlines():
    m = re.match(r'\s+nameserver\[\d+\] : ([\d.]+)', l)
    if m and m.group(1) not in dns_sys: dns_sys.append(m.group(1))
print(f'  子网掩码:DHCP {mask_pk} / ifconfig {mask_if} → {"一致" if mask_pk == mask_if else "不一致"}(前缀长度 /{bin(int(nm, 16)).count("1")})')
print(f'  广播地址:DHCP 与 ifconfig {"一致" if bc_pk == bc else "不一致"}')
print(f'  路由器:DHCP 给了 {len(router_pk)} 个,默认路由的网关{"就是" if router_pk[0] == gw else "不是"}其中第一个')
print(f'  DNS:DHCP 给了 {len(dns_pk)} 个({"、".join("公共 DNS" if not ipaddress.ip_address(x).is_private else "私有地址" for x in dns_pk)});scutil --dns 里出现的 nameserver 共 {len(dns_sys)} 个,其中 DHCP 给的 {sum(1 for x in dns_pk if x in dns_sys)} 个都在里面')
print('  地址、掩码、网关、DNS、域名这些都不用手配,是 DHCP 一次交给客户端的')
