import sys, os, re, time, http.client, base64, ssl, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x113'); CP = scp('org.springframework.boot:spring-boot-starter-security', 'org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
FILES = {
 'src/demo/Main.java': '''package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.web.server.WebServerFactoryCustomizer; import org.springframework.boot.tomcat.servlet.TomcatServletWebServerFactory; import org.springframework.context.annotation.*; import org.springframework.security.config.Customizer; import org.springframework.security.config.annotation.web.builders.HttpSecurity; import org.springframework.security.web.SecurityFilterChain; import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter.ReferrerPolicy; import org.springframework.web.bind.annotation.*; import org.springframework.http.*; import java.time.Duration;
@SpringBootApplication @RestController
public class Main {
  static String cfg() { return System.getProperty("x113.cfg", "default"); }
  @Bean SecurityFilterChain chain(HttpSecurity h) throws Exception {
    h.authorizeHttpRequests(a -> a.anyRequest().authenticated()).httpBasic(Customizer.withDefaults()).csrf(c -> c.disable());
    String c = cfg();
    if (c.equals("custom")) h.headers(hd -> hd.contentSecurityPolicy(p -> p.policyDirectives("default-src 'self'")).frameOptions(f -> f.sameOrigin()).referrerPolicy(r -> r.policy(ReferrerPolicy.SAME_ORIGIN)).permissionsPolicyHeader(p -> p.policy("geolocation=()")));
    if (c.equals("off")) h.headers(hd -> hd.disable());
    if (c.equals("channel")) h.requiresChannel(ch -> ch.anyRequest().requiresSecure());
    if (c.startsWith("secure")) { h.redirectToHttps(Customizer.withDefaults()); h.portMapper(pm -> pm.http(Integer.getInteger("x113.http")).mapsTo(Integer.getInteger("x113.https"))); }
    if (c.equals("secure-hsts")) h.headers(hd -> hd.httpStrictTransportSecurity(s -> s.maxAgeInSeconds(600).includeSubDomains(false)));
    return h.build();
  }
  @Bean WebServerFactoryCustomizer<TomcatServletWebServerFactory> extra() { return f -> { if (Boolean.getBoolean("x113.extra")) { var cn = new org.apache.catalina.connector.Connector("HTTP/1.1"); cn.setPort(Integer.getInteger("x113.http")); f.addAdditionalConnectors(cn); } }; }
  @GetMapping("/hello") String hello() { return "hi"; }
  @GetMapping("/cached") ResponseEntity<String> cached() { return ResponseEntity.ok().cacheControl(CacheControl.maxAge(Duration.ofSeconds(60))).body("c"); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
''',
 'static/a.txt': 'static file\n',
 'logback.xml': LOG,
}
b = sbuild('x113', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
BASIC = {'Authorization': 'Basic ' + base64.b64encode(b'alice:pw').decode()}
SKIP = {'date', 'content-length', 'content-type', 'keep-alive', 'connection', 'set-cookie', 'transfer-encoding'}
def req(port, path, headers=None, https=False):
    c = http.client.HTTPSConnection('127.0.0.1', port, timeout=10, context=ssl._create_unverified_context()) if https else http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    c.request('GET', path, headers=headers or {}); r = c.getresponse(); body = r.read().decode('utf-8', 'replace'); h = dict((k.lower(), v) for k, v in r.getheaders()); c.close(); return r.status, h, body
def hs(h): return '; '.join(f'{k}: {v}' for k, v in sorted(h.items()) if k not in SKIP) or '(没有安全相关的头)'
def start(cfg, **props):
    port = free_port(); p = {'server.port': port, 'x113.cfg': cfg, 'spring.security.user.name': 'alice', 'spring.security.user.password': 'pw'}; p.update(props)
    a = SApp(b, 'demo.Main', props=p, port=p['server.port'], name='app'); a.start(timeout=60); time.sleep(0.3); return a, p['server.port']
print('Spring Boot 4.0.8 / Spring Security 7;所有接口需要 Basic 认证(alice/pw);下面列出的是响应头(不含 Date、Content-Length、Content-Type 等)')
print('== 一:默认配置下的响应头(明文 HTTP)')
a, port = start('default')
for label, path, hd in [('GET /hello(带凭据)', '/hello', BASIC), ('GET /hello(不带凭据)', '/hello', {}), ('GET /nope(带凭据,不存在)', '/nope', BASIC), ('GET /cached(带凭据,控制器自己设了 Cache-Control: max-age=60)', '/cached', BASIC), ('GET /a.txt(带凭据,classpath 的静态文件)', '/a.txt', BASIC)]:
    st, h, body = req(port, path, hd); print(f'  {label} → HTTP {st};{hs(h)}')
a.stop()
print('== 二:自定义与关闭')
a, port = start('custom'); st, h, body = req(port, '/hello', BASIC); print(f'  自定义 CSP、frameOptions(sameOrigin)、referrerPolicy(same-origin)、permissionsPolicy → HTTP {st};{hs(h)}'); a.stop()
a, port = start('off'); st, h, body = req(port, '/hello', BASIC); print(f'  headers.disable() → HTTP {st};{hs(h)}'); a.stop()
print('== 三:HSTS 与 HTTP → HTTPS 重定向(Tomcat 开 TLS,自签证书;另开一个 HTTP 连接器;重定向用 http.redirectToHttps())')
ks = b['dir'] / 'ks.p12'
if ks.exists(): ks.unlink()
subprocess.run(['keytool', '-genkeypair', '-alias', 'a', '-keyalg', 'RSA', '-keysize', '2048', '-storetype', 'PKCE'.replace('PKCE', 'PKCS12'), '-keystore', str(ks), '-storepass', 'changeit', '-dname', 'CN=localhost', '-validity', '3'], capture_output=True, check=True)
hp, sp = free_port(), free_port()
for cfg in ('secure', 'secure-hsts'):
    a, port = start(cfg, **{'server.port': sp, 'server.ssl.key-store': str(ks), 'server.ssl.key-store-password': 'changeit', 'server.ssl.key-store-type': 'PKCS12', 'x113.extra': 'true', 'x113.http': hp, 'x113.https': sp})
    st, h, body = req(sp, '/hello', BASIC, https=True); print(f'  [{cfg}] HTTPS GET /hello → HTTP {st};{hs(h)}')
    if cfg == 'secure':
        st, h, body = req(hp, '/hello?x=1', BASIC); print(f'  [{cfg}] HTTP(端口映射 {"http→https"})GET /hello?x=1 → HTTP {st};Location {h.get("location", "").replace(str(sp), "<https 端口>").replace(str(hp), "<http 端口>")};{hs({k: v for k, v in h.items() if k != "location"})}')
    a.stop()
a_fail = None
try: a, port = start('channel')
except RuntimeError as e: a_fail = [l.strip() for l in str(e).splitlines() if 'Caused by' in l][-2:]
print('  requiresChannel(c -> c.anyRequest().requiresSecure())(Spring Security 6 的老写法)→ ' + (' | '.join(a_fail) if a_fail else '启动成功'))
if not a_fail: a.stop()
print('== 四:放在反向代理后面(Tomcat 只收明文 HTTP,代理用 X-Forwarded-Proto: https 告诉后端)')
for label, props in [('没有配置转发头策略', {}), ('server.forward-headers-strategy=framework', {'server.forward-headers-strategy': 'framework'}), ('server.forward-headers-strategy=native', {'server.forward-headers-strategy': 'native'})]:
    hpp = free_port(); a, port = start('secure', **{'server.port': hpp, 'x113.http': hpp, 'x113.https': 9999, **props})
    st, h, body = req(port, '/hello', BASIC); print(f'  [{label}] 不带 X-Forwarded-Proto → HTTP {st},Location {h.get("location", "-").replace(str(hpp), "<本端口>")}')
    st, h, body = req(port, '/hello', dict(BASIC, **{'X-Forwarded-Proto': 'https'})); print(f'  [{label}] 带 X-Forwarded-Proto: https → HTTP {st},Location {h.get("location", "-").replace(str(hpp), "<本端口>")},HSTS {h.get("strict-transport-security", "无")}')
    a.stop()
