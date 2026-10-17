import sys, os, re, struct, threading, statistics, errno, ssl, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
from cryptography import x509
from cryptography.x509.oid import ExtensionOID, NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding
tee('w91'); reset()
HOST = 'example.com'; IP = '104.20.23.154'
def chain_of(host=HOST, ip=IP):
    ctx = ssl.create_default_context(); s = socket.create_connection((ip, 443), timeout=8); ss = ctx.wrap_socket(s, server_hostname=host)
    ch = [x509.load_der_x509_certificate(c.public_bytes(ssl._ssl.ENCODING_DER) if hasattr(c, 'public_bytes') else c) for c in ss.get_verified_chain()]
    info = (ss.version(), ss.cipher()[0]); ss.close(); return ch, info
def name_str(n): return ', '.join(f'{a.rfc4514_attribute_name}={a.value}' for a in n)
def keyinfo(pk):
    if isinstance(pk, ec.EllipticCurvePublicKey): return f'EC {pk.curve.name}'
    if isinstance(pk, rsa.RSAPublicKey): return f'RSA {pk.key_size} 位'
    return type(pk).__name__
def now(): return datetime.datetime.now(datetime.UTC)

print('== 一:服务器给的证书链:example.com 在握手里发来了几张证书?每一张的主体、签发者、公钥类型、有效期、大小')
ch, info = chain_of()
print(f'  {info[0]},{info[1]};ssl.get_verified_chain() 返回 {len(ch)} 张证书(从叶子到根方向)')
for i, c in enumerate(ch):
    nb, na = c.not_valid_before_utc, c.not_valid_after_utc
    print(f'  [{i}] 主体 {name_str(c.subject)}')
    print(f'      签发者 {name_str(c.issuer)};公钥 {keyinfo(c.public_key())};签名算法 {c.signature_algorithm_oid._name};DER {len(c.public_bytes(serialization.Encoding.DER))} 字节')
    print(f'      有效期 {nb:%Y-%m-%d} ~ {na:%Y-%m-%d}(共 {(na - nb).days} 天;现在起还剩 {(na - now()).days} 天);序列号 {hex(c.serial_number)[:20]}…')
print(f'  整条链 DER 总计 {sum(len(c.public_bytes(serialization.Encoding.DER)) for c in ch)} 字节(这是握手时服务器要发的证书数据的量级)')

print('== 二:叶子证书里的扩展——真正决定证书能做什么的是这些')
leaf = ch[0]
for ext in leaf.extensions:
    nm = ext.oid._name; v = ext.value
    if isinstance(v, x509.SubjectAlternativeName): d = f'{len(v)} 个名字:{[str(x.value) for x in v][:6]}'
    elif isinstance(v, x509.BasicConstraints): d = f'CA = {v.ca}'
    elif isinstance(v, x509.KeyUsage): d = f'digital_signature={v.digital_signature},key_encipherment={v.key_encipherment}'
    elif isinstance(v, x509.ExtendedKeyUsage): d = [o._name for o in v]
    elif isinstance(v, x509.AuthorityInformationAccess): d = [(x.access_method._name, x.access_location.value) for x in v]
    elif isinstance(v, x509.CRLDistributionPoints): d = [str(p.full_name[0].value) for p in v]
    elif hasattr(v, '__len__'): d = f'{len(v)} 项'
    else: d = type(v).__name__
    print(f'  {nm:<26} critical={ext.critical}  {d}')

print('== 三:验证链:每一张证书的签名都要用上一级(签发者)的公钥验证;最后一张要么是已信任的根,要么由系统信任库里的某个根签发')
def verify_sig(child, parent):
    pk = parent.public_key()
    try:
        if isinstance(pk, ec.EllipticCurvePublicKey): pk.verify(child.signature, child.tbs_certificate_bytes, ec.ECDSA(child.signature_hash_algorithm))
        else: pk.verify(child.signature, child.tbs_certificate_bytes, padding.PKCS1v15(), child.signature_hash_algorithm)
        return True
    except Exception as e: return f'失败 {type(e).__name__}'
