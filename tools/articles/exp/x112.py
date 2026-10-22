import sys, os, re, time, json, base64, http.client, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x112'); CP_AS = scp('org.springframework.boot:spring-boot-starter-oauth2-authorization-server', 'org.springframework.boot:spring-boot-starter-webmvc'); CP_CL = scp('org.springframework.boot:spring-boot-starter-oauth2-client', 'org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN_AS = '''package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication public class Main { public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); } }
'''
MAIN_CL = '''package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.security.core.Authentication; import org.springframework.security.oauth2.client.OAuth2AuthorizedClient; import org.springframework.security.oauth2.client.annotation.RegisteredOAuth2AuthorizedClient; import org.springframework.security.oauth2.core.oidc.user.OidcUser; import org.springframework.security.core.annotation.AuthenticationPrincipal; import org.springframework.web.bind.annotation.*; import jakarta.servlet.http.*; import java.util.*;
@SpringBootApplication @RestController
public class Main {
  @GetMapping("/me") String me(@AuthenticationPrincipal OidcUser u, Authentication au) { return "principal 类型=" + au.getPrincipal().getClass().getSimpleName() + ",name=" + au.getName() + ",authorities=" + au.getAuthorities().stream().map(Object::toString).filter(s -> !s.startsWith("FACTOR")).sorted().toList() + ",id_token 的 claims 键=" + new TreeSet<>(u.getClaims().keySet()); }
  @GetMapping("/token") String token(@RegisteredOAuth2AuthorizedClient("demo") OAuth2AuthorizedClient c) { var at = c.getAccessToken(); var rt = c.getRefreshToken(); return "access_token 前 12 位=" + at.getTokenValue().substring(0, 12) + "…末 8 位=" + at.getTokenValue().substring(at.getTokenValue().length() - 8) + ",签发=" + at.getIssuedAt() + ",过期=" + at.getExpiresAt() + ",scopes=" + new TreeSet<>(at.getScopes()) + ",refresh_token=" + (rt == null ? "没有" : "有"); }
  @org.springframework.beans.factory.annotation.Autowired org.springframework.context.ApplicationContext ctx;
  @GetMapping("/store") String store() { var repo = ctx.getBean(org.springframework.security.oauth2.client.web.OAuth2AuthorizedClientRepository.class); var svc = ctx.getBeansOfType(org.springframework.security.oauth2.client.OAuth2AuthorizedClientService.class); return "OAuth2AuthorizedClientRepository = " + repo.getClass().getSimpleName() + ";OAuth2AuthorizedClientService = " + svc.values().stream().map(x -> x.getClass().getSimpleName()).toList(); }
  @GetMapping("/sess") String sess(HttpServletRequest rq) { HttpSession s = rq.getSession(false); return s == null ? "没有 session" : "session 属性 " + Collections.list(s.getAttributeNames()); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b_as = sbuild('x112as', {'src/demo/Main.java': MAIN_AS, 'logback.xml': LOG}, CP_AS); b_cl = sbuild('x112cl', {'src/demo/Main.java': MAIN_CL, 'logback.xml': LOG}, CP_CL)
for x in (b_as, b_cl):
    if x['crc'] != 0: print(x['cout']); sys.exit()
asp, clp = free_port(), free_port(); REDIR = f'http://127.0.0.1:{clp}/login/oauth2/code/demo'; P = 'spring.security.oauth2.authorizationserver.client.conf.'
as_props = {'server.port': asp, 'spring.security.user.name': 'alice', 'spring.security.user.password': 'pw', 'spring.security.oauth2.authorizationserver.issuer': f'http://127.0.0.1:{asp}',
 P + 'registration.client-id': 'conf', P + 'registration.client-secret': '{noop}s3cret', P + 'registration.client-authentication-methods': 'client_secret_basic', P + 'registration.authorization-grant-types': 'authorization_code,refresh_token', P + 'registration.redirect-uris': REDIR, P + 'registration.scopes': 'openid,read', P + 'require-authorization-consent': 'false', P + 'token.access-token-time-to-live': '62s'}
cl_props = lambda: {'server.port': clp, 'spring.security.oauth2.client.registration.demo.client-id': 'conf', 'spring.security.oauth2.client.registration.demo.client-secret': 's3cret', 'spring.security.oauth2.client.registration.demo.authorization-grant-type': 'authorization_code', 'spring.security.oauth2.client.registration.demo.scope': 'openid,read', 'spring.security.oauth2.client.registration.demo.provider': 'as', 'spring.security.oauth2.client.provider.as.issuer-uri': f'http://127.0.0.1:{asp}'}
class Jar:
    def __init__(self): self.c = {}
jars = {asp: Jar(), clp: Jar()}
def req(port, method, path, body=None, headers=None):
    h = dict(headers or {}); h['Accept'] = 'text/html,application/xhtml+xml'; j = jars[port]
    if j.c: h['Cookie'] = '; '.join(f'{k}={v}' for k, v in j.c.items())
    if body is not None: h['Content-Type'] = 'application/x-www-form-urlencoded'
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=20); c.request(method, path, body=body, headers=h); r = c.getresponse(); data = r.read().decode('utf-8', 'replace'); hdr = dict((k.lower(), v) for k, v in r.getheaders()); sc = [v for k, v in r.getheaders() if k.lower() == 'set-cookie']; c.close()
    for v in sc: kv = v.split(';')[0].split('=', 1); j.c[kv[0]] = kv[1]
    return r.status, hdr, data
def follow(url, first=None, trace=None):
    u = urllib.parse.urlparse(url); st, h, body = req(u.port, 'GET', u.path + ('?' + u.query if u.query else ''))
    if trace is not None: trace.append(f'{st} {u.port}{u.path}')
    return st, h, body
def login_flow():
    trace = []; st, h, body = req(clp, 'GET', '/oauth2/authorization/demo'); trace.append(f'{st} 客户端 /oauth2/authorization/demo'); loc = h['location']; authreq = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
    st, h, body = follow(loc, trace=trace)
    if st == 302 and '/login' in h['location']:
        st, h, body = follow(h['location'], trace=trace); tok = re.search(r'name="_csrf"[^>]*value="([^"]+)"', body).group(1)
        st, h, body = req(asp, 'POST', '/login', body=urllib.parse.urlencode({'username': 'alice', 'password': 'pw', '_csrf': tok})); trace.append(f'{st} AS POST /login'); st, h, body = follow(h['location'], trace=trace)
    while st == 302:
        st, h, body = follow(h['location'], trace=trace)
        if urllib.parse.urlparse(h.get('location', '')).port is None: break
    return trace, authreq
print('Spring Boot 4.0.8 / Spring Security 7 OAuth2 Client(oauth2Login)+ Spring Authorization Server;机密客户端 conf(client_secret_basic),access token 的有效期被设成 62 秒;全程用 Python 手工带 Cookie')
asa = SApp(b_as, 'demo.Main', props=as_props, port=asp, name='as'); asa.start(timeout=90); time.sleep(1.0)
cla = SApp(b_cl, 'demo.Main', props=cl_props(), port=clp, name='cl'); cla.start(timeout=90); time.sleep(1.0)
print('== 一:oauth2Login 的完整跳转与登录之后的 principal')
trace, authreq = login_flow(); print('  跳转链:' + ' → '.join(trace))
print('  客户端发给授权服务器的授权请求参数:' + str({k: (v[0][:20] + ('…' if len(v[0]) > 20 else '')) for k, v in authreq.items()}))
st, h, body = req(clp, 'GET', '/me'); print(f'  GET /me → HTTP {st} {body[:400]}')
print('  GET /sess → ' + req(clp, 'GET', '/sess')[2]); print('  GET /store → ' + req(clp, 'GET', '/store')[2])
print('== 二:令牌的存放与自动刷新')
st, h, t1 = req(clp, 'GET', '/token'); print(f'  登录完立刻 GET /token → HTTP {st} {t1}')
print('  等 4 秒(access token 的有效期是 62 秒,客户端提前 60 秒就认为快过期了)……'); time.sleep(4)
st, h, t2 = req(clp, 'GET', '/token'); print(f'  再 GET /token → HTTP {st} {t2}')
m1 = re.search(r'前 12 位=(\S+?)…末 8 位=(\S+?),', t1); m2 = re.search(r'前 12 位=(\S+?)…末 8 位=(\S+?),', t2)
print(f'  两次的 access_token 末 8 位:{m1.group(2) if m1 else None} 与 {m2.group(2) if m2 else None},{"相同(没有刷新)" if m1 and m2 and m1.group(2) == m2.group(2) else "不同(用 refresh_token 换了新的)"}')
print('== 三:客户端应用重启之后')
old = dict(jars[clp].c); cla.stop(); cla = SApp(b_cl, 'demo.Main', props=cl_props(), port=clp, name='cl'); cla.start(timeout=90); time.sleep(1.0)
st, h, body = req(clp, 'GET', '/token'); print(f'  带着重启之前的 JSESSIONID GET /token → HTTP {st},Location {h.get("location")}')
cla.stop(); asa.stop()
