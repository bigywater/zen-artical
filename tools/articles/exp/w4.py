import sys, os, re, dpkt, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w4'); reset()
ME = '192.168.9.100'; GW = '192.168.11.1'
def mm(b): return ':'.join(f'{x:02x}' for x in b[:3]) + ':xx:xx:xx'
def ipf(b): return '.'.join(map(str, b))
def sh(*a): return sysout(*a)
def arp_entries():
    return [l for l in sh('arp', '-an').splitlines() if 'en0' in l and 'incomplete' not in l and 'ff:ff:ff' not in l]
def gw_expire():
    for l in sh('netstat', '-rn', '-f', 'inet').splitlines():
        p = l.split()
        if len(p) >= 5 and p[0] == GW and 'L' in p[2]: return p[2], p[4] if len(p) > 4 else ''
    return None, None

print('== 一:ARP 缓存(邻居表):本机 en0 上记着多少个“IP → MAC”,网关那一条的标志与剩余寿命')
ents = arp_entries()
print(f'  arp -an 在 en0 上有 {len(ents)} 条已解析的邻居(同一个网段里的设备)')
for l in sh('arp', '-n', GW).splitlines()[:1]:
    print('  ' + re.sub(r'([0-9a-f]{1,2}:[0-9a-f]{1,2}:[0-9a-f]{1,2}):[0-9a-f:]+', r'\1:xx:xx:xx', l))
fl, ex = gw_expire()
print(f'  netstat -rn 里网关 {GW} 的主机路由:标志 {fl}(U 可用 H 主机路由 L 链路层地址 W 由 ARP 自动生成 I 接口作用域 R 拒绝 i 地址完成),Expire 剩余 {ex} 秒')
print('  系统参数: ' + ', '.join(f'{k.split(".")[-1]}={v}' for k, v in (l.split(': ') for l in sh('sysctl', 'net.link.ether.inet.max_age', 'net.link.ether.inet.maxtries', 'net.link.ether.inet.host_down_time').splitlines())))
time.sleep(5); fl2, ex2 = gw_expire()
print(f'  5 秒之后 Expire 剩余 {ex2} 秒(倒计时;每次用到这条邻居时系统会刷新 / 到期后重新发 ARP 请求确认)')

print('== 二:一次完整的 ARP 解析:找一台同网段在线、但本机缓存里没有它的主机,ping 它,同时抓 ARP')
cached = {l.split('(')[1].split(')')[0] for l in arp_entries()}
target = None
for last in range(2, 60):
    ip = f'192.168.9.{last}'
    if ip in cached or ip == ME: continue
    # 先不抓包地探测;注意这一次探测本身就会让它进缓存,所以探测之后换一台再做正式实验
    r = subprocess.run(['ping', '-c', '1', '-W', '400', ip], capture_output=True)
    if r.returncode == 0: target = ip; break
# target 已被探测写进缓存;再找第二台作为正式目标
cached = {l.split('(')[1].split(')')[0] for l in arp_entries()}
target = None
for last in range(60, 120):
    ip = f'192.168.9.{last}'
    if ip in cached or ip == ME: continue
    with Cap('arp', iface='en0', write=True) as c:
        r = subprocess.run(['ping', '-c', '1', '-W', '400', ip], capture_output=True)
    if r.returncode == 0: target = ip; break
