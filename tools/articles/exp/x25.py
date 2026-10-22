import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x25'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><appender name="O" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{0}: %msg%n</pattern></encoder></appender><root level="ERROR"><appender-ref ref="O"/></root></configuration>'
MAIN = r'''
package demo;
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
import org.springframework.boot.*; import org.springframework.context.ConfigurableApplicationContext; import org.springframework.context.annotation.*; import org.springframework.scheduling.TaskScheduler; import org.springframework.scheduling.annotation.*; import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
public class Main {
  static long T0; static final List<String> log = Collections.synchronizedList(new ArrayList<>());
  static void rec(String n, long bodyMs) { long s = (System.nanoTime() - T0) / 1_000_000; log.add(String.format("%5d ms  %-9s [%s] 开始,耗时 %d ms", s, n, Thread.currentThread().getName(), bodyMs)); try { Thread.sleep(bodyMs); } catch (InterruptedException e) { } }
  static void dump(String t, int from) { System.out.println("RES --- " + t); synchronized (log) { for (String l : log) System.out.println("RES " + l); } log.clear(); }
  // 一:一个快任务和一个慢任务,默认调度器
  public static class Two { @Scheduled(fixedRate = 200, initialDelay = 100) public void fast() { rec("fast", 5); } @Scheduled(fixedRate = 3000, initialDelay = 500) public void slow() { rec("slow", 1000); } }
  @Configuration @EnableScheduling static class C1 { @Bean Two two() { return new Two(); } }
  @Configuration @EnableScheduling static class C1p implements SchedulingConfigurer { @Bean Two two() { return new Two(); } public void configureTasks(org.springframework.scheduling.config.ScheduledTaskRegistrar r) { ThreadPoolTaskScheduler s = new ThreadPoolTaskScheduler(); s.setPoolSize(3); s.setThreadNamePrefix("sched-"); s.initialize(); r.setTaskScheduler(s); } }
  // 二:fixedRate / fixedDelay 遇到慢任务
  public static class Rate { @Scheduled(fixedRate = 300) public void r() { rec("fixedRate", 500); } }
  public static class Delay { @Scheduled(fixedDelay = 300) public void d() { rec("fixedDelay", 500); } }
  @Configuration @EnableScheduling static class C2a { @Bean Rate r() { return new Rate(); } } @Configuration @EnableScheduling static class C2b { @Bean Delay d() { return new Delay(); } }
  // 五:异常
  public static class Boom { final AtomicInteger n = new AtomicInteger(); @Scheduled(fixedRate = 300) public void b() { int i = n.incrementAndGet(); rec("boom#" + i, 0); if (i == 2) throw new IllegalStateException("第 2 次抛异常"); } }
  @Configuration @EnableScheduling static class C5 { @Bean Boom b() { return new Boom(); } }
  // 六:@Scheduled + @Async
  public static class AsyncJob { @Scheduled(fixedRate = 200, initialDelay = 100) @Async public void a() { rec("asyncSlow", 700); } }
  @Configuration @EnableScheduling @EnableAsync static class C6 { @Bean AsyncJob a() { return new AsyncJob(); } }
  @Configuration @org.springframework.boot.autoconfigure.EnableAutoConfiguration @EnableScheduling static class BootC { @Bean Two two() { return new Two(); } }
  public static void main(String[] args) throws Exception {
    String m = args[0]; T0 = System.nanoTime(); ConfigurableApplicationContext c; long run = Long.parseLong(args[1]);
    switch (m) {
      case "c1" -> c = new AnnotationConfigApplicationContext(C1.class); case "c1p" -> c = new AnnotationConfigApplicationContext(C1p.class);
      case "c2a" -> c = new AnnotationConfigApplicationContext(C2a.class); case "c2b" -> c = new AnnotationConfigApplicationContext(C2b.class); case "c5" -> c = new AnnotationConfigApplicationContext(C5.class); case "c6" -> c = new AnnotationConfigApplicationContext(C6.class);
      default -> { SpringApplication app = new SpringApplication(BootC.class); app.setWebApplicationType(WebApplicationType.NONE); app.setBannerMode(Banner.Mode.OFF); c = app.run(); System.out.println("RES Boot 里的 TaskScheduler Bean:" + Arrays.toString(c.getBeanNamesForType(TaskScheduler.class))); }
    }
    T0 = System.nanoTime(); Thread.sleep(run); dump(m, 0); System.exit(0);
  }
}
'''
b = sbuild('x25', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m, ms): r = srun(b, 'demo.Main', args=[m, str(ms)]); return [l[4:] if l.startswith('RES ') else l[:200] for l in r['out'].splitlines() if l.startswith('RES ') or l.startswith('LOG ')] or [r['out'][-900:]]
print('Spring Framework 7.0.9(@EnableScheduling)。时间是从容器启动完成之后算起的毫秒数')
print('== 一:默认调度器上的一个快任务(fixedRate 200 ms,耗时 5 ms)和一个慢任务(每 3 s 一次,耗时 1000 ms)。跑 2.6 s')
[print('  ' + l) for l in run('c1', 2600)]
print('== 二:同样的两个任务,调度器线程池大小设成 3')
[print('  ' + l) for l in run('c1p', 2600)]
print('== 三:Spring Boot(@EnableAutoConfiguration + @EnableScheduling)里同样的两个任务')
[print('  ' + l) for l in run('boot', 2600)]
print('== 四:fixedRate = 300 ms 与 fixedDelay = 300 ms,任务本身耗时 500 ms,各跑 3 s')
for k_ in ('c2a', 'c2b'): [print('  ' + l) for l in run(k_, 3000)]
print('== 五:任务抛异常(第 2 次抛)。fixedRate = 300 ms,跑 1.8 s')
[print('  ' + l) for l in run('c5', 1800)]
print('== 六:@Scheduled 加 @Async(fixedRate = 200 ms,每次耗时 700 ms)。跑 1.5 s')
[print('  ' + l) for l in run('c6', 1500)]
