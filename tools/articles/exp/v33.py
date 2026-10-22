import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import hmac, hashlib, base64
tee('v33'); reset()
print('网关鉴权的两种做法:(1) nginx 的 auth_request:每个请求先发一个子请求给独立的鉴权服务,200 放行、401 拒绝;(2) 网关本地校验 JWT:Envoy 1.39.3 的 jwt_authn 过滤器,用配置里内联的密钥(HS256)验签和过期时间,不访问任何外部服务。后端和鉴权服务是本进程里的 Python 服务;JWT 是我用 hmac 自己签的 HS256')
KEY = b'lab-secret-key-0123456789abcdef'
def b64(x): return base64.urlsafe_b64encode(x).rstrip(b'=').decode()
def make_jwt(sub, exp_in, jti):
    h = b64(json.dumps({'alg': 'HS256', 'typ': 'JWT', 'kid': 'k1'}).encode()); p = b64(json.dumps({'sub': sub, 'exp': int(time.time() + exp_in), 'jti': jti}).encode())
    sig = b64(hmac.new(KEY, f'{h}.{p}'.encode(), hashlib.sha256).digest()); return f'{h}.{p}.{sig}'
REVOKED = set(); AUTH_DELAY = [0.0]; AUTH_CALLS = [0]
def verify(tok):
    try:
        h, p, s = tok.split('.'); exp = b64(hmac.new(KEY, f'{h}.{p}'.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(exp, s): return None
        pl = json.loads(base64.urlsafe_b64decode(p + '=' * (-len(p) % 4)))
        if pl['exp'] < time.time() or pl['jti'] in REVOKED: return None
        return pl
    except Exception: return None
def auth_app(h):
    AUTH_CALLS[0] += 1
    if AUTH_DELAY[0]: time.sleep(AUTH_DELAY[0])
    a = h.headers.get('Authorization', ''); pl = verify(a[7:]) if a.startswith('Bearer ') else None
    if pl: h.reply(200, b'ok', {'X-User': pl['sub']})
    else: h.reply(401, b'no')
seen = []
def back_app(h): seen.append(h.headers.get('X-User')); h.reply(200, b'hello ' + (h.headers.get('X-User') or '-').encode())
AUTH = Svc(auth_app); BACK = Svc(back_app)
JWKS = json.dumps({'keys': [{'kty': 'oct', 'alg': 'HS256', 'kid': 'k1', 'k': b64(KEY)}]})
def ng_conf(cache=False):
    c_path = 'proxy_cache_path {d}/cache keys_zone=authc:1m;' if cache else ''
    cache_loc = 'proxy_cache authc; proxy_cache_key $http_authorization; proxy_cache_valid 200 5s; proxy_cache_valid 401 1s;' if cache else ''
    return f'''upstream auth {{ server 127.0.0.1:{AUTH.port}; }} upstream back {{ server 127.0.0.1:{BACK.port}; }} {c_path}
  server {{ listen {{port}}; location = /_auth {{ internal; proxy_pass http://auth; proxy_pass_request_body off; proxy_set_header Content-Length ""; {cache_loc} }}
    location / {{ auth_request /_auth; auth_request_set $auth_user $upstream_http_x_user; proxy_set_header X-User $auth_user; proxy_pass http://back; }}
    location /noauth/ {{ proxy_pass http://back/; }} }}'''
def envoy_jwt_conf(skew=None):
    skew_line = f'                  clock_skew_seconds: {skew}' if skew is not None else ''
    pre = f'''          - name: envoy.filters.http.jwt_authn
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.jwt_authn.v3.JwtAuthentication
              providers:
                p1:
                  forward: true
                  from_headers: [{{name: Authorization, value_prefix: "Bearer "}}]
{skew_line}
                  local_jwks: {{inline_string: '{JWKS}'}}
              rules:
              - match: {{prefix: "/"}}
                requires: {{provider_name: p1}}'''
    routes = '              - match: {prefix: "/"}\n                route: {cluster: back}'
    return envoy_http_conf(routes, {'back': [BACK.port]}, pre_filters=pre)
def timeit(port, tok, n=500, path='/'):
    lat = []; cnt = collections.Counter()
    for _ in range(n):
        st, b, dt = rpc(port, path, 5.0, headers={'Authorization': f'Bearer {tok}'} if tok else None); lat.append(dt); cnt[st] += 1
    return lat, cnt

# ============ 一 ============
print('== 一:鉴权带来多少延迟。500 个顺序请求,带有效的 JWT。比较:不鉴权(nginx 的 /noauth/ 路径)/ nginx auth_request(鉴权服务回得很快,~0 ms)/ auth_request(鉴权服务要 20 ms)/ auth_request + 缓存(鉴权结果按 Authorization 头缓存 5 s,鉴权服务 20 ms)/ Envoy 本地 jwt_authn。同时统计鉴权服务被调用了多少次')
tok = make_jwt('alice', 3600, 'j1'); rows = []
ng = Nginx('v33a', ng_conf()).start(); lat, cnt = timeit(ng.port, tok, 500, '/noauth/x'); rows.append(('不鉴权', f'{pct(lat, 50) * 1000:.2f} ms', f'{pct(lat, 99) * 1000:.2f} ms', 0, dict(cnt)))
AUTH_CALLS[0] = 0; AUTH_DELAY[0] = 0.0; lat, cnt = timeit(ng.port, tok); rows.append(('auth_request(鉴权服务 ~0 ms)', f'{pct(lat, 50) * 1000:.2f} ms', f'{pct(lat, 99) * 1000:.2f} ms', AUTH_CALLS[0], dict(cnt)))
AUTH_CALLS[0] = 0; AUTH_DELAY[0] = 0.02; lat, cnt = timeit(ng.port, tok); rows.append(('auth_request(鉴权服务 20 ms)', f'{pct(lat, 50) * 1000:.2f} ms', f'{pct(lat, 99) * 1000:.2f} ms', AUTH_CALLS[0], dict(cnt))); ng.stop()
ng = Nginx('v33b', ng_conf(cache=True)).start(); AUTH_CALLS[0] = 0; AUTH_DELAY[0] = 0.02; lat, cnt = timeit(ng.port, tok); rows.append(('auth_request + 缓存 5 s(鉴权服务 20 ms)', f'{pct(lat, 50) * 1000:.2f} ms', f'{pct(lat, 99) * 1000:.2f} ms', AUTH_CALLS[0], dict(cnt))); ng.stop()
ev = Envoy('v33e', envoy_jwt_conf()).start(); AUTH_CALLS[0] = 0; lat, cnt = timeit(ev.port, tok); rows.append(('Envoy 本地 jwt_authn', f'{pct(lat, 50) * 1000:.2f} ms', f'{pct(lat, 99) * 1000:.2f} ms', AUTH_CALLS[0], dict(cnt))); ev.stop()
table(rows, ['做法', '延迟中位数', 'p99', '鉴权服务被调用', '状态码'])
AUTH_DELAY[0] = 0.0

# ============ 二 ============
print('== 二:撤销令牌后多久生效。令牌有效期 12 秒;client 每 0.25 s 用同一个令牌请求一次;在第 3 秒把这个令牌加入撤销名单(jti)。看撤销之后还有多久请求仍然被放行。做法:auth_request 无缓存 / auth_request 缓存 5 s / Envoy 本地 jwt_authn(网关不知道撤销名单)')
def revoke_test(port, label):
    REVOKED.clear(); tk = make_jwt('bob', 12, 'jr-' + label); t0 = time.perf_counter(); rev_at = None; last_ok = None; first_deny = None; passed_after = 0
    while time.perf_counter() - t0 < 14.5:
        t = time.perf_counter() - t0
        if rev_at is None and t >= 3.0: REVOKED.add('jr-' + label); rev_at = t
        st, b, dt = rpc(port, '/', 5.0, headers={'Authorization': f'Bearer {tk}'})
        if rev_at is not None:
            if st == 200: passed_after += 1; last_ok = t
            elif first_deny is None: first_deny = t
        time.sleep(0.25)
    return rev_at, last_ok, first_deny, passed_after
rows = []
for label, mk in (('auth_request 无缓存', lambda: Nginx('v33c', ng_conf())), ('auth_request 缓存 5 s', lambda: Nginx('v33d', ng_conf(cache=True)))):
    ng = mk().start(); r, lo, fd, pa = revoke_test(ng.port, label.replace(' ', '')); ng.stop()
    rows.append((label, f'{(lo - r) if lo else 0:.2f} s' if lo else '立刻', f'{(fd - r):.2f} s' if fd else '没有拒绝', pa))
for label, sk in (('Envoy 本地 jwt_authn(clock_skew_seconds 保持默认)', None), ('Envoy 本地 jwt_authn(clock_skew_seconds: 1)', 1)):
    ev = Envoy('v33e2', envoy_jwt_conf(sk)).start(); r, lo, fd, pa = revoke_test(ev.port, 'envoy'); ev.stop()
    rows.append((label, f'{(lo - r):.2f} s' if lo else '立刻', f'{(fd - r):.2f} s' if fd else '没有拒绝', pa))
table(rows, ['做法', '撤销之后,最后一个被放行的请求距撤销多久', '撤销之后第一个被拒绝的请求距撤销多久', '撤销之后仍被放行的请求数'])
print('  本地校验 JWT 不查撤销名单,令牌在过期之前一直有效(令牌有效期 12 秒、撤销发生在第 3 秒,所以要等令牌过期才会被拒);Envoy jwt_authn 的 clock_skew_seconds 默认允许令牌过期之后再宽限一段时间(默认值下整个 14.5 秒的测试里令牌一直被放行,设成 1 才在过期时被拒(0 表示“用默认值”,不能用来关掉宽限));auth_request 每次问鉴权服务,撤销立刻生效;给鉴权结果加缓存,撤销的生效延迟最长就是缓存时间')

# ============ 三 ============
print('== 三:鉴权服务挂了。client 每 20 ms 用有效令牌请求一次,共 6 秒;第 2 秒把鉴权服务关掉(进程内的 Python 服务停止监听),第 4 秒不会重新拉起。比较 auth_request(无缓存)/ auth_request 缓存 5 s / Envoy 本地 jwt_authn:第 0 到 6 秒每秒放行与拒绝(状态码)的数量')
def outage(port, stopper):
    out = []; t0 = time.perf_counter(); stopped = False; i = 0
    while time.perf_counter() - t0 < 6.0:
        t = time.perf_counter() - t0
        if t >= 2.0 and not stopped: stopper(); stopped = True
        st, b, dt = rpc(port, '/', 5.0, headers={'Authorization': f'Bearer {tok}'}, keepalive=False); out.append((t, st)); i += 1
        d = t0 + i * 0.02 - time.perf_counter()
        if d > 0: time.sleep(d)
    per = []
    for s in range(6):
        c = collections.Counter(st for t, st in out if int(t) == s); per.append(f'{c.get(200, 0)}/{sum(v for k, v in c.items() if k != 200)}')
    return per
rows = []
for label, cache in (('auth_request 无缓存', False), ('auth_request 缓存 5 s,proxy_cache_use_stale error timeout', True), ('auth_request 缓存 5 s,不允许用过期缓存', 'nostale')):
    A2 = Svc(auth_app); AUTH_CALLS[0] = 0
    def ngc():
        return f'''upstream auth {{ server 127.0.0.1:{A2.port} max_fails=0; }} upstream back {{ server 127.0.0.1:{BACK.port}; }} {'proxy_cache_path {d}/cache keys_zone=authc:1m;' if cache else ''}
  server {{ listen {{port}}; location = /_auth {{ internal; proxy_pass http://auth; proxy_pass_request_body off; proxy_set_header Content-Length ""; {('proxy_cache authc; proxy_cache_key $http_authorization; proxy_cache_valid 200 5s;' + (' proxy_cache_use_stale error timeout;' if cache is True else '')) if cache else ''} }}
    location / {{ auth_request /_auth; proxy_pass http://back; }} }}'''
    ng = Nginx('v33f', ngc()).start(); per = outage(ng.port, lambda: (A2.stop(), time.sleep(0.05))); ng.stop(); rows.append((label,) + tuple(per))
ev = Envoy('v33e3', envoy_jwt_conf()).start(); per = outage(ev.port, lambda: None); ev.stop(); rows.append(('Envoy 本地 jwt_authn(鉴权服务关不关都不影响)',) + tuple(per))
table(rows, ['做法'] + [f'第 {s} 秒 放行/失败' for s in range(6)])
print('  auth_request 是网关对鉴权服务的硬依赖:无缓存时鉴权服务一挂,所有需要鉴权的请求立刻失败;带缓存且不允许用过期缓存时,缓存有效期内的请求还能放行,缓存过期之后一起失败;加了 proxy_cache_use_stale error timeout 之后,鉴权服务挂了,过期的缓存继续被用,请求一直被放行——可用性好了,代价是撤销、封禁都不再生效(这是“失败时放行”的行为);本地校验的网关不依赖外部服务')

# ============ 四 ============
print('== 四:client 伪造身份头。client 带有效令牌(sub = alice),同时伪造 X-User: admin。后端看到的 X-User 是谁。nginx:(a) 不写 proxy_set_header(转发 client 的头);(b) proxy_set_header X-User $auth_user(用鉴权服务返回的覆盖);Envoy jwt_authn 只验证令牌,不会改写 X-User')
def conf_fwd(set_hdr):
    return f'''upstream auth {{ server 127.0.0.1:{AUTH.port}; }} upstream back {{ server 127.0.0.1:{BACK.port}; }}
  server {{ listen {{port}}; location = /_auth {{ internal; proxy_pass http://auth; proxy_pass_request_body off; proxy_set_header Content-Length ""; }}
    location / {{ auth_request /_auth; auth_request_set $auth_user $upstream_http_x_user; {set_hdr} proxy_pass http://back; }} }}'''
rows = []
for label, sh_ in (('nginx (a) 不覆盖 X-User', ''), ('nginx (b) proxy_set_header X-User $auth_user', 'proxy_set_header X-User $auth_user;')):
    ng = Nginx('v33g', conf_fwd(sh_)).start(); seen.clear(); st, b, _ = rpc(ng.port, '/', 5.0, headers={'Authorization': f'Bearer {tok}', 'X-User': 'admin'}); ng.stop(); rows.append((label, st, b.decode()))
ev = Envoy('v33e4', envoy_jwt_conf()).start(); st, b, _ = rpc(ev.port, '/', 5.0, headers={'Authorization': f'Bearer {tok}', 'X-User': 'admin'}); ev.stop(); rows.append(('Envoy jwt_authn(没有配置覆盖)', st, b.decode()))
table(rows, ['配置', '状态码', '后端回应(hello + 它看到的 X-User)'])
print('  网关鉴权通过之后,要把“已验证的身份”用网关自己的值覆盖到发给后端的头里,并且把 client 发来的同名头丢掉,否则后端会信任伪造的身份')
