import sys, os, re, struct, threading, statistics, errno, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dns.message, dns.rdatatype, dns.name, dns.flags, dns.rcode
tee('w66'); reset()
R1 = '1.1.1.1'
TYPES = {1: 'A', 2: 'NS', 5: 'CNAME', 6: 'SOA', 15: 'MX', 16: 'TXT', 28: 'AAAA', 41: 'OPT', 33: 'SRV', 255: 'ANY'}
RC = {0: 'NOERROR', 1: 'FORMERR', 2: 'SERVFAIL', 3: 'NXDOMAIN', 4: 'NOTIMP', 5: 'REFUSED'}
def hexd(b, w=16):
    return '\n'.join('    ' + f'{i:04x}  ' + ' '.join(f'{x:02x}' for x in b[i:i + w]).ljust(w * 3) + ' ' + ''.join(chr(x) if 32 <= x < 127 else '.' for x in b[i:i + w]) for i in range(0, len(b), w))
def mkq(name, qtype=1, rd=True, qid=None, raw_name=None):
    qid = random.randrange(65536) if qid is None else qid
    qn = raw_name if raw_name is not None else b''.join(bytes([len(l)]) + l.encode() for l in name.rstrip('.').split('.')) + b'\x00'
    return struct.pack('!HHHHHH', qid, (0x0100 if rd else 0), 1, 0, 0, 0) + qn + struct.pack('!HH', qtype, 1)
def ask(pkt, server=R1, tmo=3):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(tmo); t0 = time.time()
    try:
        s.sendto(pkt, (server, 53)); d, _ = s.recvfrom(4096); return d, (time.time() - t0) * 1000
    except socket.timeout: return None, None
    finally: s.close()
def ask_retry(pkt, server=R1, n=4):
    for i in range(n):
        d, t = ask(pkt, server)
        if d: return d, t
    return None, None
def rdname(b, off, depth=0):
    labels = []; jumped = False; end = None
    while True:
        l = b[off]
        if l == 0: off += 1; break
        if l & 0xC0 == 0xC0:
            ptr = ((l & 0x3F) << 8) | b[off + 1]
            if end is None: end = off + 2
            off = ptr; jumped = True; continue
        labels.append(b[off + 1:off + 1 + l].decode('latin1')); off += 1 + l
    return '.'.join(labels) or '.', (end if end is not None else off)
def parse(b):
    qid, fl, qd, an, ns, ar = struct.unpack('!HHHHHH', b[:12]); off = 12; out = dict(id=qid, fl=fl, qd=qd, an=an, ns=ns, ar=ar, q=[], rr=[], ptrs=0)
    for _ in range(qd):
        n, off = rdname(b, off); t, c = struct.unpack('!HH', b[off:off + 4]); off += 4; out['q'].append((n, t, c))
    for sec, cnt in (('an', an), ('ns', ns), ('ar', ar)):
        for _ in range(cnt):
            st = off; n, off = rdname(b, off)
            if b[st] & 0xC0 == 0xC0: out['ptrs'] += 1
            t, c, ttl, rl = struct.unpack('!HHIH', b[off:off + 10]); off += 10; rd = b[off:off + rl]; rdoff = off; off += rl
            out['rr'].append((sec, n, t, c, ttl, rl, rd, rdoff))
    return out
def flagstr(fl):
    nm = [('QR', 15), ('AA', 10), ('TC', 9), ('RD', 8), ('RA', 7), ('AD', 5), ('CD', 4)]
    return ' '.join(n for n, bit in nm if fl >> bit & 1) or '(无)'

