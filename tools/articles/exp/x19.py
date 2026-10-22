import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x19'); CP = scp('org.springframework.boot:spring-boot-starter', 'org.springframework.boot:spring-boot-starter-aspectj')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.lang.management.ManagementFactory; import java.util.*;
import org.aopalliance.intercept.*; import org.aspectj.lang.ProceedingJoinPoint; import org.aspectj.lang.annotation.*;
import org.springframework.aop.framework.*; import org.springframework.aop.support.AopUtils; import org.springframework.boot.*; import org.springframework.boot.autoconfigure.EnableAutoConfiguration; import org.springframework.context.ConfigurableApplicationContext; import org.springframework.context.annotation.*;
public class Main {
  public interface Greeter { String hi(); }
  public static class WithIface implements Greeter { public String hi() { return "hi"; } public String extra() { return "extra"; } }
  public static class NoIface { public String hi() { return "hi"; } }
  @Aspect public static class Trace { @Around("execution(* demo.Main.WithIface.*(..)) || execution(* demo.Main.NoIface.*(..))") public Object around(ProceedingJoinPoint pj) throws Throwable { return pj.proceed(); } }
  @Configuration @EnableAspectJAutoProxy static class Default_ { @Bean WithIface w() { return new WithIface(); } @Bean NoIface n() { return new NoIface(); } @Bean Trace t() { return new Trace(); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class ByClass { @Bean WithIface w() { return new WithIface(); } @Bean NoIface n() { return new NoIface(); } @Bean Trace t() { return new Trace(); } }
  @Configuration @EnableAutoConfiguration @Import({Default_.class}) static class BootApp { }
  static String kind(Object o) { return AopUtils.isJdkDynamicProxy(o) ? "JDK 动态代理" : AopUtils.isCglibProxy(o) ? "CGLIB 代理" : "不是代理"; }
  static String cn(Object o) { return o.getClass().getName().replace("demo.Main$", "").replaceAll("\\$\\$SpringCGLIB\\$\\$\\d+", "·SpringCGLIB·N"); }
  static void report(ConfigurableApplicationContext c) {
    Object w = c.getBean("w"), n = c.getBean("n");
    System.out.println("RES   WithIface(有接口)的 Bean:" + kind(w) + ",类名 " + cn(w) + ";instanceof Greeter=" + (w instanceof Greeter) + ";instanceof WithIface=" + (w instanceof WithIface));
    System.out.println("RES   NoIface(没有接口)的 Bean:" + kind(n) + ",类名 " + cn(n) + ";instanceof NoIface=" + (n instanceof NoIface));
    try { c.getBean(WithIface.class); System.out.println("RES   按具体类 WithIface 取 Bean:成功"); } catch (Exception e) { System.out.println("RES   按具体类 WithIface 取 Bean:✗ " + e.getClass().getSimpleName()); }
  }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    switch (m) {
      case "plain" -> { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(args[1].equals("class") ? ByClass.class : Default_.class); System.out.println("RES @EnableAspectJAutoProxy" + (args[1].equals("class") ? "(proxyTargetClass = true)" : "(默认)") + ":"); report(c); }
      case "boot" -> { SpringApplication app = new SpringApplication(BootApp.class); app.setWebApplicationType(WebApplicationType.NONE); app.setBannerMode(Banner.Mode.OFF); ConfigurableApplicationContext c = app.run(); System.out.println("RES Boot(@EnableAutoConfiguration,没有设任何 spring.aop.* 属性):"); report(c); System.out.println("RES   spring.aop.proxy-target-class 的值 = " + c.getEnvironment().getProperty("spring.aop.proxy-target-class", "(没设)")); }
      case "cost" -> {
        int N = 2000; var cl = ManagementFactory.getClassLoadingMXBean(); MethodInterceptor nop = Invocation::proceed;
        long c0 = cl.getTotalLoadedClassCount(); long t0 = System.nanoTime(); List<Object> js = new ArrayList<>();
        for (int i = 0; i < N; i++) { ProxyFactory pf = new ProxyFactory(new WithIface()); pf.setInterfaces(Greeter.class); pf.addAdvice(nop); js.add(pf.getProxy()); }
        long jMs = (System.nanoTime() - t0) / 1_000_000; long jCls = cl.getTotalLoadedClassCount() - c0;
        c0 = cl.getTotalLoadedClassCount(); t0 = System.nanoTime(); List<Object> cs = new ArrayList<>();
        for (int i = 0; i < N; i++) { ProxyFactory pf = new ProxyFactory(new WithIface()); pf.setProxyTargetClass(true); pf.addAdvice(nop); cs.add(pf.getProxy()); }
        long cMs = (System.nanoTime() - t0) / 1_000_000; long cCls = cl.getTotalLoadedClassCount() - c0;
        System.out.println("RES 为同一个目标类创建 " + N + " 个代理:JDK " + jMs + " ms(新加载 " + jCls + " 个类);CGLIB " + cMs + " ms(新加载 " + cCls + " 个类)");
        ProxyFactory pj = new ProxyFactory(new WithIface()); pj.setInterfaces(Greeter.class); pj.addAdvice(nop); Greeter jp = (Greeter) pj.getProxy();
        ProxyFactory pc = new ProxyFactory(new WithIface()); pc.setProxyTargetClass(true); pc.addAdvice(nop); WithIface cp = (WithIface) pc.getProxy(); WithIface direct = new WithIface();
        int R = 5_000_000; long sink = 0;
        for (int i = 0; i < 1_000_000; i++) sink += jp.hi().length() + cp.hi().length() + direct.hi().length();
        long t = System.nanoTime(); for (int i = 0; i < R; i++) sink += jp.hi().length(); double j = (System.nanoTime() - t) / (double) R;
        t = System.nanoTime(); for (int i = 0; i < R; i++) sink += cp.hi().length(); double cc = (System.nanoTime() - t) / (double) R;
        t = System.nanoTime(); for (int i = 0; i < R; i++) sink += direct.hi().length(); double d = (System.nanoTime() - t) / (double) R;
        System.out.println(String.format("RES 每次调用 hi()(代理上挂一个什么都不做的 MethodInterceptor):JDK 代理 %.0f ns;CGLIB 代理 %.0f ns;直接调用 %.1f ns(sink=%d)", j, cc, d, sink));
      }
      case "extra" -> {
        ProxyFactory pj = new ProxyFactory(new WithIface()); pj.setInterfaces(Greeter.class); Object jp = pj.getProxy();
        ProxyFactory pc = new ProxyFactory(new WithIface()); pc.setProxyTargetClass(true); Object cp = pc.getProxy();
        System.out.println("RES JDK 代理的类实现的接口:" + Arrays.stream(jp.getClass().getInterfaces()).map(i -> i.getSimpleName()).toList() + ";能否强转成 WithIface:" + (jp instanceof WithIface));
        System.out.println("RES CGLIB 代理的父类:" + cp.getClass().getSuperclass().getSimpleName() + ";能调用 extra()(接口里没有的方法):" + ((WithIface) cp).extra());
      }
    }
  }
}
'''
b = sbuild('x19', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(*a): r = srun(b, 'demo.Main', args=list(a)); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-900:]]
print('Spring Framework 7.0.9(含 spring-aop、AspectJ 注解)。Spring AOP 选 JDK 动态代理还是 CGLIB')
print('== 一:纯 Spring 里 @EnableAspectJAutoProxy 的默认行为。一个切面 Trace 同时匹配 WithIface(实现了 Greeter 接口)和 NoIface(没有接口)')
[print('  ' + l) for l in run('plain', 'default')]
print('== 二:@EnableAspectJAutoProxy(proxyTargetClass = true)')
[print('  ' + l) for l in run('plain', 'class')]
print('== 三:Spring Boot(@EnableAutoConfiguration)里同样的配置,没有设任何 spring.aop.* 属性')
[print('  ' + l) for l in run('boot')]
print('== 四:两种代理的外形差别')
[print('  ' + l) for l in run('extra')]
print('== 五:创建与调用的成本。ProxyFactory 手工创建,代理上挂一个什么都不做的 MethodInterceptor。3 次运行')
for _ in range(3): [print('  ' + l) for l in run('cost')]
