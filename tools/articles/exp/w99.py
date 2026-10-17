import sys, os, re, struct, threading, statistics, errno, ftplib, tempfile, logging; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import ThreadedFTPServer
import dpkt
tee('w99'); reset()
logging.getLogger('pyftpdlib').setLevel(logging.CRITICAL)
root = tempfile.mkdtemp(prefix='w99ftp'); os.makedirs(root + '/pub')
for i in range(10): open(f'{root}/pub/f{i}.txt', 'wb').write((f'file {i}\n' * 100).encode())
open(root + '/pub/big.bin', 'wb').write(os.urandom(200000))
auth = DummyAuthorizer(); auth.add_user('alice', 'pa55w0rd', root, perm='elr')
port = lab_port()
class H(FTPHandler):
    authorizer = auth; passive_ports = range(9460, 9490); banner = 'w99 test ftp ready'
srv = ThreadedFTPServer(('127.0.0.1', port), H); threading.Thread(target=srv.serve_forever, kwargs={'timeout': 0.5, 'handle_exit': False}, daemon=True).start(); time.sleep(0.5)
def ctl(cmds, port=port, tmo=5):
    s = socket.create_connection(('127.0.0.1', port), timeout=tmo); s.settimeout(tmo); out = []
    def rd():
        buf = b''
        while True:
            d = s.recv(4096)
            if not d: break
            buf += d
            lines = buf.split(b'\r\n')
            if lines[-1] == b'' and len(lines) >= 2 and len(lines[-2]) >= 4 and lines[-2][3:4] == b' ': break
        return buf.decode(errors='replace').rstrip('\r\n').split('\r\n')
    for l in rd(): out.append(('S', l))
    data_sock = None
    for c in cmds:
        if callable(c): c(s, out); continue
        s.sendall((c + '\r\n').encode()); out.append(('C', c.replace('pa55w0rd', '********') if False else c))
        for l in rd(): out.append(('S', l))
    s.close(); return out
def show(tr, skip=()):
    for who, l in tr:
        if any(x in l for x in skip): continue
        print(f'    {who}: {l[:120]}')

print('== 一:FTP 的控制连接(端口 ' + str(port) + '):纯文本命令与三位数字的答复,和 SMTP 很像。登录、看系统、看特性、切换目录')
tr = ctl(['USER alice', 'PASS pa55w0rd', 'SYST', 'FEAT', 'PWD', 'CWD pub', 'PWD', 'TYPE I', 'SIZE f0.txt', 'QUIT'])
show(tr)
print('  注意 PASS 命令把密码 pa55w0rd 明文写在控制连接上(下面第四节抓包验证);FEAT 的多行答复用 “211-” 开头、“211 ” 结尾,和 SMTP 的 250- 一样')

print('== 二:被动模式(PASV):文件内容和目录列表不走控制连接,要另开一条数据连接。PASV 命令让服务器报告它在哪个端口等待;客户端再去连这个端口')
def pasv_list(s, out):
    s.sendall(b'PASV\r\n'); out.append(('C', 'PASV')); r = s.recv(200).decode().strip(); out.append(('S', r))
    m = re.search(r'\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)', r); p = int(m.group(5)) * 256 + int(m.group(6)); out.append(('*', f'227 里的 (127,0,0,1,{m.group(5)},{m.group(6)}) → 端口 = {m.group(5)} × 256 + {m.group(6)} = {p}'))
    d = socket.create_connection(('127.0.0.1', p), timeout=5); out.append(('*', f'客户端另开一条 TCP 连接 127.0.0.1:{d.getpeername()[1]} → 127.0.0.1:{p}(数据连接)'))
    s.sendall(b'LIST\r\n'); out.append(('C', 'LIST')); out.append(('S', s.recv(200).decode().strip().replace('\r\n', ' | ')))
    buf = b''
    while True:
        x = d.recv(4096)
        if not x: break
        buf += x
    d.close(); out.append(('*', f'数据连接上收到 {len(buf)} 字节(目录列表),服务器发完就关闭这条连接:{buf.decode(errors="replace").splitlines()[0][:70]!r} …')); out.append(('S', s.recv(200).decode().strip()))
tr = ctl(['USER alice', 'PASS pa55w0rd', 'CWD pub', 'TYPE I', pasv_list, 'QUIT'])
show([x for x in tr if x[1][:3] not in ('220',)] if False else tr[4:])

print('== 三:EPSV(扩展被动模式,同时支持 IPv6)和主动模式(PORT):主动模式是服务器反过来连客户端,穿过 NAT / 防火墙时常出问题')
def epsv(s, out):
    s.sendall(b'EPSV\r\n'); out.append(('C', 'EPSV')); out.append(('S', s.recv(200).decode().strip()))
