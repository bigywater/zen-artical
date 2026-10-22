import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x20'); CP = scp('org.springframework.boot:spring-boot-starter', 'org.springframework.boot:spring-boot-starter-aspectj')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.aspectj.lang.JoinPoint; import org.aspectj.lang.annotation.*;
import org.springframework.context.annotation.*; import org.springframework.stereotype.Component;
public class Main {
  static final List<String> hits = new ArrayList<>();
  @java.lang.annotation.Retention(java.lang.annotation.RetentionPolicy.RUNTIME) public @interface Audited { }
  @java.lang.annotation.Retention(java.lang.annotation.RetentionPolicy.RUNTIME) public @interface Marked { }
  public interface Api { String ping(); }
  public static class OrderService implements Api { 
    public String place(String id) { return "placed " + id; } @Audited public String cancel(String id) { return "cancelled " + id; } String pkgPrivate() { return "pkg"; } protected String prot() { return "prot"; } private String priv() { return "priv"; } public String ping() { return "pong"; }
    public String callInternal() { return place("inner"); } }
  @Marked public static class PayService { public String pay(int n) { return "paid " + n; } public String refund(int n) { return "refund " + n; } }
  public static class UserService { public String find(long id) { return "user " + id; } }
  @Aspect public static class Pcs {
    @Before("execution(* demo.Main.OrderService.place(..))") public void a1(JoinPoint jp) { hits.add("execution(* OrderService.place(..))"); }
    @Before("execution(* demo.Main.OrderService.*(..))") public void a2(JoinPoint jp) { hits.add("execution(* OrderService.*(..))→" + jp.getSignature().getName()); }
    @Before("within(demo.Main.PayService)") public void a3(JoinPoint jp) { hits.add("within(PayService)→" + jp.getSignature().getName()); }
    @Before("@annotation(demo.Main.Audited)") public void a4(JoinPoint jp) { hits.add("@annotation(Audited)→" + jp.getSignature().getName()); }
    @Before("@within(demo.Main.Marked)") public void a5(JoinPoint jp) { hits.add("@within(Marked)→" + jp.getSignature().getName()); }
    @Before("target(demo.Main.Api)") public void a6(JoinPoint jp) { hits.add("target(Api)→" + jp.getSignature().getName()); }
    @Before("execution(* demo.Main.UserService.find(long)) && args(id)") public void a7(JoinPoint jp, long id) { hits.add("execution(find(long)) && args(id) 拿到 id=" + id); }
    @Before("bean(userService)") public void a8(JoinPoint jp) { hits.add("bean(userService)→" + jp.getSignature().getName()); }
    @Before("execution(public * *(..)) && within(demo.Main.PayService)") public void a9(JoinPoint jp) { hits.add("execution(public * *(..)) && within(PayService)→" + jp.getSignature().getName()); }
    @Before("execution(* demo.Main.*Service.re*(..))") public void a10(JoinPoint jp) { hits.add("execution(* *Service.re*(..))→" + jp.getSignature().getDeclaringType().getSimpleName() + "." + jp.getSignature().getName()); }
  }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class Conf { @Bean Pcs pcs() { return new Pcs(); } @Bean OrderService orderService() { return new OrderService(); } @Bean PayService payService() { return new PayService(); } @Bean UserService userService() { return new UserService(); } }
  public static class CostSvc implements Api { public int n; @Audited public String m(long id) { return "m"; } public String ping() { return "p"; } }
  @Aspect public static class A0 { }
  @Aspect public static class A1 { @Before("execution(* demo.Main.CostSvc.m(..))") public void a() { Main.cnt++; } }
  @Aspect public static class A2 { @Before("execution(* demo.Main.CostSvc.m(..)) && args(id)") public void a(long id) { Main.cnt++; } }
  @Aspect public static class A3 { @Before("@annotation(demo.Main.Audited)") public void a() { Main.cnt++; } }
  @Aspect public static class A4 { @Before("target(demo.Main.Api)") public void a() { Main.cnt++; } }
  @Aspect public static class A5 { @Before("execution(* demo.Main.CostSvc.m(..)) && args(java.lang.String)") public void a() { Main.cnt++; } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) static class CostConf { @Bean CostSvc costSvc() { return new CostSvc(); } }
  static long cnt;
  static String[] COST = {"没有切面", "execution(...)", "execution(...) && args(id)", "@annotation(Audited)", "target(Api)", "execution(...) && args(String)(m 的参数是 long,静态就不可能匹配)"};
  static void call(String label, java.util.concurrent.Callable<Object> c) throws Exception { hits.clear(); Object r = null; String err = null; try { r = c.call(); } catch (Exception e) { err = e.getClass().getSimpleName(); } System.out.println("RES " + String.format("%-34s → 命中 %s", label, hits.isEmpty() ? "(没有)" : hits)); }
  public static void main(String[] args) throws Exception {
    if (args.length > 0 && args[0].equals("cost")) {
      int k = Integer.parseInt(args[1]); Class<?>[] as = {A0.class, A1.class, A2.class, A3.class, A4.class, A5.class};
      AnnotationConfigApplicationContext cc = new AnnotationConfigApplicationContext(); cc.register(CostConf.class, as[k]); cc.refresh(); CostSvc cs = cc.getBean(CostSvc.class);
      for (int i = 0; i < 2_000_000; i++) cs.m(i); cnt = 0; long R = 5_000_000; long t = System.nanoTime(); for (long i = 0; i < R; i++) cs.m(i); double ns = (System.nanoTime() - t) / (double) R;
      System.out.println(String.format("RES %s|%.0f|%d|%s", COST[k], ns, cnt, org.springframework.aop.support.AopUtils.isAopProxy(cs) ? "是代理" : "不是代理")); return;
    }
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); OrderService o = c.getBean(OrderService.class); PayService p = c.getBean(PayService.class); UserService u = c.getBean(UserService.class);
    call("orderService.place(\"1\")", () -> o.place("1")); call("orderService.cancel(\"1\")(@Audited)", () -> o.cancel("1")); call("orderService.ping()", () -> o.ping());
    call("orderService.callInternal()(内部调 place)", () -> o.callInternal());
    call("payService.pay(5)", () -> p.pay(5)); call("payService.refund(5)", () -> p.refund(5));
    call("userService.find(7L)", () -> u.find(7L));
    java.lang.reflect.Method m = OrderService.class.getDeclaredMethod("pkgPrivate"); m.setAccessible(true);
    call("orderService.pkgPrivate()(包可见)", () -> { return o.pkgPrivate(); });
    call("orderService.prot()(protected)", () -> o.prot());
  }
}
'''
b = sbuild('x20', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
r = srun(b, 'demo.Main'); L = [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-900:]]
print('Spring Framework 7.0.9(Spring AOP + AspectJ 注解,proxyTargetClass = true)。切点表达式匹配到什么。三个 Bean:OrderService(实现 Api,有 place、被 @Audited 标注的 cancel、ping、包可见的 pkgPrivate、protected 的 prot)、PayService(类上有 @Marked,有 pay、refund)、UserService(find(long))。10 个 @Before 通知各带一个不同的切点,每次调用后列出命中了哪几个')
print('== 一:每个调用命中的通知')
[print('  ' + l) for l in L]
print('== 二:切点的类型决定每次调用要不要在运行时再判断一次。同一个 CostSvc.m(long)(带 @Audited,实现 Api),通知里只做一个计数加一,每种切点各跑 3 次(5000000 次调用,预热 2000000 次)。「通知执行次数」是真正执行通知的次数;最后一行没有创建代理(AopUtils.isAopProxy = false)')
rows = {}
for rep in range(3):
    for k in range(6):
        o = srun(b, 'demo.Main', args=['cost', str(k)])['out']; l = [x[4:] for x in o.splitlines() if x.startswith('RES ')]
        if l: lab, ns, cnt, prox = l[0].split('|'); rows.setdefault(lab, []).append((float(ns), int(cnt), prox))
for lab, v in rows.items(): print(f'  {lab}:每次调用 ' + '、'.join(f'{x[0]:.0f}' for x in v) + f' ns;通知执行次数 {v[0][1]};{v[0][2]}')
