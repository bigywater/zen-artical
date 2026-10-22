import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x17'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><appender name="O" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{0}: %msg%n</pattern></encoder></appender><root level="WARN"><appender-ref ref="O"/></root></configuration>'
MAIN = r'''
package demo;
import java.util.*; import java.util.concurrent.*;
import jakarta.annotation.PreDestroy;
import org.springframework.context.*; import org.springframework.context.annotation.*; import org.springframework.context.support.DefaultLifecycleProcessor;
public class Main {
  static final long T0 = System.nanoTime(); static final List<String> seq = Collections.synchronizedList(new ArrayList<>());
  static void ev(String s) { seq.add(String.format("%5d ms  %s", (System.nanoTime() - T0) / 1_000_000, s)); }
  static void flush(String t) { System.out.println("RES --- " + t); synchronized (seq) { int i = 1; for (String s : seq) System.out.println("RES " + i++ + ". " + s); } seq.clear(); }
  public static class L implements SmartLifecycle {
    final String n; final int phase; final boolean auto; final long stopMs; final boolean asyncStop; volatile boolean run;
    L(String n, int phase, boolean auto, long stopMs, boolean asyncStop) { this.n = n; this.phase = phase; this.auto = auto; this.stopMs = stopMs; this.asyncStop = asyncStop; }
    public void start() { run = true; ev(n + ".start()  (phase " + phase + ")"); }
    public void stop() { try { Thread.sleep(stopMs); } catch (InterruptedException e) { } run = false; ev(n + ".stop()  耗时 " + stopMs + " ms"); }
    public void stop(Runnable cb) { if (!asyncStop) { stop(); cb.run(); return; } ev(n + ".stop(callback) 开始,异步" + stopMs + " ms 后回调"); new Thread(() -> { try { Thread.sleep(stopMs); } catch (InterruptedException e) { } run = false; ev(n + " 异步停止完成,调用 callback"); cb.run(); }).start(); }
    public boolean isRunning() { return run; } public int getPhase() { return phase; } public boolean isAutoStartup() { return auto; } }
  public static class Plain implements Lifecycle { volatile boolean run; public void start() { run = true; ev("Plain(普通 Lifecycle).start()"); } public void stop() { run = false; ev("Plain.stop()"); } public boolean isRunning() { return run; } }
  public static class Destroy { @PreDestroy void d() { ev("Destroy.@PreDestroy"); } }
  @Configuration static class Phases {
    @Bean L p100() { return new L("p100", 100, true, 0, false); } @Bean L pMin() { return new L("pMin", Integer.MIN_VALUE, true, 0, false); } @Bean L p0() { return new L("p0(默认 phase)", 0, true, 0, false); }
    @Bean L pMax() { return new L("pMax", Integer.MAX_VALUE, true, 0, false); } @Bean L pNeg() { return new L("p-100", -100, true, 0, false); } @Bean Destroy d() { return new Destroy(); } }
  @Configuration static class Auto { @Bean L manual() { return new L("manual(isAutoStartup=false)", 0, false, 0, false); } @Bean L auto() { return new L("auto", 0, true, 0, false); } @Bean Plain plain() { return new Plain(); } }
  @Configuration static class Same { @Bean L a() { return new L("a", 10, true, 300, true); } @Bean L b() { return new L("b", 10, true, 300, true); } @Bean L c() { return new L("c", 10, true, 300, true); } }
  @Configuration static class Diff { @Bean L a() { return new L("a", 10, true, 300, true); } @Bean L b() { return new L("b", 20, true, 300, true); } @Bean L c() { return new L("c", 30, true, 300, true); } }
  public static class Hang implements SmartLifecycle { volatile boolean run; public void start() { run = true; ev("Hang.start()"); } public void stop() { } public void stop(Runnable cb) { ev("Hang.stop(callback):永远不调用 callback"); } public boolean isRunning() { return run; } public int getPhase() { return 5; } }
  @Configuration static class HangConf { @Bean(name = "lifecycleProcessor") DefaultLifecycleProcessor lp() { DefaultLifecycleProcessor p = new DefaultLifecycleProcessor(); p.setTimeoutPerShutdownPhase(1000); return p; } @Bean Hang hang() { return new Hang(); } @Bean L other() { return new L("other(phase 0)", 0, true, 0, false); } }
  public static void main(String[] args) throws Exception {
    String m = args[0]; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext();
    switch (m) {
      case "phase" -> { c.register(Phases.class); c.refresh(); flush("refresh 完成后(5 个 SmartLifecycle,phase 各不同,@Bean 的定义顺序是 p100、pMin、p0、pMax、p-100)"); c.close(); flush("close() 之后"); }
      case "auto" -> { c.register(Auto.class); c.refresh(); flush("refresh 完成后"); ev("--- 调用 context.start()"); c.start(); flush("context.start() 之后"); ev("--- 调用 manual 的 start()"); c.getBean("manual", L.class).start(); flush("手动 start manual 之后"); }
      case "same" -> { c.register(Same.class); c.refresh(); seq.clear(); long t = System.nanoTime(); c.close(); ev("close() 返回"); flush("同一个 phase(都是 10)的三个 Bean,各异步停 300 ms(close 耗时 " + (System.nanoTime() - t) / 1_000_000 + " ms)"); }
      case "diff" -> { c.register(Diff.class); c.refresh(); seq.clear(); long t = System.nanoTime(); c.close(); ev("close() 返回"); flush("三个不同 phase(10、20、30)各异步停 300 ms(close 耗时 " + (System.nanoTime() - t) / 1_000_000 + " ms)"); }
      case "hang" -> { c.register(HangConf.class); c.refresh(); seq.clear(); long t = System.nanoTime(); c.close(); ev("close() 返回"); flush("Hang 不调用 callback,timeoutPerShutdownPhase = 1000 ms(close 耗时 " + (System.nanoTime() - t) / 1_000_000 + " ms)"); }
    }
  }
}
'''
b = sbuild('x17', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): r = srun(b, 'demo.Main', args=[m]); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ') or l.startswith('LOG ')] or [r['out'][-700:]]
print('Spring Framework 7.0.9。SmartLifecycle:启动与停止的阶段(phase)')
print('== 一:phase 决定顺序。5 个 SmartLifecycle,phase 分别是 100、Integer.MIN_VALUE、0、Integer.MAX_VALUE、-100(@Bean 定义顺序故意打乱);另有一个带 @PreDestroy 的 Bean 看销毁相对于 stop 的位置')
[print('  ' + l) for l in run('phase')]
print('== 二:谁会自动启动。manual 的 isAutoStartup() 是 false;auto 是 true;Plain 只实现了 Lifecycle(没有 SmartLifecycle)')
[print('  ' + l) for l in run('auto')]
print('== 三:停止也分阶段。三个 phase 相同的 Bean 同时异步停止,与三个 phase 不同的 Bean')
[print('  ' + l) for l in run('same')]; [print('  ' + l) for l in run('diff')]
print('== 四:有一个 Bean 的 stop(callback) 永远不调用 callback。DefaultLifecycleProcessor 的 timeoutPerShutdownPhase 设成 1000 ms')
[print('  ' + l) for l in run('hang')]