for i in range(len(ch) - 1): print(f'  [{i}] 用 [{i + 1}] 的公钥验证签名:{verify_sig(ch[i], ch[i + 1])}')
last = ch[-1]; print(f'  链的最后一张 [{len(ch) - 1}]:主体 == 签发者?{last.subject == last.issuer}(= 自签名根)')
ctx = ssl.create_default_context(); store = [x509.load_der_x509_certificate(ssl.PEM_cert_to_DER_cert(ssl.DER_cert_to_PEM_cert(c['_der'])) if False else c) for c in []]
roots = ctx.get_ca_certs(binary_form=True); rootc = [x509.load_der_x509_certificate(r) for r in roots]
print(f'  本机 Python 的信任库里有 {len(rootc)} 张根 / 受信 CA 证书')
match = [r for r in rootc if r.subject == last.issuer]
print(f'  链的最后一张的签发者 "{name_str(last.issuer)}" 在信任库里:{"找到 %d 张同名的" % len(match) if match else "没找到"};' + (f'用它验证最后一张的签名:{verify_sig(last, match[0])}' if match else ''))
print(f'  信任库里 EC 根 {sum(1 for r in rootc if isinstance(r.public_key(), ec.EllipticCurvePublicKey))} 张,RSA 根 {sum(1 for r in rootc if isinstance(r.public_key(), rsa.RSAPublicKey))} 张;最早到期的 {min(r.not_valid_after_utc for r in rootc):%Y-%m-%d},最晚到期的 {max(r.not_valid_after_utc for r in rootc):%Y-%m-%d}')

print('== 四:各种验证失败(badssl.com 提供专门配置错误的测试站):看 Python 报的错误码和原因')
for h, why in (('expired.badssl.com', '证书过期'), ('wrong.host.badssl.com', '证书是给别的主机名签的'), ('self-signed.badssl.com', '自签名证书'), ('untrusted-root.badssl.com', '根不在信任库里'), ('revoked.badssl.com', '证书已被吊销')):
    try:
        s = socket.create_connection((h, 443), timeout=6)
        try: ss = ssl.create_default_context().wrap_socket(s, server_hostname=h); r = f'握手成功({ss.version()})——没有报错'; ss.close()
        except ssl.SSLCertVerificationError as e: r = f'验证失败 错误码 {e.verify_code}:{e.verify_message}'
        except Exception as e: r = f'握手失败 {type(e).__name__}(服务器或网络直接断开)'
    except Exception as e: r = f'连不上 {type(e).__name__}'
    print(f'  {h:<28}({why}):{r}')
print('  注意 revoked.badssl.com:证书其实已被吊销,Python 的默认设置却让握手成功——默认不检查吊销(CRL / OCSP),这是常见的盲区')

print('== 五:SNI 决定服务器给哪张证书,主机名验证再决定客户端认不认:同一个 IP(104.20.23.154)上,换不同的 SNI(同时也是验证名),看服务器给的证书里写了哪些名字、默认验证是否通过')
def probe(sni, verify=True):
    ctx = ssl.create_default_context()
    if not verify: ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    s = socket.create_connection((IP, 443), timeout=8)
    try:
        ss = ctx.wrap_socket(s, server_hostname=sni)
        der = ss.getpeercert(binary_form=True); c = x509.load_der_x509_certificate(der); san = [str(v.value) for v in c.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value]; ss.close(); return san, None
    except ssl.SSLCertVerificationError as e: return None, f'验证失败:{e.verify_message}'
    except Exception as e: return None, f'握手失败:{type(e).__name__} {str(e)[:60]}'
for sni in ('example.com', 'www.example.com', 'example.org', 'totally-wrong.invalid'):
    san, err = probe(sni, True); san2, err2 = probe(sni, False)
    print(f'  SNI = {sni:<22}→ 默认验证:{"通过" if san else err};不验证时服务器给的证书 SAN:{san2 if san2 else err2}')
ctx = ssl.create_default_context(); s = socket.create_connection((IP, 443), timeout=8)
try:
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE; ss = ctx.wrap_socket(s); c = x509.load_der_x509_certificate(ss.getpeercert(binary_form=True)); print(f'  完全不发 SNI 时服务器给的证书 SAN:{[str(v.value) for v in c.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value]}'); ss.close()
except Exception as e: print(f'  完全不发 SNI:握手失败 {type(e).__name__} {str(e)[:60]}')
print('  验证由两部分组成:(1)证书链到受信任的根;(2)证书的 SAN 里有我要连的名字(通配符 *.example.com 匹配 www.example.com)。关掉第二项(check_hostname=False)只会得到“链是好的”,而不知道是不是对的站点')
