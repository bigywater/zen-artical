import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x108'); CP = scp('org.springframework.boot:spring-boot-starter-security')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty; import org.springframework.context.annotation.*; import org.springframework.security.access.annotation.Secured; import org.springframework.security.access.prepost.*; import org.springframework.security.authentication.*; import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity; import org.springframework.security.core.*; import org.springframework.security.core.authority.AuthorityUtils; import org.springframework.security.core.context.SecurityContextHolder; import org.springframework.stereotype.Service; import jakarta.annotation.security.RolesAllowed; import java.util.*;\n'
FILES = {
 'src/demo/Cfg.java': HDR + '''
@Configuration @EnableMethodSecurity @ConditionalOnProperty(name = "x108.extra", havingValue = "false", matchIfMissing = true) class CfgDefault {}
@Configuration @EnableMethodSecurity(securedEnabled = true, jsr250Enabled = true) @ConditionalOnProperty(name = "x108.extra", havingValue = "true") class CfgExtra {}
''',
 'src/demo/Doc.java': HDR + 'public record Doc(String owner, String text) {}\n',
 'src/demo/Api.java': HDR + 'public interface Api { @PreAuthorize("hasRole(\'ADMIN\')") String viaIface(); }\n',
 'src/demo/Svc.java': HDR + '''
@Service public class Svc implements Api {
  @PreAuthorize("hasRole('ADMIN')") public String admin() { return "admin 的数据"; }
  public String outer() { return "outer 里调 this.admin() → " + this.admin(); }
  @PreAuthorize("hasRole('ADMIN')") String pkgPrivate() { return "package-private 方法执行了"; }
  @PreAuthorize("hasRole('ADMIN')") private String priv() { return "private 方法执行了"; }
  public String callPriv() { return priv(); }
  public String viaIface() { return "接口上注解的方法执行了"; }
  @PreAuthorize("#name == authentication.name") public String mine(String name) { return "只能看自己的:" + name; }
  @PostAuthorize("returnObject.owner == authentication.name") public Doc doc(String owner) { return new Doc(owner, "内容"); }
  @PreFilter("filterObject.owner == authentication.name") public int count(List<Doc> docs) { return docs.size(); }
  @PostFilter("filterObject.owner == authentication.name") public List<Doc> all() { return new ArrayList<>(List.of(new Doc("alice", "a1"), new Doc("bob", "b1"), new Doc("alice", "a2"))); }
  @Secured("ROLE_ADMIN") public String secured() { return "@Secured 方法执行了"; }
  @RolesAllowed("ADMIN") public String rolesAllowed() { return "@RolesAllowed 方法执行了"; }
  @PreAuthorize("hasAuthority('FACTOR_PASSWORD')") public String factor() { return "FACTOR_PASSWORD 权限检查通过"; }
}
''',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  static void as(String user, String role) { SecurityContextHolder.setContext(SecurityContextHolder.createEmptyContext()); if (user != null) SecurityContextHolder.getContext().setAuthentication(UsernamePasswordAuthenticationToken.authenticated(user, "n/a", AuthorityUtils.createAuthorityList(role))); }
  interface Call { Object run() throws Exception; }
  static void t(String label, Call c) { String out; try { Object o = c.run(); out = String.valueOf(o); } catch (Throwable e) { Throwable rc = e; out = "抛 " + e.getClass().getSimpleName() + ":" + e.getMessage(); } r("  " + label + " ⇒ " + out); }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a); Svc s = c.getBean(Svc.class); boolean extra = "true".equals(System.getProperty("x108.extra"));
    if (!extra) {
      r("== 一:@PreAuthorize 与代理");
      r("  Svc 的实际类型:" + s.getClass().getSimpleName() + ";是不是 AOP 代理:" + org.springframework.aop.support.AopUtils.isAopProxy(s) + ";是不是 CGLIB 代理:" + org.springframework.aop.support.AopUtils.isCglibProxy(s));
      as("alice", "ROLE_USER"); t("alice(ROLE_USER)调 admin()", s::admin); as("root", "ROLE_ADMIN"); t("root(ROLE_ADMIN)调 admin()", s::admin); as(null, null); t("没有登录(SecurityContext 里没有 Authentication)调 admin()", s::admin);
      as("alice", "ROLE_USER"); t("alice 调 outer()(类内部 this.admin())", s::outer); t("alice 调 pkgPrivate()(同包,package-private)", () -> s.pkgPrivate()); t("alice 调 callPriv()(public 方法里调 private 的 priv())", s::callPriv); t("alice 调 viaIface()(注解写在接口上)", s::viaIface);
      r("== 二:表达式里用参数与返回值");
      as("alice", "ROLE_USER"); t("alice 调 mine(\\"alice\\")", () -> s.mine("alice")); t("alice 调 mine(\\"bob\\")", () -> s.mine("bob")); t("alice 调 doc(\\"alice\\")(@PostAuthorize)", () -> s.doc("alice")); t("alice 调 doc(\\"bob\\")(方法已经执行,返回值被拒绝)", () -> s.doc("bob"));
      t("alice 调 count(三个文档,两个属于 bob)(@PreFilter)", () -> s.count(new ArrayList<>(List.of(new Doc("alice", "1"), new Doc("bob", "2"), new Doc("bob", "3"))))); t("alice 调 all()(@PostFilter)", s::all);
      t("alice 调 count(不可变列表 List.of)(@PreFilter 要原地删元素)", () -> s.count(List.of(new Doc("alice", "1"), new Doc("bob", "2"))));
      r("== 三:authorities 里的 FACTOR_PASSWORD"); as("alice", "ROLE_USER"); t("手工构造的 Authentication 调 factor()(authorities 只有 ROLE_USER)", s::factor);
      r("== 四:@Secured 与 @RolesAllowed 要显式打开");
    }
    String tag = extra ? "(@EnableMethodSecurity(securedEnabled = true, jsr250Enabled = true))" : "(默认的 @EnableMethodSecurity)";
    as("alice", "ROLE_USER"); t("alice 调 secured() " + tag, s::secured); t("alice 调 rolesAllowed() " + tag, s::rolesAllowed); as("root", "ROLE_ADMIN"); t("root 调 secured() " + tag, s::secured);
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x108', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
print('Spring Boot 4.0.8 / Spring Security 7 方法级安全(非 Web 模式的单个程序,当前用户由代码直接放进 SecurityContextHolder)')
for extra in ('false', 'true'):
    r = srun(b, 'demo.Main', props={'x108.extra': extra}, timeout=120)
    for l in res(r): print(l)
    if not res(r): print(r['out'][-2000:])
