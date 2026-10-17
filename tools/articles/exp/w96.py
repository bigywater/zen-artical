import sys, os, re, struct, threading, statistics, errno, base64, hashlib, logging, io; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
import paramiko
tee('w96'); reset()
def fp(key): return 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
class Srv(paramiko.ServerInterface):
    def __init__(self, good): self.good = good
    def get_allowed_auths(self, username): return 'publickey,password'
    def check_auth_password(self, username, password): return paramiko.AUTH_SUCCESSFUL if password == 'secret' else paramiko.AUTH_FAILED
    def check_auth_publickey(self, username, key): return paramiko.AUTH_SUCCESSFUL if key == self.good else paramiko.AUTH_FAILED
    def check_channel_request(self, kind, chanid): return paramiko.OPEN_SUCCEEDED
def serve(port, hostkey, good, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(8); ls.settimeout(0.3)
    def h(c):
        try:
            t = paramiko.Transport(c); t.add_server_key(hostkey); t.start_server(server=Srv(good)); time.sleep(1.5)
        except Exception: pass
        finally:
            try: t.close()
            except Exception: pass
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
def read_packet(s, buf):
    while len(buf) < 5:
        d = s.recv(65536)
        if not d: return None, buf
        buf += d
    n = struct.unpack('>I', buf[:4])[0]
    while len(buf) < 4 + n:
        d = s.recv(65536)
        if not d: return None, buf
        buf += d
    pl = buf[5:4 + n - buf[4]]; return pl, buf[4 + n:]
def namelists(pl):
    i = 17; out = []
    for _ in range(10):
        n = struct.unpack('>I', pl[i:i + 4])[0]; out.append(pl[i + 4:i + 4 + n].decode().split(',') if n else []); i += 4 + n
    return out
LN = ['kex_algorithms', 'server_host_key_algorithms', 'encryption c→s', 'encryption s→c', 'mac c→s', 'mac s→c', 'compression c→s', 'compression s→c', 'languages c→s', 'languages s→c']
def raw_kexinit(host, port):
    s = socket.create_connection((host, port), timeout=8); s.settimeout(8); b = b''
    while b'\n' not in b: b += s.recv(256)
    banner, rest = b.split(b'\n', 1); s.sendall(b'SSH-2.0-w96probe\r\n')
    pl, rest = read_packet(s, rest); s.close(); return banner.decode().strip(), pl

print('== 一:SSH 的第一件事:双方各发一行明文版本串。本机 paramiko 服务器、github.com:22、gitlab.com:22(只读到 KEXINIT 就断开,不做认证)')
hk = paramiko.ECDSAKey.generate(bits=256); good = paramiko.ECDSAKey.generate(bits=256); port = lab_port(); stop = [False]; serve(port, hk, good, stop)
res = {}
for nm, (h, p) in (('本机 paramiko 服务器', ('127.0.0.1', port)), ('github.com', ('github.com', 22)), ('gitlab.com', ('gitlab.com', 22))):
    try: banner, pl = raw_kexinit(h, p); res[nm] = (banner, pl)
    except Exception as e: res[nm] = (None, None); print(f'  {nm}:失败 {type(e).__name__}')
for nm, (banner, pl) in res.items():
    if banner: print(f'  {nm}:版本串 {banner!r}(格式 SSH-协议版本-软件版本 [注释];协议版本 2.0)')

print('== 二:KEXINIT 报文:紧接着双方各发一个 KEXINIT,里面是各自支持的算法清单(10 个名字列表)。逐个看 github.com 与本机 paramiko 服务器给了哪些')
for nm, (banner, pl) in res.items():
    if not pl: continue
    L = namelists(pl); print(f'  {nm}:消息类型 {pl[0]}(20 = SSH_MSG_KEXINIT),cookie {pl[1:17].hex()[:16]}…(16 字节随机数)')
    for name, lst in zip(LN, L):
        if name.startswith('languages'): continue
        print(f'    {name:<28} {len(lst):>2} 个:{", ".join(lst[:5])}{" …" if len(lst) > 5 else ""}')

print('== 三:完整握手:paramiko 客户端连本机服务器,打开调试日志,看双方最后“商定”的算法。服务器端的偏好顺序决定结果')
buf = io.StringIO(); lg = logging.getLogger('paramiko.transport'); lg.setLevel(logging.DEBUG); hd = logging.StreamHandler(buf); lg.addHandler(hd)
t = paramiko.Transport(('127.0.0.1', port)); t0 = time.time(); t.start_client(timeout=10); dt = (time.time() - t0) * 1000
lg.removeHandler(hd)
print(f'  密钥交换完成用时 {dt:.1f} ms;服务器版本串 {t.remote_version!r};商定:加密 {t.local_cipher},MAC {t.local_mac},压缩 {t.local_compression};kex 引擎 {type(t.kex_engine).__name__ if t.kex_engine else None}')
for l in buf.getvalue().splitlines():
    if re.search(r'kex algos|Kex agreed|HostKey agreed|Cipher agreed|MAC agreed|Compression agreed|Switch to new keys', l): print('    ' + re.sub(r'^.*?(kex algos|Kex agreed|HostKey agreed|Cipher agreed|MAC agreed|Compression agreed|Switch to new keys)', r'\1', l)[:200])
hkr = t.get_remote_server_key(); print(f'  服务器主机密钥:类型 {hkr.get_name()},指纹 {fp(hkr)}(客户端要拿这个指纹去和已知的比较)')

print('== 四:认证:商定密钥之后才开始认证(此时通道已经加密)。先问服务器接受哪些认证方式,再分别试:错误的密码、正确的密码、错误的密钥、正确的密钥')
try: t.auth_none('alice')
except paramiko.BadAuthenticationType as e: print(f'  auth_none 的回答:服务器接受的方式 {e.allowed_types}')
for nm, f in (('错误的密码', lambda: t.auth_password('alice', 'wrong')), ('正确的密码', lambda: t.auth_password('alice', 'secret'))):
    try: r = f(); print(f'  {nm}:成功,仍需的方式 {r};已认证 {t.is_authenticated()}')
    except paramiko.AuthenticationException as e: print(f'  {nm}:失败 {type(e).__name__}')
t.close()
t2 = paramiko.Transport(('127.0.0.1', port)); t2.start_client(timeout=10)
other = paramiko.ECDSAKey.generate(bits=256)
for nm, k in (('错误的密钥', other), ('正确的密钥', good)):
    try: r = t2.auth_publickey('alice', k); print(f'  {nm}({fp(k)[:24]}…):成功;已认证 {t2.is_authenticated()}')
    except paramiko.AuthenticationException as e: print(f'  {nm}({fp(k)[:24]}…):失败 {type(e).__name__}')
t2.close()

print('== 五:主机密钥与首次信任(TOFU):客户端第一次连一台服务器,记下它的主机密钥指纹;之后同一个地址如果换了主机密钥(服务器重装或被冒充),客户端应该报警')
known = {}
def connect_check(label, p):
    tt = paramiko.Transport(('127.0.0.1', p)); tt.start_client(timeout=10); k = tt.get_remote_server_key(); f = fp(k); tt.close()
    if 'srv' not in known: known['srv'] = f; return f'第一次连接:记下指纹 {f[:30]}…(首次信任)'
    return ('指纹与记录的一致,继续' if known['srv'] == f else f'⚠ 指纹变了!记录的 {known["srv"][:24]}…,现在是 {f[:24]}…——客户端应该拒绝(OpenSSH 会显示 REMOTE HOST IDENTIFICATION HAS CHANGED)')
print('  ' + connect_check('第一次', port))
print('  ' + connect_check('第二次(同一个服务器)', port))
stop[0] = True; time.sleep(0.5)
hk2 = paramiko.ECDSAKey.generate(bits=256); port2 = lab_port(); stop2 = [False]; serve(port2, hk2, good, stop2)
print('  换一台新的服务器(新的主机密钥)占用同一个“地址”后:' + connect_check('换了密钥', port2)); stop2[0] = True

print('== 六:握手要几个往返?本机服务器,netlab 每方向 50 ms(往返 100 ms):从 TCP 连上到认证成功的总用时')
hk3 = paramiko.ECDSAKey.generate(bits=256); port3 = lab_port(); stop3 = [False]; serve(port3, hk3, good, stop3); ts = []
with lossy(loss=0, delay=50, bw=0):
    for i in range(4):
        t0 = time.time(); s = socket.create_connection(('127.0.0.1', port3)); t1 = time.time(); tt = paramiko.Transport(s); tt.start_client(timeout=10); t2_ = time.time(); tt.auth_password('alice', 'secret'); t3 = time.time(); tt.close()
        ts.append(((t1 - t0) * 1000, (t2_ - t1) * 1000, (t3 - t2_) * 1000))
stop3[0] = True
print('    TCP 握手(ms)  版本交换 + 密钥交换(ms)  认证(ms)   合计(ms)   (每行一次)')
for a, b, c in ts: print(f'    {a:9.0f}   {b:18.0f}         {c:7.0f}   {a + b + c:7.0f}')
m = [statistics.median(x[i] for x in ts) for i in range(3)]
print(f'  中位数:TCP {m[0]:.0f} ms(1 个往返)、版本 + 密钥交换 {m[1]:.0f} ms(≈ {m[1] / 100:.1f} 个往返)、认证 {m[2]:.0f} ms(≈ {m[2] / 100:.1f} 个往返);合计 {sum(m):.0f} ms ≈ {sum(m) / 100:.1f} 个往返')
