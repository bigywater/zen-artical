import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x23'); CP = scp('org.springframework.boot:spring-boot-starter', 'org.springframework.boot:spring-boot-starter-aspectj')
LOG = '<configuration><appender name="O" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{0}: %msg%n</pattern></encoder></appender><root level="WARN"><appender-ref ref="O"/></root></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.aspectj.lang.ProceedingJoinPoint; import org.aspectj.lang.annotation.*;
import org.springframework.aop.support.AopUtils; import org.springframework.context.annotation.*;
public class Main {
  static int hits; static final List<String> calls = new ArrayList<>();
  @Aspect public static class Count { @Around("execution(* demo.Main.Svc.*(..))") public Object around(ProceedingJoinPoint pj) throws Throwable { hits++; calls.add(pj.getSignature().getName()); return pj.proceed(); } }
  public static class Svc {
    final String name; static int ctor; Svc(String name) { this.name = name; ctor++; }
    public String open() { return "open:" + name; } public final String locked() { return "locked:" + name; } private String hidden() { return "hidden:" + name; } public String callHidden() { return hidden(); } public static String stat() { return "static"; }
  }
  public static class Plain { static int ctor; final String name = "plain"; public Plain() { ctor++; } public String open() { return "open:" + name; } }
  public static final class Fin { public String open() { return "open"; } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class C1 { @Bean Count count() { return new Count(); } @Bean Svc svc() { return new Svc("真名"); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class C2 { @Bean CountPlain count() { return new CountPlain(); } @Bean Plain plain() { return new Plain(); } }
  @Aspect public static class CountFin { @Around("execution(* demo.Main.Fin.*(..))") public Object around(ProceedingJoinPoint pj) throws Throwable { return pj.proceed(); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class C3 { @Bean CountFin count() { return new CountFin(); } @Bean Fin fin() { return new Fin(); } }
  @Aspect public static class CountPlain { @Around("execution(* demo.Main.Plain.*(..))") public Object around(ProceedingJoinPoint pj) throws Throwable { return pj.proceed(); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class C4 { @Bean CountPlain count() { return new CountPlain(); } @Bean Plain plain() { return new Plain(); } }
  static String t(java.util.concurrent.Callable<Object> c) { hits = 0; calls.clear(); try { Object o = c.call(); return o + "  [切面拦截 " + hits + " 次" + (calls.isEmpty() ? "" : ":" + calls) + "]"; } catch (Exception e) { return "✗ " + e.getClass().getSimpleName(); } }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    switch (m) {
      case "methods" -> { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(C1.class); Svc s = c.getBean(Svc.class);
        System.out.println("RES 目标对象构造时 name=\"真名\"。通过代理调用:");
        System.out.println("RES   open()(普通 public 方法)→ " + t(s::open)); System.out.println("RES   locked()(final 方法)→ " + t(s::locked));
        System.out.println("RES   callHidden()(public 方法,里面调 private hidden())→ " + t(s::callHidden)); System.out.println("RES   static stat() → " + t(Svc::stat));
        System.out.println("RES   Svc.ctor(构造器被调用的次数)= " + Svc.ctor + ";Bean 是代理?" + AopUtils.isAopProxy(s)); }
      case "ctor" -> { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(C2.class); Plain p = c.getBean(Plain.class); System.out.println("RES 有 public 无参构造器的 Plain,变成代理后构造器被调用了 " + Plain.ctor + " 次;isAopProxy = " + AopUtils.isAopProxy(p) + ";spring.objenesis.ignore = " + System.getProperty("spring.objenesis.ignore", "(没设)")); }
      case "final" -> { try { new AnnotationConfigApplicationContext(C3.class); System.out.println("RES final 类:启动成功?"); } catch (Exception e) { Throwable t = e; while (t.getCause() != null) t = t.getCause(); System.out.println("RES final 类 Fin 被切面匹配:" + e.getClass().getSimpleName() + " ← " + t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).split("\n")[0]); } }
      case "noargs" -> { try { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(C1.class); System.out.println("RES 只有带参构造器的 Svc 变成代理:成功,构造器被调用 " + Svc.ctor + " 次;spring.objenesis.ignore = " + System.getProperty("spring.objenesis.ignore", "(没设)")); } catch (Exception e) { Throwable t = e; while (t.getCause() != null) t = t.getCause(); System.out.println("RES 只有带参构造器的 Svc 变成代理:" + e.getClass().getSimpleName() + " ← " + t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).split("\n")[0]); } }
    }
  }
}
'''
b = sbuild('x23', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m, props=None): r = srun(b, 'demo.Main', args=[m], props=props); return [l[4:] if l.startswith('RES ') else l for l in r['out'].splitlines() if l.startswith('RES ') or l.startswith('LOG ')] or [r['out'][-900:]]
print('Spring Framework 7.0.9(Spring AOP + AspectJ,CGLIB 代理)。CGLIB 代理的限制')
print('== 一:不同种类的方法通过 CGLIB 代理调用。Svc 只有一个带参构造器 Svc(String name),构造时设置 name = 真名;切面匹配 Svc 所有方法')
[print('  ' + l) for l in run('methods')]
print('== 二:构造器被调用几次。Plain 有 public 无参构造器,变成代理。默认,与 -Dspring.objenesis.ignore=true(不用 Objenesis,走构造器)')
[print('  ' + l) for l in run('ctor')]; [print('  ' + l) for l in run('ctor', {'spring.objenesis.ignore': 'true'})]
print('== 三:只有带参构造器的类,关掉 Objenesis 之后还能被代理吗')
[print('  ' + l) for l in run('noargs')]; [print('  ' + l) for l in run('noargs', {'spring.objenesis.ignore': 'true'})]
print('== 四:final 类被切面匹配')
[print('  ' + l) for l in run('final')]
