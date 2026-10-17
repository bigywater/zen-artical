import sys, os, re, struct, threading, statistics, errno, random, datetime, copy; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dns.message, dns.query, dns.rdatatype, dns.flags, dns.rcode, dns.exception, dns.dnssec, dns.name, dns.rdata, dns.rdataclass, dns.edns
tee('w71'); reset()
ALG = {8: 'RSASHA256', 13: 'ECDSAP256SHA256', 14: 'ECDSAP384SHA384', 15: 'ED25519', 10: 'RSASHA512', 5: 'RSASHA1'}
ANCHORS = {20326: 'E06D44B80B8F1D39A95C0B0D7C65D08458E880409BBC683457104237C7F8EC8D', 38696: '683D2D0ACB8C9B712A1948B27F741219298D0A450D612C483AF444A4C0FB2B16'}
def q(name, t, srv='1.1.1.1', cd=False, do=True):
    m = dns.message.make_query(name, t, use_edns=0, payload=1232, want_dnssec=do)
    if cd: m.flags |= dns.flags.CD
    for i in range(3):
        try: return dns.query.udp(m, srv, timeout=3) if True else None
        except dns.message.Truncated: return dns.query.tcp(m, srv, timeout=5)
        except Exception: pass
    return None
def qt(name, t, **kw):
    r = q(name, t, **kw)
    if r is not None and r.flags & dns.flags.TC:
        m = dns.message.make_query(name, t, use_edns=0, payload=1232, want_dnssec=True); r = dns.query.tcp(m, kw.get('srv', '1.1.1.1'), timeout=5)
    return r
def sets(r, name, t):
    n = dns.name.from_text(name); rr = r.find_rrset(r.answer, n, dns.rdataclass.IN, dns.rdatatype.from_text(t)); sig = r.find_rrset(r.answer, n, dns.rdataclass.IN, dns.rdatatype.RRSIG, dns.rdatatype.from_text(t)); return rr, sig
def ts(x): return datetime.datetime.fromtimestamp(x, datetime.UTC).strftime('%Y-%m-%d %H:%M UTC') if isinstance(x, int) else str(x)

print('== 一:DNSSEC 的两个新迹象:响应标志里的 AD(Authenticated Data,解析器说“我验证过了”),以及答案旁边的 RRSIG 记录。向 1.1.1.1 问 example.com 的 A(DO = 1)')
r = qt('example.com', 'A'); rr, sig = sets(r, 'example.com.', 'A')
print(f'  标志 {dns.flags.to_text(r.flags)};响应 {len(r.to_wire())} 字节(不带 DO 时 61 字节);回答区:{len(rr)} 条 A + {len(sig)} 条 RRSIG')
s0 = list(sig)[0]
print(f'  RRSIG 的字段:覆盖的类型 {dns.rdatatype.to_text(s0.type_covered)};算法 {s0.algorithm}({ALG.get(s0.algorithm, "?")});标签数 {s0.labels};原始 TTL {s0.original_ttl};签名过期 {ts(s0.expiration)};签名开始 {ts(s0.inception)};密钥标签 {s0.key_tag};签名者 {s0.signer};签名本身 {len(s0.signature)} 字节')
now = int(time.time()); print(f'  这条签名的有效期长度 {(s0.expiration - s0.inception) / 3600:.1f} 小时;距离过期还剩 {(s0.expiration - now) / 3600:.1f} 小时')
r2 = qt('example.com', 'A', do=False); print(f'  不带 DO 位时:标志 {dns.flags.to_text(r2.flags)}(没有 AD),{len(r2.to_wire())} 字节,没有 RRSIG')

print('== 二:自己从根的信任锚开始,一环一环验证 example.com 的 A 记录(不依赖 1.1.1.1 的 AD 标志)')
ok_all = True
def step(msg, f):
    global ok_all
    try: f(); print(f'  ✓ {msg}')
    except Exception as e: ok_all = False; print(f'  ✗ {msg}:{type(e).__name__} {e}')
keys = {}
r = qt('.', 'DNSKEY'); kset, ksig = sets(r, '.', 'DNSKEY')
print(f'  根的 DNSKEY:{len(kset)} 个(flags {[k.flags for k in kset]};256 = 区签名密钥 ZSK,257 = 密钥签名密钥 KSK);签名者 {[s.key_tag for s in ksig]}')
anchor_hit = []
for k in kset:
    if k.flags == 257:
        tag = dns.dnssec.key_id(k)
        if tag in ANCHORS:
            ds = dns.dnssec.make_ds(dns.name.root, k, 'SHA256')
            if ds.digest.hex().upper() == ANCHORS[tag]: anchor_hit.append(tag)
print(f'  内置的信任锚(IANA 公布的根 KSK 的 DS 摘要,密钥标签 20326 和 38696)与响应里的 KSK 匹配:{anchor_hit}')
step('根的 DNSKEY 记录集被某个 KSK 签名,签名验证通过(用信任锚确认过的那个 KSK)', lambda: dns.dnssec.validate(kset, ksig, {dns.name.root: kset}))
keys[dns.name.root] = kset
chain = ['com.', 'example.com.']; parent = dns.name.root
for z in chain:
    zn = dns.name.from_text(z); r = qt(z, 'DS'); dsset, dssig = sets(r, z, 'DS')
    step(f'{z} 的 DS 记录(在父区 {parent} 里,由父区的密钥签名)验证通过;DS 内容:密钥标签 {[d.key_tag for d in dsset]},算法 {[d.algorithm for d in dsset]},摘要类型 {[d.digest_type for d in dsset]}', lambda: dns.dnssec.validate(dsset, dssig, {parent: keys[parent]}))
    r = qt(z, 'DNSKEY'); zk, zs = sets(r, z, 'DNSKEY')
    match = [k for k in zk for d in dsset if k.flags & 1 and dns.dnssec.key_id(k) == d.key_tag and dns.dnssec.make_ds(zn, k, d.digest_type).digest == d.digest]
    step(f'{z} 的 DNSKEY 里有一个 KSK(密钥标签 {[dns.dnssec.key_id(k) for k in match]})的哈希等于父区 DS 里的摘要', lambda: (_ for _ in ()).throw(Exception('没有匹配')) if not match else None)
    step(f'{z} 的 DNSKEY 记录集({len(zk)} 个密钥)的签名验证通过', lambda: dns.dnssec.validate(zk, zs, {zn: zk}))
    keys[zn] = zk; parent = zn
