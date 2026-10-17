import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f129'); R = {}
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
USERS = {'ann': 'pw-ann', 'bob': 'pw-bob'}
def mk(variant):
    a = Flask('r'); a.logger.disabled = True
    def ip_or_hdr(): return request.headers.get('X-Client', get_remote_address())
    def by_user():
        j = request.get_json(silent=True) or {}; return f'user:{j.get("username", "?")}'
    lim = Limiter(ip_or_hdr, app=a, storage_uri='memory://', default_limits=[])
    def handler():
        j = request.get_json(); ok = USERS.get(j.get('username')) == j.get('password'); return (jsonify(ok=True), 200) if ok else (jsonify(ok=False), 401)
    if variant == 'ip_all': a.post('/login')(lim.limit('3 per minute')(handler))
    elif variant == 'ip_failed': a.post('/login')(lim.limit('3 per minute', deduct_when=lambda r: r.status_code != 200)(handler))
    elif variant == 'user': a.post('/login')(lim.limit('3 per minute', key_func=by_user, deduct_when=lambda r: r.status_code != 200)(handler))
    elif variant == 'both':
        a.post('/login')(lim.limit('10 per minute', deduct_when=lambda r: r.status_code != 200)(lim.limit('3 per minute', key_func=by_user, deduct_when=lambda r: r.status_code != 200)(handler)))
    return a
def post(c, user, pw, client='c1'): r = c.post('/login', json={'username': user, 'password': pw}, headers={'X-Client': client}); return r.status_code
print('== 一:每个 IP 每分钟 3 次(不管成败都计数):正常用户的成功登录也会占额度')
c = mk('ip_all').test_client(); seq = [post(c, 'ann', 'pw-ann') for _ in range(5)]; print('  同一个 IP 连续 5 次正确登录:', seq); R['ip_all'] = seq
print()
print('== 二:只计算失败的尝试(deduct_when):成功不占额度,失败累计到 3 次后连正确的密码也被拒')
c = mk('ip_failed').test_client(); seq1 = [post(c, 'ann', 'pw-ann') for _ in range(5)]; print('  连续 5 次正确登录:', seq1)
seq2 = [post(c, 'ann', 'wrong') for _ in range(4)]; print('  同一个 IP 连续 4 次错误密码:', seq2); seq3 = post(c, 'ann', 'pw-ann'); print('  之后用正确的密码登录:', seq3, '(被限流挡住,即使密码正确)'); R['ip_failed'] = [seq1, seq2, seq3]
print()
print('== 三:按用户名限流:换 IP 也挡得住对同一个账号的连续猜测')
c = mk('user').test_client(); seq = [post(c, 'ann', f'g{i}', client=f'ip{i}') for i in range(5)]; print('  对 ann 用 5 个不同的 IP 各猜 1 次:', seq); R['user_multi_ip'] = seq
print('  这时 bob 用同样的 IP 登录:', post(c, 'bob', 'pw-bob', client='ip0'), '(别的账号不受影响)'); R['user_other'] = post(c, 'bob', 'pw-bob', client='ip0')
print('  但真正的 ann 此时也被挡住:', post(c, 'ann', 'pw-ann', client='real'), '(攻击者可以借此让账号暂时无法登录——这是按用户名限流的副作用)'); R['user_lockout_side'] = post(c, 'ann', 'pw-ann', client='real')
print()
print('== 四:两层叠加:每个用户名 3 次失败 + 每个 IP 10 次失败')
c = mk('both').test_client(); a1 = [post(c, 'ann', f'g{i}', client='one-ip') for i in range(4)]; print('  同一个 IP 猜 ann 4 次:', a1)
a2 = [post(c, f'victim{i}', 'x', client='one-ip') for i in range(10)]; print('  同一个 IP 再换 10 个不同的用户名各猜 1 次:', a2); R['both'] = [a1, a2]
print()
print('== 五:被限流时的响应:状态码、Retry-After、响应体')
a = mk('ip_all'); a.config['RATELIMIT_HEADERS_ENABLED'] = True
lim_app = a; c = lim_app.test_client()
for _ in range(3): post(c, 'ann', 'pw-ann')
r = c.post('/login', json={'username': 'ann', 'password': 'pw-ann'}, headers={'X-Client': 'c1'}); print('  第 4 次 →', r.status_code, {k: v for k, v in r.headers if k.lower() in ('retry-after', 'x-ratelimit-limit', 'x-ratelimit-remaining')}, '| 正文:', r.get_data(as_text=True)[:70].replace('\n', ' ')); R['resp'] = [r.status_code, {k: v for k, v in r.headers if k.lower() == 'retry-after'}]
save('f129', R)
