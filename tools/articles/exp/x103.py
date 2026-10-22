import sys, os, re, time, http.client, base64, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x103'); CP = scp('org.springframework.boot:spring-boot-starter-security', 'org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.annotation.*; import org.springframework.context.event.EventListener; import org.springframework.security.authentication.*; import org.springframework.security.authentication.event.*; import org.springframework.security.config.Customizer; import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration; import org.springframework.security.config.annotation.web.builders.HttpSecurity; import org.springframework.security.core.*; import org.springframework.security.core.context.SecurityContextHolder; import org.springframework.security.core.userdetails.*; import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder; import org.springframework.security.crypto.password.PasswordEncoder; import org.springframework.security.web.SecurityFilterChain; import org.springframework.security.concurrent.DelegatingSecurityContextExecutorService; import org.springframework.security.provisioning.InMemoryUserDetailsManager; import org.springframework.web.bind.annotation.*; import java.util.*; import java.util.concurrent.*;\n'
FILES = {
 'src/demo/Main.java': HDR + '''
@SpringBootApplication @RestController
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  static final List<String> EVENTS = Collections.synchronizedList(new ArrayList<>());
  @Bean PasswordEncoder enc() { return new BCryptPasswordEncoder(12); }
  @Bean UserDetailsService uds(PasswordEncoder e) { String pw = e.encode("pw");
    return new InMemoryUserDetailsManager(User.withUsername("alice").password(pw).roles("USER").build(), User.withUsername("bob").password(pw).roles("USER").disabled(true).build(), User.withUsername("carol").password(pw).roles("USER").accountLocked(true).build(), User.withUsername("dave").password(pw).roles("USER").credentialsExpired(true).build(), User.withUsername("erin").password(pw).roles("USER").build()); }
  @Bean SecurityFilterChain chain(HttpSecurity h) throws Exception { return h.authorizeHttpRequests(a -> a.anyRequest().authenticated()).httpBasic(Customizer.withDefaults()).csrf(c -> c.disable()).build(); }
  @EventListener void ev(AbstractAuthenticationEvent e) { EVENTS.add(e.getClass().getSimpleName()); }
  final ExecutorService plain = Executors.newFixedThreadPool(1); final ExecutorService wrapped = new DelegatingSecurityContextExecutorService(Executors.newFixedThreadPool(1));
  static String who() { Authentication a = SecurityContextHolder.getContext().getAuthentication(); return a == null ? "null" : a.getName(); }
  @GetMapping("/who") String whoAmI() throws Exception {
    String viaPlain = plain.submit(Main::who).get(); String viaWrapped = wrapped.submit(Main::who).get(); String[] viaNew = new String[1]; Thread t = new Thread(() -> viaNew[0] = who()); t.start(); t.join();
    return "请求线程=" + who() + ";普通线程池=" + viaPlain + ";新建线程=" + viaNew[0] + ";DelegatingSecurityContextExecutorService=" + viaWrapped; }
  static String ex(Throwable t) { return t.getClass().getSimpleName() + ":" + t.getMessage(); }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a); AuthenticationManager am = c.getBean(AuthenticationConfiguration.class).getAuthenticationManager();
    r("SecurityContextHolder 的策略:" + SecurityContextHolder.getContextHolderStrategy().getClass().getSimpleName());
    r("== 一:AuthenticationManager 的类型与各种失败");
    r("AuthenticationManager = " + am.getClass().getSimpleName() + (am instanceof ProviderManager pm ? ",providers = " + pm.getProviders().stream().map(p -> p.getClass().getSimpleName()).toList() : ""));
    String[][] cases = {{"alice", "pw"}, {"alice", "wrong"}, {"nobody", "pw"}, {"bob", "pw"}, {"carol", "pw"}, {"dave", "pw"}, {"bob", "wrong"}};
    for (String[] cs : cases) { EVENTS.clear(); long t0 = System.nanoTime(); String res; try { Authentication au = am.authenticate(UsernamePasswordAuthenticationToken.unauthenticated(cs[0], cs[1])); res = "成功,返回 " + au.getClass().getSimpleName(); } catch (Throwable t) { res = "失败 " + ex(t); }
      r(String.format("  authenticate(%s, %s):%s;用时 %.0f ms;发布的事件 %s", cs[0], cs[1], res, (System.nanoTime() - t0) / 1e6, new ArrayList<>(EVENTS))); }
    r("== 二:认证成功之后返回的 Authentication");
    UsernamePasswordAuthenticationToken in = UsernamePasswordAuthenticationToken.unauthenticated("alice", "pw"); Authentication out = am.authenticate(in);
    r("  传入的对象:authenticated=" + in.isAuthenticated() + ",credentials=" + in.getCredentials() + ";返回的对象:类型=" + out.getClass().getSimpleName() + ",authenticated=" + out.isAuthenticated() + ",principal 类型=" + out.getPrincipal().getClass().getSimpleName() + ",credentials=" + out.getCredentials() + ",authorities=" + out.getAuthorities() + ";返回的与传入的是同一个对象:" + (in == out));
    r("== 三:把 hideUserNotFoundExceptions 关掉");
    org.springframework.security.authentication.dao.DaoAuthenticationProvider dp = new org.springframework.security.authentication.dao.DaoAuthenticationProvider(c.getBean(UserDetailsService.class)); dp.setPasswordEncoder(c.getBean(PasswordEncoder.class)); dp.setHideUserNotFoundExceptions(false);
    for (String u : new String[]{"nobody"}) { long t0 = System.nanoTime(); String res; try { dp.authenticate(UsernamePasswordAuthenticationToken.unauthenticated(u, "pw")); res = "成功"; } catch (Throwable t) { res = "失败 " + ex(t); } r(String.format("  hideUserNotFoundExceptions=false:authenticate(%s, pw):%s;用时 %.0f ms", u, res, (System.nanoTime() - t0) / 1e6)); }
    r("READY"); Thread.sleep(60000); System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x103', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def req(port, path, user=None, pw='pw'):
    h = {'Authorization': 'Basic ' + base64.b64encode(f'{user}:{pw}'.encode()).decode()} if user else {}
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=10); c.request('GET', path, headers=h); r = c.getresponse(); body = r.read().decode(); c.close(); return r.status, body
def launch(extra=None):
    port = free_port(); pr = {'server.port': port}; pr.update(extra or {}); a = SApp(b, 'demo.Main', props=pr, port=port, name='stdout'); a.start(timeout=90)
    t0 = time.time()
    while time.time() - t0 < 60 and 'RES READY' not in a.log(): time.sleep(0.2)
    return a, port
print('Spring Boot 4.0.8 / Spring Security 7(BCrypt strength 12);五个用户:alice 和 erin 正常、bob 被禁用、carol 被锁定、dave 凭据已过期,密码都是 pw')
a, port = launch(); lines = [x[4:] for x in a.log().splitlines() if x.startswith('RES ') and x[4:] != 'READY']
for l in lines: print(l)
print('== 四:SecurityContext 在线程之间')
for u in ('alice', 'erin'): print(f'  用 {u} 登录 GET /who → {req(port, "/who", u)[1]}')
a.stop()
print('  -- 同样的请求,启动时设置 spring.security.strategy=MODE_INHERITABLETHREADLOCAL:')
a, port = launch({'spring.security.strategy': 'MODE_INHERITABLETHREADLOCAL'})
for u in ('alice', 'erin'): print(f'  用 {u} 登录 GET /who → {req(port, "/who", u)[1]}')
a.stop()
