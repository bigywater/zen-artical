import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x64'); CP = scp('io.projectreactor:reactor-core')
MAIN = r'''
package demo;
import java.time.Duration; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*; import java.util.function.*;
import reactor.core.publisher.*; import reactor.core.scheduler.*; import reactor.util.retry.*;
public class Main {
  static void r(String s) { System.out.println("RES " + s); System.out.flush(); }
  static <T> String collect(Flux<T> f) { List<String> out = Collections.synchronizedList(new ArrayList<>()); CountDownLatch l = new CountDownLatch(1); long t0 = System.currentTimeMillis();
    f.subscribe(v -> out.add(String.valueOf(v)), e -> { out.add("ERROR(" + e.getClass().getSimpleName() + ": " + e.getMessage() + ")"); l.countDown(); }, () -> { out.add("COMPLETE"); l.countDown(); });
    try { l.await(5, TimeUnit.SECONDS); } catch (InterruptedException e) { } return out + "  用时 " + (System.currentTimeMillis() - t0) + " ms"; }
  static Mono<Integer> risky(int i) { return i % 3 == 0 ? Mono.error(new IllegalStateException("bad-" + i)) : Mono.just(i * 10); }
  public static void main(String[] a) throws Exception {
    r("== 一:错误是终止信号;几种恢复方式");
    Flux<Integer> src = Flux.just(1, 2, 3, 4, 5).map(x -> { if (x == 3) throw new IllegalStateException("bad-3"); return x; });
    r("  不处理:" + collect(src));
    r("  onErrorReturn(-1):" + collect(src.onErrorReturn(-1)));
    r("  onErrorResume(e -> Flux.just(100, 200)):" + collect(src.onErrorResume(e -> Flux.just(100, 200))));
    r("  onErrorMap(包成 RuntimeException(\"wrapped\", e)):" + collect(src.onErrorMap(e -> new RuntimeException("wrapped:" + e.getMessage()))));
    r("  onErrorComplete():" + collect(src.onErrorComplete()));
    r("  onErrorContinue((e, v) -> 跳过出错的元素)+ map:" + collect(Flux.just(1, 2, 3, 4, 5).map(x -> { if (x == 3) throw new IllegalStateException("bad-3"); return x; }).onErrorContinue((e, v) -> {})));
    r("  onErrorContinue 对 flatMap 里返回 Mono.error 的元素:" + collect(Flux.just(1, 2, 3, 4, 5).flatMap(Main::risky).onErrorContinue((e, v) -> {})));
    r("  同样的 flatMap,不用 onErrorContinue:" + collect(Flux.just(1, 2, 3, 4, 5).flatMap(Main::risky)));
    r("== 二:恢复放在哪里:内层 vs 外层");
    r("  内层 onErrorResume(放在 flatMap 里面):" + collect(Flux.just(1, 2, 3, 4, 5).flatMap(i -> risky(i).onErrorResume(e -> Mono.just(-i)))));
    r("  外层 onErrorResume(放在 flatMap 后面):" + collect(Flux.just(1, 2, 3, 4, 5).concatMap(Main::risky).onErrorResume(e -> Flux.just(-1))));
    r("  内层 onErrorResume 里再抛异常:" + collect(Flux.just(1, 2, 3).concatMap(i -> risky(i).onErrorResume(e -> { throw new IllegalArgumentException("handler-failed"); }))));
    r("== 三:retry:重订阅整条上游");
    { AtomicInteger subs = new AtomicInteger(), sideEffects = new AtomicInteger(); Mono<String> m = Mono.defer(() -> { int n = subs.incrementAndGet(); sideEffects.incrementAndGet(); return n < 3 ? Mono.<String>error(new IllegalStateException("fail-" + n)) : Mono.just("ok-on-attempt-" + n); });
      r("  retry(5):" + collect(m.retry(5).flux()) + ";上游被订阅 " + subs.get() + " 次,副作用执行 " + sideEffects.get() + " 次"); }
    { AtomicInteger subs = new AtomicInteger(); Mono<String> m = Mono.defer(() -> Mono.<String>error(new IllegalStateException("always-fail-" + subs.incrementAndGet())));
      r("  retry(2) 一直失败:" + collect(m.retry(2).flux()) + ";上游被订阅 " + subs.get() + " 次"); subs.set(0);
      r("  Retry.max(2) 一直失败:" + collect(m.retryWhen(Retry.max(2)).flux()) + ";上游被订阅 " + subs.get() + " 次"); subs.set(0);
      r("  Retry.backoff(3, 100ms) 一直失败:" + collect(m.retryWhen(Retry.backoff(3, Duration.ofMillis(100))).flux()) + ";上游被订阅 " + subs.get() + " 次"); subs.set(0);
      r("  Retry.backoff(3, 100ms).jitter(0) 一直失败:" + collect(m.retryWhen(Retry.backoff(3, Duration.ofMillis(100)).jitter(0)).flux()) + ";上游被订阅 " + subs.get() + " 次"); subs.set(0);
      r("  Retry.fixedDelay(3, 100ms).filter(e -> false):" + collect(m.retryWhen(Retry.fixedDelay(3, Duration.ofMillis(100)).filter(e -> false)).flux()) + ";上游被订阅 " + subs.get() + " 次"); subs.set(0);
      r("  Retry.backoff(3, 100ms).jitter(0).onRetryExhaustedThrow(原异常):" + collect(m.retryWhen(Retry.backoff(3, Duration.ofMillis(100)).jitter(0).onRetryExhaustedThrow((s, sig) -> sig.failure())).flux()) + ";上游被订阅 " + subs.get() + " 次"); }
    { AtomicInteger subs = new AtomicInteger(); Flux<Integer> f = Flux.defer(() -> { int n = subs.incrementAndGet(); return Flux.just(1, 2, 3).map(x -> { if (x == 3 && n < 3) throw new IllegalStateException("fail-at-3"); return x; }); });
      r("  Flux 在第 3 个元素处失败,retry(5):" + collect(f.retry(5)) + ";上游被订阅 " + subs.get() + " 次(前面的元素重复发出)"); }
    r("== 四:timeout");
    r("  Mono.delay(300ms).timeout(100ms):" + collect(Mono.delay(Duration.ofMillis(300)).timeout(Duration.ofMillis(100)).flux()));
    r("  Mono.delay(300ms).timeout(100ms, Mono.just(-1L)):" + collect(Mono.delay(Duration.ofMillis(300)).timeout(Duration.ofMillis(100), Mono.just(-1L)).flux()));
    r("  Flux.interval(100ms).take(5).timeout(300ms)(总共 500ms,每个间隔 100ms):" + collect(Flux.interval(Duration.ofMillis(100)).take(5).timeout(Duration.ofMillis(300))));
    r("  Flux.concat(interval(100ms).take(3), Mono.delay(500ms)).timeout(300ms)(第 4 个迟到):" + collect(Flux.concat(Flux.interval(Duration.ofMillis(100)).take(3), Mono.delay(Duration.ofMillis(500))).timeout(Duration.ofMillis(300))));
    { AtomicBoolean cancelled = new AtomicBoolean(), interrupted = new AtomicBoolean(), finished = new AtomicBoolean(); Mono<String> slow = Mono.fromCallable(() -> { try { Thread.sleep(400); } catch (InterruptedException e) { interrupted.set(true); throw e; } finished.set(true); return "late"; }).subscribeOn(Schedulers.boundedElastic()).doOnCancel(() -> cancelled.set(true));
      r("  超时会取消上游:" + collect(slow.timeout(Duration.ofMillis(100)).flux()).replaceAll("  用时.*", "")); Thread.sleep(600); r("      cancelled(上游收到取消信号)= " + cancelled.get() + ",阻塞里的 Thread.sleep 被中断 = " + interrupted.get() + ",任务正常跑完 = " + finished.get()); }
    { AtomicInteger subs = new AtomicInteger(); Mono<String> flaky = Mono.defer(() -> { int n = subs.incrementAndGet(); return n < 3 ? Mono.delay(Duration.ofMillis(300)).thenReturn("slow-" + n) : Mono.just("fast-" + n); });
      r("  timeout(100ms) 放在 retry 之前(每次尝试各自限时):" + collect(flaky.timeout(Duration.ofMillis(100)).retry(3).flux()) + ";上游被订阅 " + subs.get() + " 次"); subs.set(0);
      r("  timeout(100ms) 放在 retry 之后(整体限时):" + collect(flaky.retry(3).timeout(Duration.ofMillis(100)).flux()) + ";上游被订阅 " + subs.get() + " 次"); }
    r("== 五:终止之后才到的错误去了哪里");
    { List<String> dropped = Collections.synchronizedList(new ArrayList<>()); Hooks.onErrorDropped(e -> dropped.add(e.getClass().getSimpleName() + ": " + e.getMessage()));
      Mono<String> m = Mono.<String>create(sink -> { new Thread(() -> { try { Thread.sleep(300); } catch (InterruptedException e) { } sink.error(new IllegalStateException("error-after-timeout")); }).start(); });
      r("  timeout(100ms) 取消订阅之后,源头(Mono.create 的 sink)才报错:" + collect(m.timeout(Duration.ofMillis(100)).flux()).replaceAll("  用时.*", "")); Thread.sleep(400); r("      被 Hooks.onErrorDropped 收到的错误 = " + dropped);
      Flux<Integer> a1 = Flux.<Integer>create(sk -> new Thread(() -> { try { Thread.sleep(50); } catch (Exception e) { } sk.error(new IllegalStateException("A")); }).start()); Flux<Integer> a2 = Flux.<Integer>create(sk -> new Thread(() -> { try { Thread.sleep(120); } catch (Exception e) { } sk.error(new IllegalStateException("B")); }).start());
      dropped.clear(); r("  Flux.merge(两个都会报错的源):" + collect(Flux.merge(a1, a2)).replaceAll("  用时.*", "")); Thread.sleep(300); r("      被 Hooks.onErrorDropped 收到的错误 = " + dropped + "(第二个错误去了哪里,这里没有看到)");
      dropped.clear(); Flux<Integer> bad = Flux.from(s -> { s.onSubscribe(reactor.core.publisher.Operators.emptySubscription()); s.onComplete(); s.onError(new IllegalStateException("after-complete")); });
      r("  违反协议的源:onComplete 之后又 onError:" + collect(bad.map(x -> x)).replaceAll("  用时.*", "")); r("      被 Hooks.onErrorDropped 收到的错误 = " + dropped); Hooks.resetOnErrorDropped();
      r("  没有自定义 hook 时的默认行为是在标准错误输出打一行 [ERROR] Operator called default onErrorDropped(见最后几行)"); collect(bad.map(x -> x)); }
    System.exit(0);
  }
}
'''
b, rr = build_run('x64', {'src/demo/Main.java': MAIN}, CP, timeout=120)
print('Reactor 版本:' + [j.split('/')[-1] for j in CP.split(':') if 'reactor-core' in j][0])
print('\n'.join(res(rr)) if rr['rc'] is not None else rr['out'])
if rr['rc'] not in (0, None): print(rr['out'][-1500:])

nr = [l.strip() for l in rr['out'].splitlines() if l.strip().startswith('[ERROR]') and 'Operator called default onErrorDropped' in l]
print('-- 标准错误里出现的 "Operator called default onErrorDropped" 日志共 %d 行:' % len(nr)); [print('  ' + l[:200]) for l in nr]
