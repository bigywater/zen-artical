import sys, os, re, struct, threading, statistics, errno, ssl, http.client, http.cookiejar, urllib.request, urllib.parse, email.utils; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w81'); reset()
ctx = ssl.create_default_context()

print('== 一:真实站点的 Set-Cookie 头长什么样:www.baidu.com 首页(只看头部,逐个属性拆开;值只显示前 6 个字符)')
c = http.client.HTTPSConnection('www.baidu.com', 443, timeout=8, context=ctx); c.request('GET', '/', headers={'User-Agent': 'w81'}); r = c.getresponse(); r.read()
cks = [v for k, v in r.getheaders() if k.lower() == 'set-cookie']; c.close()
print(f'  收到 {len(cks)} 个 Set-Cookie 头(同名头可以出现多次,不能像别的头一样用逗号合并)')
for ck in cks[:6]:
    parts = [p.strip() for p in ck.split(';')]; nm, _, val = parts[0].partition('=')
    attrs = {}
    for p in parts[1:]:
        k, _, v = p.partition('='); attrs[k.lower()] = v or True
    print(f'    名字 {nm:<14} 值 {val[:6]}…({len(val)} 字符);属性 {attrs}')
exp_ = [a for ck in cks for a in [dict((p.strip().partition("=")[0].lower(), p.strip().partition("=")[2]) for p in ck.split(";")[1:])] if "expires" in a]
if exp_:
    e = email.utils.parsedate_to_datetime(exp_[0]['expires'].replace('-', ' ')) if False else None
print(f'  带 Max-Age 的:{[ck.split("=")[0] + " max-age=" + re.search(r"max-age=(\\d+)", ck, re.I).group(1) for ck in cks if re.search(r"max-age=(\\d+)", ck, re.I)]}(秒;2147483647 秒 ≈ {2147483647 / 86400 / 365:.0f} 年)')

print('== 二:本机服务器 + Python 的 http.cookiejar(按 RFC 的规则存取 Cookie)。服务器依次下发几个带不同属性的 Cookie,再看后续请求带不带它们')
sent = []
def srv(port, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(16); ls.settimeout(0.3)
    def h(c):
        try:
            c.settimeout(5); buf = b''
            while b'\r\n\r\n' not in buf: buf += c.recv(65536)
            line = buf.split(b'\r\n')[0].decode(); path = line.split()[1]; ck = re.search(rb'(?im)^cookie: *(.*)$', buf); sent.append((path, ck.group(1).decode() if ck else None))
            hdr = b''
            if path == '/set':
                hdr = (b'Set-Cookie: a=1\r\nSet-Cookie: b=2; Path=/admin\r\nSet-Cookie: c=3; Secure\r\nSet-Cookie: d=4; HttpOnly; Max-Age=3600\r\n'
                       b'Set-Cookie: e=5; Domain=example.org\r\nSet-Cookie: f=6; Max-Age=0\r\nSet-Cookie: g=7; Expires=Wed, 01 Jan 2020 00:00:00 GMT\r\nSet-Cookie: h=8; Path=/api; SameSite=Strict\r\n')
            body = b'ok'
            c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n' + hdr + b'Connection: close\r\n\r\n' + body)
        except Exception: pass
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
port = lab_port(); stop = [False]; srv(port, stop)
jar = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
op.open(f'http://127.0.0.1:{port}/set').read()
print(f'  服务器下发了 8 个 Cookie(a~h);cookiejar 实际保存了 {len(jar)} 个:')
for ck in jar: print(f'    {ck.name}={ck.value}  domain={ck.domain}  path={ck.path}  secure={ck.secure}  过期={"会话结束" if ck.expires is None else ck.expires}  仅HTTP={ck.has_nonstandard_attr("HttpOnly")}')
dropped = sorted(set('abcdefgh') - {ck.name for ck in jar})
print(f'  没有保存的:{dropped}(e:Domain=example.org 与请求的主机不匹配,被拒绝;f:Max-Age=0 表示立刻删除;g:Expires 已过期)')
for path in ('/', '/admin/x', '/api/x'):
    sent.clear(); op.open(f'http://127.0.0.1:{port}{path}').read(); print(f'  请求 {path:<10}→ 带上的 Cookie 头:{sent[-1][1]}')
print('  c(Secure)在明文 HTTP 请求里没有被带上;b(Path=/admin)只在 /admin 下带上;h(Path=/api)在 /api 下带上;SameSite 是浏览器对“跨站请求”的限制,cookiejar 不实现,所以 h 的 SameSite=Strict 在这里没有起作用')
stop[0] = True

print('== 三:Cookie 的大小与数量限制(服务器侧):往 example.com 的请求里塞越来越大的 Cookie 头,看什么时候被拒绝')
def req(n):
    s = socket.create_connection(('104.20.23.154', 80), timeout=6); s.settimeout(6); s.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\nCookie: a=' + b'x' * n + b'\r\n\r\n'); buf = b''
    try:
        while True:
            d = s.recv(65536)
            if not d: break
            buf += d
            if b'\r\n' in buf and len(buf) > 40: break
    except Exception: pass
    s.close(); return buf.split(b'\r\n', 1)[0].decode('latin1')[:40] or '(无响应)'
for n in (100, 4000, 8000, 16000, 32000, 64000):
    print(f'  Cookie 头值长 {n:>5} 字节 → {req(n)}')

print('== 四:SameSite 的规则(模拟:浏览器行为我在这里没法直接测。用我实现的判断函数,把规则对不同的请求逐个套一遍)')
def sends(samesite, top_site, req_site, method, top_level_nav):
    same_site = top_site == req_site
    if same_site: return True
    if samesite == 'None': return True
    if samesite == 'Strict': return False
    return method == 'GET' and top_level_nav  # Lax
print('    情形                                             Strict   Lax    None(须 Secure)')
for nm, a in (('同站点内的任何请求', ('a.com', 'a.com', 'POST', False)), ('在 b.com 页面里的 <img src=a.com/x>', ('b.com', 'a.com', 'GET', False)), ('在 b.com 页面里点链接跳到 a.com(顶层导航 GET)', ('b.com', 'a.com', 'GET', True)), ('b.com 的表单 POST 到 a.com(顶层导航 POST)', ('b.com', 'a.com', 'POST', True)), ('b.com 的 fetch/XHR 请求 a.com', ('b.com', 'a.com', 'GET', False))):
    print(f'    {nm:<48} ' + '   '.join(f'{"带" if sends(s, *a) else "不带":<4}' for s in ('Strict', 'Lax', 'None')))
print('  (表中“站点”指可注册域名 eTLD+1,example.com 与 api.example.com 算同一站点;这张表是我按规范写的,不是实测浏览器)')