tr = ctl(['USER alice', 'PASS pa55w0rd', epsv, 'QUIT']); show(tr[-4:])
# 主动模式:客户端监听,PORT 告诉服务器地址,服务器来连
with Cap(f'tcp portrange 9400-9499 and not port {port}', iface='lo0', write=True, snaplen=96) as c:
    ls = socket.socket(); ls.bind(('127.0.0.1', 0)); ls.listen(1); lp = ls.getsockname()[1]
    s = socket.create_connection(('127.0.0.1', port), timeout=5); s.settimeout(5); s.recv(200); s.sendall(b'USER alice\r\n'); s.recv(200); s.sendall(b'PASS pa55w0rd\r\n'); s.recv(200); s.sendall(b'CWD pub\r\n'); s.recv(200)
    h = lp // 256; l_ = lp % 256; s.sendall(f'PORT 127,0,0,1,{h},{l_}\r\n'.encode()); r1 = s.recv(200).decode().strip()
    s.sendall(b'LIST\r\n'); ls.settimeout(5); dc, addr = ls.accept(); r2 = s.recv(200).decode().strip(); buf = b''
    while True:
        x = dc.recv(4096)
        if not x: break
        buf += x
    dc.close(); time.sleep(0.2); s.sendall(b'QUIT\r\n'); s.close(); ls.close(); time.sleep(0.4)
print(f'  PORT 127,0,0,1,{h},{l_}(= 端口 {h} × 256 + {l_} = {lp})→ 服务器答复 {r1!r};随后 LIST 时,**服务器**主动连客户端的 {lp} 端口:数据连接的服务器一侧端口是 {addr[1]},方向与被动模式相反;收到 {len(buf)} 字节的目录列表,控制连接答复 {r2.splitlines()[0]!r}')
print('  被动模式里数据连接由客户端发起(穿 NAT 友好);主动模式由服务器发起,客户端在 NAT 后面就收不到——这是 FTP 在现代网络里首选被动模式的原因')

print('== 四:抓包看安全性:控制连接上用户名、密码、文件名都是明文')
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=0) as c:
    ctl(['USER alice', 'PASS pa55w0rd', 'CWD pub', 'RETR f0.txt', 'QUIT'], tmo=3); time.sleep(0.4)
pl = b''
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        ip = bytes(buf[4:]); ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; tt = ip[ihl:]; off = (tt[12] >> 4) * 4; pl += tt[off:tl_ - ihl]
print(f'  控制连接的全部字节({len(pl)} 字节)里能直接读到:' + '; '.join(l.decode(errors='replace') for l in pl.split(b'\r\n') if l.startswith((b'USER', b'PASS', b'CWD', b'RETR'))))
print('  所以 FTP 的密码在路径上任何一个能抓包的地方都能被读走;FTPS(FTP over TLS)和 SFTP(基于 SSH,不是 FTP)是后来补的')

print('== 五:代价:每个文件都要一条新的数据连接。lo0 上 netlab 每方向 50 ms(往返 100 ms),被动模式取 10 个小文件(每个约 800 字节)+ 一次 200000 字节的大文件,对比总耗时')
def ftp_run(nfiles):
    t0 = time.time(); f = ftplib.FTP(); f.connect('127.0.0.1', port, timeout=10); f.login('alice', 'pa55w0rd'); f.cwd('pub'); f.voidcmd('TYPE I'); t_login = time.time() - t0; t1 = time.time()
    for i in range(nfiles): f.retrbinary(f'RETR f{i}.txt', lambda b: None)
    t2 = time.time(); f.quit(); return t_login, t2 - t1
with lossy(loss=0, delay=50, bw=0):
    rs = [ftp_run(10) for _ in range(2)]
    f = ftplib.FTP(); f.connect('127.0.0.1', port, timeout=10); f.login('alice', 'pa55w0rd'); f.cwd('pub'); f.voidcmd('TYPE I'); t1 = time.time(); n = [0]; f.retrbinary('RETR big.bin', lambda b: n.__setitem__(0, n[0] + len(b))); tb = time.time() - t1; f.quit()
tl_ = statistics.median(r[0] for r in rs); tf = statistics.median(r[1] for r in rs)
print(f'  登录(TCP 握手 + 220 + USER + PASS + CWD + TYPE)中位 {tl_ * 1000:.0f} ms ≈ {tl_ / 0.1:.1f} 个往返;取 10 个小文件 中位 {tf * 1000:.0f} ms,平均每个 {tf * 100:.0f} ms ≈ {tf / 10 / 0.1:.1f} 个往返(PASV 1 个、连数据端口 1 个、RETR 1 个,外加传输收尾)')
print(f'  取一个 {n[0]} 字节的大文件:{tb * 1000:.0f} ms')
print(f'  对比 HTTP/1.1 keep-alive:取一个小文件只要 1 个往返;FTP 小文件每个要约 {tf / 10 / 0.1:.0f} 个往返,所以 FTP 不适合大量小文件')
srv.close_all()
