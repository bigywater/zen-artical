import sys, os, re, struct, threading, statistics, errno, ssl, datetime, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP as SMTPProto
import dpkt
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
tee('w98'); reset()
key = ec.generate_private_key(ec.SECP256R1()); nm = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
cert = x509.CertificateBuilder().subject_name(nm).issuer_name(nm).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=2)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), False).sign(key, hashes.SHA256())
CF, KF = str(WT / 'w98_c.pem'), str(WT / 'w98_k.pem'); open(CF, 'wb').write(cert.public_bytes(serialization.Encoding.PEM)); open(KF, 'wb').write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); sctx.load_cert_chain(CF, KF)
got = []
class H:
    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if address.startswith('blocked@'): return '550 5.7.1 Relaying denied'
        if address.startswith('later@'): return '450 4.2.0 Greylisted, try again later'
        envelope.rcpt_tos.append(address); return '250 OK'
    async def handle_DATA(self, server, session, envelope):
        got.append((envelope.mail_from, list(envelope.rcpt_tos), envelope.content.decode('utf8', 'replace'))); return '250 OK: queued as w98-1'
port = lab_port()
ctl = Controller(H(), hostname='127.0.0.1', port=port, tls_context=sctx, require_starttls=False, server_hostname='mail.w98.test', data_size_limit=2000); ctl.start(); time.sleep(0.5)
def readreply_s(s):
    buf = b''
    while True:
        d = s.recv(4096)
        if not d: break
        buf += d
        lines = buf.split(b'\r\n')
        if len(lines) >= 2 and lines[-1] == b'' and all(len(l) >= 4 for l in lines[:-1]) and lines[-2][3:4] == b' ': break
    return buf.decode('utf8', 'replace').rstrip('\r\n').split('\r\n')
def dialogue(cmds, port=port, show_banner=True, tmo=5):
    s = socket.create_connection(('127.0.0.1', port), timeout=tmo); s.settimeout(tmo); out = []
    def readreply():
        buf = b''
        while True:
            d = s.recv(4096)
            if not d: break
            buf += d
            lines = buf.split(b'\r\n')
            if len(lines) >= 2 and lines[-1] == b'' and all(len(l) >= 4 for l in lines[:-1]) and lines[-2][3:4] == b' ': break
        return buf.decode('utf8', 'replace').rstrip('\r\n').split('\r\n')
    if show_banner:
        for l in readreply(): out.append(('S', l))
    for c in cmds:
        if isinstance(c, tuple): raw = c[1]; label = c[0]
        else: raw = (c + '\r\n').encode(); label = c
        s.sendall(raw)
        for ln in label.split('\r\n') if isinstance(c, tuple) else [label]: out.append(('C', ln))
        for l in readreply(): out.append(('S', l))
    s.close(); return out
def show(tr):
    for who, l in tr: print(f'    {"C: " if who == "C" else "S: "}{l[:110]}')

print('== 一:一次完整的 SMTP 对话(明文,本机 aiosmtpd 服务器,逐行):服务器先发 220 问候,客户端 EHLO,MAIL FROM / RCPT TO 给出“信封”,DATA 发“信件”(以 CRLF.CRLF 结束),QUIT。每个答复前三位是状态码')
msg = ('From: "Alice" <alice@example.org>\r\nTo: bob@w98.test\r\nSubject: hello\r\nDate: Thu, 15 Oct 2026 12:00:00 +0000\r\n\r\nFirst line.\r\n.dot-line\r\nLast line.').encode()
stuffed = msg.replace(b'\r\n.', b'\r\n..') + b'\r\n.\r\n'
tr = dialogue(['EHLO client.w98.test', 'MAIL FROM:<envelope-sender@w98.test>', 'RCPT TO:<bob@w98.test>', 'RCPT TO:<hidden-bcc@w98.test>', 'DATA', ('<信件(带点开头的行已转义)>', stuffed), 'QUIT'])
show(tr)
print(f'  EHLO 的多行答复:前面各行用 “250-”,最后一行用 “250 ”(横线表示后面还有,空格表示最后一行);列出的扩展有 {[l[4:].split()[0] for who, l in tr[2:8] if who == "S" and l[:3] == "250" and l[3] in "- "]}')
time.sleep(0.3); mf, rt, ct = got[-1]
print(f'  服务器收到的信封:MAIL FROM = {mf!r},RCPT TO = {rt}——信封里有 hidden-bcc@w98.test,但信件头里的 To 只写了 bob@w98.test(这就是 Bcc 的实现原理:信封收件人 ≠ 信件头里的收件人)')
print(f'  信件头里的 From = {re.search(r"From: (.*)", ct).group(1).strip()!r},与信封的 MAIL FROM {mf!r} 完全不同:SMTP 不核对两者,这是伪造发件人的基础')
print(f'  点转义:我发出的正文里有一行以点开头 ".dot-line",在线上写成 "..dot-line"(上面 C: 行里显示的是转义前的说明;实际字节见下);服务器还原后收到的正文里这一行是 {[l.strip() for l in ct.split(chr(10)) if "dot-line" in l]}')
print(f'  线上字节(转义后正文的一部分):{stuffed[stuffed.find(b"First"):stuffed.find(b"Last") + 5]!r}')

