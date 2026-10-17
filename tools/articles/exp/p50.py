import sys, os, re, secrets, json, urllib.parse as up, http.cookies; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, lxml.html
tee('p50')
SESS = {}

def cookie_sid(h):
    c = http.cookies.SimpleCookie(next((v for k, v in h.hdrs if k.lower() == 'cookie'), '')); return c['sid'].value if 'sid' in c else None
def new_token(s): s['token'] = secrets.token_hex(8); return s['token']
def form_page(s, msg=''):
    return f'<html><body><p>{msg}</p><form method="post" action="/login"><input type="hidden" name="csrf_token" value="{s["token"]}"><input type="hidden" name="form_id" value="login-v2"><input type="hidden" name="next" value="/account"><input name="username"><input name="password" type="password"><input name="website" style="display:none" tabindex="-1" autocomplete="off"><button>Login</button></form><meta name="csrf-token" content="{s["token"]}"></body></html>'.encode()
def site(h):
    p = up.urlsplit(h.path).path; sid = cookie_sid(h); s = SESS.get(sid)
    if p == '/login' and h.command == 'GET':
        hd = {}
        if s is None:
            sid = secrets.token_hex(8); s = SESS[sid] = dict(user=None); new_token(s); hd['Set-Cookie'] = f'sid={sid}; Path=/; HttpOnly'
        return h.reply(200, form_page(s), headers=hd)
    if p == '/login' and h.command == 'POST':
        f = {k: v[0] for k, v in up.parse_qs(h.body.decode()).items()}
        if s is None: return h.reply(403, b'no session')
        if f.get('csrf_token') != s['token']: new_token(s); return h.reply(403, b'csrf token mismatch')
        if f.get('form_id') != 'login-v2': return h.reply(400, b'missing form_id')
        if f.get('website'): return h.reply(400, b'honeypot filled')
        if (f.get('username'), f.get('password')) != ('alice', 'secret'):
            new_token(s); return h.reply(401, form_page(s, 'bad credentials'))              # 登录失败:token 轮换
        new_sid = secrets.token_hex(8); SESS[new_sid] = dict(user='alice', token=secrets.token_hex(8))   # 登录成功:换新的会话 id
        return h.reply(302, b'', headers={'Location': f.get('next', '/account'), 'Set-Cookie': f'sid={new_sid}; Path=/; HttpOnly'})
    if p == '/account':
        if s and s.get('user'): return h.reply(200, b'welcome alice')
        return h.reply(302, b'', headers={'Location': '/login'})
    if p == '/api/profile' and h.command == 'POST':
        if s is None or dict((k.lower(), v) for k, v in h.hdrs).get('x-csrf-token') != s['token']: return h.reply(403, b'csrf header mismatch')
        return h.reply(200, b'{"ok": true}', headers={'Content-Type': 'application/json'})
    h.reply(404, b'')

def parse_form(html):
    doc = lxml.html.fromstring(html); form = doc.xpath('//form')[0]
    fields = {i.get('name'): i.get('value', '') for i in form.xpath('.//input[@name]') if i.get('type') != 'submit'}
    return fields

with Srv(site) as sv:
    B = sv.url('')
    print('== 一:正确的登录流程(requests.Session 自动带 cookie):逐个请求')
    s = requests.Session(); r1 = s.get(B + '/login')
    f = parse_form(r1.content); print(f'  ① GET /login → {r1.status_code},Set-Cookie: {r1.headers.get("Set-Cookie", "")[:30]}…;页面里的表单字段(含隐藏字段)= {f}')
    f.update(username='alice', password='secret')
    r2 = s.post(B + '/login', data=f, allow_redirects=False); print(f'  ② POST /login(带上全部隐藏字段和账号密码)→ {r2.status_code},Location={r2.headers.get("Location")},Set-Cookie: {r2.headers.get("Set-Cookie", "")[:30]}…(登录成功后会话 id 换了)')
    r3 = s.get(B + '/account'); print(f'  ③ GET /account → {r3.status_code} {r3.text!r}')
    print(f'  会话 cookie 在登录前后的值:{r1.headers["Set-Cookie"].split(";")[0]} → {r2.headers["Set-Cookie"].split(";")[0]}(不同)')

    print('== 二:故意做错的每一步,服务器怎么拒绝')
    def post(sess, data, **kw): return sess.post(B + '/login', data=data, allow_redirects=False, **kw)
    base = lambda sess: parse_form(sess.get(B + '/login').content)
    s = requests.Session(); r = post(s, dict(username='alice', password='secret')); print(f'  没先 GET 表单、没有 cookie 就直接 POST:{r.status_code} {r.text!r}')
    s = requests.Session(); f = base(s); f.pop('csrf_token'); f.update(username='alice', password='secret'); r = post(s, f); print(f'  有 cookie 但漏了 csrf_token 字段:{r.status_code} {r.text!r}')
    s = requests.Session(); f = base(s); f['csrf_token'] = 'abc'; f.update(username='alice', password='secret'); r = post(s, f); print(f'  csrf_token 值不对:{r.status_code} {r.text!r}')
    s = requests.Session(); f = base(s); f.pop('form_id'); f.update(username='alice', password='secret'); r = post(s, f); print(f'  token 对但漏了另一个隐藏字段 form_id:{r.status_code} {r.text!r}')
    s = requests.Session(); f = base(s); f.update(username='alice', password='secret', website='http://x.test'); r = post(s, f); print(f'  把页面上所有 text 输入框都填了(包括 CSS 隐藏的蜜罐 website):{r.status_code} {r.text!r}')
    s = requests.Session(); s2 = requests.Session(); fa = base(s); fb = base(s2); fa.update(username='alice', password='secret'); r = post(s2, fa); print(f'  用会话 A 的 token 配会话 B 的 cookie:{r.status_code} {r.text!r}')

    print('== 三:token 在登录失败后轮换:用旧 token 再提交会怎样')
    s = requests.Session(); f = base(s); old = f['csrf_token']; f.update(username='alice', password='WRONG')
    r = post(s, f); print(f'  ① 密码错误:{r.status_code}(服务器换了新的 token)')
    f2 = dict(f); f2['password'] = 'secret'; r = post(s, f2); print(f'  ② 还用旧 token 再提交正确密码:{r.status_code} {r.text!r}')
    f3 = parse_form(post(s, dict(f, csrf_token='x')).content if False else s.get(B + '/login').content); f3.update(username='alice', password='secret'); r = post(s, f3); print(f'  ③ 重新 GET 表单拿新 token 后提交:{r.status_code}')

    print('== 四:AJAX 风格:token 放在 <meta name="csrf-token"> 里,通过 X-CSRF-Token 请求头回传')
    s = requests.Session(); html = s.get(B + '/login').content; tok = lxml.html.fromstring(html).xpath('//meta[@name="csrf-token"]/@content')[0]
    r = s.post(B + '/api/profile', json={'name': 'x'}); print(f'  只发 JSON、不带头:{r.status_code} {r.text!r}')
    r = s.post(B + '/api/profile', json={'name': 'x'}, headers={'X-CSRF-Token': tok}); print(f'  带 X-CSRF-Token: {r.status_code} {r.text!r}')
    print('== 五:如何通用地收集一个表单要提交的字段')
    print('  做法:取表单里所有带 name 的 <input>(隐藏字段取默认值),只覆盖用户名、密码;不要碰蜜罐和其它隐藏字段。上面第一节就是这样做的:字段 = ' + str(sorted(parse_form(requests.get(B + '/login').content).keys())))
purge()
