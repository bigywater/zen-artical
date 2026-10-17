import sys, os, re, struct, threading, statistics, errno, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dns.message, dns.query, dns.rdatatype, dns.flags, dns.name, dns.rdataclass, dns.exception, dns.rcode
tee('w67'); reset()
ROOT = '198.41.0.4'
def q1(server, name, rtype='A', rd=False, edns=-1):
    m = dns.message.make_query(name, rtype, use_edns=edns, payload=1232) if edns >= 0 else dns.message.make_query(name, rtype)
    if not rd: m.flags &= ~dns.flags.RD
    for i in range(3):
        t0 = time.time()
        try:
            r = dns.query.udp(m, server, timeout=2.5); return r, (time.time() - t0) * 1000
        except (dns.exception.Timeout, OSError): continue
    return None, None
def glue_ips(resp, nsnames):
    ips = []
    for rr in resp.additional:
        if rr.rdtype == dns.rdatatype.A and rr.name.to_text().lower() in nsnames:
            ips += [x.address for x in rr]
    return ips
def iterate(name, rtype='A', verbose=True, maxq=30):
    steps = []; server = ROOT; sname = 'a.root-servers.net'; cur = name; nq = 0; cname_hops = 0
    while nq < maxq:
        r, t = q1(server, cur, rtype); nq += 1
        if r is None: steps.append((sname, server, None, '无响应', 0, 0)); return steps, None
        ans = [rr for rr in r.answer if rr.rdtype == dns.rdatatype.from_text(rtype) or rr.rdtype == dns.rdatatype.CNAME]
        if r.answer:
            cn = [rr for rr in r.answer if rr.rdtype == dns.rdatatype.CNAME]; final = [rr for rr in r.answer if rr.rdtype == dns.rdatatype.from_text(rtype)]
            steps.append((sname, server, t, f'回答:{len(final)} 条 {rtype}' + (f',{len(cn)} 条 CNAME' if cn else '') + ('(AA)' if r.flags & dns.flags.AA else ''), 0, 0))
            if final: return steps, [x.to_text() for rr in final for x in rr]
            if cn: cur = cn[-1][0].target.to_text(); cname_hops += 1; server = ROOT; sname = 'a.root-servers.net'; continue
        ns = [rr for rr in r.authority if rr.rdtype == dns.rdatatype.NS]
        if not ns:
            steps.append((sname, server, t, f'无回答也无转介(RCODE {dns.rcode.to_text(r.rcode())})', 0, 0)); return steps, None
        zone = ns[0].name.to_text(); names = [x.target.to_text().lower() for rr in ns for x in rr]
        ips = glue_ips(r, set(names))
        steps.append((sname, server, t, f'转介到 {zone}:授权区 {len(names)} 个 NS,附加区带 {len(ips)} 个 IPv4 胶水地址', len(names), len(ips)))
        if not ips:
            # 无胶水:用 1.1.1.1 解析第一个 NS 的地址(额外的一次查询,计入)
            rr_, tt = q1('1.1.1.1', names[0], 'A', True); nq += 1
            ips = [x.address for a in (rr_.answer if rr_ else []) for x in a if a.rdtype == dns.rdatatype.A]
            steps.append(('1.1.1.1', '1.1.1.1', tt, f'(无胶水)递归解析 NS {names[0]}', 0, 0))
            if not ips: return steps, None
        server = ips[0]; sname = names[0]
    return steps, None
def show(name, rtype='A'):
    t0 = time.time(); steps, ans = iterate(name, rtype); tot = (time.time() - t0) * 1000
    for i, (sn, ip, t, desc, nn, ng) in enumerate(steps):
        print(f'    第 {i + 1} 问:{sn:<26} {"" if t is None else f"{t:6.1f} ms"}  {desc}')
    print(f'    共 {len(steps)} 问,总耗时 {tot:.0f} ms;最终 {ans}')
    return len(steps), tot, steps

print('== 一:迭代解析 example.com 的 A 记录:自己从根服务器开始,每次 RD=0(不要求对方递归),看每一问得到什么')
n1, tot1, st1 = show('example.com')
print('  每一问只回答“我知道的最近一层”:根服务器不知道 example.com,但知道谁管 com.;com. 的服务器不知道地址,但知道谁管 example.com;最后一问才是权威服务器的 AA 回答')

print('== 二:转介报文长什么样:再问一次根服务器,看它给 example.com 的转介(RCODE、标志、授权区、附加区)')
r, t = q1(ROOT, 'example.com')
print(f'  RCODE {dns.rcode.to_text(r.rcode())};标志 {dns.flags.to_text(r.flags)};问题 1,回答 {len(r.answer)},授权 {sum(len(rr) for rr in r.authority)},附加 {sum(len(rr) for rr in r.additional)} 条;{len(r.to_wire())} 字节')
for rr in r.authority[:1]:
    print(f'  授权区(前 3 条):' + ';'.join(f'{rr.name} NS {x.target}' for x in list(rr)[:3]) + f' …共 {len(rr)} 条')
