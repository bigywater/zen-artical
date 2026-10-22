import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v29'); reset()
print('nginx 的 location 匹配规则:先找最长的前缀 location(= 精确匹配直接命中;^~ 前缀命中就不再看正则),再按配置文件里的顺序依次试正则(~ 区分大小写、~* 不区分),第一个匹配的正则胜出;没有正则匹配就用刚才记下的最长前缀。每个 location 直接 return 自己的名字,不经过上游,nginx 1.31.6')
LOCS = '''location = /exact { return 200 "A: = /exact"; }
  location /a/ { return 200 "B: prefix /a/"; }
  location /a/b/ { return 200 "C: prefix /a/b/"; }
  location ^~ /static/ { return 200 "D: ^~ /static/"; }
  location ~ \\.php$ { return 200 "E: regex ~ .php 结尾"; }
  location ~* \\.(jpg|png)$ { return 200 "F: regex ~* .jpg/.png 结尾"; }
  location ~ ^/a/b/c { return 200 "G: regex ~ ^/a/b/c"; }
  location / { return 200 "H: prefix /"; }'''
def raw_get(port, path):
    s = socket.create_connection(('127.0.0.1', port)); s.settimeout(5); s.sendall(f'GET {path} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'.encode()); d = b''
    while True:
        x = s.recv(65536)
        if not x: break
        d += x
    s.close(); head, _, body = d.partition(b'\r\n\r\n'); return head.split(b' ')[1].decode(), body.decode(errors='replace').strip()

# ============ 一 ============
print('== 一:优先级矩阵。配置里有 8 个 location(A 精确 /exact;B 前缀 /a/;C 前缀 /a/b/;D ^~ 前缀 /static/;E 正则 .php$;F 不区分大小写正则 .jpg/.png;G 正则 ^/a/b/c;H 前缀 /)。发一批路径,看每个路径命中谁')
ng = Nginx('v29a', f'server {{ listen {{port}}; {LOCS} }}').start()
paths = ['/exact', '/exact/', '/exact?x=1', '/a/x', '/a/b/x', '/a/b/c/d', '/a/b/cx', '/static/x', '/static/x.php', '/static/a.jpg', '/x.php', '/a/x.php', '/a/x.png', '/pic.JPG', '/pic.jpg/', '/A/b/c', '/nothing']
table([(p,) + raw_get(ng.port, p) for p in paths], ['请求路径', '状态码', '命中'])
ng.stop()
print('  几个值得注意的:/a/b/c/d 最长前缀是 C(/a/b/),但正则 G 匹配,正则胜过普通前缀;/a/x.png 同样是正则 F 胜过前缀 B;/static/x.php 命中 D 而不是 E,因为 ^~ 前缀一旦是最长前缀就不再试正则;/exact/ 不等于 /exact,落到 B 之外的 H;/A/b/c 在这台 macOS 上也命中了 G(~ 本应区分大小写,见第四节)')

# ============ 二 ============
print('== 二:正则的顺序。两个正则都能匹配 /api/v1/users.json:R1 = ~ ^/api/ ,R2 = ~ \\.json$。配置里先写谁,谁就命中(正则按文件里出现的顺序试,第一个匹配的胜出)')
rows = []
for name, first, second in (('R1 写在前', 'location ~ ^/api/ { return 200 "R1: ^/api/"; }', 'location ~ \\.json$ { return 200 "R2: .json 结尾"; }'), ('R2 写在前', 'location ~ \\.json$ { return 200 "R2: .json 结尾"; }', 'location ~ ^/api/ { return 200 "R1: ^/api/"; }')):
    ng = Nginx('v29b', f'server {{ listen {{port}}; {first} {second} location / {{ return 200 "H: /"; }} }}').start(); rows.append((name, raw_get(ng.port, '/api/v1/users.json')[1])); ng.stop()