print('== 一:一个 DNS 查询报文的每个字节:查 example.com 的 A 记录,手工拼出来(随机 ID,RD=1),逐字节标注')
q = mkq('example.com', 1, True, qid=0x1a2b)
print(hexd(q))
print(f'  共 {len(q)} 字节 = 12 字节头 + 问题区。头部:ID={q[0]:02x}{q[1]:02x}  标志={q[2]:02x}{q[3]:02x}(0x0100:QR=0 查询,Opcode=0,RD=1 期望递归)  QDCOUNT={struct.unpack("!H", q[4:6])[0]} ANCOUNT={struct.unpack("!H", q[6:8])[0]} NSCOUNT={struct.unpack("!H", q[8:10])[0]} ARCOUNT={struct.unpack("!H", q[10:12])[0]}')
print(f'  问题区:07 "example" 03 "com" 00 = {q[12:].index(0) + 1} 字节的名字(每个标签前一个长度字节,以长度 0 结束),后面 QTYPE={struct.unpack("!H", q[-4:-2])[0]}(A)、QCLASS={struct.unpack("!H", q[-2:])[0]}(IN)各 2 字节')
d = dns.message.make_query('example.com', 'A', id=0x1a2b, use_edns=False); w = d.to_wire()
print(f'  对照 dnspython 生成的报文:{len(w)} 字节,{"与手工拼的逐字节相同" if w == q else "与手工拼的不同(RD 标志等)"}')

print('== 二:发给 1.1.1.1 的响应,逐字节解析(名字压缩指针 0xC0xx 是什么)')
resp, rt = ask_retry(q)
print(hexd(resp))
r = parse(resp)
print(f'  响应 {len(resp)} 字节,往返 {rt:.1f} ms;ID {r["id"]:#06x}(与查询相同:{r["id"] == 0x1a2b}),标志 {r["fl"]:#06x} = {flagstr(r["fl"])},RCODE = {RC.get(r["fl"] & 15, r["fl"] & 15)};问题 {r["qd"]} / 回答 {r["an"]} / 授权 {r["ns"]} / 附加 {r["ar"]}')
for sec, n, t, c, ttl, rl, rd, _o in r['rr']:
    val = '.'.join(str(x) for x in rd) if t == 1 and rl == 4 else f'{rl} 字节'
    print(f'  [{sec}] {n}  类型 {TYPES.get(t, t)}  类 {c}  TTL {ttl}  RDLENGTH {rl}  RDATA {val}')
i = resp.index(b'\xc0\x0c') if b'\xc0\x0c' in resp else -1
print(f'  回答区里记录的名字写成 2 字节的指针 {resp[i]:02x}{resp[i + 1]:02x}:高两位 11 表示“这是指针”,低 14 位 = {((resp[i] & 0x3F) << 8) | resp[i + 1]} 是报文内的偏移(从 ID 开头算),指向第 12 字节——问题区里的 example.com' if i > 0 else '  没有压缩指针')
print(f'  报文里共有 {r["ptrs"]} 个记录名使用了压缩指针')

print('== 三:标志位:同一个名字,不同提问方式得到的标志。1.1.1.1 是递归解析器;example.com 的权威服务器则只回答自己负责的区')
def line(nm, pkt, server=R1):
    d, t = ask_retry(pkt, server)
    if not d: print(f'  {nm:<44}:无响应'); return None
    p = parse(d); print(f'  {nm:<44}:标志 {flagstr(p["fl"])};RCODE {RC.get(p["fl"] & 15)};回答 {p["an"]} 授权 {p["ns"]} 附加 {p["ar"]};{len(d)} 字节'); return p
line('递归解析器,RD=1,存在的名字', mkq('example.com', 1, True))
line('递归解析器,RD=0(不要求递归)', mkq('example.com', 1, False))
line('递归解析器,example.com 下不存在的子名字', mkq('no-such-name-w66.example.com', 1, True))
p = line('递归解析器,不存在的顶级域 .invalid', mkq('no-such-name-w66.invalid', 1, True))
if p:
    soa = [x for x in p['rr'] if x[2] == 6]
    print(f'    NXDOMAIN 的授权区带 SOA({len(soa)} 条):其中的最小 TTL 字段决定这个否定答案能缓存多久(负缓存,下一篇展开)')
