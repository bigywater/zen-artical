import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v17'); reset()
print('反向代理的请求流程:client → nginx 1.31.6(本机 Homebrew)→ 后端。后端是本进程里的小 HTTP 服务,把自己收到的请求原样回显(请求行、HTTP 版本和全部请求头),client 看到的是 nginx 回给它的响应。下面看 nginx 默认情况下改写了什么')

def echo_app(tag):
    def app(h):
        hs = [f'{k}: {v}' for k, v in h.headers.items()]
        body = json.dumps({'tag': tag, 'line': f'{h.command} {h.path} {h.request_version}', 'headers': hs}, ensure_ascii=False).encode()
        h.reply(200, body, {'X-Backend': tag, 'Server': 'pyback/0.1', 'Keep-Alive': 'timeout=5', 'X-Secret-Internal': 'yes'})
    return app
B1 = Svc(echo_app('b1')); B2 = Svc(echo_app('b2'))

def get(port, path='/', headers=None, host=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        hd = dict(headers or {})
        if host: hd['Host'] = host
        c.request('GET', path, headers=hd); r = c.getresponse(); d = r.read(); return r.status, r.getheaders(), d, r.version
    finally: c.close()

# ============ 一 ============
print('== 一:nginx 转发给后端的请求,和 client 发来的请求有什么不同。client 发 GET /hello?a=1,带请求头 Host: shop.example.test、X-Trace: t-1、Accept-Encoding: gzip、一个空值的头 X-Empty、一个带下划线的头 X_under。比较:nginx 默认配置(只有 proxy_pass)与常见的写法(proxy_set_header Host $host; X-Real-IP; X-Forwarded-For; proxy_http_version 1.1; Connection "")')
conf_default = f'upstream u {{ server 127.0.0.1:{B1.port}; }} server {{ listen {{port}}; location / {{ proxy_pass http://u; }} }}'
conf_common = f'upstream u {{ server 127.0.0.1:{B1.port}; }} server {{ listen {{port}}; location / {{ proxy_pass http://u; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_http_version 1.1; proxy_set_header Connection ""; }} }}'
sent = {'Host': 'shop.example.test', 'X-Trace': 't-1', 'Accept-Encoding': 'gzip', 'X-Empty': '', 'X_under': 'u1', 'User-Agent': 'v17-client'}
seen = {}
for name, conf in (('default', conf_default), ('common', conf_common)):
    ng = Nginx('v17' + name, conf).start(); st, hs, d, ver = get(ng.port, '/hello?a=1', sent); j = json.loads(d); seen[name] = j; ng.stop()
print('  client 发出的请求头:', ', '.join(f"{k}: {v!r}" for k, v in sent.items()))
print('  后端看到的请求行(默认配置):', seen['default']['line'], '    (常见写法):', seen['common']['line'])
names = sorted({h.split(':')[0] for h in seen['default']['headers']} | {h.split(':')[0] for h in seen['common']['headers']} | set(sent))
def val(j, n):
    for h in j['headers']:
        if h.split(':')[0].lower() == n.lower(): return h.split(': ', 1)[1] if ': ' in h else ''
    return None
rows = []
for n in names:
    rows.append((n, repr(sent[n]) if n in sent else '-', repr(val(seen['default'], n)) if val(seen['default'], n) is not None else '(没有)', repr(val(seen['common'], n)) if val(seen['common'], n) is not None else '(没有)'))
table(rows, ['请求头', 'client 发的', '后端看到的(默认配置)', '后端看到的(常见写法)'])

# ============ 二 ============
print('== 二:nginx 回给 client 的响应,和后端发的响应有什么不同。后端的响应头:Server: pyback/0.1、X-Backend、Keep-Alive: timeout=5、X-Secret-Internal: yes,以及 Python 自己加的 Date。默认配置 vs proxy_hide_header X-Secret-Internal + proxy_pass_header Server')
conf_hide = f'upstream u {{ server 127.0.0.1:{B1.port}; }} server {{ listen {{port}}; location / {{ proxy_pass http://u; proxy_hide_header X-Secret-Internal; proxy_pass_header Server; }} }}'
resp = {}
for name, conf in (('direct', None), ('default', conf_default), ('hide', conf_hide)):
    if conf is None: st, hs, d, ver = get(B1.port, '/x')
    else:
        ng = Nginx('v17r' + name, conf).start(); st, hs, d, ver = get(ng.port, '/x'); ng.stop()
    resp[name] = [(k, v) for k, v in hs]
hn = sorted({k.lower() for r in resp.values() for k, v in r})
def rv(r, n):
    for k, v in r:
        if k.lower() == n: return v
    return '(没有)'
table([(n, rv(resp['direct'], n), rv(resp['default'], n), rv(resp['hide'], n)) for n in hn], ['响应头', '直连后端', '经过 nginx(默认)', '经过 nginx(hide X-Secret-Internal + pass Server)'])

# ============ 三 ============
print('== 三:listener、路由、上游三层。同一个 nginx 里:两个 listener(两个端口 P1、P2)、其中 P1 上有两个 server 块(按 Host 选)、server 里有三条路由(/api/、/static/、其余)、两个上游池(api、web)。发一批请求,看每个 (端口, Host, 路径) 落到哪个后端')
P1, P2 = free_port(), free_port()
conf = f"""upstream api {{ server 127.0.0.1:{B1.port}; }} upstream web {{ server 127.0.0.1:{B2.port}; }}
  server {{ listen {P1}; server_name shop.test; location /api/ {{ proxy_pass http://api; }} location /static/ {{ proxy_pass http://web; }} location / {{ return 200 'shop-default\\n'; }} }}
  server {{ listen {P1} default_server; server_name _; location / {{ return 404 'no-such-host\\n'; }} }}
  server {{ listen {P2}; server_name admin.test; location / {{ proxy_pass http://web; }} }}"""
ng = Nginx('v17l', conf, port=P1).start()
wait_port(P2, 10)
rows = []
for port, host, path in ((P1, 'shop.test', '/api/users'), (P1, 'shop.test', '/static/a.js'), (P1, 'shop.test', '/other'), (P1, 'unknown.test', '/api/users'), (P2, 'admin.test', '/api/users'), (P2, 'shop.test', '/x')):
    st, hs, d, ver = get(port, path, host=host)
    try: who = json.loads(d)['tag']
    except Exception: who = d.decode().strip()
    rows.append((f'端口 {"P1" if port == P1 else "P2"}', host, path, st, who))
table(rows, ['listener', 'Host 头', '路径', '状态码', '落到哪里'])
ng.stop()
print('  第一层 listener(端口 + server_name 选 server 块)→ 第二层路由(location 选一条规则)→ 第三层上游(upstream 里选一台后端)。Host 对不上任何 server_name 时落到该端口的 default_server;P2 上只有一个 server 块,所以不管 Host 是什么都落到它')
