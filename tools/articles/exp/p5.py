import sys, os, inspect; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests
tee('p5')

def hv(h, k): return next((v for kk, v in h['hdrs'] if kk.lower() == k.lower()), None)

def router(h):
    p = h.path.split('?')[0]
    if p.startswith('/r') and p[2:].isdigit():
        h.reply(int(p[2:]), b'', headers={'Location': '/final'})
    elif p == '/loop': h.reply(302, b'', headers={'Location': '/loop'})
    elif p == '/chain/0': h.reply(200, b'end')
    elif p.startswith('/chain/'): h.reply(302, b'', headers={'Location': f'/chain/{int(p[7:]) - 1}'})
    elif p == '/rel': h.reply(301, b'', headers={'Location': 'sub/page'})
    else: h.reply(200, b'final')

print('== 一:POST 遇到不同状态码的重定向,到目标地址时变成了什么(服务器记录目标地址收到的请求)')
with Srv(router) as sv:
    for code in (301, 302, 303, 307, 308):
        sv.reset()
        r = requests.post(sv.url(f'/r{code}'), data=b'a=1&b=2', headers={'X-Probe': 'yes'})
        last = sv.log[-1]
        print(f'  POST /r{code} → 目标 {last["path"]}:方法 {last["method"]},请求体 {len(last["body"])} 字节,Content-Type={hv(last, "Content-Type")},Content-Length={hv(last, "Content-Length")};服务器共收到 {len(sv.log)} 个请求;history={[x.status_code for x in r.history]}')

print('== 二:GET 带 allow_redirects=False 看到原始响应;history 记录每一跳;相对 Location 的解析')
with Srv(router) as sv:
    r = requests.get(sv.url('/r302'), allow_redirects=False)
    print(f'  allow_redirects=False:状态 {r.status_code},Location={r.headers["Location"]},is_redirect={r.is_redirect},r.next.url={r.next.url if r.next else None}')
    r = requests.get(sv.url('/chain/3'))
    print(f'  /chain/3 逐跳:{[(x.status_code, x.url.replace(sv.url(""), "")) for x in r.history]} → 最终 {r.status_code} {r.url.replace(sv.url(""), "")}')
    r = requests.get(sv.url('/rel'))
    print(f'  /rel 回 301 Location: sub/page(相对路径)→ 最终 URL {r.url.replace(sv.url(""), "")},状态 {r.status_code}')

print('== 三:跳转次数上限:默认 30,超过抛 TooManyRedirects')
with Srv(router) as sv:
    print(f'  Session.max_redirects 默认值 = {requests.Session().max_redirects}')
    try: requests.get(sv.url('/loop'))
    except Exception as e: print(f'  /loop(一直 302 到自己):{type(e).__name__}: {str(e)[:70]};服务器收到 {len(sv.log)} 个请求')
    s = requests.Session(); s.max_redirects = 5; sv.reset()
    try: s.get(sv.url('/loop'))
    except Exception as e: print(f'  max_redirects=5:{type(e).__name__};服务器收到 {len(sv.log)} 个请求')
    for n in (29, 30, 31):
        sv.reset()
        try: r = requests.get(sv.url(f'/chain/{n}')); res = f'成功,history {len(r.history)} 跳'
        except Exception as e: res = type(e).__name__
        print(f'  链长 {n} 跳:{res};服务器收到 {len(sv.log)} 个请求')

print('== 四:跳到另一个主机(这里是另一个端口)时,哪些请求头被带过去了')
with Srv(lambda h: h.reply(200, b'B')) as B, Srv(lambda h: h.reply(302, b'', headers={'Location': B.url('/dest')})) as A:
    for label, kw in (('headers= 手写 Authorization、X-Token、Cookie', dict(headers={'Authorization': 'Bearer secret-token', 'X-Token': 'custom-secret', 'Cookie': 'sid=abc'})),
                      ('auth=(user, pass)', dict(auth=('user', 'pass')))):
        A.reset(); B.reset()
        requests.get(A.url('/start'), **kw)
        a, b = A.log[-1], B.log[-1]
        names = lambda x: [k for k, _ in x['hdrs']]
        print(f'  {label}:A 收到的头 {names(a)}')
        print(f'  {label}:B 收到的头 {names(b)}')
print('  requests 的 should_strip_auth(决定跳转时要不要去掉 Authorization)对几组 URL 的判断:')
ss = requests.Session()
for a, b in (('http://example.test/a', 'http://example.test/b'), ('http://example.test:8000/a', 'http://example.test:9000/a'),
             ('http://example.test/a', 'https://example.test/a'), ('http://example.test:8080/a', 'https://example.test:8443/a'),
             ('https://example.test/a', 'http://example.test/a'), ('http://example.test/a', 'http://other.test/a')):
    print(f'    {a} → {b}:去掉 Authorization = {ss.should_strip_auth(a, b)}')
purge()
