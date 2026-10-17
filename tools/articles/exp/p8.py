import sys, os, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, socket, http.cookiejar
tee('p8')
_orig = socket.getaddrinfo
def _gai(host, *a, **k):
    if isinstance(host, str) and (host.endswith('.test') or host.endswith('.uk') or host == 'localhost2'): host = '127.0.0.1'
    return _orig(host, *a, **k)
socket.getaddrinfo = _gai   # 只改这个进程里的解析:*.test / *.uk 都指向本机回环

def server(h):
    u = urllib.parse.urlparse(h.path); q = urllib.parse.parse_qs(u.query)
    if u.path.endswith('/set'):
        hd = {}
        h.send_response(200); h.send_header('Content-Length', '2')
        for c in q.get('c', []): h.send_header('Set-Cookie', c)
        h.end_headers(); h.wfile.write(b'ok')
    else:
        ck = next((v for k, v in h.hdrs if k.lower() == 'cookie'), '')
        h.reply(200, ck.encode())

with Srv(server) as sv, Srv(server) as sv2:
    P, P2 = sv.port, sv2.port
    def run(sc, src, targets, note=''):
        s = requests.Session()
        s.get(f'http://{src}:{P}/set', params={'c': sc})
        stored = [f'{c.name}(domain={c.domain!r}, path={c.path!r}, domain_specified={c.domain_specified}, secure={c.secure})' for c in s.cookies]
        sent, nope = [], []
        for t in targets:
            port = P2 if t.startswith('@') else P
            lab = ('另一个端口的 ' if t.startswith('@') else '') + t.lstrip('@')
            t = t.lstrip('@')
            host, _, rest = t.partition('/')
            r = s.get(f'http://{host}:{port}/{rest}')
            (sent if 'k=v' in r.text else nope).append(lab)
        print(f'  Set-Cookie: {sc}  (来自 {src})')
        print(f'    保存下来的:{stored if stored else "无(被拒绝)"}')
        print(f'    之后请求时带上了:{sent};没带:{nope}' + (f'  {note}' if note else ''))

    print('== 一:没有 Domain 属性(host-only cookie):只发回给设置它的那个主机')
    run('k=v', 'www.example.test', ['www.example.test/', 'api.example.test/', 'example.test/', 'sub.www.example.test/', 'other.test/'])
    print('== 二:有 Domain=example.test:子域名也带上;设成别人的域名则被拒绝')
    run('k=v; Domain=example.test', 'www.example.test', ['www.example.test/', 'api.example.test/', 'example.test/', 'sub.www.example.test/', 'other.test/', 'notexample.test/'])
    run('k=v; Domain=.example.test', 'www.example.test', ['www.example.test/', 'api.example.test/', 'example.test/'], '(前导点写法)')
    run('k=v; Domain=other.test', 'www.example.test', ['www.example.test/', 'other.test/'])
    print('== 三:Path 属性:前缀匹配到路径边界')
    run('k=v; Path=/app', 'www.example.test', ['www.example.test/', 'www.example.test/app', 'www.example.test/app/', 'www.example.test/app/x', 'www.example.test/application', 'www.example.test/App'])
    print('== 四:不写 Path 时,默认路径取设置它的 URL 的目录部分')
    s = requests.Session(); s.get(f'http://www.example.test:{P}/a/b/set', params={'c': 'k=v'})
    print(f'  从 /a/b/set 设置的 cookie,保存的 path = {[c.path for c in s.cookies]}')
    sent = [t for t in ('/', '/a', '/a/', '/a/b/x', '/a/c') if 'k=v' in s.get(f'http://www.example.test:{P}{t}').text]
    print(f'  之后请求这些路径时带上了:{sent}')
    print('== 五:Cookie 不区分端口(RFC 6265):在端口 A 设置,发给同主机的端口 B 照样带上')
    run('k=v', 'www.example.test', ['www.example.test/', '@www.example.test/'], '(第二个目标 @ 是另一个端口的服务器)')
    print('== 六:Secure 与过期')
    run('k=v; Secure', 'www.example.test', ['www.example.test/'], '(服务器是 http,不是 https)')
    s = requests.Session(); s.get(f'http://www.example.test:{P}/set', params={'c': 'k=v'})
    print(f'  先设置 k=v,jar 里有 {len(s.cookies)} 个;', end='')
    s.get(f'http://www.example.test:{P}/set', params={'c': 'k=v; Max-Age=0'}); print(f'再收到 Max-Age=0 后有 {len(s.cookies)} 个')
    s.get(f'http://www.example.test:{P}/set', params={'c': 'k=v'}); s.get(f'http://www.example.test:{P}/set', params={'c': 'k=v; Expires=Thu, 01 Jan 1970 00:00:00 GMT'}); print(f'  再设置 k=v 后收到过去的 Expires:jar 里有 {len(s.cookies)} 个')
    print('== 七:公共后缀:Domain 设成一个很宽的域,http.cookiejar 会不会拦住')
    run('k=v; Domain=test', 'www.example.test', ['www.example.test/', 'other.test/'])
    run('k=v; Domain=.test', 'www.example.test', ['www.example.test/', 'other.test/'])
    run('k=v; Domain=co.uk', 'shop.co.uk', ['shop.co.uk/', 'other.co.uk/', 'bank.co.uk/'])
    run('k=v; Domain=.co.uk', 'shop.co.uk', ['shop.co.uk/', 'other.co.uk/', 'bank.co.uk/'])
    from http.cookiejar import DefaultCookiePolicy as DCP
    print(f'  默认策略 DefaultCookiePolicy().strict_ns_domain = {DCP().strict_ns_domain}(DomainLiberal = {DCP.DomainLiberal},DomainStrict = {DCP.DomainStrict})')
    s = requests.Session(); s.cookies.set_policy(DCP(strict_ns_domain=DCP.DomainStrict))
    s.get(f'http://shop.co.uk:{P}/set', params={'c': 'k=v; Domain=co.uk'})
    print(f'  换成 strict_ns_domain=DomainStrict 后,收到 Domain=co.uk:jar 里有 {len(s.cookies)} 个')
    s = requests.Session(); s.cookies.set_policy(DCP(strict_ns_domain=DCP.DomainStrict))
    s.get(f'http://shop.co.uk:{P}/set', params={'c': 'k=v'}); s.get(f'http://www.example.test:{P}/set', params={'c': 'k=v'})
    print(f'  DomainStrict 下不写 Domain 的 host-only cookie 照常保存:jar 里有 {len(s.cookies)} 个')
    print('== 八:手写 Cookie 头 与 cookies= 参数 与 Session 的 jar 的关系')
    s = requests.Session(); s.get(f'http://www.example.test:{P}/set', params={'c': 'k=v'})
    r = s.get(f'http://www.example.test:{P}/', cookies={'extra': '1'}); print(f'  Session 里已有 k=v,请求时再传 cookies={{"extra":"1"}} → 服务器收到 Cookie: {r.text!r};jar 里现在有 {sorted(c.name for c in s.cookies)}')
    r = s.get(f'http://www.example.test:{P}/', headers={'Cookie': 'manual=2'}); print(f'  请求时手写 headers={{"Cookie": "manual=2"}} → 服务器收到 Cookie: {r.text!r}')
    r = requests.get(f'http://www.example.test:{P}/set', params={'c': 'k=v'}); r2 = requests.get(f'http://www.example.test:{P}/')
    print(f'  不用 Session 的 requests.get:r.cookies={dict(r.cookies)};紧接着再 requests.get 同一个主机,服务器收到 Cookie: {r2.text!r}')
purge()
