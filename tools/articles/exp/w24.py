import sys, os, re, struct, collections, ipaddress, itertools; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w24'); reset()
def kind(a):
    x = ipaddress.ip_address(a.split('%')[0])
    if x.is_loopback: return '回环 ::1'
    if x.is_link_local: return '链路本地 fe80::/10'
    if x in ipaddress.ip_network('fc00::/7'): return '唯一本地 fc00::/7'
    if x in ipaddress.ip_network('2000::/3'): return '全球单播 2000::/3'
    if x.is_multicast: return '组播 ff00::/8'
    return '其它'

print('== 一:本机每个接口上的 IPv6 地址(ifconfig):类型、前缀长度、作用域编号、标志;地址本身只写类型')
o = sysout('ifconfig'); cur = None; inv = []
for l in o.splitlines():
    m = re.match(r'^(\w+): flags=', l)
    if m: cur = m.group(1); continue
    m = re.match(r'^\s+inet6 (\S+) prefixlen (\d+)(.*)$', l)
    if m and cur:
        a = m.group(1); rest = m.group(3).split()
        inv.append((cur, kind(a), int(m.group(2)), [w for w in rest if w in ('secured', 'temporary', 'autoconf', 'deprecated', 'tentative', 'anycast', 'dynamic')], 'scopeid' in rest))
byif = collections.OrderedDict()
for ifn, k_, pl, fl, sc in inv: byif.setdefault(ifn, []).append((k_, pl, fl, sc))
print(f'  有 IPv6 地址的接口 {len(byif)} 个,共 {len(inv)} 个地址')
for ifn, L in byif.items(): print(f'    {ifn:<7}' + ';'.join(f'{k_} /{pl}' + (f' [{",".join(fl)}]' if fl else '') + (' 带作用域编号' if sc else '') for k_, pl, fl, sc in L))
cnt = collections.Counter(k_ for _, k_, _, _, _ in inv)
print('  按类型统计:' + ';'.join(f'{k_} {v}' for k_, v in cnt.items()) + f';全球单播 / 唯一本地地址 {cnt.get("全球单播 2000::/3", 0) + cnt.get("唯一本地 fc00::/7", 0)} 个——这台机器所在的网络没有给它分配可路由的 IPv6 地址,所以它没有公网 IPv6 连通性')

print('== 二:IPv6 地址的写法:同一个地址有很多种写法,RFC 5952 规定输出时只用一种;用 ipaddress 模块验证压缩规则')
cases = ['2001:0db8:0000:0000:0000:ff00:0042:8329', '2001:db8:0:0:1:0:0:1', '2001:db8:0:1:1:1:1:1', '0:0:0:0:0:0:0:1', '0:0:0:0:0:0:0:0', '2001:db8::', 'FE80::0202:B3FF:FE1E:8329', '::ffff:192.0.2.128', '64:ff9b::192.0.2.33']
print('    输入                                      → 压缩(RFC 5952)           完整展开')
for c in cases:
    a = ipaddress.IPv6Address(c); print(f'    {c:<42}→ {a.compressed:<24}{a.exploded}')
g = ['2001', 'db8', '0', '0', '0', '0', '0', '1']
forms = set()
for start in range(9):
    for end in range(start, 9):
        if start < end and not all(x == '0' for x in g[start:end]): continue
        if start == end: runs = [None]
        else: runs = [(start, end)]
        for run in runs:
            parts = []; ok = True
            idx = list(range(8))
            left = g[:start] if run else g; right = g[end:] if run else []
            def variants(h): return [h.zfill(n) for n in range(len(h), 5)]
            for lv in itertools.product(*[variants(h) for h in left]):
                for rv in itertools.product(*[variants(h) for h in right]):
                    forms.add(':'.join(lv) + ('::' + ':'.join(rv) if run else ''))
    # 只计算压缩一次的情形
ok = sum(1 for f in forms if ipaddress.IPv6Address(f) == ipaddress.IPv6Address('2001:db8::1'))
print(f'  2001:db8::1 这一个地址,只算小写字母,按“每组可补前导 0 + 压缩任意一段连续的 0 组(或不压缩)”枚举出 {len(forms)} 种写法,其中经 ipaddress 解析都等于 2001:db8::1 的有 {ok} 种;RFC 5952 规定输出时:去掉前导 0、小写、压缩最长的连续 0 组(等长取最左)、单个 0 组不压缩')
print(f'  ::ffff:192.0.2.128 是 IPv4 映射地址,Python 里 .ipv4_mapped = {ipaddress.IPv6Address("::ffff:192.0.2.128").ipv4_mapped};64:ff9b::/96 是 NAT64 的转换前缀')

