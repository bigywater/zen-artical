import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v26'); reset()
print('网关改写请求头:X-Forwarded-For(XFF)、Host、真实 IP。后端是本进程里的 Python 服务,回显它看到的请求头;nginx 1.31.6。本机只有 127.0.0.1 和 ::1 两个环回地址,所以“不同来源”用这两个地址来区分')
def echo(h):
    h.reply(200, json.dumps({k.lower(): v for k, v in h.headers.items()}, ensure_ascii=False).encode())
B = Svc(echo)
def get(port, headers=None, v6=False, version=None, raw=None):
    host = '::1' if v6 else '127.0.0.1'
    af = socket.AF_INET6 if v6 else socket.AF_INET
    s = socket.socket(af); s.settimeout(5); s.connect((host, port))
    if raw: s.sendall(raw)
    else:
        hd = ''.join(f'{k}: {v}\r\n' for k, v in (headers or {}).items()); s.sendall(f'GET / HTTP/1.1\r\nHost: gw.test\r\n{hd}Connection: close\r\n\r\n'.encode())
    d = b''
    while True:
        x = s.recv(65536)
        if not x: break
        d += x
    s.close(); body = d.split(b'\r\n\r\n', 1)[1]
    try: return json.loads(body)
    except Exception: return {'_raw': body[:80].decode(errors='replace')}

# ============ 一 ============
print('== 一:X-Forwarded-For 怎么写。client(127.0.0.1)发的请求自带一个伪造的 X-Forwarded-For: 6.6.6.6。四种 nginx 写法,后端看到的 X-Forwarded-For 是什么')
cases = [('不写 proxy_set_header(默认)', ''), ('$proxy_add_x_forwarded_for(追加)', 'proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;'), ('$remote_addr(覆盖)', 'proxy_set_header X-Forwarded-For $remote_addr;'), ('置空(不转发)', 'proxy_set_header X-Forwarded-For "";')]
rows = []
for name, d in cases:
    ng = Nginx('v26a', f'upstream u {{ server 127.0.0.1:{B.port}; }} server {{ listen {{port}}; location / {{ proxy_pass http://u; {d} }} }}').start()
    j1 = get(ng.port, {'X-Forwarded-For': '6.6.6.6'}); j2 = get(ng.port, {}); ng.stop()
    rows.append((name, j1.get('x-forwarded-for', '(没有)'), j2.get('x-forwarded-for', '(没有)')))
table(rows, ['写法', 'client 伪造了 XFF: 6.6.6.6 时后端看到', 'client 没带 XFF 时后端看到'])
print('  默认:client 发什么就原样转给后端(伪造的 6.6.6.6 照单全收);$proxy_add_x_forwarded_for 在 client 带的值后面追加 client 的地址,最左边仍然是伪造的值;直接面对公网的最外层网关应该用 $remote_addr 覆盖,不要相信 client 自己带的 XFF')

