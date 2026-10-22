import sys, os, re, time, http.client, base64, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x105'); CP = scp('org.springframework.boot:spring-boot-starter-security', 'org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.annotation.*; import org.springframework.security.authentication.*; import org.springframework.security.config.Customizer; import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration; import org.springframework.security.config.annotation.web.builders.HttpSecurity; import org.springframework.security.config.http.SessionCreationPolicy; import org.springframework.security.core.*; import org.springframework.security.core.context.*; import org.springframework.security.web.SecurityFilterChain; import org.springframework.security.web.context.HttpSessionSecurityContextRepository; import org.springframework.security.web.csrf.CsrfToken; import org.springframework.web.bind.annotation.*; import jakarta.servlet.http.*; import java.util.*;\n'
FILES = {
 'src/demo/Main.java': HDR + '''
@SpringBootApplication @RestController
public class Main {
  @Bean SecurityFilterChain chain(HttpSecurity h) throws Exception {
    String cfg = System.getProperty("x105.cfg", "default");
    h.authorizeHttpRequests(a -> a.requestMatchers("/api/login-*").permitAll().anyRequest().authenticated());
    if (cfg.equals("stateless")) h.httpBasic(Customizer.withDefaults()).sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS)).csrf(c -> c.disable());
    else { h.formLogin(Customizer.withDefaults()); if (cfg.equals("fixnone")) h.sessionManagement(s -> s.sessionFixation(f -> f.none())); }
    if (!cfg.equals("default") && !cfg.equals("fixnone")) { }
    h.csrf(c -> c.ignoringRequestMatchers("/api/login-*")); return h.build(); }
  final AuthenticationConfiguration ac; Main(AuthenticationConfiguration ac) { this.ac = ac; }
  @GetMapping("/who") String who(HttpServletRequest rq) { Authentication a = SecurityContextHolder.getContext().getAuthentication(); HttpSession s = rq.getSession(false); return "用户=" + (a == null ? null : a.getName()) + ",session=" + (s == null ? "没有" : s.getId().substring(0, 8)); }
  @GetMapping("/sess") String sess(HttpServletRequest rq) { HttpSession s = rq.getSession(false); if (s == null) return "没有 session"; List<String> n = Collections.list(s.getAttributeNames()); Object ctx = s.getAttribute(HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY); return "session 属性 " + n + ",SPRING_SECURITY_CONTEXT 的类型=" + (ctx == null ? null : ctx.getClass().getSimpleName()) + ",maxInactiveInterval=" + s.getMaxInactiveInterval() + " 秒"; }
  @GetMapping("/csrf") String csrf(HttpServletRequest rq) { CsrfToken t = (CsrfToken) rq.getAttribute(CsrfToken.class.getName()); return t == null ? "无" : t.getToken(); }
  String login(String u, HttpServletRequest rq, HttpServletResponse rs, boolean save) throws Exception {
    Authentication au = ac.getAuthenticationManager().authenticate(UsernamePasswordAuthenticationToken.unauthenticated(u, "pw")); SecurityContext ctx = SecurityContextHolder.createEmptyContext(); ctx.setAuthentication(au); SecurityContextHolder.setContext(ctx);
    if (save) new HttpSessionSecurityContextRepository().saveContext(ctx, rq, rs); return "已认证 " + au.getName() + (save ? ",并保存到 SecurityContextRepository" : ",没有保存") + ";本请求内 SecurityContextHolder 里是 " + SecurityContextHolder.getContext().getAuthentication().getName(); }
  @GetMapping("/api/login-nosave") String nosave(@RequestParam String u, HttpServletRequest rq, HttpServletResponse rs) throws Exception { return login(u, rq, rs, false); }
  @GetMapping("/api/login-save") String save(@RequestParam String u, HttpServletRequest rq, HttpServletResponse rs) throws Exception { return login(u, rq, rs, true); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x105', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
class Client:
    def __init__(self, port): self.port = port; self.cookie = None
    def req(self, method, path, body=None, headers=None, follow=False):
        h = dict(headers or {})
        if self.cookie: h['Cookie'] = self.cookie
        if body is not None: h['Content-Type'] = 'application/x-www-form-urlencoded'
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10); c.request(method, path, body=body, headers=h); r = c.getresponse(); data = r.read().decode('utf-8', 'replace'); hdr = r.getheaders(); c.close()
        sc = [v for k, v in hdr if k.lower() == 'set-cookie']
        for v in sc:
            if v.startswith('JSESSIONID='): self.cookie = v.split(';')[0]
        return r.status, dict((k.lower(), v) for k, v in hdr), data, sc
def sid(c): return c.cookie.split('=')[1][:8] if c.cookie else None
def start(cfg='default'):
    port = free_port(); a = SApp(b, 'demo.Main', props={'server.port': port, 'x105.cfg': cfg, 'spring.security.user.name': 'alice', 'spring.security.user.password': 'pw'}, port=port, name='stdout'); a.start(timeout=90); time.sleep(0.5); return a, port
def form_login(c):
    st, h, body, sc = c.req('GET', '/login'); tok = re.search(r'name="_csrf"\s+type="hidden"\s+value="([^"]+)"', body) or re.search(r'name="_csrf"[^>]*value="([^"]+)"', body)
    before = sid(c); st, h, body, sc = c.req('POST', '/login', body=urllib.parse.urlencode({'username': 'alice', 'password': 'pw', '_csrf': tok.group(1)})); return st, h, sc, before
print('Spring Boot 4.0.8 / Spring Security 7;用户 alice / pw;客户端是 Python http.client,手动带 Cookie')
print('== 一:表单登录之后,登录态存在哪里')
a, port = start(); c = Client(port)
st, h, body, sc = c.req('GET', '/who'); print(f'  未登录 GET /who → HTTP {st},Location {h.get("location")}')
st, h, sc, before = form_login(c)
print(f'  访问 /login 页面时拿到的 JSESSIONID 前 8 位 = {before}(没有登录的会话);POST /login → HTTP {st},Location {h.get("location")};登录之后的 JSESSIONID 前 8 位 = {sid(c)}(与登录前{"相同" if before == sid(c) else "不同"})')
print('  登录响应的 Set-Cookie:' + ' | '.join(sc))
print('  GET /who → ' + c.req('GET', '/who')[2]); print('  GET /sess → ' + c.req('GET', '/sess')[2])
print('== 二:会话固定攻击防护(登录前后 session id 变不变)')
a.stop(); a, port = start('fixnone'); c = Client(port); st, h, sc, before = form_login(c)
print(f'  sessionFixation().none():登录前 {before},登录后 {sid(c)},{"没有变" if before == sid(c) else "变了"}'); a.stop()
print('== 三:无状态(SessionCreationPolicy.STATELESS + httpBasic)')
a, port = start('stateless'); c = Client(port); hb = {'Authorization': 'Basic ' + base64.b64encode(b'alice:pw').decode()}
st, h, body, sc = c.req('GET', '/who', headers=hb); print(f'  带 Basic 的 GET /who → HTTP {st} {body};响应有 Set-Cookie:{bool(sc)}')
st, h, body, sc = c.req('GET', '/who'); print(f'  不带凭据再请求一次 → HTTP {st}(服务端什么都没记住)'); a.stop()
print('== 四:自己写登录接口:不显式保存 SecurityContext 会怎样')
a, port = start(); 
for ep in ('/api/login-nosave', '/api/login-save'):
    c = Client(port); st, h, body, sc = c.req('GET', ep + '?u=alice'); print(f'  GET {ep} → HTTP {st} {body};Set-Cookie 条数 {len(sc)}')
    st, h, body, sc = c.req('GET', '/who'); print(f'    随后带着 Cookie GET /who → HTTP {st}' + (f',{body}' if st == 200 else f',Location {h.get("location")}'))
print('== 五:退出登录')
c = Client(port); form_login(c); tok = c.req('GET', '/csrf')[2]; old = c.cookie
st, h, body, sc = c.req('POST', '/logout', body=urllib.parse.urlencode({'_csrf': tok})); print(f'  POST /logout → HTTP {st},Location {h.get("location")};响应 Set-Cookie:{sc}')
c2 = Client(port); c2.cookie = old; st, h, body, sc = c2.req('GET', '/who'); print(f'  拿着退出前的旧 Cookie 再 GET /who → HTTP {st},Location {h.get("location")}')
a.stop()
