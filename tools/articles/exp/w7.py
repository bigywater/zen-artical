import sys, os, re, ipaddress, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w7'); reset()
FL = [(0x1, 'UP'), (0x2, 'BROADCAST'), (0x4, 'DEBUG'), (0x8, 'LOOPBACK'), (0x10, 'POINTOPOINT'), (0x20, 'SMART'), (0x40, 'RUNNING'), (0x80, 'NOARP'), (0x100, 'PROMISC'), (0x200, 'ALLMULTI'), (0x400, 'OACTIVE'), (0x800, 'SIMPLEX'), (0x1000, 'LINK0'), (0x2000, 'LINK1'), (0x4000, 'LINK2'), (0x8000, 'MULTICAST')]
print('== 一:ifconfig en0 每个字段是什么意思(MAC 地址被隐去)')
out = sysout('ifconfig', 'en0')
for l in out.splitlines():
    l = priv(re.sub(r'ether [0-9a-f:]+', 'ether xx:xx:xx:xx:xx:xx', l))
    if l.strip(): print('  ' + l[:130])
m = re.search(r'flags=([0-9a-f]+)<([^>]*)>', out); val = int(m.group(1), 16); names = m.group(2).split(',')
dec = [n for b, n in FL if val & b]
print(f'  flags=0x{val:x} 逐位拆开:' + ' + '.join(f'0x{b:x}({n})' for b, n in FL if val & b) + f';与 ifconfig 打印的 <{m.group(2)}> {"一致" if set(dec) == set(names) else "不一致"}')

print('== 二:十六进制子网掩码怎么读:netmask 0xfffffc00 → 点分十进制 → 前缀长度;用本机的地址算出网络号、广播地址、可用主机数(地址用示例数值表示,不直接打印)')
mm = re.search(r'inet (\d+\.\d+\.\d+\.\d+) netmask (0x[0-9a-f]+) broadcast (\d+\.\d+\.\d+\.\d+)', out)
addr, mask, bc = mm.group(1), int(mm.group(2), 16), mm.group(3)
dotted = '.'.join(str((mask >> s) & 255) for s in (24, 16, 8, 0)); plen = bin(mask).count('1')
net = ipaddress.ip_interface(f'{addr}/{plen}').network
print(f'  掩码 0x{mask:08x} = {dotted} = /{plen}(32 位里前 {plen} 位是 1,后 {32 - plen} 位是 0)')
print(f'  网络号 = 地址 AND 掩码 = {net.network_address}/{plen};网络里共 {net.num_addresses} 个地址,可用主机 {net.num_addresses - 2} 个(去掉全 0 的网络号与全 1 的广播地址)')
print(f'  ifconfig 给出的广播地址 {bc} = 网络号 OR (NOT 掩码) = {net.broadcast_address} —— 两者{"相同" if str(net.broadcast_address) == bc else "不同"}')
print(f'  本机地址落在网络内的第 {int(ipaddress.ip_address(addr)) - int(net.network_address)} 个位置(从网络号算起);同一网段的另一台主机地址与本机 AND 掩码后得到同一个网络号,才被当作“直连”')
ex = ipaddress.ip_interface('10.1.2.200/22'); print(f'  对照一个示例 10.1.2.200/22:网络号 {ex.network.network_address},广播 {ex.network.broadcast_address},可用主机 {ex.network.num_addresses - 2} 个,地址范围 {ex.network[1]} ~ {ex.network[-2]}')

print('== 三:这台机器有 23 个网络接口?ifconfig -l 列出名字;networksetup 告诉你每个是什么;再看哪些真的在用(UP 且有 IPv4 地址)')
names_ = sysout('ifconfig', '-l').split()
hw = sysout('networksetup', '-listallhardwareports'); port = {}
cur = None
for l in hw.splitlines():
    if l.startswith('Hardware Port:'): cur = l.split(': ', 1)[1]
    elif l.startswith('Device:') and cur: port[l.split(': ', 1)[1].strip()] = cur
allout = sysout('ifconfig', '-a')
blocks = re.split(r'\n(?=[a-z0-9]+: flags)', allout)
info = {}
for b in blocks:
    mm_ = re.match(r'([a-z0-9]+): flags=([0-9a-f]+)<([^>]*)> mtu (\d+)', b)
    if not mm_: continue
    n_, fl, fn, mtu = mm_.groups(); info[n_] = dict(flags=fn, mtu=int(mtu), v4=re.findall(r'\n\tinet (\d+\.\d+\.\d+\.\d+)', b), v6=len(re.findall(r'\n\tinet6 ', b)), up='UP' in fn.split(','))
kinds = collections.Counter(re.sub(r'\d+$', '', n_) for n_ in names_)
print(f'  接口 {len(names_)} 个,按名字前缀分:' + ', '.join(f'{k}×{v}' for k, v in kinds.most_common()))
for pre, desc in (('lo', '回环'), ('en', '以太网 / Wi-Fi / 雷电网桥适配器'), ('utun', '用户态隧道(VPN、iCloud 专用中继等)'), ('awdl', 'Apple 无线直连(AirDrop)'), ('llw', '低延迟 WLAN(Apple 内部)'), ('bridge', '桥接(雷电网桥)'), ('gif', '通用隧道'), ('stf', '6to4 隧道'), ('anpi', 'Apple 网络(以太网适配器相关)'), ('ap', '软件 AP'), ('nan', 'Wi-Fi 感知'), ('pktap', '抓包伪接口')):
    ms = [n_ for n_ in names_ if re.sub(r'\d+$', '', n_) == pre]
    if ms: print(f'    {pre:<7}× {len(ms):<2} {desc}' + (f'   (networksetup: {", ".join(sorted({port[n_] for n_ in ms if n_ in port}))})' if any(n_ in port for n_ in ms) else ''))
used = [n_ for n_, d in info.items() if d['up'] and d['v4']]
print(f'  UP 且有 IPv4 地址的接口: {used},其余接口要么没有 IPv4(只有 IPv6 链路本地或没地址)、要么没 UP')

print('== 四:每个接口的收发计数(netstat -ib):字节、包、错误、冲突——看 en0 和 lo0,以及 IPv6 / IPv4 各一行的含义')
ni = sysout('netstat', '-I', 'en0', '-b').splitlines()
print('  ' + ni[0][:100])
for l in ni[1:4]:
    print('  ' + priv(re.sub(r'[0-9a-f]{2}(:[0-9a-f]{2}){5}', 'xx:xx:xx:xx:xx:xx', l))[:110])
nl = sysout('netstat', '-I', 'lo0', '-b').splitlines()
print('  ' + nl[0][:100]); print('  ' + nl[1][:110])
print('  同一个接口出现多行:一行是链路层(<Link#N> + MAC),每个地址再各占一行,计数是整个接口共用的')

print('== 五:一个接口可以有多个地址吗?数各接口的 IPv4 / IPv6 地址个数;macOS 用 ifconfig 接口 alias 加别名(需要 root,这里不做)')
for n_ in ('lo0', 'en0', 'utun0', 'awdl0', 'bridge0'):
    if n_ in info: print(f'  {n_}: IPv4 地址 {len(info[n_]["v4"])} 个,IPv6 地址 {info[n_]["v6"]} 个,flags={info[n_]["flags"]},mtu={info[n_]["mtu"]}')
print('  大多数 UP 的接口会有一个 IPv6 链路本地地址(fe80::/10);bridge0 这种没有被配置的是例外。IPv4 的 169.254.x.x 是没有 DHCP 时的自分配地址(见 DHCP / 特殊地址两篇)')