# ============ 二 ============
print('== 二:两层网关,真实 IP 用 realip 模块还原。L1(外层,同时监听 127.0.0.1 和 ::1)把请求转给 L2(内层,也同时监听两个地址),L2 再转给后端。L1 用 $proxy_add_x_forwarded_for;L2 用 realip:real_ip_header X-Forwarded-For;real_ip_recursive on;并写后端头 X-Real-Seen: $remote_addr(realip 还原出的地址)。client 的来源地址是 ::1,带伪造的 XFF: 6.6.6.6。两条路:经过 L1(L1 连 L2 用的是 127.0.0.1)和直连 L2(来源 ::1)。比较 L2 的 set_real_ip_from:只信 127.0.0.1(L1 的地址)/ 信 127.0.0.1 和 ::1 / 信所有人(0.0.0.0/0 与 ::/0)')
rows = []
for name, trust in (('只信 127.0.0.1(L1)', ['127.0.0.1']), ('信 127.0.0.1 和 ::1', ['127.0.0.1', '::1']), ('信所有人 0.0.0.0/0 与 ::/0', ['0.0.0.0/0', '::/0'])):
    tl = ' '.join(f'set_real_ip_from {t};' for t in trust)
    ng2 = Nginx('v26b2', f'upstream u {{ server 127.0.0.1:{B.port}; }} server {{ listen {{port}}; listen [::1]:{{port}}; {tl} real_ip_header X-Forwarded-For; real_ip_recursive on; location / {{ proxy_pass http://u; proxy_set_header X-Real-Seen $remote_addr; }} }}').start()
    ng1 = Nginx('v26b1', f'upstream u {{ server 127.0.0.1:{ng2.port}; }} server {{ listen {{port}}; listen [::1]:{{port}}; location / {{ proxy_pass http://u; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }} }}').start()
    via = get(ng1.port, {'X-Forwarded-For': '6.6.6.6'}, v6=True); direct = get(ng2.port, {'X-Forwarded-For': '6.6.6.6'}, v6=True); ng1.stop(); ng2.stop()
    rows.append((name, '经过 L1', via.get('x-real-seen'), via.get('x-forwarded-for')))
    rows.append(('', '直连 L2', direct.get('x-real-seen'), direct.get('x-forwarded-for')))
table(rows, ['L2 信任谁', 'client(来源 ::1)走哪条路', 'L2 还原出来的“真实 IP”', 'L2 收到的 X-Forwarded-For'])
print('  “真实 IP”应该是 ::1(client 的真实来源)。信任范围太大时,直连 L2 的 client 只要自己带一个 XFF,L2 就把它当成真实 IP(冒充成功);只信 L1 时,不是 L1 发来的连接,XFF 被忽略,真实 IP 就是连接的对端地址;经过 L1 时,real_ip_recursive on 从右往左跳过受信任的地址,取到第一个不受信任的(L1 追加的 client 地址)')

# ============ 三 ============
print('== 三:Host 头。后端看到的 Host 取决于 nginx 怎么写:(a) 默认(Host 变成 upstream 组名 u);(b) proxy_set_header Host $host;(c) $http_host;(d) $host:$server_port。三种请求:Host: Shop.Test:8443(有端口、大小写混合);Host: shop.test;HTTP/1.0 请求完全不带 Host。server 块的 server_name 是 shop.test')
reqs = [('Host: Shop.Test:8443', b'GET / HTTP/1.1\r\nHost: Shop.Test:8443\r\nConnection: close\r\n\r\n'), ('Host: shop.test', b'GET / HTTP/1.1\r\nHost: shop.test\r\nConnection: close\r\n\r\n'), ('HTTP/1.0,没有 Host', b'GET / HTTP/1.0\r\n\r\n')]
cfgs = [('(a) 默认', ''), ('(b) $host', 'proxy_set_header Host $host;'), ('(c) $http_host', 'proxy_set_header Host $http_host;'), ('(d) $host:$server_port', 'proxy_set_header Host $host:$server_port;')]
rows = []
for name, d in cfgs:
    ng = Nginx('v26c', f'upstream u {{ server 127.0.0.1:{B.port}; }} server {{ listen {{port}}; server_name shop.test; location / {{ proxy_pass http://u; {d} }} }}').start()
    row = [name]
    for rn, raw in reqs:
        row.append(repr(get(ng.port, raw=raw).get('host', '(没有)')))
    rows.append(tuple(row)); ng.stop()
table(rows, ['写法'] + [r[0] for r in reqs])
print('  $host 是小写、去掉端口的主机名,没带 Host 时取 server_name;$http_host 是 client 原样发来的(含端口、大小写),没带 Host 时它是空值,而 proxy_set_header 对空值的头不会发送,于是后端看到的是默认的 u;$host:$server_port 里的端口是 nginx 自己监听的端口;后端要拼绝对 URL 或做虚拟主机路由,要选对。nginx 自己按 Host 选 server 块时大小写不敏感')
