import sys, os, re, time, http.client, base64; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x107'); CP = scp('org.springframework.boot:spring-boot-starter-security', 'org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.annotation.*; import org.springframework.security.config.Customizer; import org.springframework.security.config.annotation.web.builders.HttpSecurity; import org.springframework.security.web.SecurityFilterChain; import org.springframework.web.bind.annotation.*; import org.springframework.web.servlet.config.annotation.*; import org.springframework.web.cors.*; import java.util.*;\n'
FILES = {
 'src/demo/Main.java': HDR + '''
@SpringBootApplication @RestController
public class Main {
  static String cfg() { return System.getProperty("x107.cfg", "mvc-only"); }
  @Bean SecurityFilterChain chain(HttpSecurity h) throws Exception { h.authorizeHttpRequests(a -> a.anyRequest().authenticated()).httpBasic(Customizer.withDefaults()).csrf(c -> c.disable()); if (cfg().equals("security-cors") || cfg().equals("patterns") || cfg().equals("star-credentials")) h.cors(Customizer.withDefaults()); return h.build(); }
  @Bean WebMvcConfigurer mvc() { return new WebMvcConfigurer() { public void addCorsMappings(CorsRegistry r) { if (cfg().equals("mvc-only") || cfg().equals("security-cors")) r.addMapping("/api/**").allowedOrigins("https://app.example").allowedMethods("GET", "POST", "PUT").allowedHeaders("Content-Type", "X-Token").allowCredentials(true); } }; }
  @Bean("corsConfigurationSource") @org.springframework.context.annotation.Conditional(StarCond.class) CorsConfigurationSource src() { CorsConfiguration c = new CorsConfiguration(); if (cfg().equals("star-credentials")) c.setAllowedOrigins(List.of("*")); else c.setAllowedOriginPatterns(List.of("https://*.example")); c.setAllowedMethods(List.of("GET", "POST")); c.setAllowedHeaders(List.of("*")); c.setAllowCredentials(true); UrlBasedCorsConfigurationSource s = new UrlBasedCorsConfigurationSource(); s.registerCorsConfiguration("/api/**", c); return s; }
  static class StarCond implements org.springframework.context.annotation.Condition { public boolean matches(org.springframework.context.annotation.ConditionContext c, org.springframework.core.type.AnnotatedTypeMetadata m) { return cfg().equals("star-credentials") || cfg().equals("patterns"); } }
  @GetMapping("/api/data") String data() { return "data"; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x107', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
BASIC = {'Authorization': 'Basic ' + base64.b64encode(b'alice:pw').decode()}
def req(port, method, path, headers):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=10); c.request(method, path, headers=headers); r = c.getresponse(); body = r.read().decode('utf-8', 'replace'); h = dict((k.lower(), v) for k, v in r.getheaders()); c.close(); return r.status, h, body
def cors_h(h): return {k: v for k, v in h.items() if k.startswith('access-control') or k == 'vary' or k == 'www-authenticate'}
def start(cfg):
    port = free_port(); a = SApp(b, 'demo.Main', props={'server.port': port, 'x107.cfg': cfg, 'spring.security.user.name': 'alice', 'spring.security.user.password': 'pw'}, port=port, name='stdout')
    try: a.start(timeout=60); time.sleep(0.4); return a, port, None
    except RuntimeError: 
        txt = a.logf.read_text(); msg = [x.strip() for x in txt.splitlines() if 'allowCredentials' in x or 'IllegalArgumentException' in x][:2]; a.stop(); return None, None, ' | '.join(m[:420] for m in msg)
PRE = {'Origin': 'https://app.example', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type,x-token'}
print('Spring Boot 4.0.8 / Spring Security 7 / Spring MVC;/api/data 需要 Basic 认证(alice/pw);浏览器的跨域预检 = 不带凭据的 OPTIONS + Origin + Access-Control-Request-*')
print('== 一:MVC 里配了 CORS(addCorsMappings),Security 没有 .cors()')
a, port, e = start('mvc-only')
st, h, body = req(port, 'OPTIONS', '/api/data', PRE); print(f'  预检 OPTIONS /api/data(Origin https://app.example)→ HTTP {st},相关响应头 {cors_h(h)}')
st, h, body = req(port, 'GET', '/api/data', dict(BASIC, Origin='https://app.example')); print(f'  带凭据的 GET /api/data(Origin https://app.example)→ HTTP {st},相关响应头 {cors_h(h)}')
st, h, body = req(port, 'GET', '/api/data', dict(BASIC, Origin='https://evil.example')); print(f'  带凭据的 GET /api/data(Origin https://evil.example)→ HTTP {st} {body[:60]},相关响应头 {cors_h(h)}')
a.stop()
print('== 二:Security 里加上 http.cors(Customizer.withDefaults())')
a, port, e = start('security-cors')
st, h, body = req(port, 'OPTIONS', '/api/data', PRE); print(f'  预检(允许的 Origin)→ HTTP {st},相关响应头 {cors_h(h)}')
st, h, body = req(port, 'OPTIONS', '/api/data', dict(PRE, Origin='https://evil.example')); print(f'  预检(不在允许列表里的 Origin https://evil.example)→ HTTP {st} {body[:40]},相关响应头 {cors_h(h)}')
st, h, body = req(port, 'OPTIONS', '/api/data', dict(PRE, **{'Access-Control-Request-Method': 'DELETE'})); print(f'  预检(请求方法 DELETE 不在允许列表里)→ HTTP {st} {body[:40]}')
st, h, body = req(port, 'OPTIONS', '/api/data', dict(PRE, **{'Access-Control-Request-Headers': 'x-other'})); print(f'  预检(请求头 x-other 不在允许列表里)→ HTTP {st} {body[:40]}')
st, h, body = req(port, 'GET', '/api/data', dict(BASIC, Origin='https://app.example')); print(f'  带凭据的 GET → HTTP {st},相关响应头 {cors_h(h)}')
a.stop()
print('== 三:全局 CorsConfigurationSource:allowCredentials 与通配')
a, port, e = start('star-credentials'); print('  setAllowedOrigins(["*"]) + setAllowCredentials(true):' + ('应用启动成功' if a else '应用启动失败:' + e))
if a:
    st, h, body = req(port, 'OPTIONS', '/api/data', PRE); print(f'    但预检请求 → HTTP {st} {body[:100]},相关响应头 {cors_h(h)}')
    lg = [x.strip() for x in a.log().splitlines() if 'allowCredentials' in x or 'IllegalArgumentException' in x][:1]; print('    服务端日志:' + (lg[0][:420] if lg else '(无)'))
    a.stop()
a, port, e = start('patterns')
if a:
    st, h, body = req(port, 'OPTIONS', '/api/data', dict(PRE, Origin='https://shop.example')); print(f'  setAllowedOriginPatterns(["https://*.example"]) + allowCredentials(true):预检 Origin https://shop.example → HTTP {st},相关响应头 {cors_h(h)}')
    st, h, body = req(port, 'OPTIONS', '/api/data', dict(PRE, Origin='https://shop.other')); print(f'    预检 Origin https://shop.other → HTTP {st} {body[:40]}')
    a.stop()
