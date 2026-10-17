import sys, os, re, struct, threading, statistics, errno, random, string; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dns.message, dns.query, dns.rdatatype, dns.flags, dns.rcode, dns.exception
tee('w68'); reset()
def q(server, name, rtype='A'):
    m = dns.message.make_query(name, rtype)
    for i in range(3):
        t0 = time.time()
        try: r = dns.query.udp(m, server, timeout=2.5); return r, (time.time() - t0) * 1000
        except (dns.exception.Timeout, OSError): continue
    return None, None
def ttls(r): return [rr.ttl for rr in r.answer if rr.rdtype == dns.rdatatype.A] if r else None
def rand(n=10): return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))

print('== 一:TTL 在缓存里倒数:每 2 秒向 1.1.1.1 和 8.8.8.8 各问一次 example.net 的 A 记录(权威 TTL 是 300 秒),共 8 轮。缓存命中时返回的 TTL 是“剩余寿命”,会逐轮减少')
rows = []
for i in range(8):
    a, ta = q('1.1.1.1', 'example.net'); b, tb = q('8.8.8.8', 'example.net')
    rows.append((i * 2, ttls(a), ttls(b))); time.sleep(2)
print('    轮次(s)   1.1.1.1 返回的 TTL   8.8.8.8 返回的 TTL')
for t, a, b in rows: print(f'    {t:>5}      {a}            {b}')
da = [rows[i][1][0] - rows[i + 1][1][0] for i in range(7)]; db = [rows[i][2][0] - rows[i + 1][2][0] for i in range(7)]
print(f'  相邻两轮的差(应约等于实际间隔 2 秒加上查询耗时):1.1.1.1 {da};8.8.8.8 {db}')

print('== 二:TTL 到期之后:github.com 的权威 TTL 很短(60 秒)。每 5 秒向 8.8.8.8 问一次,共 17 轮(85 秒),看 TTL 倒数、归零后重新装满')
seq = []
for i in range(17):
    r, t = q('8.8.8.8', 'github.com'); seq.append((i * 5, ttls(r)[0] if ttls(r) else None, t)); time.sleep(5)
print('    ' + ' '.join(f'{t}s:{ttl}' for t, ttl, _ in seq))
jumps = [(seq[i][0], seq[i][1], seq[i + 1][1]) for i in range(len(seq) - 1) if seq[i][1] is not None and seq[i + 1][1] is not None and seq[i + 1][1] > seq[i][1]]
print(f'  TTL 往上跳(= 缓存过期、重新向权威服务器取)的位置:{jumps};最大值 {max(t for _, t, _ in seq if t)}')
ds = [(seq[i][2], seq[i][1]) for i in range(len(seq)) if seq[i][2]]
print(f'  每次往返时间(ms):{[round(t) for _, _, t in seq if t]}')

print('== 三:缓存命中与未命中的耗时差:对一个随机的不存在的子名字(<随机串>.example.net)第一次问(必须去权威服务器问)和紧接着第二次问(命中负缓存),各 8 个名字,问 1.1.1.1')
miss = []; hit = []; hit_ttl = []
for i in range(8):
    nm = rand() + '.example.net'
    r1, t1 = q('1.1.1.1', nm); r2, t2 = q('1.1.1.1', nm)
    if t1 and t2: miss.append(t1); hit.append(t2)
    if r1: hit_ttl.append((dns.rcode.to_text(r1.rcode()), [rr.ttl for rr in r1.authority if rr.rdtype == dns.rdatatype.SOA]))
print(f'  这些随机名字的响应:{hit_ttl[:3]} …(RCODE 和授权区 SOA 的 TTL)')
print(f'  第一次(未命中):{[round(x) for x in miss]};中位 {statistics.median(miss):.0f} ms')
print(f'  第二次(命中):{[round(x) for x in hit]};中位 {statistics.median(hit):.0f} ms;差值中位 {statistics.median(miss) - statistics.median(hit):.0f} ms')

print('== 四:负缓存(RFC 2308):不存在的名字也会被缓存,时间由响应里 SOA 的 minimum 字段和 SOA 本身的 TTL 中较小者决定。看 NXDOMAIN 响应的授权区 SOA')
nm = rand() + '.invalid'
r, t = q('1.1.1.1', nm); soa = [rr for rr in r.authority if rr.rdtype == dns.rdatatype.SOA][0]; s0 = list(soa)[0]
print(f'  {nm.split(".")[0][:3]}….invalid → RCODE {dns.rcode.to_text(r.rcode())};授权区 SOA 记录的 TTL = {soa.ttl} 秒,SOA 里的 minimum 字段 = {s0.minimum} 秒;负缓存时间 = min({soa.ttl}, {s0.minimum}) = {min(soa.ttl, s0.minimum)} 秒')
out = []
for i in range(4):
    time.sleep(3); r2, t2 = q('1.1.1.1', nm); out.append(r2.authority[0].ttl if r2.authority else None)
print(f'  之后每 3 秒再问同一个名字,授权区 SOA 的 TTL 倒数:{out}(命中负缓存,剩余寿命在减少)')
for ty in ('SRV', 'NAPTR', 'HINFO', 'WKS'):
    try: r, t = q('1.1.1.1', 'example.net', ty)
    except Exception: continue
    soa = [rr for rr in r.authority if rr.rdtype == dns.rdatatype.SOA]
    if r.rcode() == 0 and not r.answer and soa:
        out2 = []
        for i in range(3):
            time.sleep(2); r2, _ = q('1.1.1.1', 'example.net', ty); out2.append([rr.ttl for rr in r2.authority if rr.rdtype == dns.rdatatype.SOA])
        print(f'  对照 NODATA:example.net 的 {ty} 记录 → RCODE NOERROR、回答 0 条、授权区有 SOA(TTL {soa[0].ttl},minimum {list(soa[0])[0].minimum});隔 2 秒再问 3 次,SOA 的 TTL:{out2}——“名字存在但没有这种类型”也会被缓存')
        break
else: print('  (没有找到合适的 NODATA 对照类型)')

print('== 五:本机操作系统自己有缓存吗?用 getaddrinfo 对同一个名字连续调用,看耗时。macOS 有 mDNSResponder 做缓存;Python 自己没有缓存')
def ga(nm):
    t0 = time.time()
    try: socket.getaddrinfo(nm, 80, socket.AF_INET, socket.SOCK_STREAM); ok = True
    except socket.gaierror as e: ok = False
    return (time.time() - t0) * 1000, ok
nm = 'example.net'
print('  example.net(存在)连续 6 次:' + ','.join(f'{ga(nm)[0]:.1f}' for _ in range(6)) + ' ms')
nm2 = rand() + '.example.net'
print(f'  随机的不存在子名字 {nm2.split(".")[0][:3]}….example.net 连续 4 次(NODATA / NXDOMAIN):' + ','.join(f'{ga(nm2)[0]:.1f}' for _ in range(4)) + ' ms')
nm3 = rand() + '.invalid'
print(f'  随机的 .invalid 名字连续 4 次:' + ','.join(f'{ga(nm3)[0]:.1f}' for _ in range(4)) + ' ms')
