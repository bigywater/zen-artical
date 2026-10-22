import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x21'); CP = scp('org.springframework.boot:spring-boot-starter', 'org.springframework.boot:spring-boot-starter-aspectj')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.aspectj.lang.ProceedingJoinPoint; import org.aspectj.lang.annotation.*;
import org.springframework.context.annotation.*; import org.springframework.core.Ordered; import org.springframework.core.annotation.Order;
public class Main {
  static final List<String> seq = new ArrayList<>(); static void ev(String s) { seq.add(s); }
  static void flush(String t) { System.out.println("RES --- " + t); int i = 1; for (String s : seq) System.out.println("RES " + i++ + ". " + s); seq.clear(); }
  public static class Svc { public String ok() { ev("    ▶ 目标方法 ok()"); return "ok"; } public String fail() { ev("    ▶ 目标方法 fail() 抛异常"); throw new IllegalStateException("boom"); } public String arg(String s) { ev("    ▶ 目标方法 arg(" + s + ")"); return s; } }
  static abstract class Tpl {
    final String n; Tpl(String n) { this.n = n; }
    void around(ProceedingJoinPoint pj) throws Throwable { }
  }
  @Aspect @Order(1) public static class A {
    @Around("execution(* demo.Main.Svc.ok()) || execution(* demo.Main.Svc.fail())") public Object around(ProceedingJoinPoint pj) throws Throwable { ev("A.around 前"); try { return pj.proceed(); } finally { ev("A.around 后(finally)"); } }
    @Before("execution(* demo.Main.Svc.ok()) || execution(* demo.Main.Svc.fail())") public void before() { ev("A.before"); }
    @After("execution(* demo.Main.Svc.ok()) || execution(* demo.Main.Svc.fail())") public void after() { ev("A.after(finally 型)"); }
    @AfterReturning("execution(* demo.Main.Svc.ok())") public void ret() { ev("A.afterReturning"); }
    @AfterThrowing("execution(* demo.Main.Svc.fail())") public void thr() { ev("A.afterThrowing"); }
  }
  @Aspect @Order(2) public static class B {
    @Around("execution(* demo.Main.Svc.ok()) || execution(* demo.Main.Svc.fail())") public Object around(ProceedingJoinPoint pj) throws Throwable { ev("  B.around 前"); try { return pj.proceed(); } finally { ev("  B.around 后(finally)"); } }
    @Before("execution(* demo.Main.Svc.ok()) || execution(* demo.Main.Svc.fail())") public void before() { ev("  B.before"); }
    @After("execution(* demo.Main.Svc.ok()) || execution(* demo.Main.Svc.fail())") public void after() { ev("  B.after"); }
    @AfterReturning("execution(* demo.Main.Svc.ok())") public void ret() { ev("  B.afterReturning"); }
    @AfterThrowing("execution(* demo.Main.Svc.fail())") public void thr() { ev("  B.afterThrowing"); }
  }
  @Aspect public static class Names { // 同一个切面里两个 @Before,方法名与声明顺序相反
    @Before("execution(* demo.Main.Svc.ok())") public void zzz() { ev("Names.zzz(先声明)"); }
    @Before("execution(* demo.Main.Svc.ok())") public void aaa() { ev("Names.aaa(后声明)"); }
    @After("execution(* demo.Main.Svc.ok())") public void yyy() { ev("Names.yyy(@After)"); }
    @Around("execution(* demo.Main.Svc.ok())") public Object mmm(ProceedingJoinPoint pj) throws Throwable { ev("Names.mmm(@Around)前"); Object r = pj.proceed(); ev("Names.mmm(@Around)后"); return r; }
  }
  @Aspect public static class Skip { @Around("execution(* demo.Main.Svc.arg(..))") public Object around(ProceedingJoinPoint pj) throws Throwable { Object[] a = pj.getArgs(); ev("Skip.around 看到参数 " + Arrays.toString(a) + ",改成 [改过]后 proceed"); return pj.proceed(new Object[]{"改过"}); } }
  @Aspect public static class Swallow { @Around("execution(* demo.Main.Svc.arg(..))") public Object around(ProceedingJoinPoint pj) { ev("Swallow.around 没有调用 proceed(),直接返回 \"缓存值\""); return "缓存值"; } }
  @Aspect public static class OrderedViaBean { @Before("execution(* demo.Main.Svc.ok())") public void b() { ev("OrderedViaBean.before"); } }
  @Aspect public static class OrderedViaClass implements Ordered { public int getOrder() { return 0; } @Before("execution(* demo.Main.Svc.ok())") public void b() { ev("OrderedViaInterface(getOrder=0).before"); } }
  @Aspect public static class Plain { @Before("execution(* demo.Main.Svc.ok())") public void b() { ev("PlainNoOrder.before"); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class C1 { @Bean Svc svc() { return new Svc(); } @Bean A a() { return new A(); } @Bean B b() { return new B(); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class C1r { @Bean Svc svc() { return new Svc(); } @Bean B b() { return new B(); } @Bean A a() { return new A(); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class C2 { @Bean Svc svc() { return new Svc(); } @Bean Names n() { return new Names(); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class C3 { @Bean Svc svc() { return new Svc(); } @Bean Skip s() { return new Skip(); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class C4 { @Bean Svc svc() { return new Svc(); } @Bean Swallow s() { return new Swallow(); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class C5 { @Bean Svc svc() { return new Svc(); } @Bean Plain plain() { return new Plain(); } @Bean @Order(-5) OrderedViaBean viaBean() { return new OrderedViaBean(); } @Bean OrderedViaClass viaIface() { return new OrderedViaClass(); } }
  public static void main(String[] args) throws Exception {
    String m = args[0]; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(m.equals("two") ? C1.class : m.equals("tworev") ? C1r.class : m.equals("names") ? C2.class : m.equals("args") ? C3.class : m.equals("swallow") ? C4.class : C5.class);
    Svc s = c.getBean(Svc.class);
    switch (m) {
      case "two", "tworev" -> { s.ok(); flush("正常返回 ok()(A 的 @Order(1),B 的 @Order(2)" + (m.equals("tworev") ? ";这次 @Bean 的定义顺序是 B 先 A 后" : "") + ")"); try { s.fail(); } catch (Exception e) { ev("调用者收到 " + e.getClass().getSimpleName()); } flush("抛异常 fail()"); }
      case "names" -> { s.ok(); flush("同一个切面里的多个通知,没有 @Order"); }
      case "args" -> { ev("返回值 = " + s.arg("原值")); flush("@Around 里修改参数后 proceed(Object[])"); }
      case "swallow" -> { ev("返回值 = " + s.arg("原值")); flush("@Around 不调用 proceed()"); }
      case "ordsrc" -> { s.ok(); flush("三个切面:Plain(没有顺序)、OrderedViaBean(@Bean 方法上 @Order(-5))、OrderedViaInterface(实现 Ordered,getOrder=0)"); }
    }
  }
}
'''
b = sbuild('x21', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): r = srun(b, 'demo.Main', args=[m]); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-900:]]
print('Spring Framework 7.0.9(Spring AOP + AspectJ 注解,CGLIB 代理)。通知的执行顺序')
print('== 一:一个切面里五种通知(@Around、@Before、@After、@AfterReturning、@AfterThrowing),两个切面 A(@Order(1))与 B(@Order(2)),缩进两格的是 B。正常返回与抛异常两种路径')
[print('  ' + l) for l in run('two')]
print('== 二:同样两个切面,把 @Bean 的定义顺序倒过来(B 先 A 后)。顺序变吗')
[print('  ' + l) for l in run('tworev')[:16]]
print('== 三:同一个切面里的通知,没有 @Order,方法名故意和声明顺序相反')
[print('  ' + l) for l in run('names')]
print('== 四:@Around 改参数 / 不调用 proceed()')
[print('  ' + l) for l in run('args')]; [print('  ' + l) for l in run('swallow')]
print('== 五:切面的顺序从哪里来。Plain 没有顺序;OrderedViaBean 的 @Order(-5) 写在 @Bean 方法上;OrderedViaClass 实现 Ordered(getOrder = 0)')
[print('  ' + l) for l in run('ordsrc')]