table(rows, ['配置顺序', '/api/v1/users.json 命中'])
rows = []
for name, locs in (('前缀 /api/ 写在正则前', 'location /api/ { return 200 "P: prefix /api/"; } location ~ \\.json$ { return 200 "R: .json 结尾"; }'), ('前缀 /api/ 写在正则后', 'location ~ \\.json$ { return 200 "R: .json 结尾"; } location /api/ { return 200 "P: prefix /api/"; }'), ('前缀换成 ^~ /api/', 'location ~ \\.json$ { return 200 "R: .json 结尾"; } location ^~ /api/ { return 200 "P: ^~ /api/"; }')):
    ng = Nginx('v29b', f'server {{ listen {{port}}; {locs} location / {{ return 200 "H: /"; }} }}').start(); rows.append((name, raw_get(ng.port, '/api/v1/users.json')[1])); ng.stop()
table(rows, ['配置', '/api/v1/users.json 命中'])
print('  普通前缀 location 的先后顺序无关紧要(按前缀长度比),但正则的先后顺序决定谁胜出;普通前缀和正则谁先写也不影响“正则胜过前缀”;想让某个前缀不被正则抢走,要用 ^~')

# ============ 三 ============
print('== 三:匹配前 nginx 会先规范化路径。同一个配置(第一节的 8 个 location),发这些“看起来不同但规范化之后相同”的路径:连续斜杠、百分号编码、. 和 .. 段、查询串')
ng = Nginx('v29c', f'server {{ listen {{port}}; {LOCS} }}').start()
paths = ['/a/x', '//a//x', '/%61/x', '/a/./x', '/a/b/../x', '/a/%2e%2e/exact', '/a%2fx', '/exact%3Fx=1', '/exact?x=1']
table([(p,) + raw_get(ng.port, p) for p in paths], ['请求路径', '状态码', '命中'])
ng.stop()
print('  nginx 在选 location 之前把 URI 规范化:合并连续的斜杠(merge_slashes 默认 on)、解码百分号(%61 = a)、去掉 . 和 .. 段;%2f(编码的斜杠)被解码成真正的斜杠还是留作字符,以及 %3F 是否被当成问号,都要看这一节的实际结果,不要凭想象')

# ============ 四 ============
print('== 四:大小写。同一份 location 配置,macOS 上的 nginx 1.31.6 与 Linux 上的 nginx 1.27(Docker 镜像 nginx:1.27-alpine,容器里是 Linux)各自对大小写不同的路径命中谁。注意两边 nginx 版本也不同(1.31.6 对 1.27),所以差别可能来自操作系统,也可能来自版本,这里只能说“观察到不同”')
conf_txt = f"""events {{ worker_connections 64; }}
http {{ access_log off; server {{ listen 80; {LOCS} }} }}
"""
cdir = TT / 'v29docker'; cdir.mkdir(exist_ok=True); (cdir / 'nginx.conf').write_text(conf_txt)
dport = free_port()
subprocess.run(['docker', 'rm', '-f', 'v29nginx'], capture_output=True)
r = subprocess.run(['docker', 'run', '-d', '--rm', '--name', 'v29nginx', '-p', f'127.0.0.1:{dport}:80', '-v', f'{cdir}/nginx.conf:/etc/nginx/nginx.conf:ro', 'nginx:1.27-alpine'], capture_output=True, text=True)
ng = Nginx('v29d', f'server {{ listen {{port}}; {LOCS} }}').start()
wait_port(dport, 20)
ver = sh('docker exec v29nginx nginx -v')
paths = ['/EXACT', '/A/x', '/A/B/x', '/a/B/C/d', '/A/b/c', '/pic.JPG', '/x.PHP', '/STATIC/x.php']
rows = []
for p in paths:
    rows.append((p, raw_get(ng.port, p)[1], raw_get(dport, p)[1]))
table(rows, ['请求路径', 'macOS · nginx 1.31.6', 'Linux 容器 · ' + ver.replace('nginx version: ', '')])
ng.stop(); subprocess.run(['docker', 'rm', '-f', 'v29nginx'], capture_output=True)
print('  据我对 nginx 文档的记忆,在大小写不敏感的操作系统(macOS、Cygwin、Windows)上前缀 location 的匹配会忽略大小写(这一句我没有在这次实验里核对文档原文);实测这台 macOS 上连 ~ 正则也不区分大小写(/A/b/c 命中了 ~ ^/a/b/c),而 Linux 容器里 ~ 区分大小写。在 macOS 上开发、在 Linux 上部署的配置,路径大小写相关的路由行为可能不一致')
