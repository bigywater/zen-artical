import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v30'); reset()
print('路径重写:proxy_pass 末尾有没有 URI(包括只有一个斜杠),和 rewrite。上游是本进程里的 Python 服务,回显它收到的请求行里的路径(含查询串);nginx 1.31.6。请求用原始 socket 发出,保证 nginx 收到的就是写的这个字符串')
B = Svc(lambda h: h.reply(200, h.path.encode()))
def raw_get(port, path):
    s = socket.create_connection(('127.0.0.1', port)); s.settimeout(5); s.sendall(f'GET {path} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'.encode()); d = b''
    while True:
        x = s.recv(65536)
        if not x: break
        d += x
    s.close(); head, _, body = d.partition(b'\r\n\r\n'); return head.split(b' ')[1].decode(), body.decode(errors='replace'), head
def run(loc_body, paths, name='v30a'):
    ng = Nginx(name, f'upstream u {{ server 127.0.0.1:{B.port}; }} server {{ listen {{port}}; {loc_body} }}').start()
    out = []
    for p in paths:
        st, body, head = raw_get(ng.port, p)
        if st == '200': out.append(body)
        elif st in ('301', '302'): out.append(f'{st} → ' + [l.split(': ', 1)[1] for l in head.decode().split('\r\n') if l.lower().startswith('location:')][0].replace(f':{ng.port}', ':PORT'))
        else: out.append(st)
    ng.stop(); return out

# ============ 一 ============
print('== 一:proxy_pass 末尾的斜杠。规则:proxy_pass 的地址里有 URI 部分(哪怕只是一个 /)时,用它替换请求路径里匹配 location 的那一段前缀;没有 URI 部分时,原样转发整个请求路径。下面每行是一种 location + proxy_pass 的写法,每列是一个请求路径,格子里是上游实际收到的路径')
paths = ['/api/users?id=1', '/api/', '/api', '/apix/y', '/api//users']
cfgs = [('location /api/ { proxy_pass http://u; }', 'location /api/ + proxy_pass http://u'), ('location /api/ { proxy_pass http://u/; }', 'location /api/ + proxy_pass http://u/'), ('location /api/ { proxy_pass http://u/v1/; }', 'location /api/ + proxy_pass http://u/v1/'), ('location /api { proxy_pass http://u/; }', 'location /api + proxy_pass http://u/'), ('location /api { proxy_pass http://u/v1; }', 'location /api + proxy_pass http://u/v1'), ('location /api/ { proxy_pass http://u/v1; }', 'location /api/ + proxy_pass http://u/v1')]
rows = []
for body, name in cfgs:
    rows.append((name,) + tuple(run(body, paths)))
table(rows, ['配置'] + paths)
print('  看格子:proxy_pass 带 URI 时,用它替换请求路径里匹配 location 的那段前缀,其余部分接在后面,并且路径被规范化(连续斜杠合并);不带 URI 时原样转发整条路径(/api//users 原样到上游)。location /api(没有末尾斜杠)会把 /apix/y 也匹配进来,前缀 /api 被换掉后剩下的 x 接在 URI 后面(/x/y);location /api/ 配 proxy_pass http://u/v1(末尾没有斜杠)时,/api/users 变成 /v1users,前缀 /api/ 换成了 /v1,没有补斜杠。/api(不带斜杠)在 location /api/ 的配置下,nginx 自己回 301 补斜杠;/apix/y 不匹配 location /api/,落到没有 location 的默认处理(404)')

# ============ 二 ============
print('== 二:rewrite 的标志。location /old/ 里写 rewrite ^/old/(.*)$ /new/$1 加不同标志,再 proxy_pass http://u;(不带 URI)。另有一个 location /new/ 直接 return 200 "hit /new/ location"。看请求 /old/a/b?x=1 最后发生了什么。标志:无(继续往下执行后面的指令)/ break(停止 rewrite、用改写后的 URI 继续)/ last(用改写后的 URI 重新选 location)/ redirect(302 重定向)/ permanent(301)')
rows = []
for flag in ('', 'break', 'last', 'redirect', 'permanent'):
    loc = f'location /old/ {{ rewrite ^/old/(.*)$ /new/$1 {flag}; proxy_pass http://u; }} location /new/ {{ return 200 "hit /new/ location"; }}'
    r = run(loc, ['/old/a/b?x=1'])[0]; rows.append((flag or '(无标志)', r))
table(rows, ['标志', '请求 /old/a/b?x=1 的结果(上游收到的路径,或 nginx 自己的响应)'])
print('  没有标志时,rewrite 改了 URI 之后,当前 location 里剩下的 rewrite 模块指令(rewrite、return、set、if)继续执行,然后 nginx 用改写后的 URI 重新选 location——效果和 last 一样,所以请求命中 /new/,根本没到上游(我原以为会接着执行 proxy_pass,实测不是);只有 break 才会停在当前 location,用改写后的 URI 去 proxy_pass(上游收到 /new/a/b?x=1);redirect / permanent 返回 302 / 301 让 client 重新请求。查询串默认保留')

# ============ 三 ============
print('== 三:查询串和路径编码。三种写法:(a) proxy_pass http://u;(无 URI);(b) proxy_pass http://u/;(有 URI);(c) rewrite 之后 proxy_pass(无 URI)。请求路径里带百分号编码、连续斜杠和 ..。格子里是上游收到的路径')
paths = ['/api/a%20b?q=%41', '/api/a%2Fb', '/api/x/../y', '/api//z']
cfgs = [('(a) location /api/ + proxy_pass http://u', 'location /api/ { proxy_pass http://u; }'), ('(b) location /api/ + proxy_pass http://u/', 'location /api/ { proxy_pass http://u/; }'), ('(c) rewrite ^/api/(.*)$ /$1 break + proxy_pass http://u', 'location /api/ { rewrite ^/api/(.*)$ /$1 break; proxy_pass http://u; }')]
rows = []
for name, body in cfgs:
    rows.append((name,) + tuple(run(body, paths)))
table(rows, ['写法'] + paths)
print('  不带 URI 的 proxy_pass 原样转发请求里的路径(%2F、.. 段、// 都保持原样);带 URI 的 proxy_pass 和 rewrite 之后转发的是 nginx 处理过的路径:.. 被解析掉、// 被合并、%2F 被解码成了真正的斜杠(/api/a%2Fb 变成 /a/b),%20 仍保持编码。网关和上游对路径的理解不一致(例如上游看到的是 %2F 还是 /),是路径穿越和缓存投毒类问题的来源之一')