frames = []
with open(c.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(b)
        if isinstance(e.data, dpkt.arp.ARP): frames.append((ts, e, len(b), b))
mine = [(ts, e, l, b) for ts, e, l, b in frames if ipf(e.data.tpa) == target or ipf(e.data.spa) == target]
if not target or not mine:
    print('  (扫描范围内没有找到合适的在线主机,本节用本机能触发的另一类请求代替——见第三节)')
else:
    t0 = mine[0][0]
    for ts, e, l, b in mine[:2]:
        a = e.data
        print(f'  +{(ts - t0) * 1000:7.3f} ms  {"请求" if a.op == 1 else "应答"}  帧长 {l}  以太网: 目的 {mm(e.dst)}(' + ('广播' if e.dst == b'\xff' * 6 else '单播') + f') 源 {mm(e.src)} 类型 0x{e.type:04x}')
        print(f'      ARP: 硬件类型 {a.hrd}(1=以太网) 协议类型 0x{a.pro:04x}(IPv4) 硬件地址长 {a.hln} 协议地址长 {a.pln} 操作 {a.op}({"请求 who-has" if a.op == 1 else "应答 is-at"})')
        print(f'      发送方 MAC {mm(a.sha)} IP {ipf(a.spa)};目标 MAC {mm(a.tha) if any(a.tha) else "00:00:00:00:00:00(未知)"} IP {ipf(a.tpa)}')
    if len(mine) >= 2: print(f'  请求到应答 {(mine[1][0] - mine[0][0]) * 1000:.2f} ms(解析一个邻居的代价);之后 ping 才真正发出。ARP 报文本体 {len(mine[0][1].data)} 字节')
    print('  这台主机的 MAC 现在在本机缓存里: ' + str(any(target in l for l in arp_entries())))

print('== 三:没人应答会怎样?每秒 ping 一次不存在的 IP 192.168.9.253,共 8 秒,抓 ARP:请求怎么重发(sysctl maxtries=5)')
with Cap('arp and host 192.168.9.253', iface='en0', write=True) as c3:
    pr3 = subprocess.run(['ping', '-c', '8', '-i', '1', '-W', '300', '192.168.9.253'], capture_output=True, text=True, timeout=30)
ts3 = []
with open(c3.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(b)
        if isinstance(e.data, dpkt.arp.ARP) and e.data.op == 1 and ipf(e.data.spa) == ME: ts3.append(ts)
print(f'  本机发出的 ARP 请求 {len(ts3)} 个,时刻(相对第一个,秒): {[round(t - ts3[0], 2) for t in ts3]}')
print('  ping 的输出: ' + ' | '.join(l for l in (pr3.stdout + pr3.stderr).splitlines() if l.strip())[:300])
print(f'  arp -an 里这个地址的状态: ' + (next((re.sub(r"([0-9a-f]{1,2}:){3}[0-9a-f:]+", "…", l) for l in sh("arp", "-an").splitlines() if "192.168.9.253" in l), "(没有条目)")) + '  ← incomplete = 已发了请求、一直没等到应答')

print('== 四:这个网段上 30 秒的 ARP 流量(别的设备之间的也能看到,因为请求是广播):请求 / 应答比例、应答延迟、免费 ARP 与探测')
with Cap('arp', iface='en0', write=True) as c4:
    time.sleep(30)
req = {}; lat = []; nreq = nrep = ngrat = nprobe = 0
with open(c4.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(b)
        if not isinstance(e.data, dpkt.arp.ARP): continue
        a = e.data
        if a.op == 1:
            nreq += 1
            if a.spa == a.tpa: ngrat += 1
            if a.spa == b'\0\0\0\0': nprobe += 1
            req.setdefault((a.tpa, a.spa), ts)
        elif a.op == 2:
            nrep += 1
            k = (a.spa, a.tpa)
            if k in req: lat.append((ts - req[k]) * 1000)
lat.sort()
print(f'  30 秒共 {nreq + nrep} 个 ARP 帧:请求 {nreq} 个(广播)、应答 {nrep} 个(单播);其中免费 ARP(发送方 IP = 目标 IP){ngrat} 个,ARP 探测(发送方 IP = 0.0.0.0){nprobe} 个')
if lat: print(f'  配上对的请求 → 应答 {len(lat)} 对,延迟 p50 {lat[len(lat) // 2]:.2f} ms,p90 {lat[int(len(lat) * .9)]:.2f} ms,最大 {lat[-1]:.2f} ms')
print('  应答只抓到极少数:应答是单播,通常只送到提问者,本机这个抓包点看不到别人收到的单播;而请求是广播,整个网段都能看到(请求 166 个对应答 2 个就是这个原因)')

print('== 五:发给自己和环回不需要 ARP:ping 127.0.0.1 与 ping 本机自己的 en0 地址,同时在 lo0 与 en0 上抓 ARP')
with Cap('arp', iface='en0', write=True) as c5a, Cap('not ip and not ip6', iface='lo0', write=True) as c5b:
    subprocess.run(['ping', '-c', '2', '127.0.0.1'], capture_output=True); subprocess.run(['ping', '-c', '2', ME], capture_output=True)
mine5 = 0
with open(c5a.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(b)
        if isinstance(e.data, dpkt.arp.ARP) and (ipf(e.data.spa) == ME or ipf(e.data.tpa) == ME): mine5 += 1
print(f'  en0 上与本机地址 {ME} 相关的 ARP 帧:{mine5} 个;lo0 上非 IP 的帧(ARP 或别的):{c5b.count} 个——发往本机自己的地址走本机内部(lo0),根本不会出网卡,也就不需要 ARP')