nsd, _ = ask_retry(mkq('example.com', 2, True))
pn = parse(nsd); nsn = []
for sec, n, t, c, ttl, rl, rd, rdoff in pn['rr']:
    if t == 2: nsn.append(rdname(nsd, rdoff)[0])
print(f'  example.com 的 NS 记录:{nsn}')
ad, _ = ask_retry(mkq(nsn[0], 1, True)); apn = parse(ad); aip = [ '.'.join(str(x) for x in rd) for sec, n, t, c, ttl, rl, rd, _o in apn['rr'] if t == 1][0]
print(f'  其中 {nsn[0]} 的地址 {aip}(公网地址)')
line('权威服务器,RD=1(权威服务器不递归)', mkq('example.com', 1, True), aip)
line('权威服务器,RD=0', mkq('example.com', 1, False), aip)
line('权威服务器,不是它托管的名字 www.kernel.org', mkq('www.kernel.org', 1, True), aip)

print('== 四:名字压缩省了多少字节:把真实响应里每个域名(问题名、记录名、RDATA 里的域名)都按完整展开计算大小,对比实际收到的字节数')
def name_len(d, off):
    n, e = rdname(d, off); return (0 if n == '.' else len(n) + 1) + 1
for nm, t in (('example.com', 'NS'), ('example.com', 'MX'), ('www.iana.org', 'A'), ('iana.org', 'NS'), ('iana.org', 'SOA')):
    d, _ = ask_retry(mkq(nm, dns.rdatatype.from_text(t), True))
    if not d: print(f'  {nm} {t}:无响应'); continue
    p = parse(d); full = 12
    for n_, t_, c_ in p['q']: full += (len(n_) + 2) + 4
    for sec, n_, t_, c_, ttl, rl, rd, ro in p['rr']:
        full += (len(n_) + 2) + 10
        if t_ in (2, 5): full += name_len(d, ro)
        elif t_ == 15: full += 2 + name_len(d, ro + 2)
        elif t_ == 6:
            l1 = name_len(d, ro); e1 = rdname(d, ro)[1]; l2 = name_len(d, e1); full += l1 + l2 + 20
        else: full += rl
    print(f'  {nm} {t}:实际响应 {len(d)} 字节(回答 {p["an"]} / 授权 {p["ns"]} / 附加 {p["ar"]});全部展开的估算 {full} 字节,压缩省了 {full - len(d)} 字节({(full - len(d)) / full:.0%})')

print('== 五:服务器怎么对待提问的细节:(1) 问题区名字的大小写是否原样回显(DNS 0x20 防伪造);(2) 非法长度的标签怎么办')
for nm in ('eXaMpLe.CoM', 'EXAMPLE.COM'):
    d, _ = ask_retry(mkq(nm, 1, True)); p = parse(d)
    print(f'  发 {nm} → 响应问题区里写的是 {p["q"][0][0]};回答里的记录名 {[x[1] for x in p["rr"]][:1]}')
bad = mkq('', 1, True, raw_name=bytes([64]) + b'a' * 64 + b'\x00')
d, t = ask_retry(bad, n=3)
if d: p = parse(d) if len(d) >= 12 else None; print(f'  发一个长度字节为 64(超过标签上限 63)的名字 → 响应 RCODE {RC.get(struct.unpack("!H", d[2:4])[0] & 15)},{len(d)} 字节')
else: print('  发一个长度字节为 64 的名字 → 3 次都没有响应(服务器直接丢弃)')
bad2 = mkq('', 1, True, raw_name=bytes([0x80]) + b'x' * 5 + b'\x00')
d, t = ask_retry(bad2, n=3)
print((f'  发一个长度字节为 0x80(保留的高两位 10)的名字 → 响应 RCODE {RC.get(struct.unpack("!H", d[2:4])[0] & 15)},{len(d)} 字节' if d else '  发一个长度字节为 0x80 的名字 → 3 次都没有响应(服务器直接丢弃)'))