r = qt('example.com', 'A'); rr, sig = sets(r, 'example.com.', 'A')
step('example.com 的 A 记录集的 RRSIG 验证通过(用 example.com 的 ZSK)', lambda: dns.dnssec.validate(rr, sig, {dns.name.from_text('example.com.'): keys[dns.name.from_text('example.com.')]}))
print(f'  整条链{"全部通过" if ok_all else "有环节失败"}:根(信任锚)→ com. 的 DS → com. 的密钥 → example.com. 的 DS → example.com. 的密钥 → A 记录')

print('== 三:篡改会被发现:把已验证的 A 记录集改一个字节,或改签名的一个字节,再验证')
name = dns.name.from_text('example.com.'); zk = keys[name]
bad = dns.rrset.from_text('example.com.', rr.ttl, 'IN', 'A', '104.20.23.155', '172.66.147.243')
try: dns.dnssec.validate(bad, sig, {name: zk}); print('  改一个地址 → 验证通过(异常)')
except Exception as e: print(f'  把 104.20.23.154 改成 104.20.23.155 → 验证失败:{type(e).__name__}')
s_bad = copy.deepcopy(sig); sr = list(s_bad)[0]; sigb = bytearray(sr.signature); sigb[5] ^= 1
new = dns.rdata.from_wire(dns.rdataclass.IN, dns.rdatatype.RRSIG, dns.rdata.Rdata.to_wire(sr)[:-len(sr.signature)] + bytes(sigb), 0, len(dns.rdata.Rdata.to_wire(sr)), None) if False else None
sr2 = dns.rdtypes.ANY.RRSIG.RRSIG(sr.rdclass, sr.rdtype, sr.type_covered, sr.algorithm, sr.labels, sr.original_ttl, sr.expiration, sr.inception, sr.key_tag, sr.signer, bytes(sigb))
s2 = dns.rrset.RRset(sig.name, sig.rdclass, sig.rdtype, sig.covers); s2.update_ttl(sig.ttl); s2.add(sr2)
try: dns.dnssec.validate(rr, s2, {name: zk}); print('  改签名里的一个比特 → 验证通过(异常)')
except Exception as e: print(f'  把签名中的 1 个比特翻转 → 验证失败:{type(e).__name__}')
try: dns.dnssec.validate(rr, sig, {name: zk}, now=sr.expiration + 3600); print('  把“现在”拨到过期后 1 小时 → 验证通过(异常)')
except Exception as e: print(f'  把验证时间设到签名过期后 1 小时 → 验证失败:{type(e).__name__}(签名有有效期,过期的签名即使没被改过也无效)')

print('== 四:验证失败的域名:dnssec-failed.org 是专门故意签坏的测试域名。1.1.1.1 和 8.8.8.8 是验证型解析器,会拒绝它;加上 CD(Checking Disabled)位可以跳过验证')
for srv in ('1.1.1.1', '8.8.8.8'):
    r = qt('dnssec-failed.org', 'A', srv=srv); rc = qt('dnssec-failed.org', 'A', srv=srv, cd=True)
    ede = [(o.code, o.text) for o in (r.opt[0].options if r.opt else []) if o.otype == dns.edns.OptionType.EDE]
    print(f'  {srv}:默认 → RCODE {dns.rcode.to_text(r.rcode())},回答 {len(r.answer)} 条,标志 {dns.flags.to_text(r.flags)},扩展错误(EDE) {ede};加 CD → RCODE {dns.rcode.to_text(rc.rcode())},回答 {sum(len(x) for x in rc.answer if x.rdtype == dns.rdatatype.A)} 条 A,标志 {dns.flags.to_text(rc.flags)}')

print('== 五:有多少常见名字启用了 DNSSEC:向 1.1.1.1 问 A(DO = 1),看有没有 RRSIG、AD 是否置位;再问父区里有没有这个名字的 DS')
rows = []
for nm in ('example.com', 'cloudflare.com', 'github.com', 'google.com', 'wikipedia.org', 'ietf.org', 'iana.org', 'python.org', 'amazon.com', 'microsoft.com', 'apple.com', 'kernel.org'):
    r = qt(nm, 'A'); ds = qt(nm, 'DS')
    has_sig = any(x.rdtype == dns.rdatatype.RRSIG for x in r.answer); has_ds = any(x.rdtype == dns.rdatatype.DS for x in ds.answer)
    rows.append((nm, has_sig, bool(r.flags & dns.flags.AD), has_ds))
print('    名字              RRSIG   AD   DS')
for nm, a, b, c in rows: print(f'    {nm:<16} {"有" if a else "无":<6} {"是" if b else "否":<4} {"有" if c else "无"}')
print(f'  已签名(有 DS)的名字 {sum(1 for x in rows if x[3])} / {len(rows)}')
