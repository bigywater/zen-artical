import sys, os, re, time, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x102'); CP = scp('org.springframework.boot:spring-boot-starter-security', 'org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty; import org.springframework.context.annotation.*; import org.springframework.core.annotation.Order; import org.springframework.security.config.Customizer; import org.springframework.security.config.annotation.web.builders.HttpSecurity; import org.springframework.security.config.annotation.web.configuration.WebSecurityCustomizer; import org.springframework.security.web.SecurityFilterChain; import org.springframework.security.web.FilterChainProxy; import org.springframework.security.web.DefaultSecurityFilterChain; import org.springframework.web.bind.annotation.*; import java.util.*;\n'
FILES = {
 'src/demo/Cfgs.java': HDR + '''
@Configuration class CfgTwo {
  @Bean @ConditionalOnProperty(name = "x102.cfg", havingValue = "two") @Order(1) SecurityFilterChain api(HttpSecurity h) throws Exception { return h.securityMatcher("/api/**").authorizeHttpRequests(a -> a.anyRequest().authenticated()).httpBasic(Customizer.withDefaults()).csrf(c -> c.disable()).build(); }
  @Bean @ConditionalOnProperty(name = "x102.cfg", havingValue = "two") @Order(2) SecurityFilterChain web(HttpSecurity h) throws Exception { return h.authorizeHttpRequests(a -> a.requestMatchers("/open/**").permitAll().anyRequest().authenticated()).formLogin(Customizer.withDefaults()).build(); }
  @Bean @ConditionalOnProperty(name = "x102.cfg", havingValue = "two-error") @Order(1) SecurityFilterChain api2(HttpSecurity h) throws Exception { return h.securityMatcher("/api/**").authorizeHttpRequests(a -> a.anyRequest().authenticated()).httpBasic(Customizer.withDefaults()).csrf(c -> c.disable()).build(); }
  @Bean @ConditionalOnProperty(name = "x102.cfg", havingValue = "two-error") @Order(2) SecurityFilterChain web2(HttpSecurity h) throws Exception { return h.authorizeHttpRequests(a -> a.requestMatchers("/open/**", "/error").permitAll().anyRequest().authenticated()).formLogin(Customizer.withDefaults()).build(); }
}
@Configuration class CfgMis {
  @Bean @ConditionalOnProperty(name = "x102.cfg", havingValue = "misordered") @Order(1) SecurityFilterChain web(HttpSecurity h) throws Exception { return h.authorizeHttpRequests(a -> a.anyRequest().authenticated()).formLogin(Customizer.withDefaults()).build(); }
  @Bean @ConditionalOnProperty(name = "x102.cfg", havingValue = "misordered") @Order(2) SecurityFilterChain api(HttpSecurity h) throws Exception { return h.securityMatcher("/api/**").authorizeHttpRequests(a -> a.anyRequest().authenticated()).httpBasic(Customizer.withDefaults()).build(); }
}
@Configuration class CfgIgn {
  @Bean @ConditionalOnProperty(name = "x102.cfg", havingValue = "ignoring") WebSecurityCustomizer ign() { return w -> w.ignoring().requestMatchers("/ignored/**"); }
  @Bean @ConditionalOnProperty(name = "x102.cfg", havingValue = "ignoring") SecurityFilterChain c(HttpSecurity h) throws Exception { return h.authorizeHttpRequests(a -> a.requestMatchers("/permitted/**").permitAll().anyRequest().authenticated()).build(); }
}
''',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication @RestController
public class Main {
  @GetMapping("/**") String any(jakarta.servlet.http.HttpServletRequest r) { return "ok " + r.getRequestURI(); }
  static void r(String s) { System.out.println("RES " + s); }
  public static void main(String[] a) {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a); FilterChainProxy fcp = c.getBean(FilterChainProxy.class);
    for (var e : c.getBeansOfType(org.springframework.boot.web.servlet.DelegatingFilterProxyRegistrationBean.class).entrySet()) r("Servlet 容器里登记的 DelegatingFilterProxy:name=" + e.getValue().getFilterName() + ",order=" + e.getValue().getOrder());
    r("FilterChainProxy 里有 " + fcp.getFilterChains().size() + " 条 SecurityFilterChain");
    int i = 0; for (var ch : fcp.getFilterChains()) { i++; r("  链 " + i + ":" + ch.getClass().getSimpleName() + ",匹配规则 = " + (ch instanceof DefaultSecurityFilterChain d ? d.getRequestMatcher() : "?") + ",过滤器 " + ch.getFilters().size() + " 个");
      if (System.getProperty("x102.list") != null || i == 1) { int j = 0; for (var f : ch.getFilters()) r(String.format("      %2d. %s", ++j, f.getClass().getSimpleName())); } }
    for (String u : new String[]{"/api/x", "/other", "/open/x", "/ignored/x", "/permitted/x"}) { var chs = fcp.getFilters(u); r("  URL " + u + " 实际会经过的过滤器 " + chs.size() + " 个" + (chs.isEmpty() ? "(没有任何链匹配,不经过 Spring Security)" : ",第一个 " + chs.get(0).getClass().getSimpleName() + ",含 BasicAuthenticationFilter=" + chs.stream().anyMatch(f -> f.getClass().getSimpleName().equals("BasicAuthenticationFilter")) + ",含 UsernamePasswordAuthenticationFilter=" + chs.stream().anyMatch(f -> f.getClass().getSimpleName().equals("UsernamePasswordAuthenticationFilter")))); }
    r("READY"); try { Thread.sleep(60000); } catch (Exception e) {} System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x102', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def http_get(port, path, hdrs=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=10); c.request('GET', path, headers=hdrs or {}); r = c.getresponse(); body = r.read().decode('utf-8', 'replace'); h = dict((k.lower(), v) for k, v in r.getheaders()); c.close(); return r.status, h, body
def scenario(title, cfg, paths, list_all=False):
    port = free_port(); props = {'server.port': port, 'x102.cfg': cfg, 'spring.security.user.name': 'u', 'spring.security.user.password': 'p'}
    if list_all: props['x102.list'] = '1'
    a = SApp(b, 'demo.Main', props=props, port=port, name='stdout'); print('  -- ' + title + ':')
    try: a.start(timeout=90); time.sleep(0.5)
    except RuntimeError as e:
        txt = a.logf.read_text(); msg = [x.strip() for x in txt.splitlines() if 'A filter chain' in x or 'IllegalArgumentException' in x][:2]; print('    应用启动失败,进程退出;日志里的原因:' + ' | '.join(m[:1700] for m in msg)); a.stop(); return
    for l in [x[4:] for x in a.log().splitlines() if x.startswith('RES ') and x[4:] != 'READY']: print('    ' + l)
    for p, hd in paths:
        st, h, body = http_get(port, p, hd)
        sec = [k for k in ('x-content-type-options', 'x-frame-options', 'cache-control', 'strict-transport-security') if k in h]
        print(f'    GET {p}{" (带 Basic u:p)" if hd else ""} → HTTP {st}' + (f',Location {h["location"]}' if 'location' in h else '') + (f',WWW-Authenticate {h["www-authenticate"]}' if 'www-authenticate' in h else '') + f',安全相关响应头 {sec}')
    a.stop()
import base64
BASIC = {'Authorization': 'Basic ' + base64.b64encode(b'u:p').decode()}
print('Spring Boot 4.0.8 / Spring Security 7(随 spring-boot-starter-security);一个 @RestController 对所有路径返回 ok;默认用户 u / p')
print('== 一:什么都不配时的那条默认链')
scenario('默认(没有自己写 SecurityFilterChain)', 'default', [('/x', None), ('/x', BASIC)])
print('== 二:自己写两条链:/api/** 用 httpBasic,其余用表单登录')
scenario('链 1 = securityMatcher(/api/**) @Order(1);链 2 = 兜底 @Order(2)', 'two', [('/api/x', None), ('/api/x', BASIC), ('/other', None), ('/open/x', None)])
scenario('链 1 = securityMatcher(/api/**);链 2 里多了 /error 的 permitAll', 'two-error', [('/api/x', None), ('/api/x', BASIC)])
print('== 三:顺序写反:兜底链放在前面')
scenario('链 1 = 兜底 @Order(1);链 2 = securityMatcher(/api/**) @Order(2)', 'misordered', [('/api/x', None), ('/api/x', BASIC)])
print('== 四:ignoring 与 permitAll 的区别')
scenario('/ignored/** 走 web.ignoring(),/permitted/** 走 permitAll()', 'ignoring', [('/ignored/x', None), ('/permitted/x', None), ('/secret', None)])