v4 = sum(1 for rr in r.additional if rr.rdtype == dns.rdatatype.A for x in rr); v6 = sum(1 for rr in r.additional if rr.rdtype == dns.rdatatype.AAAA for x in rr)
print(f'  附加区(胶水记录):A {v4} 条、AAAA {v6} 条——有了它们才能不绕回头去查这些 NS 名字自己的地址')
print(f'  标志里没有 AA(根服务器对 example.com 不权威),也没有 RA(根服务器不做递归);回答区是空的')

print('== 三:几个名字各要多少问(迭代,从根开始),含 CNAME 的和多层域名的')
rows = []
for nm in ('example.com', 'iana.org', 'www.bbc.co.uk', 'www.github.com', 'python.org'):
    print(f'  {nm}:'); n, tot, st = show(nm); rows.append((nm, n, tot))
print('  汇总:' + ';'.join(f'{nm} {n} 问 {tot:.0f} ms' for nm, n, tot in rows))

print('== 四:同样的名字交给递归解析器 1.1.1.1:本机只发 1 个查询(RD=1)。1.1.1.1 替我们做了上面那些事;重复问同一个名字,缓存让后面更快。每个名字问 5 次')
for nm in ('example.com', 'www.bbc.co.uk', 'www.github.com'):
    ts = []
    for i in range(5):
        r, t = q1('1.1.1.1', nm, 'A', True)
        if t: ts.append(t)
        time.sleep(0.2)
    print(f'  {nm}:5 次往返(ms):{[round(x) for x in ts]};中位 {statistics.median(ts):.0f} ms')
it = {nm: tot for nm, n, tot in rows}
print(f'  对比自己迭代:example.com {it["example.com"]:.0f} ms,www.bbc.co.uk {it["www.bbc.co.uk"]:.0f} ms,www.github.com {it["www.github.com"]:.0f} ms(本机到各服务器的往返都是公网,没有缓存)')

print('== 五:根服务器有 13 个名字(a~m.root-servers.net)。向每一个都问同一个问题(example.com 的转介),量往返时间——它们都是任播,同一个名字背后有很多台机器')
r, t = q1(ROOT, '.', 'NS', edns=0)
names = sorted(x.target.to_text().lower() for rr in r.answer for x in rr)
ips = {}
for rr in r.additional:
    if rr.rdtype == dns.rdatatype.A:
        for x in rr: ips[rr.name.to_text().lower()] = x.address
res = []
for nm in names:
    if nm not in ips: continue
    ts = []
    for i in range(3):
        rr_, tt = q1(ips[nm], 'example.com')
        if tt: ts.append(tt)
    if ts: res.append((nm.split('.')[0], statistics.median(ts)))
print('  ' + ';'.join(f'{a} {t:.0f}' for a, t in res) + '(单位 ms,各问 3 次取中位)')
print(f'  根服务器名字共 {len(names)} 个;最快 {min(res, key=lambda x: x[1])[0]} {min(t for a, t in res):.0f} ms,最慢 {max(res, key=lambda x: x[1])[0]} {max(t for a, t in res):.0f} ms')

print('== 六:www.bbc.co.uk 的异常:第三节里根服务器 a 仅用 30 ms 就“回答”了 www.bbc.co.uk(根服务器既不可能知道这个名字的地址,而到 a 根的正常往返是 240~300 ms)。验证:把同一个查询发到一个根本没有 DNS 服务的地址(192.0.2.1,文档专用地址),看会不会有回应;用 example.com 做对照')
def collect(server, name, secs=3.0):
    pkt = dns.message.make_query(name, 'A').to_wire(); s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s_.settimeout(0.3); t0 = time.time(); s_.sendto(pkt, (server, 53)); got = []
    while time.time() - t0 < secs:
        try: d, a = s_.recvfrom(4096); got.append(((time.time() - t0) * 1000, a[0], d))
        except socket.timeout: pass
    s_.close(); return got
for server, nm in (('192.0.2.1', 'example.com'), ('192.0.2.1', 'www.bbc.co.uk'), ('192.0.2.1', 'www.facebook.com'), ('198.41.0.4', 'www.bbc.co.uk')):
    got = collect(server, nm)
    print(f'  向 {server} 问 {nm}:{len(got)} 个响应' + ('' if not got else ';' + ';'.join(f'+{t:.0f} ms 来自 {a},{len(d)} 字节,答案 {[x.to_text() for rr in dns.message.from_wire(d).answer for x in rr]},TTL {[rr.ttl for rr in dns.message.from_wire(d).answer]},标志 {dns.flags.to_text(dns.message.from_wire(d).flags)}' for t, a, d in got[:4])))
print('  192.0.2.1 是预留给文档的地址,不会有任何真实的 DNS 服务;如果它“回答”了,说明响应是路径上的某个设备伪造的。结论只限于“这台机器所在的网络路径”,不涉及别的网络')
