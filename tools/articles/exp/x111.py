import sys, os, re, time, json, base64, hashlib, secrets, http.client, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x111'); CP = scp('org.springframework.boot:spring-boot-starter-oauth2-authorization-server', 'org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = '''package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication public class Main { public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); } }
'''
b = sbuild('x111', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
port = free_port(); REDIR = 'http://127.0.0.1:9999/cb'; P = 'spring.security.oauth2.authorizationserver.client.demo.'
props = {'server.port': port, 'spring.security.user.name': 'alice', 'spring.security.user.password': 'pw',
 P + 'registration.client-id': 'demo', P + 'registration.client-authentication-methods': 'none', P + 'registration.authorization-grant-types': 'authorization_code,refresh_token', P + 'registration.redirect-uris': REDIR, P + 'registration.scopes': 'openid,read,offline_access', P + 'require-proof-key': 'true', P + 'require-authorization-consent': 'false',
 'spring.security.oauth2.authorizationserver.client.conf.registration.client-id': 'conf', 'spring.security.oauth2.authorizationserver.client.conf.registration.client-secret': '{noop}s3cret', 'spring.security.oauth2.authorizationserver.client.conf.registration.client-authentication-methods': 'client_secret_basic', 'spring.security.oauth2.authorizationserver.client.conf.registration.authorization-grant-types': 'authorization_code,refresh_token', 'spring.security.oauth2.authorizationserver.client.conf.registration.redirect-uris': REDIR, 'spring.security.oauth2.authorizationserver.client.conf.registration.scopes': 'openid,read', 'spring.security.oauth2.authorizationserver.client.conf.require-authorization-consent': 'false',
 'spring.security.oauth2.authorizationserver.issuer': f'http://127.0.0.1:{port}'}
a = SApp(b, 'demo.Main', props=props, port=port, name='stdout'); a.start(timeout=90); time.sleep(1.0)
class Client:
    def __init__(self): self.cookies = {}
    def req(self, method, path, body=None, headers=None):
        h = dict(headers or {})
        if self.cookies: h['Cookie'] = '; '.join(f'{k}={v}' for k, v in self.cookies.items())
        if body is not None and 'Content-Type' not in h: h['Content-Type'] = 'application/x-www-form-urlencoded'
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=15); c.request(method, path, body=body, headers=h); r = c.getresponse(); data = r.read().decode('utf-8', 'replace'); hdr = dict((k.lower(), v) for k, v in r.getheaders()); sc = [v for k, v in r.getheaders() if k.lower() == 'set-cookie']; c.close()
        for v in sc: kv = v.split(';')[0].split('=', 1); self.cookies[kv[0]] = kv[1]
        return r.status, hdr, data
def b64u(x): return base64.urlsafe_b64encode(x).rstrip(b'=').decode()
def jwt_part(t, i): s = t.split('.')[i]; return json.loads(base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)))
SCOPE = 'openid read'; CLIENT = 'demo'
def authorize(c, extra=None, verifier=None, state='st1'):
    verifier = verifier or b64u(secrets.token_bytes(32)); challenge = b64u(hashlib.sha256(verifier.encode()).digest())
    q = {'response_type': 'code', 'client_id': CLIENT, 'redirect_uri': REDIR, 'scope': SCOPE, 'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256'}; q.update(extra or {})
    q = {k: v for k, v in q.items() if v is not None}
    HT = {'Accept': 'text/html,application/xhtml+xml'}
    st, h, body = c.req('GET', '/oauth2/authorize?' + urllib.parse.urlencode(q), headers=HT); trace = [(st, h.get('location'))]
    if st == 302 and '/login' in (h.get('location') or ''):
        st, h, body = c.req('GET', '/login', headers=HT); tok = re.search(r'name="_csrf"[^>]*value="([^"]+)"', body).group(1)
        st, h, body = c.req('POST', '/login', body=urllib.parse.urlencode({'username': 'alice', 'password': 'pw', '_csrf': tok})); trace.append((st, h.get('location')))
        if st == 302: st, h, body = c.req('GET', urllib.parse.urlparse(h['location']).path + '?' + urllib.parse.urlparse(h['location']).query, headers=HT); trace.append((st, h.get('location')))
    return verifier, st, h.get('location'), body, trace
def token(data, basic=None):
    c = Client(); hd = {'Authorization': 'Basic ' + base64.b64encode(basic.encode()).decode()} if basic else {}; st, h, body = c.req('POST', '/oauth2/token', body=urllib.parse.urlencode(data), headers=hd); return st, body
