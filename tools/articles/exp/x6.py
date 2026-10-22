import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x6'); CP = scp('org.springframework.boot:spring-boot-starter', 'org.springframework.boot:spring-boot-starter-aspectj')
MAIN = r'''
package demo;
import java.util.*;
import jakarta.annotation.PostConstruct;
import org.aspectj.lang.annotation.*;
import org.springframework.aop.support.AopUtils;
import org.springframework.beans.factory.annotation.Autowired; import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.context.annotation.*; import org.springframework.stereotype.Component;
public class Main {
  static final List<String> seq = new ArrayList<>();
  static void ev(String s) { seq.add(s); }
  // 一:setter / 字段循环
  public static class A { B b; boolean ready; public A() { ev("构造 A"); } @Autowired public void setB(B b) { this.b = b; ev("A.setB(B 已经构造" + (b.ready ? "且初始化完成" : ",但还没初始化完成") + ")"); } @PostConstruct void init() { ready = true; ev("A.@PostConstruct"); } }
  public static class B { A a; boolean ready; public B() { ev("构造 B"); } @Autowired public void setA(A a) { this.a = a; ev("B.setA(拿到的 A " + (a.ready ? "已初始化完成" : "还没初始化完成") + ")"); } @PostConstruct void init() { ready = true; ev("B.@PostConstruct(此时 A.ready=" + a.ready + ")"); } }
  @Configuration static class Cyc { @Bean A a() { return new A(); } @Bean B b() { return new B(); } }
  // 二:构造器循环
  public static class CA { public CA(CB b) { } } public static class CB { public CB(CA a) { } }
  @Configuration static class CtorCyc { @Bean CA ca(CB b) { return new CA(b); } @Bean CB cb(CA a) { return new CB(a); } }
  // 三:循环 + 自定义 BPP 包装(没有 getEarlyBeanReference)
  public interface Svc { String hi(); }
  public static class SA implements Svc { @Autowired SB sb; public SA() { ev("构造 SA"); } @Autowired public void setSb2(SB x) { ev("SA 注入 SB(此时 SB 里的 sa=" + (x.sa == null ? "null" : x.sa.getClass().getSimpleName()) + ")"); } public String hi() { return "SA"; } }
  public static class SB { @Autowired Svc sa; public SB() { ev("构造 SB"); } @Autowired public void setSa2(Svc s) { ev("SB 注入 sa:" + (java.lang.reflect.Proxy.isProxyClass(s.getClass()) ? "代理" : "原始对象")); } }
  public static class WrapBpp implements BeanPostProcessor {
    public Object postProcessAfterInitialization(Object b, String n) { if (b instanceof SA) { Svc t = (Svc) b; return java.lang.reflect.Proxy.newProxyInstance(Main.class.getClassLoader(), new Class<?>[]{Svc.class}, (p, m, a) -> m.invoke(t, a)); } return b; } }
  @Configuration static class WrapCyc { @Bean static WrapBpp w() { return new WrapBpp(); } @Bean SA sa() { return new SA(); } @Bean SB sb() { return new SB(); } }
  // 四:循环 + Spring AOP
  @Aspect @Component public static class Asp { @Around("execution(* demo.Main.PA.hello(..))") public Object around(org.aspectj.lang.ProceedingJoinPoint pj) throws Throwable { return "[切面]" + pj.proceed(); } }
  @Component public static class PA { @Autowired PB pb; public String hello() { return "PA.hello"; } }
  @Component public static class PB { @Autowired PA pa; }
  @Configuration @EnableAspectJAutoProxy @Import({Asp.class, PA.class, PB.class}) static class AopCyc { }
  // 五:@Lazy 打破构造器循环
  public static class LA { public LA(@Lazy LB b) { ev("构造 LA(拿到的 LB 是" + (b.getClass().getName().contains("$$") || b.getClass().getName().contains("Proxy") ? "一个懒加载代理" : "真对象") + ")"); } }
  public static class LB { public LB(LA a) { ev("构造 LB"); } }
  @Configuration static class LazyCyc { @Bean LA la(@Lazy LB b) { return new LA(b); } @Bean LB lb(LA a) { return new LB(a); } }
  static void tryRun(String label, Class<?> c, boolean showSeq) {
    seq.clear();
    try { AnnotationConfigApplicationContext ctx = new AnnotationConfigApplicationContext(c); if (showSeq) { int i = 1; for (String s : seq) System.out.println("RES   " + (i++) + ". " + s); } 
      if (c == Cyc.class) { A a = ctx.getBean(A.class); B b = ctx.getBean(B.class); System.out.println("RES   a.b == b ? " + (a.b == b) + ";b.a == a ? " + (b.a == a)); }
      if (c == WrapCyc.class) { int i = 1; for (String q : seq) System.out.println("RES   " + (i++) + ". " + q); SB sb = ctx.getBean(SB.class); Svc sa = ctx.getBean(Svc.class); System.out.println("RES   isAllowRawInjectionDespiteWrapping=" + ctx.getDefaultListableBeanFactory().isAllowRawInjectionDespiteWrapping() + ";构造 SA 的次数 " + seq.stream().filter(q -> q.equals("构造 SA")).count() + ",构造 SB 的次数 " + seq.stream().filter(q -> q.equals("构造 SB")).count()); System.out.println("RES   启动成功。容器里的 sa 是代理?" + java.lang.reflect.Proxy.isProxyClass(sa.getClass()) + ";SB 里持有的 sa 是代理?" + java.lang.reflect.Proxy.isProxyClass(sb.sa.getClass()) + ";两者是同一个对象?" + (sa == sb.sa)); }
      if (c == AopCyc.class) { PA pa = ctx.getBean(PA.class); PB pb = ctx.getBean(PB.class); System.out.println("RES   容器里的 PA 是代理?" + AopUtils.isAopProxy(pa) + ";PB 持有的 pa 是代理?" + AopUtils.isAopProxy(pb.pa) + ";pb.pa.hello() = " + pb.pa.hello() + ";pb.pa 就是容器里的 PA?" + (pb.pa == pa)); }
      ctx.close(); }
    catch (Exception e) { Throwable t = e; while (t.getCause() != null && !(t instanceof org.springframework.beans.factory.BeanCurrentlyInCreationException)) t = t.getCause(); System.out.println("RES   " + label + " → " + t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).split("\n")[0].replace("demo.Main$", "")); }
  }
  public static void main(String[] args) {
    String m = args[0];
    switch (m) {
      case "setter" -> tryRun("setter", Cyc.class, true);
      case "ctor" -> tryRun("ctor", CtorCyc.class, false);
      case "wrap" -> tryRun("wrap", WrapCyc.class, false);
      case "aop" -> tryRun("aop", AopCyc.class, false);
      case "lazy" -> tryRun("lazy", LazyCyc.class, true);
      case "boot" -> {
        boolean allow = Boolean.parseBoolean(args[1]);
        org.springframework.boot.SpringApplication app = new org.springframework.boot.SpringApplication(Cyc.class); app.setWebApplicationType(org.springframework.boot.WebApplicationType.NONE); app.setBannerMode(org.springframework.boot.Banner.Mode.OFF);
        if (allow) app.setAllowCircularReferences(true);
        try { app.run().close(); System.out.println("RES   allowCircularReferences=" + allow + ":启动成功"); } catch (Exception e) { Throwable t = e; while (t.getCause() != null) t = t.getCause(); System.out.println("RES   allowCircularReferences=" + allow + ":" + t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).split("\n")[0]); }
      }
    }
  }
}
'''
b = sbuild('x6', {'src/demo/Main.java': MAIN, 'logback.xml': '<configuration><root level="ERROR"/></configuration>'}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(*a): r = srun(b, 'demo.Main', args=list(a)); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')], r
print('Spring Framework 7.0.9(含 Boot 的 SpringApplication 与 Spring AOP / AspectJ)。循环依赖:A 依赖 B,B 又依赖 A')
print('== 一:setter / 字段注入的循环(纯 Spring)。A、B 互相依赖,记下构造、注入、初始化的时间线')
L, r = run('setter'); [print('  ' + l) for l in L]
print('== 二:构造器注入的循环(纯 Spring)')
L, r = run('ctor'); [print('  ' + l) for l in L]
print('== 三:Spring Boot 的 SpringApplication 对 setter 循环的态度')
for v in ('false', 'true'): L, r = run('boot', v); [print('  ' + l) for l in L]
print('== 四:循环依赖 + 自定义 BPP 在 postProcessAfterInitialization 里把 SA 换成 JDK 代理(这个 BPP 只实现了 BeanPostProcessor,没有提前暴露代理的能力)。我记得老版本在这里会抛 “has been injected into other beans in its raw version as part of a circular reference, but has eventually been wrapped” 这样的异常(没有在老版本上验证)。看 7.0.9 里发生了什么')
L, r = run('wrap'); [print('  ' + l) for l in L]
print('== 五:循环依赖 + Spring AOP(@Aspect 环绕通知 PA.hello,PA 与 PB 互相依赖)。Spring 的自动代理创建器会提前暴露代理')
L, r = run('aop'); [print('  ' + l) for l in L]
print('== 六:用 @Lazy 打破构造器循环(LA 的构造器参数 LB 标 @Lazy)')
L, r = run('lazy'); [print('  ' + l) for l in L]
