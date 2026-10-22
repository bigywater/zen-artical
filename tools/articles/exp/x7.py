import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x7'); CP = scp('org.springframework.boot:spring-boot-starter', 'org.springframework.boot:spring-boot-starter-aspectj')
MAIN = r'''
package demo;
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
import org.springframework.aop.support.AopUtils; import org.springframework.aop.scope.ScopedObject;
import org.springframework.beans.factory.ObjectProvider; import org.springframework.beans.factory.annotation.*; import org.springframework.beans.factory.config.CustomScopeConfigurer;
import org.springframework.context.annotation.*; import org.springframework.context.support.SimpleThreadScope;
public class Main {
  static final AtomicInteger made = new AtomicInteger();
  public static class Proto { final int id = made.incrementAndGet(); public int id() { return id; } }
  public interface Ctx { int id(); }
  public static class ThreadCtx implements Ctx { final int id = made.incrementAndGet(); final String thread = Thread.currentThread().getName(); public int id() { return id; } public String thread() { return thread; } }
  // 一/二:singleton 里注入 prototype
  public static class Naive { @Autowired Proto p; int use() { return p.id(); } }
  public static class WithProvider { @Autowired ObjectProvider<Proto> p; int use() { return p.getObject().id(); } }
  public static abstract class WithLookup { @Lookup public abstract Proto make(); int use() { return make().id(); } }
  public static class WithProxy { @Autowired Proto p; int use() { return p.id(); } }
  @Configuration static class Conf {
    @Bean @Scope("prototype") Proto proto() { return new Proto(); } @Bean Naive naive() { return new Naive(); } @Bean WithProvider withProvider() { return new WithProvider(); }
    @Bean WithLookup withLookup() { return new WithLookup() { @Override public Proto make() { throw new IllegalStateException("会被 Spring 的子类重写"); } }; } }
  @Configuration @ComponentScan(basePackageClasses = Main.class, useDefaultFilters = false, includeFilters = @ComponentScan.Filter(type = FilterType.ASSIGNABLE_TYPE, classes = LookupBean.class)) static class LookupConf { @Bean @Scope("prototype") Proto proto() { return new Proto(); } }
  @org.springframework.stereotype.Component public static abstract class LookupBean { @Lookup public abstract Proto make(); int use() { return make().id(); } }
  @Configuration static class ProxyConf { @Bean @Scope(value = "prototype", proxyMode = ScopedProxyMode.TARGET_CLASS) Proto proto() { return new Proto(); } @Bean WithProxy withProxy() { return new WithProxy(); } }
  // 三:thread 作用域 + scoped proxy
  public static class Holder { @Autowired Ctx ctx; }
  @Configuration static class ThreadConf {
    @Bean static CustomScopeConfigurer scopes() { CustomScopeConfigurer c = new CustomScopeConfigurer(); c.addScope("thread", new SimpleThreadScope()); return c; }
    @Bean @Scope(value = "thread", proxyMode = ScopedProxyMode.INTERFACES) Ctx ctx() { return new ThreadCtx(); } @Bean Holder holder() { return new Holder(); } }
  @Configuration static class ThreadClassConf {
    @Bean static CustomScopeConfigurer scopes() { CustomScopeConfigurer c = new CustomScopeConfigurer(); c.addScope("thread", new SimpleThreadScope()); return c; }
    @Bean @Scope(value = "thread", proxyMode = ScopedProxyMode.INTERFACES) ThreadCtx ctx() { return new ThreadCtx(); } @Bean ByClass byClass(ThreadCtx t) { return new ByClass(); } }
  public static class ByClass { }
  // 五:singleton 共享可变状态
  public static class Counter { int n; AtomicInteger a = new AtomicInteger(); void inc() { n++; } }
  @Configuration static class CounterConf { @Bean Counter counter() { return new Counter(); } }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    if (m.equals("naive")) {
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class);
      Naive n = c.getBean(Naive.class); WithProvider wp = c.getBean(WithProvider.class);
      System.out.println("RES (a) 单例 Naive 里 @Autowired 了 prototype 的 Proto:连续 3 次 use() 得到的 id → " + n.use() + "," + n.use() + "," + n.use() + "(同一个对象:创建 Naive 时注入的那一个)");
      System.out.println("RES (b) ObjectProvider<Proto>.getObject():连续 3 次得到的 id → " + wp.use() + "," + wp.use() + "," + wp.use());
      System.out.println("RES     直接 getBean(Proto) 两次的 id → " + c.getBean(Proto.class).id() + "," + c.getBean(Proto.class).id());
    } else if (m.equals("lookup")) {
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(LookupConf.class); made.set(0); LookupBean l = c.getBean(LookupBean.class);
      System.out.println("RES (c) @Lookup:连续 3 次 use() 的 id → " + l.use() + "," + l.use() + "," + l.use() + ";LookupBean 的类 " + l.getClass().getSimpleName().split("\\$\\$")[0] + "$$…" + "(Spring 生成的 CGLIB 子类)");
    } else if (m.equals("protoproxy")) {
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(ProxyConf.class); made.set(0); WithProxy w = c.getBean(WithProxy.class);
      System.out.println("RES (d) prototype + scoped proxy(TARGET_CLASS):注入的是代理?" + AopUtils.isAopProxy(w.p) + ";连续 3 次 p.id() → " + w.use() + "," + w.use() + "," + w.use() + "(每次方法调用都创建了新的目标对象);made=" + made.get());
    } else if (m.equals("thread")) {
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(ThreadConf.class); made.set(0); Holder h = c.getBean(Holder.class);
      System.out.println("RES 单例 Holder 里的 ctx 是代理?" + AopUtils.isAopProxy(h.ctx) + ",实现了 ScopedObject?" + (h.ctx instanceof ScopedObject));
      System.out.println("RES 主线程连续 3 次 id → " + h.ctx.id() + "," + h.ctx.id() + "," + h.ctx.id());
      List<Integer> ids = Collections.synchronizedList(new ArrayList<>()); List<Thread> ts = new ArrayList<>();
      for (int i = 0; i < 3; i++) { Thread t = new Thread(() -> { ids.add(h.ctx.id()); ids.add(h.ctx.id()); }, "T" + i); ts.add(t); t.start(); } for (Thread t : ts) t.join();
      Collections.sort(ids); System.out.println("RES 另外 3 个线程各调用 2 次,拿到的 id(排序后)→ " + ids + ";目标对象一共创建了 " + made.get() + " 个(主线程 1 个 + 3 个线程各 1 个)");
    } else if (m.equals("byclass")) {
      try { new AnnotationConfigApplicationContext(ThreadClassConf.class); System.out.println("RES 按具体类 ThreadCtx 注入:成功"); } catch (Exception e) { Throwable t = e; while (t.getCause() != null) t = t.getCause(); System.out.println("RES proxyMode=INTERFACES,却按具体类 ThreadCtx 注入 → " + t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).split("\n")[0].replace("demo.Main$", "")); }
    } else if (m.equals("shared")) {
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(CounterConf.class); Counter k = c.getBean(Counter.class);
      int threads = 8, per = 200000; ExecutorService ex = Executors.newFixedThreadPool(threads); List<Future<?>> fs = new ArrayList<>();
      for (int i = 0; i < threads; i++) fs.add(ex.submit(() -> { for (int j = 0; j < per; j++) { k.inc(); k.a.incrementAndGet(); } })); for (Future<?> f : fs) f.get(); ex.shutdown();
      System.out.println("RES 单例里的 int 字段 n++:期望 " + threads * per + ",实际 " + k.n + ",丢了 " + (threads * per - k.n) + " 次;同一个单例里的 AtomicInteger:" + k.a.get());
    }
  }
}
'''
b = sbuild('x7', {'src/demo/Main.java': MAIN, 'logback.xml': '<configuration><root level="ERROR"/></configuration>'}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): r = srun(b, 'demo.Main', args=[m]); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-600:]]
print('Spring Framework 7.0.9(含 spring-aop 的 scoped proxy)。作用域与单例里的状态')
print('== 一:单例里注入 prototype。(a)直接 @Autowired Proto;(b)ObjectProvider<Proto>.getObject()')
[print('  ' + l) for l in run('naive')]
print('== 二:另外两种办法。(c)@Lookup 方法注入;(d)prototype 加 scoped proxy(proxyMode = TARGET_CLASS)')
[print('  ' + l) for l in run('lookup')]; [print('  ' + l) for l in run('protoproxy')]
print('== 三:自定义 thread 作用域(SimpleThreadScope)加 scoped proxy(INTERFACES)。单例 Holder 持有的 ctx 是代理;主线程与另外 3 个线程各自拿到什么')
[print('  ' + l) for l in run('thread')]
print('== 四:proxyMode = INTERFACES 的代理只实现了接口,按具体类 ThreadCtx 注入会怎样')
[print('  ' + l) for l in run('byclass')]
print('== 五:单例的线程安全。一个单例里有 int 字段和 AtomicInteger,8 个线程各调用 200000 次')
for _ in range(3): [print('  ' + l) for l in run('shared')]
