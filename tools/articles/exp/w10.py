import sys, os, re, ipaddress, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w10'); reset()
def info(cidr):
    n = ipaddress.ip_interface(cidr); net = n.network
    hosts = net.num_addresses - 2 if net.prefixlen < 31 else net.num_addresses
    first = net[1] if net.prefixlen < 31 else net[0]; last = net[-2] if net.prefixlen < 31 else net[-1]
    return f'{cidr:<18} 掩码 {str(net.netmask):<16} 通配符 {str(net.hostmask):<12} 网络号 {str(net.network_address):<13} 广播 {str(net.broadcast_address):<15} 可用主机 {hosts:<6} 范围 {first} ~ {last}'

print('== 一:用代码算 CIDR:同一个地址在不同前缀长度下的网络号、广播地址、可用主机数')
for c in ('10.1.2.200/8', '10.1.2.200/16', '10.1.2.200/22', '10.1.2.200/24', '172.16.5.9/20', '192.0.2.77/26', '192.0.2.77/28', '192.0.2.77/30'):
    print('  ' + info(c))
print('  规律:前缀每加 1 位,地址数减半;可用主机数 = 2^(32−前缀) − 2')

print('== 二:/31 与 /32 的特殊情况:/31 没有网络号和广播地址(点对点链路用,RFC 3021),/32 是单个主机')
for c in ('192.0.2.4/30', '192.0.2.4/31', '192.0.2.4/32'):
    n = ipaddress.ip_network(c, strict=False)
    print(f'  {c}: 共 {n.num_addresses} 个地址,地址列表 {[str(a) for a in n]}')
print('  ipaddress 的 hosts() 在 /31 上返回两个地址,在 /32 上返回一个,与 RFC 3021 / 主机路由的约定一致:' + str([len(list(ipaddress.ip_network(c).hosts())) for c in ('192.0.2.0/30', '192.0.2.0/31', '192.0.2.0/32')]))

print('== 三:划分(VLSM):把 10.0.0.0/24 切给四个部门,需要主机数 60、28、12、2——从大到小分配,每个选刚好够用的最小前缀,检查不重叠')
need = [('A', 60), ('B', 28), ('C', 12), ('D', 2)]
pool = ipaddress.ip_network('10.0.0.0/24'); cur = int(pool.network_address); alloc = []
for name, h in sorted(need, key=lambda x: -x[1]):
    plen = 32
    while (1 << (32 - plen)) - 2 < h: plen -= 1
    size = 1 << (32 - plen)
    if cur % size: cur += size - cur % size
    net = ipaddress.ip_network((cur, plen)); alloc.append((name, h, net)); cur += size
for name, h, net in alloc:
    print(f'  部门 {name}:需要 {h:<3} 台 → {str(net):<16} (可用 {net.num_addresses - 2:<3} 台,浪费 {net.num_addresses - 2 - h} 个)')
ok = not any(a[2].overlaps(b[2]) for i, a in enumerate(alloc) for b in alloc[i + 1:])
print(f'  四个子网互不重叠: {ok};用掉 {sum(n.num_addresses for _, _, n in alloc)} 个地址,/24 里还剩 {pool.num_addresses - sum(n.num_addresses for _, _, n in alloc)} 个')

print('== 四:汇总(路由聚合):8 个连续的 /24 能合并成一条 /21;不连续或没对齐就合并不了')
nets = [ipaddress.ip_network(f'10.8.{i}.0/24') for i in range(8)]
print('  10.8.0.0/24 ~ 10.8.7.0/24 合并 → ' + str(list(ipaddress.collapse_addresses(nets))))
nets2 = [ipaddress.ip_network(f'10.8.{i}.0/24') for i in (1, 2, 3, 4)]
print('  10.8.1.0/24 ~ 10.8.4.0/24(从 1 开始,没有对齐到 4 的倍数)→ ' + str(list(ipaddress.collapse_addresses(nets2))))
nets3 = [ipaddress.ip_network(f'10.8.{i}.0/24') for i in (0, 1, 2, 4)]
print('  10.8.0.0/24, .1, .2, .4(缺 .3)→ ' + str(list(ipaddress.collapse_addresses(nets3))))
print('  聚合要求:个数是 2 的幂、起点按这个大小对齐(/21 的起点必须是 8 的倍数),否则只能合并一部分')

print('== 五:判断“某个 IP 在不在子网里”只需要一次与运算:(ip AND mask) == network。比较 100 万次查询——ipaddress 对象 vs 整数位运算')
net = ipaddress.ip_network('172.16.0.0/20'); n_int = int(net.network_address); m_int = int(net.netmask)
random.seed(1); base = int(ipaddress.ip_address('172.16.0.0')); ips = [base + random.getrandbits(16) for _ in range(1000000)]   # 在 172.16.0.0/16 里随机取,期望 1/16 落在 /20 内
t0 = time.perf_counter(); c1 = sum(1 for i in ips if ipaddress.ip_address(i) in net); t1 = time.perf_counter() - t0
t0 = time.perf_counter(); c2 = sum(1 for i in ips if (i & m_int) == n_int); t2 = time.perf_counter() - t0
print(f'  100 万个 172.16.0.0/16 里的随机地址,落在 172.16.0.0/20 内的有 {c1} 个(位运算算出 {c2} 个,{"一致" if c1 == c2 else "不一致"})')
print(f'  ipaddress.ip_address() in network: {t1 * 1000:.0f} ms;整数 (ip & mask) == network: {t2 * 1000:.0f} ms,快 {t1 / t2:.0f} 倍——路由器做最长前缀匹配就是在做这个运算')

print('== 六:这台机器的路由表里前缀长度的真实分布(netstat -rn -f inet,地址已遮盖),验证 “目的地写法里省略末尾的 0”')
rt = sysout('netstat', '-rn', '-f', 'inet').splitlines()
pf = []
for l in rt:
    p = l.split()
    if len(p) >= 4 and re.match(r'^(default|\d+(\.\d+)*(/\d+)?)$', p[0]):
        pf.append(p[0])
cntp = {}
for d in pf:
    m = re.search(r'/(\d+)$', d)
    k = int(m.group(1)) if m else (0 if d == 'default' else 32)
    cntp[k] = cntp.get(k, 0) + 1
print(f'  路由表共 {len(pf)} 条目的地;前缀长度分布: ' + ', '.join(f'/{k}×{v}' for k, v in sorted(cntp.items())))
for l in rt:
    p = l.split()
    if p and (p[0] in ('default', '127', '169.254', '224.0.0/4', '255.255.255.255/32') or p[0].endswith('/22')):
        print('  ' + priv(l)[:100])
print(f'  另有 {len([d for d in pf if d.startswith("169.254.")])} 条 169.254.x.x 的主机路由(同网段邻居的 ARP 条目,标志 UHLSW,不逐条列出)')
print('  netstat 把目的地的尾部 0 省略写(127 = 127.0.0.0/8,169.254 = 169.254.0.0/16),/N 给出前缀长度;default 就是 0.0.0.0/0')
