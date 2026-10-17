import sys, os, struct, dpkt; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w5'); reset()
def hexs(b): return ' '.join(f'{x:02x}' for x in b)
def tcpdump_r(path, *flags): return subprocess.run(['tcpdump', '-nn', '-e', '-r', str(path), *flags], capture_output=True, text=True).stdout.strip().splitlines()
def write_pcap(path, frames, linktype=1):
    with open(path, 'wb') as f:
        w = dpkt.pcap.Writer(f, linktype=linktype)
        for i, fr in enumerate(frames): w.writepkt(fr, ts=1700000000 + i)
DST = bytes.fromhex('021122334455'); SRC = bytes.fromhex('02aabbccddee')
ip = dpkt.ip.IP(src=bytes([10, 0, 0, 1]), dst=bytes([10, 0, 0, 2]), p=dpkt.ip.IP_PROTO_UDP, data=dpkt.udp.UDP(sport=1234, dport=5678, data=b'hello vlan', ulen=8 + 10))
ip.len = len(bytes(ip)); ippkt = bytes(ip)
untagged = DST + SRC + struct.pack('!H', 0x0800) + ippkt
def tag(pcp, dei, vid, tpid=0x8100): return struct.pack('!HH', tpid, (pcp << 13) | (dei << 12) | vid)
tagged = DST + SRC + tag(5, 0, 100) + struct.pack('!H', 0x0800) + ippkt
qinq = DST + SRC + tag(0, 0, 200, 0x88a8) + tag(5, 0, 100) + struct.pack('!H', 0x0800) + ippkt

print('== 一:这台机器的网卡有没有 VLAN?真实网口上 20 秒内有没有带 802.1Q 标签(EtherType 0x8100)的帧?')
print('  ifconfig 里含 vlan 的接口: ' + (', '.join(l.split(':')[0] for l in sysout('ifconfig', '-a').splitlines() if l and not l.startswith('\t') and 'vlan' in l.lower()) or '没有'))
nv = sysout('networksetup', '-listVLANs').strip().splitlines()
print('  networksetup -listVLANs: ' + (nv[0][:100] if nv else '(空)'))
with Cap('vlan', iface='en0', write=True) as c:
    subprocess.run(['curl', '-s', '--noproxy', '*', '-o', '/dev/null', '--max-time', '4', 'http://example.com'], capture_output=True); time.sleep(16)
print(f'  en0 上 `vlan` 过滤器 20 秒内抓到 {c.count} 个帧——接入口(access port)上交换机已经把标签剥掉了,主机看到的是普通帧;标签只在交换机之间的干道(trunk)上出现')

print('== 二:没法在这台机器上造 VLAN 流量(创建 VLAN 接口、注入带标签的帧都要 root / 写 bpf),所以按 IEEE 802.1Q 的格式自己用 struct 拼一个带标签的帧,写成 pcap,让 tcpdump 来解析它——解析出来的 VLAN 号、优先级与我拼进去的一致,说明格式拼对了')
print(f'  没标签的帧(前 18 字节): {hexs(untagged[:18])}')
print(f'    目的 MAC {hexs(untagged[0:6])}  源 MAC {hexs(untagged[6:12])}  EtherType {hexs(untagged[12:14])}(0800=IPv4)')
print(f'  带标签的帧(前 22 字节): {hexs(tagged[:22])}')
print(f'    目的 MAC、源 MAC 之后多出 4 字节: {hexs(tagged[12:16])}  → TPID={hexs(tagged[12:14])}(8100 = 802.1Q) TCI={hexs(tagged[14:16])}(0xa064);原来的 EtherType {hexs(tagged[16:18])} 被挤到标签后面')
tci = struct.unpack('!H', tagged[14:16])[0]
print(f'    TCI 拆开:PCP = {tci >> 13}(3 位优先级) DEI = {(tci >> 12) & 1}(1 位丢弃标志) VID = {tci & 0xfff}(12 位 VLAN 号)')
p1 = WT / 'w5_tagged.pcap'; write_pcap(p1, [untagged, tagged])
for l in tcpdump_r(p1): print('  tcpdump 解析: ' + l[:170])
e = dpkt.ethernet.Ethernet(tagged)
print(f'  dpkt 解析: vlan_tags = [(pri, cfi, vid)] = {[(t.pri, t.cfi, t.id) for t in e.vlan_tags]},去掉标签后载荷是 {type(e.data).__name__}')

print('== 三:标签让帧长 +4。载荷 1500 字节(标准 MTU)的帧:没标签 1514 字节(不含 FCS),带标签 1518,含 FCS 分别是 1518 与 1522——所以交换机、网卡要支持 1522 的最大帧,而 VLAN 子接口的 MTU 仍是 1500')
payload = bytes(1500)
f_un = DST + SRC + struct.pack('!H', 0x0800) + payload
f_tg = DST + SRC + tag(0, 0, 100) + struct.pack('!H', 0x0800) + payload
print(f'  载荷 1500:没标签 {len(f_un)} 字节,带标签 {len(f_tg)} 字节(+{len(f_tg) - len(f_un)});加上 4 字节 FCS:{len(f_un) + 4} → {len(f_tg) + 4}')
print(f'  最小帧(按 802.3 / 802.1Q 规范,不是实测):整个帧含 FCS 至少 64 字节,所以没标签时载荷至少 {60 - 14} 字节,带标签时载荷至少 {60 - 14 - 4} 字节,更短的由网卡补零')

print('== 四:Q-in-Q(802.1ad):运营商在客户的标签外面再套一层 S-TAG,外层 TPID=0x88a8;两层标签 +8 字节')
p2 = WT / 'w5_qinq.pcap'; write_pcap(p2, [qinq])
print(f'  双层标签的帧(前 26 字节): {hexs(qinq[:26])}')
for l in tcpdump_r(p2): print('  tcpdump 解析: ' + l[:200])
eq = dpkt.ethernet.Ethernet(qinq)
print(f'  帧长 {len(qinq)} 字节,比没标签的多 {len(qinq) - len(untagged)} 字节(2 个标签 × 4)')

print('== 五:VLAN 号只有 12 位:能取 0~4095,其中 0(只带优先级、不属于任何 VLAN)和 4095(保留)不能用来划分,实际可用 1~4094,共 4094 个;PCP 3 位,0~7。用代码把所有取值打包再解包一遍')
ok = all((lambda t: (struct.unpack('!H', t[2:4])[0] >> 13, struct.unpack('!H', t[2:4])[0] & 0xfff))(tag(p, 0, v)) == (p, v) for p in range(8) for v in range(4096))
print(f'  8 × 4096 = {8 * 4096} 种 (PCP, VID) 组合打包后再解出来全部一致: {ok}')
print(f'  可用 VLAN 号 1~4094 = {4094} 个;PCP 0~7 = 8 级优先级(7 最高,不同厂商对应的队列策略不同)')
print('  VLAN 1 通常是默认 VLAN;很多交换机的 trunk 上默认 VLAN 的帧不带标签(native VLAN)——这是配置错误的常见来源,本机无法实验')
