import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x13'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><appender name="O" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{0}: %msg%n</pattern></encoder></appender><root level="WARN"><appender-ref ref="O"/></root></configuration>'
MAIN = r'''
package demo;
import java.util.ArrayList; import java.util.Collections; import java.util.List; import java.util.concurrent.*;
import jakarta.annotation.PostConstruct;
import org.springframework.context.*; import org.springframework.context.annotation.*; import org.springframework.context.event.*; import org.springframework.core.annotation.Order;
public class Main {
  static final List<String> seq = Collections.synchronizedList(new ArrayList<>()); static void ev(String s) { seq.add(s + "  [线程 " + Thread.currentThread().getName() + "]"); }
  static void flush(String t) { System.out.println("RES --- " + t); int i = 1; synchronized (seq) { for (String s : seq) System.out.println("RES " + i++ + ". " + s); } seq.clear(); }
  public record OrderPlaced(String id, int amount) { }
  public static class Evt extends ApplicationEvent { final String msg; public Evt(Object src, String msg) { super(src); this.msg = msg; } }
  public static class Box<T> { final T v; Box(T v) { this.v = v; } }
  public static class BoxR<T> extends Box<T> implements org.springframework.core.ResolvableTypeProvider { BoxR(T v) { super(v); } public org.springframework.core.ResolvableType getResolvableType() { return org.springframework.core.ResolvableType.forClassWithGenerics(BoxR.class, v.getClass()); } }
  public static class Listeners {
    @EventListener @Order(2) void second(OrderPlaced e) { ev("second(@Order(2)) 收到 " + e.id()); }
    @EventListener @Order(1) void first(OrderPlaced e) { ev("first(@Order(1)) 收到 " + e.id()); }
    @EventListener(condition = "#e.amount > 100") void big(OrderPlaced e) { ev("big(condition amount>100) 收到 " + e.id() + " 金额 " + e.amount()); }
    @EventListener void onStr(Box<String> b) { ev("Box<String> 的监听器收到 " + b.v); }
    @EventListener void onStrR(BoxR<String> b) { ev("BoxR<String> 的监听器收到 " + b.v); }
    @EventListener void onIntR(BoxR<Integer> b) { ev("BoxR<Integer> 的监听器收到 " + b.v); }
    @EventListener void onInt(Box<Integer> b) { ev("Box<Integer> 的监听器收到 " + b.v); }
    @EventListener Evt chain(OrderPlaced e) { return new Evt(this, "由监听器的返回值发布:" + e.id()); }
    @EventListener void onEvt(Evt e) { ev("onEvt 收到 " + e.msg); }
  }
  public static class Boom { @EventListener @Order(1) void bad(Evt e) { ev("bad(@Order(1)) 抛异常"); throw new IllegalStateException("监听器失败"); } @EventListener @Order(2) void after(Evt e) { ev("after(@Order(2)) 收到"); } }
  @Configuration static class Sync { @Bean Listeners l() { return new Listeners(); } }
  @Configuration static class BoomConf { @Bean Boom b() { return new Boom(); } }
  @Configuration static class AsyncConf {
    @Bean(name = "applicationEventMulticaster") SimpleApplicationEventMulticaster m() { SimpleApplicationEventMulticaster m = new SimpleApplicationEventMulticaster(); ThreadPoolExecutor ex = new ThreadPoolExecutor(2, 2, 1, TimeUnit.SECONDS, new LinkedBlockingQueue<>(), r -> new Thread(r, "event-pool")); m.setTaskExecutor(ex); m.setErrorHandler(t -> ev("ErrorHandler 收到异常:" + t.getMessage())); return m; }
    @Bean Boom b() { return new Boom(); } @Bean Slow s() { return new Slow(); } }
  public static class Slow { @EventListener void slow(OrderPlaced e) throws Exception { Thread.sleep(300); ev("Slow 监听器处理完 " + e.id()); } }
  // 早期事件
  public static class Early { Early(ApplicationEventPublisher p) { this.p = p; } final ApplicationEventPublisher p; @PostConstruct void init() { p.publishEvent(new Evt(this, "Early.@PostConstruct 里发布")); ev("Early.@PostConstruct 发布完毕"); } }
  public static class Cls implements ApplicationListener<Evt> { public void onApplicationEvent(Evt e) { ev("ApplicationListener 类型的 Bean 收到 " + e.msg); } }
  public static class Anno { @EventListener void on(Evt e) { ev("@EventListener 方法收到 " + e.msg); } }
  @Configuration static class EarlyConf { @Bean Early early(ApplicationEventPublisher p) { return new Early(p); } @Bean Cls cls() { return new Cls(); } @Bean Anno anno() { return new Anno(); } }
  @Configuration static class Built { @Bean Anno2 a() { return new Anno2(); } }
  public static class Anno2 { @EventListener void r(ContextRefreshedEvent e) { ev("ContextRefreshedEvent"); } @EventListener void s(ContextStartedEvent e) { ev("ContextStartedEvent"); } @EventListener void c(ContextClosedEvent e) { ev("ContextClosedEvent"); } @EventListener void st(ContextStoppedEvent e) { ev("ContextStoppedEvent"); } }
  public static void main(String[] args) throws Exception {
    String m = args[0]; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext();
    switch (m) {
      case "sync" -> { c.register(Sync.class); c.refresh(); ev("publisher 调用 publishEvent 之前"); c.publishEvent(new OrderPlaced("A1", 50)); ev("publisher 的 publishEvent 返回了"); c.publishEvent(new OrderPlaced("A2", 500)); ev("publisher 的 publishEvent 返回了"); flush("同步发布两个 OrderPlaced(金额 50 与 500)"); seq.clear(); c.publishEvent(new Box<>("字符串")); c.publishEvent(new Box<>(42)); ev("(以上两个 Box 事件发布完,上面没有任何 Box 监听器被调用的记录就是没有被调用)"); flush("泛型事件:普通的 Box<String> 与 Box<Integer>(类型实现 ResolvableTypeProvider 之前)"); c.publishEvent(new BoxR<>("字符串")); c.publishEvent(new BoxR<>(42)); flush("泛型事件:实现了 ResolvableTypeProvider 的 BoxR<String> 与 BoxR<Integer>"); }
      case "boom" -> { c.register(BoomConf.class); c.refresh(); try { c.publishEvent(new Evt("t", "x")); } catch (Exception e) { ev("publishEvent 抛给了发布者:" + e.getClass().getSimpleName() + ": " + e.getMessage()); } flush("同步监听器抛异常"); }
      case "async" -> { c.register(AsyncConf.class); c.refresh(); long t0 = System.nanoTime(); c.publishEvent(new OrderPlaced("B1", 1)); ev("publishEvent 返回,用了 " + (System.nanoTime() - t0) / 1_000_000 + " ms"); c.publishEvent(new Evt("t", "y")); ev("第二个 publishEvent 返回"); Thread.sleep(800); flush("多播器配了线程池(SimpleApplicationEventMulticaster.setTaskExecutor)与 ErrorHandler"); System.exit(0); }
      case "early" -> { c.register(EarlyConf.class); c.refresh(); flush("在 Early 的 @PostConstruct 里发布事件(此时容器还在 refresh 的单例创建阶段)"); }
      case "builtin" -> { c.register(Built.class); c.refresh(); c.start(); c.stop(); c.close(); flush("内置事件"); }
    }
  }
}
'''
b = sbuild('x13', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): r = srun(b, 'demo.Main', args=[m]); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-600:]]
print('Spring Framework 7.0.9。ApplicationEvent 与 @EventListener')
print('== 一:同步事件。普通的 publishEvent:监听器在谁的线程里执行,发布者要不要等,@Order 和 condition、泛型、返回值再发布')
[print('  ' + l) for l in run('sync')]
print('== 二:同步监听器抛异常。两个监听器 bad(@Order(1))、after(@Order(2))')
[print('  ' + l) for l in run('boom')]
print('== 三:多播器配线程池。Evt 的两个监听器(bad 抛异常、after),OrderPlaced 的监听器 Slow 睡 300 ms。ErrorHandler 记录异常')
[print('  ' + l) for l in run('async')]
print('== 四:在 bean 初始化阶段发布事件。Early 的 @PostConstruct 发布 Evt;两个监听器:一个是实现了 ApplicationListener 的 Bean(Cls),一个是 @EventListener 方法(Anno)')
[print('  ' + l) for l in run('early')]
print('== 五:容器自带的几个事件的顺序(refresh、start、stop、close 各调用一次)')
[print('  ' + l) for l in run('builtin')]
