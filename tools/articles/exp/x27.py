import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x27'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.io.IOException; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
import org.springframework.context.annotation.*; import org.springframework.core.retry.RetryException; import org.springframework.core.retry.RetryListener; import org.springframework.core.retry.RetryPolicy; import org.springframework.core.retry.RetryTemplate; import org.springframework.resilience.InvocationRejectedException; import org.springframework.resilience.annotation.*; import org.springframework.resilience.retry.MethodRetryPredicate;
public class Main {
  static long T0; static final List<String> log = Collections.synchronizedList(new ArrayList<>());
  static void rec(String s) { log.add(String.format("%5d ms  %s", (System.nanoTime() - T0) / 1_000_000, s)); }
  static void flush(String t) { System.out.println("RES --- " + t); synchronized (log) { for (String l : log) System.out.println("RES " + l); } log.clear(); }
  public static class Flaky {
    final AtomicInteger n = new AtomicInteger();
    void reset() { n.set(0); }
    @Retryable public String defaults(int failTimes) { int i = n.incrementAndGet(); rec("defaults 第 " + i + " 次执行"); if (i <= failTimes) throw new IllegalStateException("失败 " + i); return "ok@" + i; }
    @Retryable(maxRetries = 4, delay = 100) public String fast(int failTimes) { int i = n.incrementAndGet(); rec("fast 第 " + i + " 次执行"); if (i <= failTimes) throw new IllegalStateException("失败 " + i); return "ok@" + i; }
    @Retryable(maxRetries = 5, delay = 100, multiplier = 2, maxDelay = 500) public String backoff(int failTimes) { int i = n.incrementAndGet(); rec("backoff 第 " + i + " 次执行"); if (i <= failTimes) throw new IllegalStateException("失败 " + i); return "ok@" + i; }
    @Retryable(includes = IOException.class, delay = 50) public String onlyIo(Exception e) throws Exception { rec("onlyIo 执行(抛 " + e.getClass().getSimpleName() + ")"); throw e; }
    @Retryable(excludes = IllegalArgumentException.class, delay = 50) public String excl(Exception e) throws Exception { rec("excl 执行(抛 " + e.getClass().getSimpleName() + ")"); throw e; }
    @Retryable(includes = IOException.class, delay = 50, maxRetries = 2) public String nested() throws Exception { rec("nested 执行(抛 RuntimeException,cause 是 IOException)"); throw new RuntimeException("包了一层", new IOException("底层")); }
    @Retryable(predicate = OnlyMsg.class, delay = 50) public String pred(String msg) { rec("pred 执行(消息 " + msg + ")"); throw new IllegalStateException(msg); }
    @Retryable(maxRetries = 2, delay = 50) public String exhaust() { rec("exhaust 执行"); throw new IllegalStateException("总是失败"); }
    @Retryable(maxRetries = 10, delay = 200, timeout = 500) public String withTimeout() { rec("withTimeout 执行"); throw new IllegalStateException("总是失败"); }
    @ConcurrencyLimit(2) public String limited() throws Exception { int c = cur.incrementAndGet(); max.accumulateAndGet(c, Math::max); Thread.sleep(300); cur.decrementAndGet(); return "ok"; }
    @ConcurrencyLimit(value = 2, policy = ConcurrencyLimit.ThrottlePolicy.REJECT) public String limitedReject() throws Exception { Thread.sleep(300); return "ok"; }
    final AtomicInteger cur = new AtomicInteger(), max = new AtomicInteger(); public int maxSeen() { return max.get(); }
  }
  public static class OnlyMsg implements MethodRetryPredicate { public boolean shouldRetry(java.lang.reflect.Method m, Throwable t) { return t.getMessage().startsWith("可重试"); } }
  @Configuration @EnableResilientMethods static class Conf { @Bean Flaky flaky() { return new Flaky(); } }
  static String t(java.util.concurrent.Callable<Object> c) { try { return "返回 " + c.call(); } catch (Throwable e) { return "抛 " + e.getClass().getSimpleName() + ": " + e.getMessage() + (e.getCause() != null ? " ← 原因 " + e.getCause().getClass().getSimpleName() + ": " + e.getCause().getMessage() : "") + (e.getSuppressed().length > 0 ? "(suppressed " + e.getSuppressed().length + " 个)" : ""); } }
  public static void main(String[] args) throws Exception {
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Flaky f = c.getBean(Flaky.class); String m = args[0]; T0 = System.nanoTime();
    switch (m) {
      case "defaults" -> { T0 = System.nanoTime(); String r = t(() -> f.defaults(2)); rec("→ " + r); flush("默认的 @Retryable(maxRetries = 3、delay = 1000 ms),前 2 次失败"); f.reset(); T0 = System.nanoTime(); r = t(() -> f.fast(2)); rec("→ " + r); flush("@Retryable(maxRetries = 4, delay = 100),前 2 次失败"); }
      case "backoff" -> { T0 = System.nanoTime(); String r = t(() -> f.backoff(10)); rec("→ " + r); flush("maxRetries = 5, delay = 100, multiplier = 2, maxDelay = 500,总是失败"); }
      case "filter" -> { T0 = System.nanoTime();
        rec("→ " + t(() -> f.onlyIo(new IOException("io")))); rec("→ " + t(() -> f.onlyIo(new IllegalStateException("ise")))); rec("→ " + t(() -> f.excl(new IllegalArgumentException("iae")))); rec("→ " + t(() -> f.excl(new IllegalStateException("ise"))));
        rec("→ " + t(() -> f.nested())); rec("→ " + t(() -> f.pred("可重试:x"))); rec("→ " + t(() -> f.pred("别重试"))); flush("includes / excludes / 嵌套的原因 / predicate"); }
      case "exhaust" -> { T0 = System.nanoTime(); rec("→ " + t(() -> f.exhaust())); flush("maxRetries = 2,总是失败:次数用完之后调用者看到什么"); T0 = System.nanoTime(); rec("→ " + t(() -> f.withTimeout())); flush("timeout = 500 ms、delay = 200 ms、maxRetries = 10,总是失败"); }
      case "template" -> { RetryPolicy p = RetryPolicy.builder().maxRetries(2).delay(java.time.Duration.ofMillis(50)).build(); RetryTemplate rt = new RetryTemplate(p); AtomicInteger n = new AtomicInteger(); T0 = System.nanoTime();
        rt.setRetryListener(new RetryListener() { public void beforeRetry(RetryPolicy rp, org.springframework.core.retry.Retryable<?> r) { rec("RetryListener.beforeRetry"); } public void onRetryFailure(RetryPolicy rp, org.springframework.core.retry.Retryable<?> r, Throwable ex) { rec("RetryListener.onRetryFailure(" + ex.getMessage() + ")"); } public void onRetrySuccess(RetryPolicy rp, org.springframework.core.retry.Retryable<?> r, Object res) { rec("RetryListener.onRetrySuccess"); } public void onRetryPolicyExhaustion(RetryPolicy rp, org.springframework.core.retry.Retryable<?> r, RetryException ex) { rec("RetryListener.onRetryPolicyExhaustion"); } });
        try { Object r = rt.execute(() -> { int i = n.incrementAndGet(); rec("RetryTemplate 执行第 " + i + " 次"); if (i < 3) throw new IllegalStateException("编程式失败 " + i); return "ok"; }); rec("→ 返回 " + r); } catch (Exception e) { rec("→ 抛 " + e); }
        flush("RetryTemplate(maxRetries = 2、delay = 50 ms),前 2 次失败"); n.set(0); T0 = System.nanoTime(); try { rt.execute(() -> { rec("RetryTemplate 执行(总是失败)"); throw new IllegalStateException("总是失败"); }); } catch (RetryException e) { rec("→ 次数用完:" + e.getClass().getSimpleName() + ": " + e.getMessage().replaceAll("\\s+", " ").replaceAll("Lambda/0x[0-9a-f]+", "Lambda") + "(最后的原因 " + e.getCause().getClass().getSimpleName() + ",suppressed " + e.getSuppressed().length + " 个)"); } catch (Exception e) { rec("→ 抛 " + e); } flush("RetryTemplate 总是失败"); }
      case "limit" -> { for (String k : new String[]{"block", "reject"}) { int N = 8; ExecutorService ex = Executors.newFixedThreadPool(N); CountDownLatch go = new CountDownLatch(1); List<Future<String>> fs = new ArrayList<>();
          for (int i = 0; i < N; i++) fs.add(ex.submit(() -> { go.await(); return k.equals("block") ? f.limited() : f.limitedReject(); })); long t0 = System.nanoTime(); go.countDown(); int ok = 0, rej = 0; String why = "";
          for (Future<String> fu : fs) { try { fu.get(); ok++; } catch (ExecutionException e) { rej++; why = e.getCause().getClass().getSimpleName(); } } long ms = (System.nanoTime() - t0) / 1_000_000; ex.shutdown();
          System.out.println("RES   @ConcurrencyLimit(2" + (k.equals("reject") ? ", policy = REJECT" : "") + "),8 个线程同时调用一个耗时 300 ms 的方法:成功 " + ok + " 个,被拒绝 " + rej + " 个" + (rej > 0 ? "(" + why + ")" : "") + ",全部结束花了 " + ms + " ms" + (k.equals("block") ? ",方法内观察到的最大并发 " + f.maxSeen() : "")); } }
    }
    System.exit(0);
  }
}
'''
b = sbuild('x27', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): r = srun(b, 'demo.Main', args=[m]); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1200:]]
print('Spring Framework 7.0.9 内置的 @Retryable(org.springframework.resilience.annotation.Retryable,要加 @EnableResilientMethods)与 RetryTemplate(org.springframework.core.retry);不是独立项目 spring-retry')
for t_, k_ in (('一', 'defaults'), ('二', 'backoff'), ('三', 'filter'), ('四', 'exhaust'), ('五', 'template'), ('六', 'limit')):
    title = {'defaults': '默认值与最简单的用法', 'backoff': '指数退避', 'filter': '哪些异常会被重试', 'exhaust': '次数用完与超时', 'template': '编程式的 RetryTemplate 与 RetryListener', 'limit': '同一个包里的 @ConcurrencyLimit'}[k_]
    print(f'== {t_}:{title}'); [print('  ' + l) for l in run(k_)]