print('== 三:IPv6 地址空间怎么划分(查表 + 计算):每类前缀占整个地址空间的多大比例,以及 Python 对样本地址的分类')
ROWS = [('::/128', '未指定地址'), ('::1/128', '回环'), ('::ffff:0:0/96', 'IPv4 映射地址'), ('64:ff9b::/96', 'NAT64 转换前缀'), ('2000::/3', '全球单播(目前分配的都在这里)'), ('2001:db8::/32', '文档用'), ('fc00::/7', '唯一本地(类似 IPv4 私有地址)'), ('fe80::/10', '链路本地'), ('ff00::/8', '组播')]
print('    前缀               地址个数(2 的几次方)   占整个空间         用途')
for p, why in ROWS:
    n = ipaddress.ip_network(p); e = 128 - n.prefixlen
    frac = 2.0 ** -n.prefixlen
    print(f'    {p:<19}2^{e:<4}                  {frac:.3e}       {why}')
print(f'  全球单播 2000::/3 占整个 128 位空间的 1/8;IPv4 整个空间是 2^32,一个 /64 子网(2^64 个地址)就是整个 IPv4 空间的 {2 ** 64 // 2 ** 32:,} 倍')
print('    样本地址                   global private linklocal multicast loopback unspecified')
for sm in ('::', '::1', 'fe80::1', 'fd12:3456::1', '2001:db8::1', '2606:4700:4700::1111', 'ff02::1', '::ffff:192.0.2.1', '64:ff9b::192.0.2.1'):
    a = ipaddress.IPv6Address(sm)
    print(f'    {sm:<27}' + ''.join(f'{"是" if f else "-":>8}' for f in (a.is_global, a.is_private, a.is_link_local, a.is_multicast, a.is_loopback, a.is_unspecified)))

print('== 四:作用域实测:链路本地地址必须带“%接口”才知道往哪个接口发;::1 收发;向 ff02::1(本链路所有节点)ping 看有几个邻居应答')
def sa(addr, port, ifname):
    return socket.getaddrinfo(f'{addr}%{ifname}', port, socket.AF_INET6, socket.SOCK_DGRAM, 0, socket.AI_NUMERICHOST)[0][4]
ls = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
try:
    ls.bind(sa('fe80::1', 0, 'lo0')); port = ls.getsockname()[1]; ls.settimeout(1)
    s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM); s.sendto(b'link-local-lo0', sa('fe80::1', port, 'lo0')); d, _ = ls.recvfrom(100)
    print(f'  fe80::1%lo0 上收发:成功,收到 {d!r};套接字地址是四元组 (地址, 端口, flowinfo, scope_id={ls.getsockname()[3]}),scope_id 就是接口编号(lo0 的编号 {socket.if_nametoindex("lo0")})')
except Exception as e: print(f'  fe80::1%lo0 上收发失败:{type(e).__name__}: {getattr(e, "strerror", e)}')
ga = [l for l in sysout('ifconfig', 'en0').splitlines() if 'inet6 fe80' in l]
mine6 = ga[0].split()[1].split('%')[0] if ga else None
if mine6:
    s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    for nm, tgt in (('scope_id = 0(不带接口)', (mine6, 9, 0, 0)), ('scope_id = en0 的编号', (mine6, 9, 0, socket.if_nametoindex('en0')))):
        try: s.sendto(b'x', tgt); print(f'  往本机自己的链路本地地址({nm})发 UDP:发送成功')
        except Exception as e: print(f'  往本机自己的链路本地地址({nm})发 UDP:{type(e).__name__}: {getattr(e, "strerror", e)}')
    nb = [ (m.group(1)) for l in sysout('ndp', '-an').splitlines() for m in [re.match(r'^(fe80:\S+?)%en0\s+[0-9a-f:]{11,}\s', l)] if m and m.group(1) != mine6]
    if nb:
        s2 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        for nm, tgt in (('scope_id = 0', (nb[0], 9, 0, 0)), ('scope_id = en0 的编号', (nb[0], 9, 0, socket.if_nametoindex('en0')))):
            try: s2.sendto(b'x', tgt); print(f'  往邻居表里的一个邻居(链路本地地址,{nm})发 UDP:发送成功')
            except Exception as e: print(f'  往邻居表里的一个邻居(链路本地地址,{nm})发 UDP:{type(e).__name__}: {getattr(e, "strerror", e)}')
