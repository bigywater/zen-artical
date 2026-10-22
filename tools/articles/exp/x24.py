import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x24'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><appender name="O" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{0}: %msg%n</pattern></encoder></appender><root level="ERROR"><appender-ref ref="O"/></root></configuration>'
MAIN = r'''
package demo;
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
import org.springframework.aop.interceptor.AsyncUncaughtExceptionHandler; import org.springframework.core.task.*;
import org.springframework.boot.*; import org.springframework.context.ConfigurableApplicationContext; import org.springframework.context.annotation.*; import org.springframework.scheduling.annotation.*; import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
public class Main {
  static final ThreadLocal<String> TL = new ThreadLocal<>(); static final Set<String> threads = ConcurrentHashMap.newKeySet(); static final AtomicInteger done = new AtomicInteger();
  public static class Work {
    @Async public void fire(int ms) { threads.add(Thread.currentThread().getName()); try { Thread.sleep(ms); } catch (InterruptedException e) { } done.incrementAndGet(); }
    @Async public void boomVoid() { throw new IllegalStateException("void 方法里的异常"); }
    @Async public CompletableFuture<String> boomFuture() { throw new IllegalStateException("Future 方法里的异常"); }
    @Async public String returnsString() { return "我是返回值"; }
    @Async public CompletableFuture<String> ok() { return CompletableFuture.completedFuture("来自 " + Thread.currentThread().getName() + ",ThreadLocal=" + TL.get()); }
    public String callInternal() { fire(0); return Thread.currentThread().getName(); } 
    @Async public void who(List<String> out) { out.add(Thread.currentThread().getName()); } }
  @Configuration @EnableAsync static class NoExec { @Bean Work work() { return new Work(); } }
  @Configuration @EnableAsync static class Pool implements AsyncConfigurer { @Bean Work work() { return new Work(); }
    public Executor getAsyncExecutor() { ThreadPoolTaskExecutor e = new ThreadPoolTaskExecutor(); e.setCorePoolSize(4); e.setMaxPoolSize(4); e.setQueueCapacity(1000); e.setThreadNamePrefix("pool-"); e.initialize(); return e; } }
  @Configuration @EnableAsync static class Handler implements AsyncConfigurer { @Bean Work work() { return new Work(); }
    public AsyncUncaughtExceptionHandler getAsyncUncaughtExceptionHandler() { return (ex, m, p) -> System.out.println("RES   自定义 AsyncUncaughtExceptionHandler 收到:" + ex.getMessage() + ",方法 " + m.getName()); } }
  @Configuration @EnableAsync static class Decor implements AsyncConfigurer { @Bean Work work() { return new Work(); }
    public Executor getAsyncExecutor() { ThreadPoolTaskExecutor e = new ThreadPoolTaskExecutor(); e.setCorePoolSize(2); e.setThreadNamePrefix("deco-"); e.setTaskDecorator(r -> { String v = TL.get(); return () -> { TL.set(v); try { r.run(); } finally { TL.remove(); } }; }); e.initialize(); return e; } }
  @Configuration @EnableAsync static class Sat implements AsyncConfigurer { final boolean callerRuns; Sat() { this(false); } Sat(boolean c) { callerRuns = c; } @Bean Work work() { return new Work(); }
    public Executor getAsyncExecutor() { ThreadPoolTaskExecutor e = new ThreadPoolTaskExecutor(); e.setCorePoolSize(2); e.setMaxPoolSize(2); e.setQueueCapacity(2); e.setThreadNamePrefix("sat-"); if (callerRuns) e.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy()); e.initialize(); return e; } }
  @Configuration @EnableAsync static class SatCaller extends Sat { SatCaller() { super(true); } }
  @Configuration static class BootConf { @Bean Work work() { return new Work(); } }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    switch (m) {
      case "default" -> { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(NoExec.class); Work w = c.getBean(Work.class); for (int i = 0; i < 100; i++) w.fire(30); Thread.sleep(800);
        System.out.println("RES 纯 Spring,@EnableAsync 没有配置执行器:100 次 @Async 调用(每次 30 ms)用了 " + threads.size() + " 个不同的线程,线程名举例 " + threads.stream().sorted().limit(2).toList()); System.exit(0); }
      case "pool" -> { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Pool.class); Work w = c.getBean(Work.class); for (int i = 0; i < 100; i++) w.fire(30); Thread.sleep(1500);
        System.out.println("RES 配了 ThreadPoolTaskExecutor(核心 4):100 次调用用了 " + threads.size() + " 个线程 " + threads.stream().sorted().toList() + ";完成 " + done.get() + " 个"); System.exit(0); }
      case "boot" -> { @SuppressWarnings("unused") Object o = null; SpringApplication app = new SpringApplication(BootAsync.class); app.setWebApplicationType(WebApplicationType.NONE); app.setBannerMode(Banner.Mode.OFF); ConfigurableApplicationContext c = app.run(); Work w = c.getBean(Work.class); for (int i = 0; i < 100; i++) w.fire(30); Thread.sleep(1500);
        System.out.println("RES Spring Boot(@EnableAutoConfiguration + @EnableAsync,没有配执行器):100 次调用用了 " + threads.size() + " 个线程 " + threads.stream().sorted().toList() + ";容器里的 TaskExecutor Bean:" + Arrays.toString(c.getBeanNamesForType(TaskExecutor.class))); System.exit(0); }
      case "exc" -> { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(args[1].equals("custom") ? Handler.class : NoExec.class); Work w = c.getBean(Work.class);
        w.boomVoid(); Thread.sleep(300); CompletableFuture<String> f = w.boomFuture(); try { f.get(); } catch (Exception e) { System.out.println("RES   boomFuture() 返回的 Future:get() 抛 " + e.getClass().getSimpleName() + " ← " + e.getCause().getClass().getSimpleName() + ": " + e.getCause().getMessage()); }
        try { System.out.println("RES   returnsString()(@Async 但返回 String)调用返回:" + w.returnsString()); } catch (Exception e) { System.out.println("RES   returnsString()(@Async 但返回 String)→ " + e.getClass().getSimpleName() + ": " + e.getMessage()); } System.exit(0); }
      case "ctx" -> { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(args[1].equals("deco") ? Decor.class : Pool.class); Work w = c.getBean(Work.class); TL.set("请求-42"); System.out.println("RES   " + (args[1].equals("deco") ? "加了 TaskDecorator" : "没有 TaskDecorator") + ":提交线程 ThreadLocal = 请求-42;异步线程里读到 → " + w.ok().get()); System.exit(0); }
      case "sat" -> { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(args[1].equals("caller") ? SatCaller.class : Sat.class); Work w = c.getBean(Work.class); int ok = 0, rej = 0; List<String> rejNames = new ArrayList<>(); long t0 = System.nanoTime();
        for (int i = 0; i < 10; i++) { try { w.fire(300); ok++; } catch (Exception e) { rej++; if (rejNames.size() < 1) rejNames.add(e.getClass().getSimpleName()); } }
        long submit = (System.nanoTime() - t0) / 1_000_000; Thread.sleep(1500); System.out.println("RES   核心 2、最大 2、队列 2" + (args[1].equals("caller") ? "、CallerRunsPolicy" : "、默认拒绝策略") + ",提交 10 个各 300 ms 的任务:提交本身花了 " + submit + " ms;被拒绝 " + rej + " 个 " + rejNames + ";最终完成 " + done.get() + " 个;执行过的线程 " + threads.stream().sorted().toList()); System.exit(0); }
      case "self" -> { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Pool.class); Work w = c.getBean(Work.class); List<String> out = Collections.synchronizedList(new ArrayList<>()); w.who(out); Thread.sleep(200); System.out.println("RES   从外部调用 @Async 方法 who():执行线程 " + out + ";callInternal() 里调 this.fire(0) 的调用者线程 " + w.callInternal() + "(内部调用不异步,见自调用篇)"); System.exit(0); }
    }
  }
  @Configuration @org.springframework.boot.autoconfigure.EnableAutoConfiguration @EnableAsync static class BootAsync { @Bean Work work() { return new Work(); } }
}
'''
b = sbuild('x24', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(*a): r = srun(b, 'demo.Main', args=list(a)); return [l[4:] if l.startswith('RES ') else l[:230] for l in r['out'].splitlines() if l.startswith('RES ') or l.startswith('LOG ')] or [r['out'][-900:]]
print('Spring Framework 7.0.9(@EnableAsync;一个 Work Bean,@Async 方法见下)。线程池、异常、上下文')
print('== 一:没有配置执行器时用什么线程池。纯 Spring 与 Spring Boot 的默认')
for k_ in ('default', 'boot', 'pool'): [print('  ' + l) for l in run(k_)]
print('== 二:异常去哪了。(a)默认(没有自定义处理器):void 方法、返回 CompletableFuture 的方法、@Async 但返回 String 的方法;(b)自定义 AsyncUncaughtExceptionHandler')
print('  (a)默认:'); [print('  ' + l) for l in run('exc', 'default')]
print('  (b)自定义处理器:'); [print('  ' + l) for l in run('exc', 'custom')]
print('== 三:ThreadLocal 能不能带到异步线程')
for k_ in ('plain', 'deco'): [print('  ' + l) for l in run('ctx', k_)]
print('== 四:执行器满了。核心 2、最大 2、队列 2,同时提交 10 个各 300 ms 的任务')
for k_ in ('reject', 'caller'): [print('  ' + l) for l in run('sat', k_)]
print('== 五:@Async 的内部调用')
[print('  ' + l) for l in run('self')]
