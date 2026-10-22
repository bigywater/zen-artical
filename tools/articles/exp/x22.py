import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x22'); CP = scp('org.springframework.boot:spring-boot-starter', 'org.springframework.boot:spring-boot-starter-aspectj')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.aspectj.lang.ProceedingJoinPoint; import org.aspectj.lang.annotation.*;
import org.springframework.aop.framework.AopContext; import org.springframework.aop.support.AopUtils;
import org.springframework.beans.factory.annotation.Autowired; import org.springframework.context.annotation.*;
public class Main {
  static int intercepted;
  @java.lang.annotation.Retention(java.lang.annotation.RetentionPolicy.RUNTIME) public @interface Counted { }
  @Aspect public static class Count { @Around("@annotation(demo.Main.Counted)") public Object around(ProceedingJoinPoint pj) throws Throwable { intercepted++; return pj.proceed(); } }
  public static class Svc {
    public String field = "字段值"; String thisInfo;
    @Counted public String b() { thisInfo = "this 是代理?" + AopUtils.isAopProxy(this) + ",this.getClass()=" + this.getClass().getSimpleName(); return "b"; }
    public String a() { return this.b(); }
    public String thisInfo() { return thisInfo; } }
  public static class SelfInject extends Svc { @Autowired @Lazy SelfInject self; public String a() { return self.b(); } }
  public static class ViaContext extends Svc { public String a() { return ((ViaContext) AopContext.currentProxy()).b(); } }
  public static class Other { @Autowired Svc svc; public String a() { return svc.b(); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class Base { @Bean Count count() { return new Count(); } }
  @Configuration static class C1 { @Bean Svc svc() { return new Svc(); } }
  @Configuration static class C2 { @Bean SelfInject svc() { return new SelfInject(); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true, exposeProxy = true) static class C3 { @Bean Count count() { return new Count(); } @Bean ViaContext svc() { return new ViaContext(); } }
  @Configuration static class C4 { @Bean Svc svc() { return new Svc(); } @Bean Other other() { return new Other(); } }
  static void t(String label, Object target, java.util.concurrent.Callable<Object> a, java.util.concurrent.Callable<Object> b) throws Exception { intercepted = 0; b.call(); int ext = intercepted; intercepted = 0; a.call(); int in = intercepted; System.out.println("RES " + String.format("%-40s → 外部直接调 b():拦截 %d 次;经过 a() 间接调 b():拦截 %d 次", label, ext, in)); }
  public static void main(String[] args) throws Exception {
    String m = args[0]; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext();
    switch (m) {
      case "self" -> { c.register(Base.class, C1.class); c.refresh(); Svc s = c.getBean(Svc.class); t("(a)普通的自调用 this.b()", s, s::a, s::b); System.out.println("RES   外部调 b() 时目标方法里的 this:" + s.thisInfo() + "(proxy 把调用转给了目标对象,this 是目标,不是代理)"); }
      case "fix1" -> { c.register(Base.class, C2.class); c.refresh(); SelfInject s = c.getBean(SelfInject.class); t("(b)注入自己的代理(@Autowired @Lazy self)", s, s::a, s::b); }
      case "fix2" -> { c.register(C3.class); c.refresh(); ViaContext s = c.getBean(ViaContext.class); t("(c)AopContext.currentProxy()(exposeProxy=true)", s, s::a, s::b);
        AnnotationConfigApplicationContext c2 = new AnnotationConfigApplicationContext(); c2.register(Base.class, C1.class); c2.refresh(); ViaContext raw = new ViaContext(); try { raw.a(); } catch (Exception e) { System.out.println("RES   没有 exposeProxy=true(或不是代理对象)时 AopContext.currentProxy() → " + e.getClass().getSimpleName() + ": " + e.getMessage().split("\n")[0]); } }
      case "fix3" -> { c.register(Base.class, C4.class); c.refresh(); Other o = c.getBean(Other.class); Svc s = c.getBean(Svc.class); t("(d)拆成两个 Bean(Other 调 svc.b())", o, o::a, s::b); }
      case "field" -> { c.register(Base.class, C1.class); c.refresh(); Svc s = c.getBean(Svc.class); System.out.println("RES 通过代理读 public 字段 s.field = " + s.field + "(目标对象里是 \"字段值\");这个 Bean 的类:" + s.getClass().getSimpleName().replaceAll("\\$\\$.*", "·CGLIB") + "(AopUtils.isAopProxy=" + AopUtils.isAopProxy(s) + ")"); Object tgt = ((org.springframework.aop.framework.Advised) s).getTargetSource().getTarget(); System.out.println("RES 目标对象上读 field = " + ((Svc) tgt).field); }
    }
  }
}
'''
b = sbuild('x22', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): r = srun(b, 'demo.Main', args=[m]); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-900:]]
print('Spring Framework 7.0.9(Spring AOP + AspectJ,CGLIB 代理)。自调用:一个切面拦截带 @Counted 的方法 b();类里的 a() 调用 b()')
print('== 一:普通的自调用')
[print('  ' + l) for l in run('self')]
print('== 二:办法一:注入自己的代理;办法二:AopContext.currentProxy();办法三:拆成两个 Bean')
for k_ in ('fix1', 'fix2', 'fix3'): [print('  ' + l) for l in run(k_)]
print('== 三:代理对象上读 public 字段')
[print('  ' + l) for l in run('field')]
