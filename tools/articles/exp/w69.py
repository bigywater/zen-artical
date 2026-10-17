import sys, os, re, struct, threading, statistics, errno, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dns.message, dns.query, dns.rdatatype, dns.flags, dns.rcode, dns.exception
tee('w69'); reset()
TN = {1: 'A', 2: 'NS', 5: 'CNAME', 6: 'SOA', 12: 'PTR', 15: 'MX', 16: 'TXT', 28: 'AAAA', 33: 'SRV', 65: 'HTTPS', 257: 'CAA', 41: 'OPT', 255: 'ANY', 13: 'HINFO'}
def ask(server, name, t, rd=True):
    pkt = struct.pack('!HHHHHH', random.randrange(65536), 0x0100, 1, 0, 0, 0) + b''.join(bytes([len(l)]) + l.encode() for l in name.rstrip('.').split('.')) + b'\x00' + struct.pack('!HH', t, 1)
    for i in range(3):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(2.5)
        try: s.sendto(pkt, (server, 53)); d, _ = s.recvfrom(4096); s.close(); return d
        except socket.timeout: s.close()
    return None
def rdname(b, off):
    labels = []; end = None
    while True:
        l = b[off]
        if l == 0: off += 1; break
        if l & 0xC0 == 0xC0:
            ptr = ((l & 0x3F) << 8) | b[off + 1]
            if end is None: end = off + 2
            off = ptr; continue
        labels.append(b[off + 1:off + 1 + l].decode('latin1')); off += 1 + l
    return '.'.join(labels) or '.', (end if end is not None else off)
def rrs(b):
    qid, fl, qd, an, ns, ar = struct.unpack('!HHHHHH', b[:12]); off = 12
    for _ in range(qd): _, off = rdname(b, off); off += 4
    out = []
    for _ in range(an + ns + ar):
        n, off = rdname(b, off); t, c, ttl, rl = struct.unpack('!HHIH', b[off:off + 10]); off += 10; out.append((n, t, ttl, rl, off, b[off:off + rl])); off += rl
    return fl & 15, an, out
def hx(b, n=40): return ' '.join(f'{x:02x}' for x in b[:n]) + (' …' if len(b) > n else '')
def dec(b, t, off, rd):
    if t == 1: return 'IPv4 ' + '.'.join(str(x) for x in rd)
    if t == 28: return 'IPv6 ' + socket.inet_ntop(socket.AF_INET6, rd)
    if t in (2, 5, 12): return '名字 ' + rdname(b, off)[0]
    if t == 15: return f'优先级 {struct.unpack("!H", rd[:2])[0]},邮件服务器 {rdname(b, off + 2)[0]}'
    if t == 16:
        parts = []; i = 0
        while i < len(rd): l = rd[i]; parts.append(rd[i + 1:i + 1 + l].decode('latin1')); i += 1 + l
        return f'{len(parts)} 个字符串(各 ≤255 字节,前缀 1 字节长度):' + ' | '.join(p[:70] + ('…' if len(p) > 70 else '') for p in parts)
    if t == 6:
        m, e = rdname(b, off); r, e2 = rdname(b, e); ser, ref, ret, exp, mn = struct.unpack('!IiiiI', b[e2:e2 + 20]) if False else struct.unpack('!IIIII', b[e2:e2 + 20])
        return f'主名字服务器 {m},管理员邮箱 {r}(第一个点代表 @),序列号 {ser},刷新 {ref},重试 {ret},过期 {exp},最小 TTL {mn}'
    if t == 33:
        pr, w, po = struct.unpack('!HHH', rd[:6]); return f'优先级 {pr},权重 {w},端口 {po},目标 {rdname(b, off + 6)[0]}'
    if t == 257:
        fl, tl_ = rd[0], rd[1]; return f'flags {fl},tag "{rd[2:2 + tl_].decode()}",value "{rd[2 + tl_:].decode()}"'
    if t == 65:
        pr = struct.unpack('!H', rd[:2])[0]; tn, e = rdname(b, off + 2); return f'SvcPriority {pr},TargetName {tn},SvcParams {len(rd) - (e - off)} 字节'
    if t == 13: return 'CPU/OS 两个字符串 ' + hx(rd, 30)
    return hx(rd)
