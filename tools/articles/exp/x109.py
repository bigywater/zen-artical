import sys, os, re, time, http.client, base64; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x109'); CP = scp('org.springframework.boot:spring-boot-starter-security', 'org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty; import org.springframework.context.annotation.*; import org.springframework.security.authorization.*; import org.springframework.security.config.Customizer; import org.springframework.security.config.annotation.web.builders.HttpSecurity; import org.springframework.security.core.userdetails.*; import org.springframework.security.provisioning.InMemoryUserDetailsManager; import org.springframework.security.access.hierarchicalroles.*; import org.springframework.security.web.SecurityFilterChain; import org.springframework.security.web.access.intercept.RequestAuthorizationContext; import org.springframework.web.bind.annotation.*; import java.util.*; import java.util.function.Supplier;\n'
FILES = {
 'src/demo/Main.java': HDR + '''
@SpringBootApplication @RestController
public class Main {
  static String cfg() { return System.getProperty("x109.cfg", "good"); }
  @Bean UserDetailsService uds() { return new InMemoryUserDetailsManager(User.withUsername("alice").password("{noop}pw").roles("USER").build(), User.withUsername("root").password("{noop}pw").roles("ADMIN").build(), User.withUsername("eve").password("{noop}pw").authorities("ADMIN").build()); }
  @Bean @ConditionalOnProperty(name = "x109.cfg", havingValue = "hier") RoleHierarchy hier() { return RoleHierarchyImpl.fromHierarchy("ROLE_ADMIN > ROLE_USER"); }
  static final List<String> LOG = Collections.synchronizedList(new ArrayList<>());
  @Bean SecurityFilterChain chain(HttpSecurity h) throws Exception {
    h.httpBasic(Customizer.withDefaults()).csrf(c -> c.disable());
    switch (cfg()) {
      case "misordered" -> h.authorizeHttpRequests(a -> a.requestMatchers("/a/**").hasRole("USER").requestMatchers("/a/admin/**").hasRole("ADMIN").anyRequest().denyAll());
      case "rolePrefix" -> h.authorizeHttpRequests(a -> a.requestMatchers("/admin").hasRole("ROLE_ADMIN").anyRequest().authenticated());
      case "anyfirst" -> h.authorizeHttpRequests(a -> a.anyRequest().authenticated().requestMatchers("/admin").hasRole("ADMIN"));
      case "custom" -> h.authorizeHttpRequests(a -> a.requestMatchers("/custom").access(new AuthorizationManager<RequestAuthorizationContext>() { public AuthorizationResult authorize(Supplier<? extends org.springframework.security.core.Authentication> au, RequestAuthorizationContext ctx) { boolean ok = "127.0.0.1".equals(ctx.getRequest().getRemoteAddr()) && "yes".equals(ctx.getRequest().getHeader("X-Internal")) && au.get().getName().equals("alice"); System.out.println("RES custom manager:用户=" + au.get().getName() + ",远端=" + ctx.getRequest().getRemoteAddr() + ",X-Internal=" + ctx.getRequest().getHeader("X-Internal") + " → " + ok); return new AuthorizationDecision(ok); } }).anyRequest().authenticated());
      default -> h.authorizeHttpRequests(a -> a.requestMatchers("/a/admin/**").hasRole("ADMIN").requestMatchers("/a/**").hasRole("USER").requestMatchers("/user").hasRole("USER").requestMatchers("/admin").hasRole("ADMIN").requestMatchers("/byauth").hasAuthority("ROLE_ADMIN").requestMatchers("/noprefix").hasAuthority("ADMIN").requestMatchers("/either").hasAnyRole("USER", "ADMIN").anyRequest().denyAll());
    }
    return h.build(); }
  @GetMapping("/**") String any(jakarta.servlet.http.HttpServletRequest r) { return "ok " + r.getRequestURI(); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x109', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def get(port, path, user=None, hdrs=None):
    h = dict(hdrs or {})
    if user: h['Authorization'] = 'Basic ' + base64.b64encode(f'{user}:pw'.encode()).decode()
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=10); c.request('GET', path, headers=h); r = c.getresponse(); r.read(); c.close(); return r.status
def start(cfg):
    port = free_port(); a = SApp(b, 'demo.Main', props={'server.port': port, 'x109.cfg': cfg}, port=port, name='stdout')
    try: a.start(timeout=60); time.sleep(0.4); return a, port, None
    except RuntimeError:
        txt = a.logf.read_text(); msg = [x.strip() for x in txt.splitlines() if 'ROLE_' in x or 'anyRequest' in x or 'IllegalArgumentException' in x or 'IllegalStateException' in x][:2]; a.stop(); return None, None, ' | '.join(m[:520] for m in msg)
def table(port, rows):
    for path in rows:
        print(f'    GET {path:<12}' + ';'.join(f'{u}→{get(port, path, u)}' for u in ('alice', 'root', 'eve')))
print('Spring Boot 4.0.8 / Spring Security 7;三个用户:alice = roles(USER) 即 ROLE_USER;root = roles(ADMIN) 即 ROLE_ADMIN;eve = authorities("ADMIN")(没有 ROLE_ 前缀);表中是 HTTP 状态码,200 通过,403 拒绝')
print('== 一:hasRole 与 hasAuthority')
a, port, e = start('good'); print('  规则:/user hasRole(USER);/admin hasRole(ADMIN);/byauth hasAuthority(ROLE_ADMIN);/noprefix hasAuthority(ADMIN);/either hasAnyRole(USER, ADMIN)'); table(port, ['/user', '/admin', '/byauth', '/noprefix', '/either']); a.stop()
a, port, e = start('rolePrefix'); print('  hasRole("ROLE_ADMIN"):' + ('应用启动成功' if a else '应用启动失败:' + e))
if a: a.stop()
print('== 二:规则的顺序(第一个匹配的生效)')
a, port, e = start('good'); print('  正确顺序:先 /a/admin/** hasRole(ADMIN),再 /a/** hasRole(USER):'); table(port, ['/a/x', '/a/admin/x']); a.stop()
a, port, e = start('misordered'); print('  写反:先 /a/** hasRole(USER),再 /a/admin/** hasRole(ADMIN):'); table(port, ['/a/x', '/a/admin/x']); a.stop()
a, port, e = start('anyfirst'); print('  anyRequest().authenticated() 写在前面,后面又写 requestMatchers("/admin"):' + ('应用启动成功' if a else '应用启动失败:' + e))
if a: a.stop()
print('== 三:RoleHierarchy 与自定义 AuthorizationManager')
a, port, e = start('good'); print('  没有 RoleHierarchy:/user 需要 hasRole(USER):'); table(port, ['/user']); a.stop()
a, port, e = start('hier'); print('  声明 RoleHierarchy bean "ROLE_ADMIN > ROLE_USER":'); table(port, ['/user', '/admin']); a.stop()
a, port, e = start('custom'); print('  自定义 AuthorizationManager(只允许本机、带 X-Internal: yes、并且用户是 alice):')
for user, hd in (('alice', {'X-Internal': 'yes'}), ('alice', {}), ('root', {'X-Internal': 'yes'})): print(f'    GET /custom 用户 {user},头 {hd} → {get(port, "/custom", user, hd)}')
print('  服务端记录的 custom manager 调用:')
import re as _re
for l in [x for x in a.log().splitlines() if 'custom manager' in x]: print('    ' + l.strip()[4:][:200])
a.stop()