for grp in ('ff02::1', 'ff02::2'):
    o = sysout('ping6', '-c', '3', '-I', 'en0', grp, timeout=30)
    srcs = collections.Counter(); hl = collections.Counter()
    for m in re.finditer(r'bytes from (\S+?)(?:%\w+)?, icmp_seq=\d+ hlim=(\d+)', o): srcs[m.group(1)] += 1; hl[int(m.group(2))] += 1
    print(f'  ping6 -c 3 -I en0 {grp}:共收到 {sum(srcs.values())} 个应答,来自 {len(srcs)} 个不同的链路本地地址;应答里的跳数限制取值 {dict(hl)}' + (f';其中本机自己的地址也应答了' if mine6 in srcs else ''))
o = sysout('netstat', '-g', '-n', '-I', 'en0')
v6 = o.split('IPv6 Multicast Group Memberships')[1] if 'IPv6 Multicast Group Memberships' in o else ''
grp_en0 = [l.split()[0] for l in v6.splitlines() if '%en0' in l]
print(f'  en0 上加入的 IPv6 组播组 {len(grp_en0)} 个,按作用域(ff0X 的 X):' + ';'.join(f'ff0{k_}:{v}' for k_, v in sorted(collections.Counter(g_[3] for g_ in grp_en0).items())) + '(1 = 接口本地,2 = 链路本地)')

print('== 五:接口标识符(地址的后 64 位)怎么来:EUI-64 由 MAC 地址推出(中间插 ff:fe、翻转第 7 位);检查本机和邻居的链路本地地址是不是这样生成的,以及“被请求节点组播地址”')
def eui64(macs):
    b = bytearray(int(x, 16) for x in macs.split(':')); b[0] ^= 2
    return bytes(b[:3]) + b'\xff\xfe' + bytes(b[3:])
mymac = [l.split()[1] for l in sysout('ifconfig', 'en0').splitlines() if l.strip().startswith('ether ')][0]
if mine6:
    iid = ipaddress.IPv6Address(mine6).packed[8:]
    print(f'  本机:MAC 推出的 EUI-64 接口标识符与链路本地地址的后 64 位{"相同" if iid == eui64(mymac) else "不同"};地址标志里有 secured(= 稳定的不透明标识符,不是由 MAC 推出的)' if 'secured' in ga[0] else f'  本机:EUI-64 与实际{"相同" if iid == eui64(mymac) else "不同"}')
nd = sysout('ndp', '-an'); n_eui = n_tot = 0
for l in nd.splitlines():
    m = re.match(r'^(fe80:\S+?)%en0\s+([0-9a-f:]+)\s', l)
    if m and m.group(2).count(':') == 5:
        n_tot += 1
        if ipaddress.IPv6Address(m.group(1)).packed[8:] == eui64(m.group(2)): n_eui += 1
print(f'  邻居表(ndp -an)里 en0 上有 MAC 的 {n_tot} 个邻居:链路本地地址是 EUI-64(由 MAC 推出)的 {n_eui} 个,不是的 {n_tot - n_eui} 个——地址只统计个数')
if mine6:
    p = ipaddress.IPv6Address(mine6).packed; sn = ipaddress.IPv6Address(bytes.fromhex('ff0200000000000000000001ff') + p[13:16])
    print(f'  被请求节点组播地址 = ff02::1:ff + 地址的后 24 位 → 形如 ff02::1:ff__:____(本机一个);en0 上有没有加入:{"有" if any(ipaddress.IPv6Address(g_.split("%")[0]) == sn for g_ in grp_en0) else "没有"}')
    print(f'  en0 上加入的组播组里,被请求节点组(ff02::1:ffXX:XXXX 形式)有 {sum(1 for g_ in grp_en0 if g_.lower().startswith("ff02::1:ff"))} 个——每个地址对应一个,邻居发现用它代替广播')
