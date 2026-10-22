import sys, os, re, time, json, threading, http.client, http.server; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x110'); CP = scp('org.springframework.boot:spring-boot-starter-oauth2-resource-server', 'org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.annotation.*; import org.springframework.security.config.Customizer; import org.springframework.security.config.annotation.web.builders.HttpSecurity; import org.springframework.security.core.Authentication; import org.springframework.security.oauth2.core.*; import org.springframework.security.oauth2.jwt.*; import org.springframework.security.web.SecurityFilterChain; import org.springframework.web.bind.annotation.*; import java.time.Duration; import java.util.*;\n'
FILES = {
 'src/demo/Mint.java': '''package demo;
import com.nimbusds.jose.*; import com.nimbusds.jose.crypto.*; import com.nimbusds.jose.jwk.*; import com.nimbusds.jose.jwk.gen.RSAKeyGenerator; import com.nimbusds.jwt.*; import java.util.*; import java.nio.file.*;
public class Mint {
  static String sign(RSAKey k, JWTClaimsSet c) throws Exception { SignedJWT j = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(k.getKeyID()).build(), c); j.sign(new RSASSASigner(k)); return j.serialize(); }
  static JWTClaimsSet.Builder base(long expOff) { long now = System.currentTimeMillis(); return new JWTClaimsSet.Builder().issuer("https://issuer.example").subject("alice").issueTime(new Date(now - 600_000)).expirationTime(new Date(now + expOff * 1000)).claim("scope", "read write").claim("roles", List.of("ADMIN")); }
  static void r(String n, String t) { System.out.println("RES " + n + " " + t); }
  public static void main(String[] a) throws Exception {
    RSAKey k1 = new RSAKeyGenerator(2048).keyID("k1").generate(), k2 = new RSAKeyGenerator(2048).keyID("k2").generate(); String dir = a[0];
    Files.writeString(Path.of(dir, "jwks1.json"), new JWKSet(k1.toPublicJWK()).toString()); Files.writeString(Path.of(dir, "jwks2.json"), new JWKSet(k2.toPublicJWK()).toString());
    r("valid", sign(k1, base(300).build())); r("expired30", sign(k1, base(-30).build())); r("expired90", sign(k1, base(-90).build())); r("nbffuture", sign(k1, base(300).notBeforeTime(new Date(System.currentTimeMillis() + 120_000)).build()));
    r("wrongiss", sign(k1, base(300).issuer("https://evil.example").build())); r("noscope", sign(k1, base(300).claim("scope", null).build())); r("k2valid", sign(k2, base(300).build()));
    String v = sign(k1, base(300).build()); String[] p = v.split("\\\\."); String payload = new String(Base64.getUrlDecoder().decode(p[1])).replace("alice", "mallory"); r("tampered", p[0] + "." + Base64.getUrlEncoder().withoutPadding().encodeToString(payload.getBytes()) + "." + p[2]);
    String hdrNone = Base64.getUrlEncoder().withoutPadding().encodeToString("{\\"alg\\":\\"none\\",\\"typ\\":\\"JWT\\"}".getBytes()); r("algnone", hdrNone + "." + p[1] + ".");
    SignedJWT hs = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.HS256).keyID("k1").build(), base(300).build()); hs.sign(new MACSigner(k1.toPublicJWK().toRSAPublicKey().getEncoded().length < 32 ? new byte[32] : java.util.Arrays.copyOf(k1.toPublicJWK().toRSAPublicKey().getEncoded(), 64))); r("hs256", hs.serialize());
  }
}
''',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication @RestController
public class Main {
  @Bean JwtDecoder decoder() { NimbusJwtDecoder d = NimbusJwtDecoder.withJwkSetUri(System.getProperty("x110.jwks")).build(); String mode = System.getProperty("x110.mode", "default");
    OAuth2TokenValidator<Jwt> v = switch (mode) { case "strict" -> new org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator<>(new JwtTimestampValidator(Duration.ZERO)); case "issuer" -> JwtValidators.createDefaultWithIssuer("https://issuer.example"); default -> JwtValidators.createDefault(); }; d.setJwtValidator(v); return d; }
  @Bean SecurityFilterChain chain(HttpSecurity h) throws Exception { h.authorizeHttpRequests(a -> a.requestMatchers("/read").hasAuthority("SCOPE_read").requestMatchers("/admin").hasRole("ADMIN").anyRequest().authenticated()).oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults())).csrf(c -> c.disable()); return h.build(); }
  @GetMapping("/**") String any(Authentication au, jakarta.servlet.http.HttpServletRequest r) { return r.getRequestURI() + " 用户=" + au.getName() + " authorities=" + au.getAuthorities().stream().map(Object::toString).sorted().toList(); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x110', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
D = JT / 'x110_wd'; import shutil; shutil.rmtree(D, ignore_errors=True); D.mkdir(parents=True)
r = srun(b, 'demo.Mint', args=[str(D)], timeout=120); T = {l.split(' ', 1)[0]: l.split(' ', 1)[1] for l in res(r)}
if not T: print(r['out'][-1500:]); sys.exit()
STATE = {'file': 'jwks1.json', 'down': False, 'hits': 0}
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        STATE['hits'] += 1
        if STATE['down']: self.send_response(503); self.end_headers(); return
        body = (D / STATE['file']).read_bytes(); self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
jp = free_port(); srv = http.server.ThreadingHTTPServer(('127.0.0.1', jp), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
def start(mode='default'):
    port = free_port(); a = SApp(b, 'demo.Main', props={'server.port': port, 'x110.jwks': f'http://127.0.0.1:{jp}/jwks', 'x110.mode': mode}, port=port, name='stdout'); a.start(timeout=60); time.sleep(0.4); return a, port
def get(port, path, tok=None):
    h = {'Authorization': 'Bearer ' + tok} if tok else {}
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=10); c.request('GET', path, headers=h); r = c.getresponse(); body = r.read().decode(); wa = r.getheader('WWW-Authenticate'); c.close(); return r.status, wa, body
def show(label, port, path, tok):
    st, wa, body = get(port, path, tok); extra = ''
    if wa:
        m = re.search(r'error="([^"]+)"(?:, error_description="([^"]*)")?', wa); extra = f',WWW-Authenticate: {wa[:30]}…' + (f' error={m.group(1)} description={m.group(2)}' if m else '')
    print(f'  {label} → HTTP {st}' + (f',{body[:150]}' if st == 200 else '') + extra)
print('Spring Boot 4.0.8 / Spring Security 7 资源服务器(spring-boot-starter-oauth2-resource-server,Nimbus JOSE 10.4);RS256 令牌由我自己生成,JWKS 由一个本地 Python 服务提供')
print('== 一:签名与基本校验(JwtValidators.createDefault(),即只校验时间)')
a, port = start()
show('不带令牌 GET /read', port, '/read', None)
show('有效令牌 GET /read', port, '/read', T['valid']); show('有效令牌 GET /admin(令牌里有 roles = [ADMIN])', port, '/admin', T['valid']); show('没有 scope 的令牌 GET /read', port, '/read', T['noscope'])
for n, lab in (('tampered', '篡改了 payload(sub 改成 mallory)的令牌'), ('algnone', 'alg = none 的令牌'), ('hs256', 'alg = HS256、用公钥字节当密钥的令牌'), ('expired90', '过期 90 秒的令牌'), ('nbffuture', 'nbf 在 120 秒之后的令牌'), ('wrongiss', 'iss 是别的签发者的令牌')): show(lab + ' GET /read', port, '/read', T[n])
a.stop()
print('== 二:时钟偏差(默认容忍 60 秒)')
a, port = start()
show('过期 30 秒的令牌(默认)', port, '/read', T['expired30']); show('过期 90 秒的令牌(默认)', port, '/read', T['expired90']); a.stop()
a, port = start('strict'); show('过期 30 秒的令牌,JwtTimestampValidator(Duration.ZERO)', port, '/read', T['expired30']); a.stop()
a, port = start('issuer'); show('iss 不对的令牌,JwtValidators.createDefaultWithIssuer', port, '/read', T['wrongiss']); show('iss 正确的令牌,createDefaultWithIssuer', port, '/read', T['valid']); a.stop()
print('== 三:JWKS 与密钥轮换(JWKS 服务从 {k1} 切到 {k2})')
STATE.update(file='jwks1.json', down=False, hits=0); a, port = start()
show('第 1 步 JWKS = {k1}:k1 令牌', port, '/read', T['valid']); print(f'    此时 JWKS 服务被访问了 {STATE["hits"]} 次')
STATE['file'] = 'jwks2.json'; h0 = STATE['hits']; t0 = time.time(); show('第 2 步 JWKS 切成 {k2} 之后立刻:k2 令牌(kid 不在缓存里)', port, '/read', T['k2valid']); print(f'    这一步 JWKS 服务又被访问了 {STATE["hits"] - h0} 次')
show('第 3 步:k1 令牌(k2 令牌触发的那次刷新已经把缓存换成了 {k2})', port, '/read', T['valid'])
time.sleep(16); show('第 4 步 等 16 秒之后:k2 令牌', port, '/read', T['k2valid']); show('第 5 步:k1 令牌(JWKS 里已经没有 k1)', port, '/read', T['valid']); print(f'    累计 JWKS 服务被访问 {STATE["hits"]} 次')
STATE['down'] = True; show('第 6 步 JWKS 服务宕机:k2 令牌(已缓存)', port, '/read', T['k2valid']); a.stop()
STATE['down'] = True; a, port = start(); show('JWKS 服务宕机时刚启动的应用:k2 令牌', port, '/read', T['k2valid']); a.stop()
print('== 四:scope 与 roles 怎么变成 authorities')
STATE.update(file='jwks1.json', down=False); a, port = start(); show('GET /read(令牌 scope = "read write")', port, '/read', T['valid']); show('GET /anything', port, '/anything', T['valid']); a.stop()
srv.shutdown()