print(f'Spring Boot 4.0.8 / Spring Authorization Server(spring-boot-starter-oauth2-authorization-server);公开客户端 demo(client-authentication-methods = none),require-proof-key = true,require-authorization-consent = false,用户 alice/pw;客户端流程用 Python 手工走,没有浏览器')
print('== 一:授权码加 PKCE 的完整流程')
c = Client(); verifier, st, loc, body, trace = authorize(c)
print('  GET /oauth2/authorize 的跳转链:' + ' → '.join(f'{s} {(l or "")[:70]}' for s, l in trace))
qs = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query); code = qs.get('code', [None])[0]; print(f'  最终回到 redirect_uri,带 code(长度 {len(code) if code else 0})和 state = {qs.get("state")}')
print(f'  code_verifier 长度 {len(verifier)},code_challenge = BASE64URL(SHA256(code_verifier)),method = S256')
st, body = token({'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIR, 'client_id': 'demo', 'code_verifier': verifier}); tr = json.loads(body)
print(f'  POST /oauth2/token → HTTP {st},返回的字段 {sorted(tr)},token_type = {tr.get("token_type")},expires_in = {tr.get("expires_in")},scope = {tr.get("scope")}')
at = tr['access_token']; print(f'  access_token 是 JWT:header {jwt_part(at, 0)};claims 的键 {sorted(jwt_part(at, 1))};iss = {jwt_part(at, 1).get("iss")};sub = {jwt_part(at, 1).get("sub")};aud = {jwt_part(at, 1).get("aud")};有效期 = {jwt_part(at, 1)["exp"] - jwt_part(at, 1)["iat"]} 秒')
print(f'  id_token 的 claims 的键 {sorted(jwt_part(tr["id_token"], 1))}')
print('== 二:各种错误')
st, body = token({'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIR, 'client_id': 'demo', 'code_verifier': verifier}); print(f'  同一个 code 再换一次令牌 → HTTP {st} {body}')
c2 = Client(); v2, st2, loc2, body2, tr2 = authorize(c2); code2 = urllib.parse.parse_qs(urllib.parse.urlparse(loc2).query)['code'][0]
st, body = token({'grant_type': 'authorization_code', 'code': code2, 'redirect_uri': REDIR, 'client_id': 'demo', 'code_verifier': b64u(secrets.token_bytes(32))}); print(f'  换令牌时 code_verifier 写错 → HTTP {st} {body}')
c3 = Client(); v3, st3, loc3, body3, tr3 = authorize(c3); code3 = urllib.parse.parse_qs(urllib.parse.urlparse(loc3).query)['code'][0]
st, body = token({'grant_type': 'authorization_code', 'code': code3, 'redirect_uri': REDIR, 'client_id': 'demo'}); print(f'  换令牌时不带 code_verifier → HTTP {st} {body}')
c4 = Client(); v4, st4, loc4, body4, tr4 = authorize(c4, {'code_challenge': None, 'code_challenge_method': None}); print(f'  授权请求里不带 code_challenge(公开客户端要求 PKCE)→ 最终 HTTP {st4},Location {(loc4 or "")[:140]}')
c5 = Client(); v5, st5, loc5, body5, tr5 = authorize(c5, {'redirect_uri': 'http://127.0.0.1:9999/other'}); print(f'  授权请求里 redirect_uri 不是注册的那个 → HTTP {st5},{(loc5 or "")[:100]};页面内容 {re.sub(chr(10), " ", body5)[:200]!r}')
c6 = Client(); v6, st6, loc6, body6, tr6 = authorize(c6, {'code_challenge_method': 'plain'}); print(f'  code_challenge_method = plain → 最终 HTTP {st6},Location {(loc6 or "")[:140]}')
print('== 三:刷新令牌与发现文档')
print(f'  公开客户端 demo(client-authentication-methods = none)已注册 refresh_token 授权类型,scope 请求 "openid read" 时,令牌响应里有 refresh_token:{"refresh_token" in tr}')
SCOPE = 'openid read offline_access'; c7 = Client(); v7, st7, loc7, body7, tr7_ = authorize(c7); code7 = urllib.parse.parse_qs(urllib.parse.urlparse(loc7).query)['code'][0]
st, body = token({'grant_type': 'authorization_code', 'code': code7, 'redirect_uri': REDIR, 'client_id': 'demo', 'code_verifier': v7}); tr = json.loads(body)
print(f'  scope 再加上 offline_access 之后(仍是公开客户端):令牌响应的字段 {sorted(tr)}')
SCOPE = 'openid read'; CLIENT = 'conf'; c8 = Client(); v8, st8, loc8, body8, tr8_ = authorize(c8); code8 = urllib.parse.parse_qs(urllib.parse.urlparse(loc8).query)['code'][0]
st, body = token({'grant_type': 'authorization_code', 'code': code8, 'redirect_uri': REDIR, 'code_verifier': v8}, basic='conf:s3cret'); tr = json.loads(body)
print(f'  机密客户端 conf(client_secret_basic)+ PKCE:POST /oauth2/token → HTTP {st},返回的字段 {sorted(tr)}')
st, body = token({'grant_type': 'refresh_token', 'refresh_token': tr['refresh_token']}, basic='conf:s3cret'); rt = json.loads(body); print(f'  用 refresh_token 换新令牌 → HTTP {st},返回的字段 {sorted(rt)};新的 refresh_token 与旧的相同:{rt.get("refresh_token") == tr["refresh_token"]};新的 access_token 与旧的相同:{rt.get("access_token") == tr["access_token"]}')
st, body = token({'grant_type': 'refresh_token', 'refresh_token': tr['refresh_token']}, basic='conf:s3cret'); print(f'  再用同一个旧的 refresh_token 换一次 → HTTP {st}')
st, body = token({'grant_type': 'refresh_token', 'refresh_token': tr['refresh_token']}); print(f'  不带客户端凭据用 refresh_token → HTTP {st} {body[:80]}')
st, h, body = Client().req('GET', '/.well-known/openid-configuration'); d = json.loads(body); print(f'  /.well-known/openid-configuration → HTTP {st},issuer = {d["issuer"]},code_challenge_methods_supported = {d.get("code_challenge_methods_supported")},token_endpoint_auth_methods_supported = {d.get("token_endpoint_auth_methods_supported")},grant_types_supported = {d.get("grant_types_supported")}')
st, h, body = Client().req('GET', '/oauth2/jwks'); k = json.loads(body)['keys']; print(f'  /oauth2/jwks → HTTP {st},{len(k)} 把密钥,kty = {k[0]["kty"]},kid 长度 {len(k[0]["kid"])},use = {k[0].get("use")}')
a.stop()