print('== 二:错误答复与重试:状态码第一位分类——2 成功、3 继续、4 临时失败(稍后重试)、5 永久失败(别再试了)。本机服务器对特定收件人故意返回不同的码')
tr = dialogue(['EHLO client.w98.test', 'MAIL FROM:<a@w98.test>', 'RCPT TO:<blocked@w98.test>', 'RCPT TO:<later@w98.test>', 'RCPT TO:<ok@w98.test>', 'FOOBAR', 'RSET', 'DATA', 'QUIT'])
show([x for x in tr if not (x[0] == 'S' and x[1].startswith('250-'))])
print('  550 永久失败:发送方的邮件系统应该退信;450 临时失败(灰名单):应该稍后重试;500 未知命令;503 命令顺序不对(这里 RSET 之后还没有 MAIL FROM 就 DATA)')

print('== 三:SIZE 限制:服务器宣告 SIZE(最大 2000 字节)。声明过大的邮件在 MAIL FROM 阶段就被拒绝;不声明而直接发过大的正文,会在 DATA 结束后才拒绝')
tr = dialogue(['EHLO client.w98.test', 'MAIL FROM:<a@w98.test> SIZE=5000'], tmo=4); show([x for x in tr if x[0] == 'C' or 'SIZE' in x[1] or x[1].startswith('552')])
big = (b'Subject: big\r\n\r\n' + (b'x' * 98 + b'\r\n') * 30 + b'.\r\n'); tr = dialogue(['EHLO client.w98.test', 'MAIL FROM:<a@w98.test>', 'RCPT TO:<ok@w98.test>', 'DATA', ('<约 3000 字节正文,每行 98 字节>', big), 'QUIT']); show(tr[-4:])

print('== 四:STARTTLS:先明文说 EHLO,服务器宣告 STARTTLS;客户端发 STARTTLS、服务器回 220 之后,同一个 TCP 连接升级成 TLS,再重新 EHLO。抓 lo0 看升级前的明文和升级后的密文')
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=0) as c:
    s = socket.create_connection(('127.0.0.1', port), timeout=5); s.settimeout(5); readreply_s(s); s.sendall(b'EHLO client.w98.test\r\n'); e1 = '\n'.join(readreply_s(s)); s.sendall(b'STARTTLS\r\n'); st = '\n'.join(readreply_s(s)).strip()
    cc = ssl.create_default_context(); cc.check_hostname = False; cc.verify_mode = ssl.CERT_NONE; ss = cc.wrap_socket(s, server_hostname='localhost'); ss.sendall(b'EHLO client.w98.test\r\n'); e2 = readreply_s(ss); e2 = '\n'.join(e2)
    ss.sendall(b'MAIL FROM:<secret-sender@w98.test>\r\n'); readreply_s(ss); ss.sendall(b'QUIT\r\n'); readreply_s(ss); ss.close(); time.sleep(0.4)
print(f'  升级前 EHLO 答复里有 STARTTLS:{"STARTTLS" in e1};STARTTLS 命令的答复:{st};升级后再次 EHLO 的答复里还有 STARTTLS:{"STARTTLS" in e2}(已经加密就不再宣告)')
pl = b''
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        ip = bytes(buf[4:]); ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; tt = ip[ihl:]; off = (tt[12] >> 4) * 4; pl += tt[off:tl_ - ihl]
print(f'  整个连接的字节里:能找到明文 "EHLO client.w98.test" 吗?{"能(升级前的那一次)" if b"EHLO client.w98.test" in pl else "不能"};能找到明文 "STARTTLS" 命令吗?{"能" if b"STARTTLS" in pl else "不能"};能找到升级后才发的 "secret-sender@w98.test" 吗?{"能" if b"secret-sender" in pl else "找不到(已加密)"}')
print('  注意 STARTTLS 的弱点:升级前一切是明文,路径上的设备可以把 “250 STARTTLS” 从 EHLO 答复里删掉(降级攻击),发送方若是“尽量用 TLS”策略就会继续明文')

print('== 五:真实的邮件服务器(只做问候和 EHLO,不发信):gmail-smtp-in.l.google.com、mx1.qq.com、smtp.163.com 的 25 端口')
for host in ('gmail-smtp-in.l.google.com', 'mx1.qq.com', 'smtp.163.com'):
    try:
        t0 = time.time(); s = socket.create_connection((host, 25), timeout=8); s.settimeout(6); ban = s.recv(300).decode(errors='replace').strip(); tb = (time.time() - t0) * 1000
        s.sendall(b'EHLO w98.test\r\n'); time.sleep(0.8); e = s.recv(4000).decode(errors='replace'); s.sendall(b'QUIT\r\n'); s.close()
        exts = [l[4:].split()[0] for l in e.split('\r\n') if l[:3] == '250' and len(l) > 4][1:]
        print(f'  {host}:问候 {ban[:60]!r}({tb:.0f} ms);EHLO 扩展 {exts}')
    except Exception as ex: print(f'  {host}:失败 {type(ex).__name__}')
ctl.stop()
