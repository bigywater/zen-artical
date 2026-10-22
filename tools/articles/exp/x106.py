import sys, os, re, time, http.client, base64, urllib.parse, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x106'); CP = scp('org.springframework.boot:spring-boot-starter-security', 'org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.annotation.*; import org.springframework.security.config.Customizer; import org.springframework.security.config.annotation.web.builders.HttpSecurity; import org.springframework.security.web.SecurityFilterChain; import org.springframework.security.web.csrf.*; import org.springframework.web.bind.annotation.*; import jakarta.servlet.http.*; import java.util.*;\n'
FILES = {
 'src/demo/Main.java': HDR + '''
@SpringBootApplication @RestController
public class Main {
  @Bean SecurityFilterChain chain(HttpSecurity h) throws Exception {
    String cfg = System.getProperty("x106.cfg", "default"); h.authorizeHttpRequests(a -> a.anyRequest().authenticated()).formLogin(Customizer.withDefaults());
    if (cfg.equals("cookie")) h.csrf(c -> c.csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse()));
    else if (cfg.equals("cookie-spa")) h.csrf(c -> c.csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse()).csrfTokenRequestHandler(new CsrfTokenRequestAttributeHandler()));
    else if (cfg.equals("ignoring")) h.csrf(c -> c.ignoringRequestMatchers("/api/**"));
    else if (cfg.equals("disabled")) h.csrf(c -> c.disable());
    return h.build(); }
  @GetMapping("/csrf") String csrf(HttpServletRequest rq) { CsrfToken t = (CsrfToken) rq.getAttribute(CsrfToken.class.getName()); String raw = ""; HttpSession s = rq.getSession(false); if (s != null) for (String n : Collections.list(s.getAttributeNames())) if (n.contains("CSRF")) { Object v = s.getAttribute(n); if (v instanceof CsrfToken ct) raw = ct.getToken(); } return t.getHeaderName() + "|" + t.getParameterName() + "|" + t.getToken() + "|" + raw; }
  @PostMapping("/post") String post() { return "posted"; }
  @PostMapping("/api/post") String apiPost() { return "api posted"; }
  @DeleteMapping("/item") String del() { return "deleted"; }
  @GetMapping("/who") String who() { return "ok"; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x106', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
class Client:
    def __init__(self, port): self.port = port; self.cookies = {}
    def req(self, method, path, body=None, headers=None):
        h = dict(headers or {})
        if self.cookies: h['Cookie'] = '; '.join(f'{k}={v}' for k, v in self.cookies.items())
        if body is not None: h['Content-Type'] = 'application/x-www-form-urlencoded'
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10); c.request(method, path, body=body, headers=h); r = c.getresponse(); data = r.read().decode('utf-8', 'replace'); hdr = r.getheaders(); c.close()
        sc = [v for k, v in hdr if k.lower() == 'set-cookie']
        for v in sc:
            kv = v.split(';')[0].split('=', 1); self.cookies[kv[0]] = kv[1]
        return r.status, dict((k.lower(), v) for k, v in hdr), data, sc
def start(cfg='default'):
    port = free_port(); a = SApp(b, 'demo.Main', props={'server.port': port, 'x106.cfg': cfg, 'spring.security.user.name': 'alice', 'spring.security.user.password': 'pw'}, port=port, name='stdout'); a.start(timeout=90); time.sleep(0.5); return a, Client(port)
def login(c):
    st, h, body, sc = c.req('GET', '/login'); m = re.search(r'name="_csrf"[^>]*value="([^"]+)"', body); tok = m.group(1) if m else None
    d = {'username': 'alice', 'password': 'pw'}
    if tok: d['_csrf'] = tok
    return c.req('POST', '/login', body=urllib.parse.urlencode(d)), tok
def tokens(c):
    st, h, body, sc = c.req('GET', '/csrf'); hn, pn, masked, raw = body.split('|'); return hn, pn, masked, raw
def msg(c, body_headers=None):
    return None
def post(c, path='/post', method='POST', headers=None, body=''):
    st, h, data, sc = c.req(method, path, body=body, headers=headers); return st, data[:120].replace('\n', ' ')
print('Spring Boot 4.0.8 / Spring Security 7;用户 alice / pw;表单登录;默认 CSRF 防护;Python http.client 手动带 Cookie')
print('== 一:默认配置下令牌是什么样')
a, c = start(); login(c)
hn, pn, m1, raw = tokens(c); _, _, m2, raw2 = tokens(c)
print(f'  令牌的请求头名 = {hn},请求参数名 = {pn}')
print(f'  同一个会话里连续取两次令牌:第 1 次 {m1}(长度 {len(m1)});第 2 次 {m2}(长度 {len(m2)});两次相同:{m1 == m2}')
print('  各种带法 POST /post:')
for lab, kw in (('不带令牌', {}), ('用请求头 X-CSRF-TOKEN 带第 1 次的令牌', {'headers': {hn: m1}}), ('用请求头带第 2 次的令牌(同一会话里另一个掩码)', {'headers': {hn: m2}}), ('用请求头带一个随便写的令牌', {'headers': {hn: 'abc'}}), ('用表单参数 _csrf 带令牌', {'body': f'{pn}=' + urllib.parse.quote(m1)})):
    print(f'    {lab} → ' + str(post(c, **kw)))
print('  不同的 HTTP 方法(不带令牌):GET /who → ' + str(c.req('GET', '/who')[0]) + ';POST /post → ' + str(post(c)[0]) + ';DELETE /item → ' + str(post(c, '/item', 'DELETE')[0]) + ';HEAD /who → ' + str(c.req('HEAD', '/who')[0]) + ';OPTIONS /who → ' + str(c.req('OPTIONS', '/who')[0]))
print('== 二:登录之前取到的令牌,登录之后还能用吗')
a.stop(); a, c = start(); st, h, body, sc = c.req('GET', '/login'); pre = re.search(r'name="_csrf"[^>]*value="([^"]+)"', body).group(1)
st, h, _, _ = c.req('POST', '/login', body=urllib.parse.urlencode({'username': 'alice', 'password': 'pw', '_csrf': pre})); hn, pn, post_m, _ = tokens(c)
print(f'  登录页里的令牌 {pre[:12]}…(登录用的);登录成功 → HTTP {st}')
print('  登录之后用登录页那个旧令牌 POST /post → ' + str(post(c, headers={'X-CSRF-TOKEN': pre})))
print('  登录之后取到新令牌再 POST /post → ' + str(post(c, headers={'X-CSRF-TOKEN': post_m})))
print('== 三:单页应用常用的 CookieCsrfTokenRepository')
for cfg, lab in (('cookie', 'CookieCsrfTokenRepository.withHttpOnlyFalse() + 默认的请求处理器'), ('cookie-spa', 'CookieCsrfTokenRepository.withHttpOnlyFalse() + CsrfTokenRequestAttributeHandler(明文)')):
    a.stop(); a, c = start(cfg); login(c); c.req('GET', '/who'); xsrf = c.cookies.get('XSRF-TOKEN')
    hn, pn, masked, raw = tokens(c); xsrf = c.cookies.get('XSRF-TOKEN')
    print(f'  {lab}:Cookie XSRF-TOKEN = {xsrf[:12] if xsrf else None}…(长度 {len(xsrf) if xsrf else 0});/csrf 接口给出的令牌长度 {len(masked)}')
    print('    把 Cookie 里的值原样放进 X-XSRF-TOKEN 请求头 POST /post → ' + str(post(c, headers={'X-XSRF-TOKEN': xsrf})))
    print('    用 /csrf 接口给出的令牌放进 X-XSRF-TOKEN 请求头 → ' + str(post(c, headers={'X-XSRF-TOKEN': masked})))
print('== 四:放行与关闭')
a.stop(); a, c = start('ignoring'); login(c); print('  csrf.ignoringRequestMatchers("/api/**"):POST /api/post 不带令牌 → ' + str(post(c, '/api/post')) + ';POST /post 不带令牌 → ' + str(post(c)))
a.stop(); a, c = start('disabled'); login(c); print('  csrf.disable():POST /post 不带令牌 → ' + str(post(c)))
a.stop()