def other_set(b):
    rc, an, out = rrs(b); return sorted((n.lower(), t, tuple(rd)) for n, t, ttl, rl, off, rd in out[:an])

def show(title, name, t, server='1.1.1.1', max_rr=4):
    d = ask(server, name, t)
    if not d: print(f'  {title}:无响应'); return None
    rc, an, out = rrs(d)
    print(f'  {title} —— 问 {name} 的 {TN.get(t, t)}(类型号 {t}):RCODE {rc},回答 {an} 条,报文 {len(d)} 字节')
    for n, tt, ttl, rl, off, rd in out[:min(an, max_rr)]:
        print(f'    {n}  {TN.get(tt, tt)}  TTL {ttl}  RDLENGTH {rl}  RDATA 字节:{hx(rd)}')
        print(f'      解读:{dec(d, tt, off, rd)}')
    if an > max_rr: print(f'    …共 {an} 条,只显示前 {max_rr} 条')
    d2 = ask('8.8.8.8', name, t)
    if d2:
        a, b = other_set(d), other_set(d2); same = (a == b)
        print(f'    与 8.8.8.8 比较:{"回答完全一致" if same else "回答不完全一致(条数 %d 对 %d;%s)" % (len(a), len(b), "不同解析器的负载均衡 / 缓存可能给出不同子集")}')
    return d

print('== 一:地址与别名记录:A(4 字节)、AAAA(16 字节)、CNAME(一个名字)。每个都给出 RDATA 的原始字节和解读')
show('A', 'example.com', 1); show('AAAA', 'example.com', 28); show('CNAME', 'www.github.com', 5)
print('== 二:邮件与委派:MX(优先级 + 邮件服务器名)、NS(区的名字服务器)、SOA(区的管理信息)')
show('MX', 'gmail.com', 15); show('NS', 'example.com', 2); show('SOA', 'example.com', 6)
print('== 三:文本与服务发现:TXT(一串带长度前缀的字符串,常用来放 SPF / 验证信息)、SRV(优先级、权重、端口、目标)、CAA(允许哪些 CA 签发证书)')
show('TXT', 'gmail.com', 16, max_rr=3); show('SRV', '_imaps._tcp.gmail.com', 33); show('CAA', 'google.com', 257)
print('== 四:反向解析 PTR 与新类型 HTTPS(SVCB)')
print('  反向名字的构造:IPv4 地址 1.1.1.1 的四段倒过来,加后缀 .in-addr.arpa → 1.1.1.1.in-addr.arpa;一个任意地址 a.b.c.d 就是 d.c.b.a.in-addr.arpa;IPv6 要把 32 个十六进制位逐位倒过来加 .ip6.arpa')
show('PTR', '1.1.1.1.in-addr.arpa', 12); show('HTTPS', 'cloudflare.com', 65)
print('== 五:ANY 类型的现状:历史上 ANY 能“列出所有记录”,但会被拿去做放大攻击,RFC 8482 允许服务器用最小回答敷衍')
for nm in ('example.com', 'cloudflare.com'):
    d = ask('1.1.1.1', nm, 255)
    if d:
        rc, an, out = rrs(d); print(f'  问 {nm} 的 ANY:RCODE {rc},回答 {an} 条:{[(TN.get(t, t), rdname(d, off)[0] if t == 13 else "") for n, t, ttl, rl, off, rd in out[:an]]};报文 {len(d)} 字节')
        for n, t, ttl, rl, off, rd in out[:an]:
            if t == 13: cl = rd[0]; cpu = rd[1:1 + cl].decode('latin1'); print(f'    HINFO 的 CPU 字段 = "{cpu}"(RFC 8482 的约定)')
print('  类型号表(本篇用到的):' + ','.join(f'{TN[k]}={k}' for k in (1, 2, 5, 6, 12, 15, 16, 28, 33, 65, 257)))
