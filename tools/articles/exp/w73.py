import sys, os, re, struct, threading, statistics, errno, random, string; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dns.message, dns.rdatatype
import dpkt
tee('w73'); reset()
def rand(n=8): return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))
TN = {1: 'A', 28: 'AAAA', 65: 'HTTPS', 12: 'PTR', 2: 'NS', 15: 'MX', 16: 'TXT', 6: 'SOA'}
def my_ip():
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.connect(('8.8.8.8', 53)); a = u.getsockname()[0]; u.close(); return a
MYIP = my_ip()
def watch(fn, flt=None, tag='w73'):
    flt = f'udp port 53 or (udp port 5353 and src host {MYIP})'
    with Cap(flt, iface='en0', write=True, snaplen=300) as c:
        t0 = time.time(); err = None
        try: res = fn()
        except Exception as e: res = None; err = e
        dt = (time.time() - t0) * 1000; time.sleep(0.6)
    pk = []
    with open(c.pcap, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            if e.type != 0x0800: continue
            ip = e.data
            if not isinstance(ip.data, dpkt.udp.UDP): continue
            u = ip.data; kind = 'dns53' if 53 in (u.sport, u.dport) else 'mdns'
            try: m = dns.message.from_wire(bytes(u.data), ignore_trailing=True)
            except Exception: m = None
            q = [(q_.name.to_text(), TN.get(q_.rdtype, q_.rdtype)) for q_ in m.question] if m and m.question else []
            if kind == 'dns53' and not any(tag in n for n, _ in q): continue
            pk.append(dict(ts=ts, dst=socket.inet_ntoa(ip.dst), src=socket.inet_ntoa(ip.src), kind=kind, resp=bool(m and m.flags & 0x8000), q=q, rcode=m.rcode() if m else None, an=len(m.answer) if m else 0, size=len(u.data)))
    return res, err, dt, pk
def prt(pk, dt, limit=14):
    if not pk: print('    (没有抓到 DNS / mDNS 包)'); return
    t0 = pk[0]['ts']
    for p in pk[:limit]:
        if p['kind'] == 'dns53':
            who = f'→ {p["dst"]}' if not p['resp'] else f'← {p["src"]}'
            print(f'    +{(p["ts"] - t0) * 1000:7.1f} ms  {who:<22} {"响应" if p["resp"] else "查询"}  {p["q"]}' + (f'  RCODE {p["rcode"]},回答 {p["an"]}' if p['resp'] else ''))
        else:
            print(f'    +{(p["ts"] - t0) * 1000:7.1f} ms  mDNS 本机→{p["dst"]}  {"响应" if p["resp"] else "查询"}  {p["q"]}')
    if len(pk) > limit: print(f'    …共 {len(pk)} 个包')

print('== 一:本机的 DNS 配置(macOS 不是读 /etc/resolv.conf,而是系统配置里的“解析器列表”,用 scutil --dns 看)')
txt = sysout('scutil', '--dns')
blocks = re.split(r'\n\n(?=resolver #)', txt.split('DNS configuration (for scoped queries)')[0])
blocks = [b for b in blocks if b.startswith('resolver #') or 'resolver #' in b[:30]]
print(f'  默认(非作用域)解析器共 {len(blocks)} 个:')
for b in blocks:
    ls = [l.strip() for l in b.splitlines() if l.strip()]
    keep = [l for l in ls if l.startswith(('resolver', 'search domain', 'domain', 'nameserver', 'options', 'timeout', 'flags', 'order'))]
    print('    ' + ' | '.join(re.sub(r'192\.168\.\d+\.\d+', '<本机局域网IP>', l) for l in keep))
print('  /etc/hosts 的文件头说明它在 macOS 上“不被大多数进程用于 DNS 主机名解析”——但里面的 localhost / broadcasthost 仍有效(第四节验证)')

print('== 二:一次 getaddrinfo(\"w73-<随机>.example.com\") 在线路上发了什么(抓 en0 的 UDP 53 / 5353)。分别用 AF_UNSPEC(IPv4 + IPv6 都要)和只要 IPv4')
nm = f'w73-{rand()}.example.com'
res, err, dt, pk = watch(lambda: socket.getaddrinfo(nm, 80, socket.AF_UNSPEC, socket.SOCK_STREAM))
print(f'  AF_UNSPEC:耗时 {dt:.0f} ms,{"结果 " + str([a[4][0] for a in res]) if res else "失败 " + type(err).__name__};抓到 {len(pk)} 个包')
prt(pk, dt)
nm2 = f'w73-{rand()}.example.com'
res, err, dt, pk = watch(lambda: socket.getaddrinfo(nm2, 80, socket.AF_INET, socket.SOCK_STREAM))
print(f'  只要 IPv4(AF_INET):耗时 {dt:.0f} ms;抓到 {len(pk)} 个包')
prt(pk, dt)
types = lambda pk: sorted({q[1] for p in pk if not p['resp'] for q in p['q']})
print(f'  AF_INET 时发出的查询类型:{types(pk)}')

print('== 三:单标签名字(没有点)与搜索域:getaddrinfo(\"w73host<随机>\")。系统配置里有搜索域 lan')
nm = f'w73host{rand(6)}'
res, err, dt, pk = watch(lambda: socket.getaddrinfo(nm, 80, socket.AF_INET, socket.SOCK_STREAM))
print(f'  耗时 {dt:.0f} ms,{"结果 " + str([a[4][0] for a in res]) if res else "失败:" + type(err).__name__ + " " + str(err)};抓到 {len(pk)} 个包')
prt(pk, dt)
qn = sorted({q[0] for p in pk if not p['resp'] for q in p['q']})
print(f'  出现过的查询名字:{qn}(带不带搜索域后缀、是否有裸名字)')
srv = sorted({p['dst'] for p in pk if not p['resp'] and p['kind'] == 'dns53'})
print(f'  这次查询发往的服务器:{srv}')

print('== 四:不走 DNS 的名字:localhost 和 broadcasthost(/etc/hosts 里有),各解析一次,看有没有 DNS 包')
for nm in ('localhost', 'broadcasthost'):
    res, err, dt, pk = watch(lambda: socket.getaddrinfo(nm, 80, socket.AF_UNSPEC, socket.SOCK_STREAM))
    print(f'  {nm}:耗时 {dt:.1f} ms,结果 {sorted({a[4][0] for a in res}) if res else "失败"};抓到的 DNS / mDNS 包 {len(pk)} 个')

print('== 五:.local 名字走 mDNS(多播),不走上面的 DNS 服务器')
nm = f'w73-{rand(6)}.local'
res, err, dt, pk = watch(lambda: socket.getaddrinfo(nm, 80, socket.AF_INET, socket.SOCK_STREAM))
print(f'  getaddrinfo(\"{nm}\"):耗时 {dt:.0f} ms,{"结果 " + str([a[4][0] for a in res]) if res else "失败:" + type(err).__name__};抓到 {len(pk)} 个包:')
prt(pk, dt, 8)
kinds = {}
for p in pk: kinds[(p['kind'], p['dst'])] = kinds.get((p['kind'], p['dst']), 0) + 1
print(f'  按(类型, 目的地址)计数:{kinds}')
