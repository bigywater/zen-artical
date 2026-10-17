import sys, os, re, ipaddress, random, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w11'); reset()
FLAGS = {'U': '路由可用', 'G': '下一跳是网关', 'H': '主机路由(/32)', 'S': '静态(手动 / 系统添加)', 'C': '可克隆:用到时为每个目的地克隆一条主机路由', 'c': '该路由是克隆出来的', 'g': '默认路由标志(网关路由)', 'L': '带链路层地址(ARP 邻居)', 'W': '由克隆产生', 'I': '绑定到特定接口(ifscope)', 'i': '地址已解析完成', 'R': '拒绝', 'm': '组播', 'b': '广播', 'r': '路由已被缓存', 'D': '由 ICMP 重定向动态创建', 'B': '黑洞,丢弃'}
rt = sysout('netstat', '-rn', '-f', 'inet').splitlines()
def parse(l):
    p = l.split()
    if len(p) < 4 or not re.match(r'^(default|\d+(\.\d+)*(/\d+)?)$', p[0]): return None
    d = p[0]
    if d == 'default': net = ipaddress.ip_network('0.0.0.0/0')
    else:
        base, _, pl = d.partition('/'); oc = base.split('.')
        plen = int(pl) if pl else (8 * len(oc) if len(oc) < 4 else 32)
        net = ipaddress.ip_network('.'.join(oc + ['0'] * (4 - len(oc))) + f'/{plen}', strict=False)
    return dict(net=net, gw=p[1], flags=p[2], iface=p[3] if len(p) > 3 else '?')
routes = [r for r in map(parse, rt) if r]

print('== 一:netstat -rn 的列和 flags 字母:挑出最有代表性的几条路由逐个解释(地址已遮盖)')
print('  Destination        Gateway            Flags               Netif Expire')
shown = 0
for l in rt:
    p = l.split()
    if p and (p[0] in ('default', '127', '169.254', '224.0.0/4', '255.255.255.255/32') or p[0].endswith('/22') or p[0] == '127.0.0.1'):
        print('  ' + priv(l)[:90])
seen = set()
for r in routes:
    for ch in r['flags']:
        seen.add(ch)
print('  出现过的 flags 字母含义: ' + ';'.join(f'{c}={FLAGS.get(c, "?")}' for c in 'UGHSCcgLWIimb' if c in seen))

print('== 二:route get 看内核对某个目的地选的是哪条路由(目的、掩码、网关、接口、标志、MTU)')
for dest, why in (('127.0.0.1', '回环'), ('192.168.9.100', '本机自己的 en0 地址'), ('192.168.9.20', '同网段的邻居'), ('8.8.8.8', '公网地址'), ('224.0.0.1', '组播'), ('169.254.1.1', '链路本地')):
    r = sysout('route', '-n', 'get', dest)
    d = {k.strip(): v.strip() for k, v in (l.split(':', 1) for l in r.splitlines() if ':' in l)}
    gw = d.get('gateway', '(直连)')
    print(f'  {why:<10}目的地 {"<本机局域网IP>" if dest.startswith("192.168") else dest:<15}→ 匹配的路由 {priv(d.get("destination", "?"))}/{d.get("mask", "?")}  网关 {priv(gw)}  接口 {d.get("interface", "?")}  标志 {d.get("flags", "?")}')

print('== 三:自己实现最长前缀匹配:把本机路由表读进来,对一组目的地做“匹配所有路由、取前缀最长的”,与内核 route get 选出的接口比较')
def lpm(ip):
    a = ipaddress.ip_address(ip); best = None
    for r in routes:
        if a in r['net'] and (best is None or r['net'].prefixlen > best['net'].prefixlen): best = r
    return best
tests = ['127.0.0.1', '192.168.9.100', '192.168.9.108', '192.168.11.1', '8.8.8.8', '1.1.1.1', '224.0.0.251', '255.255.255.255', '169.254.100.1', '10.0.0.1', '172.16.0.1', '203.0.113.9']
agree = 0
for ip in tests:
    b = lpm(ip); k = sysout('route', '-n', 'get', ip)
    d = {x.strip(): v.strip() for x, v in (l.split(':', 1) for l in k.splitlines() if ':' in l)}
    ok = b is not None and b['iface'] == d.get('interface')
    agree += ok
    shown = '<本机局域网IP>' if ip.startswith('192.168') else ip
    print(f'  {shown:<17}我的 LPM: /{b["net"].prefixlen if b else "-"} 接口 {b["iface"] if b else "-":<5} 内核: 接口 {d.get("interface", "?"):<5} {"一致" if ok else "不一致"}')
own = [l for l in rt if l.split() and l.split()[0] == '192.168.9.100']
print(f'  netstat -rn 里有没有本机自己 en0 地址的那条路由: {"有" if own else "没有"}(route get 却能查到一条标志含 LOCAL、出口 lo0 的主机路由)')
print(f'  {len(tests)} 个目的地里 {agree} 个一致。多条路由同时匹配时,总是前缀最长的赢——例如本机自己 en0 的地址同时匹配 default(/0)、局域网(/22)、主机路由 /32,选的是 /32')
print(f'  路由表里一共有 {len(routes)} 条路由,前缀分布 ' + str(sorted({r["net"].prefixlen for r in routes})))

print('== 四:查表的代价:同样的“最长前缀匹配”,逐条扫描 vs 按前缀长度分桶用哈希。表里放 20000 条随机路由,查 5 万个随机地址')
random.seed(3)
table = {}
for _ in range(20000):
    pl = random.choice([8, 12, 16, 20, 22, 24, 24, 24, 28, 32]); net = ipaddress.ip_network((random.getrandbits(32) >> (32 - pl) << (32 - pl), pl)); table[net] = len(table)
lin = [(int(n.network_address), n.prefixlen, v) for n, v in table.items()]
buckets = {}
for n, v in table.items(): buckets.setdefault(n.prefixlen, {})[int(n.network_address)] = v
lens = sorted(buckets, reverse=True)
qs = [random.getrandbits(32) for _ in range(5000)]
def scan(ip):
    best = None
    for net_, pl, v in lin:
        if (ip >> (32 - pl) << (32 - pl)) == net_ and (best is None or pl > best[0]): best = (pl, v)
    return best
def hashed(ip):
    for pl in lens:
        v = buckets[pl].get(ip >> (32 - pl) << (32 - pl))
        if v is not None: return (pl, v)
    return None
t0 = time.perf_counter(); r1 = [scan(q) for q in qs]; t1 = time.perf_counter() - t0
qs2 = [random.getrandbits(32) for _ in range(50000)]
t0 = time.perf_counter(); r2 = [hashed(q) for q in qs]; t2 = time.perf_counter() - t0
t0 = time.perf_counter(); [hashed(q) for q in qs2]; t3 = time.perf_counter() - t0
print(f'  逐条扫描:5000 次查询 {t1 * 1000:.0f} ms(每次 {t1 / 5000 * 1e6:.0f} µs);按前缀长度分桶 + 哈希:同样 5000 次 {t2 * 1000:.0f} ms(每次 {t2 / 5000 * 1e6:.1f} µs),两种方法结果{"一致" if r1 == r2 else "不一致"}')
print(f'  分桶哈希对 5 万次查询 {t3 * 1000:.0f} ms;最多只要比较 {len(lens)} 个前缀长度,与路由条数无关——真实路由器用 trie 或硬件 TCAM,思路是一样的:不要逐条比')
