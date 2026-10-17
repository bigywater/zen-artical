import sys, time, os, json, subprocess, ssl, socket, pathlib, re, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r127'); R = {}
D = RDATA / 's127'; shutil.rmtree(D, ignore_errors=True); D.mkdir(parents=True)
def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=D, **kw); return r
def ossl(*a): r = run(['openssl', *a]); assert r.returncode == 0, r.stderr; return r
# 证书:CA、服务端(SAN=localhost,127.0.0.1)、客户端(CN=svc-app)、另一个不被信任的 CA 签的客户端
ossl('ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', 'ca.key'); ossl('req', '-x509', '-new', '-key', 'ca.key', '-sha256', '-days', '30', '-subj', '/CN=Test Root CA', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-out', 'ca.crt')
ossl('ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', 'server.key'); ossl('req', '-new', '-key', 'server.key', '-subj', '/CN=redis-server', '-out', 'server.csr')
(D / 'san.cnf').write_text('subjectAltName=DNS:localhost,IP:127.0.0.1\n')
ossl('x509', '-req', '-in', 'server.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key', '-CAcreateserial', '-days', '30', '-sha256', '-extfile', 'san.cnf', '-out', 'server.crt')
ossl('ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', 'client.key'); ossl('req', '-new', '-key', 'client.key', '-subj', '/CN=svc-app', '-out', 'client.csr')
ossl('x509', '-req', '-in', 'client.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key', '-CAcreateserial', '-days', '30', '-sha256', '-out', 'client.crt')
ossl('ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', 'rogue-ca.key'); ossl('req', '-x509', '-new', '-key', 'rogue-ca.key', '-sha256', '-days', '30', '-subj', '/CN=Rogue CA', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-out', 'rogue-ca.crt')
ossl('ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', 'rogue.key'); ossl('req', '-new', '-key', 'rogue.key', '-subj', '/CN=svc-app', '-out', 'rogue.csr')
ossl('x509', '-req', '-in', 'rogue.csr', '-CA', 'rogue-ca.crt', '-CAkey', 'rogue-ca.key', '-CAcreateserial', '-days', '30', '-sha256', '-out', 'rogue.crt')
print('== 一:用 openssl 生成一套本地测试证书(不涉及任何真实证书)')
for f in ('ca.crt', 'server.crt', 'client.crt', 'rogue.crt'):
    r = ossl('x509', '-in', f, '-noout', '-subject', '-issuer'); print(f'  {f:<11}', ' | '.join(r.stdout.strip().splitlines()))
print('  server.crt SAN:', re.search(r'DNS:.*', ossl('x509', '-in', 'server.crt', '-noout', '-ext', 'subjectAltName').stdout).group(0))
PP, TP = 9153, 9152
conf = f'''port {PP}
tls-port {TP}
bind 127.0.0.1
dir {D}
save ""
appendonly no
protected-mode no
logfile {D}/redis.log
tls-cert-file {D}/server.crt
tls-key-file {D}/server.key
tls-ca-cert-file {D}/ca.crt
tls-auth-clients no
enable-debug-command yes
'''
(D / 'redis.conf').write_text(conf)
p = subprocess.Popen(['redis-server', str(D / 'redis.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=D)
t0 = time.time()
while time.time() - t0 < 10:
    try: c = C(PP); c.close(); break
    except Exception: time.sleep(0.05)
print()
print('== 二:同一个实例同时开明文口 %d 和 TLS 口 %d;分别用什么客户端连得上' % (PP, TP))
cli = ['redis-cli', '-p', str(TP)]
def rc(args, label):
    r = run(cli + args); o = (r.stdout + r.stderr).strip().replace('\n', ' / ')[:170]; print(f'  {label:<44} → {o}'); return o
R['cli'] = {}
R['cli']['no_tls'] = rc(['PING'], '明文 redis-cli 连 TLS 口')
R['cli']['no_ca'] = rc(['--tls', 'PING'], '--tls 但没给 --cacert')
R['cli']['ca'] = rc(['--tls', '--cacert', 'ca.crt', 'PING'], '--tls --cacert ca.crt')
R['cli']['rogue_ca'] = rc(['--tls', '--cacert', 'rogue-ca.crt', 'PING'], '--tls --cacert(不相关的 CA)')
R['cli']['insecure'] = rc(['--tls', '--insecure', 'PING'], '--tls --insecure(不校验服务端证书)')
r = run(['redis-cli', '-p', str(PP), 'PING']); print(f'  {"明文 redis-cli 连明文口":<44} → {r.stdout.strip()}')
print('  用原始套接字向 TLS 口发明文 PING:', end=' ')
s = socket.create_connection(('127.0.0.1', TP)); s.settimeout(2); s.sendall(b'PING\r\n')
try: d = s.recv(100); print('收到', d[:60])
except Exception as e: print(type(e).__name__, '(没有任何回复,或连接被关)')
s.close()
print()
print('== 三:tls-auth-clients:要求 / 不要求客户端证书')
adm = ['redis-cli', '-p', str(TP), '--tls', '--cacert', 'ca.crt']
R['auth'] = {}
run(adm + ['CONFIG', 'SET', 'tls-auth-clients', 'yes'])
R['auth']['yes_cfg'] = run(['redis-cli', '-p', str(PP), 'CONFIG', 'GET', 'tls-auth-clients']).stdout.split()[-1]
print('  tls-auth-clients =', R['auth']['yes_cfg'])
R['auth']['yes_nocert'] = rc(['--tls', '--cacert', 'ca.crt', 'PING'], 'yes:不带客户端证书')
R['auth']['yes_cert'] = rc(['--tls', '--cacert', 'ca.crt', '--cert', 'client.crt', '--key', 'client.key', 'PING'], 'yes:带受信任 CA 签的客户端证书')
R['auth']['yes_rogue'] = rc(['--tls', '--cacert', 'ca.crt', '--cert', 'rogue.crt', '--key', 'rogue.key', 'PING'], 'yes:带不受信任 CA 签的证书(CN 也叫 svc-app)')
run(['redis-cli', '-p', str(PP), 'CONFIG', 'SET', 'tls-auth-clients', 'optional'])
R['auth']['opt_nocert'] = rc(['--tls', '--cacert', 'ca.crt', 'PING'], 'optional:不带证书')
R['auth']['opt_rogue'] = rc(['--tls', '--cacert', 'ca.crt', '--cert', 'rogue.crt', '--key', 'rogue.key', 'PING'], 'optional:带不受信任的证书')
run(['redis-cli', '-p', str(PP), 'CONFIG', 'SET', 'tls-auth-clients', 'no'])
vr = run(['openssl', 'verify', '-CAfile', 'ca.crt', 'rogue.crt']); print('  openssl verify -CAfile ca.crt rogue.crt →', (vr.stdout + vr.stderr).strip().replace('\n', ' / ')[:140])
print()
print('== 四:协商到的 TLS 版本、套件,以及主机名校验')
ctx = ssl.create_default_context(cafile=str(D / 'ca.crt'))
with socket.create_connection(('127.0.0.1', TP)) as raw:
    with ctx.wrap_socket(raw, server_hostname='localhost') as ss: print('  协议', ss.version(), ' 套件', ss.cipher()[0]); R['ver'] = [ss.version(), ss.cipher()[0]]
try:
    with socket.create_connection(('127.0.0.1', TP)) as raw: ctx.wrap_socket(raw, server_hostname='wrong.example')
    print('  server_hostname=wrong.example → 握手成功(没有校验主机名?)'); R['hostname'] = 'ok'
except ssl.SSLCertVerificationError as e: print('  server_hostname=wrong.example →', str(e)[:110]); R['hostname'] = str(e)[:110]
for v in (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3):
    c2 = ssl.create_default_context(cafile=str(D / 'ca.crt')); c2.minimum_version = v; c2.maximum_version = v
    try:
        with socket.create_connection(('127.0.0.1', TP)) as raw, c2.wrap_socket(raw, server_hostname='localhost') as ss: print(f'  客户端只允许 {v.name} →', ss.version())
    except Exception as e: print(f'  客户端只允许 {v.name} → 失败', str(e)[:80])
print('  服务端 tls-protocols 配置:', run(['redis-cli', '-p', str(PP), 'CONFIG', 'GET', 'tls-protocols']).stdout.split()[-1:] or '空(默认)')
print()
print('== 五:代价:握手、单次往返、吞吐(同一个实例、同一台机器)')
def handshake(n):
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        with socket.create_connection(('127.0.0.1', TP)) as raw, ctx.wrap_socket(raw, server_hostname='localhost') as ss: ss.sendall(C.enc(['PING'])); ss.recv(100)
        ts.append((time.perf_counter() - t) * 1000)
    return ts
def plainconn(n):
    ts = []
    for _ in range(n):
        t = time.perf_counter(); c = C(PP); c.do('PING'); c.close(); ts.append((time.perf_counter() - t) * 1000)
    return ts
def med(x): x = sorted(x); return x[len(x) // 2]
def p99(x): x = sorted(x); return x[int(len(x) * .99)]
h = handshake(300); pc = plainconn(300)
print(f'  新建连接 + 1 次 PING(300 次):明文 中位 {med(pc):.2f} ms / p99 {p99(pc):.2f} ms;TLS 中位 {med(h):.2f} ms / p99 {p99(h):.2f} ms')
R['conn'] = dict(plain_med=med(pc), plain_p99=p99(pc), tls_med=med(h), tls_p99=p99(h))
def pings(sock_send, n=20000):
    ts = []
    for _ in range(n):
        t = time.perf_counter(); sock_send(); ts.append((time.perf_counter() - t) * 1e6)
    return ts
pc_ = C(PP); pl = pings(lambda: pc_.do('PING'))
raw = socket.create_connection(('127.0.0.1', TP)); ss = ctx.wrap_socket(raw, server_hostname='localhost'); ping = C.enc(['PING'])
def tp(): ss.sendall(ping); ss.recv(100)
tl_ = pings(tp)
print(f'  已建立连接上的 PING 往返(20000 次):明文 中位 {med(pl):.0f} µs / p99 {p99(pl):.0f} µs;TLS 中位 {med(tl_):.0f} µs / p99 {p99(tl_):.0f} µs')
R['rtt'] = dict(plain_med=med(pl), plain_p99=p99(pl), tls_med=med(tl_), tls_p99=p99(tl_))
def bench(tls):
    args = ['redis-benchmark', '-p', str(TP if tls else PP), '-t', 'set,get', '-n', '200000', '-c', '50', '-q', '-P', '1'] + (['--tls', '--cacert', 'ca.crt'] if tls else [])
    r = run(args); return [f'{m[0]}: {float(m[1]):.0f} req/s p50={m[2]} ms' for m in re.findall(r'(SET|GET): ([\d.]+) requests per second, p50=([\d.]+)', r.stdout.replace('\r', '\n'))][-2:] or [r.stderr[:100]]
b1 = bench(False); b2 = bench(True)
print('  redis-benchmark(-c 50 -n 200000,无流水线)明文:', ' | '.join(x.strip() for x in b1)); print('  redis-benchmark 同参数 TLS:', ' | '.join(x.strip() for x in b2))
R['bench'] = dict(plain=b1, tls=b2)
print()
print('== 六:证书身份映射到 ACL 用户(tls-auth-clients-user)')
g = run(['redis-cli', '-p', str(PP), 'CONFIG', 'GET', 'tls-auth-clients-user']).stdout.strip().replace('\n', ' ')
print('  CONFIG GET tls-auth-clients-user →', g or '(空)'); R['cfg_user'] = g
ossl('ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', 'client2.key'); ossl('req', '-new', '-key', 'client2.key', '-subj', '/CN=nobody', '-out', 'client2.csr')
ossl('x509', '-req', '-in', 'client2.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key', '-CAcreateserial', '-days', '30', '-sha256', '-out', 'client2.crt')
adm2 = ['redis-cli', '-p', str(PP)]
run(adm2 + ['ACL', 'SETUSER', 'svc-app', 'on', 'nopass', '~app:*', '-@all', '+get', '+set'])
run(adm2 + ['CONFIG', 'SET', 'tls-auth-clients', 'yes'])
R['map'] = {}
def rc2(args, label, key):
    r = run(cli + args); o = (r.stdout + r.stderr).strip().replace('\n', ' / ')[:150]; print(f'  {label:<58} → {o}'); R['map'][key] = o
c1 = ['--tls', '--cacert', 'ca.crt', '--cert', 'client.crt', '--key', 'client.key']; c2 = ['--tls', '--cacert', 'ca.crt', '--cert', 'client2.crt', '--key', 'client2.key']
rc2(c1 + ['ACL', 'WHOAMI'], '映射关闭(off)时,带 CN=svc-app 的证书,ACL WHOAMI', 'off')
print('  CONFIG SET tls-auth-clients-user CN →', run(adm2 + ['CONFIG', 'SET', 'tls-auth-clients-user', 'CN']).stdout.strip())
rc2(c1 + ['ACL', 'WHOAMI'], '映射 CN 时,带 CN=svc-app 的证书,ACL WHOAMI', 'cn_match')
rc2(c1 + ['SET', 'app:1', 'x'], '  同一证书的连接 SET app:1(用户有 +set ~app:*)', 'cn_set')
rc2(c1 + ['SET', 'other', 'x'], '  同一证书的连接 SET other(没有权限的 key)', 'cn_other')
rc2(c2 + ['ACL', 'WHOAMI'], '映射 CN 时,带 CN=nobody 的证书(没有这个用户)', 'cn_nomatch')
rc2(['--tls', '--cacert', 'ca.crt', '--cert', 'client.crt', '--key', 'client.key', '--user', 'default', '--pass', 'x', 'ACL', 'WHOAMI'], '带证书但又显式 AUTH default(此处 default 是 nopass)', 'cn_then_auth')
print('  INFO stats:', [l for l in run(adm2 + ['INFO', 'stats']).stdout.splitlines() if 'tls_cert' in l or 'denied_auth' in l])
R['stat_tls_cert'] = [l for l in run(adm2 + ['INFO', 'stats']).stdout.splitlines() if 'tls_cert' in l]
save('r127', R)
p.terminate(); p.wait(10)
