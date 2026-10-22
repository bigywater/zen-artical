import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x56'); CP = scp('io.projectreactor:reactor-core')
MAIN = r'''
package demo;
import java.time.Duration; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*; import java.util.function.*;
import reactor.core.publisher.*; import reactor.core.scheduler.*; import org.reactivestreams.Subscription;
public class Main {
  static void r(String s) { System.out.println("RES " + s); System.out.flush(); }
  static void nap(long ms) { try { Thread.sleep(ms); } catch (InterruptedException e) { throw new RuntimeException(e); } }
  static void nano(long ns) { long t = System.nanoTime(); while (System.nanoTime() - t < ns) { } }
  public static void main(String[] a) throws Exception {
    r("== 一:Flux.interval 不支持背压:生产每 1 ms 一个,消费者每个处理 20 ms");
    {
      List<Long> got = Collections.synchronizedList(new ArrayList<>()); CountDownLatch done = new CountDownLatch(1); AtomicReference<Throwable> err = new AtomicReference<>();
      Flux.interval(Duration.ofMillis(1)).publishOn(Schedulers.newSingle("slow"), 4).subscribe(v -> { got.add(v); nap(20); }, e -> { err.set(e); done.countDown(); }, done::countDown);
      done.await(5, TimeUnit.SECONDS);
      r("消费者实际处理了 " + got.size() + " 个元素就收到错误:" + err.get().getClass().getSimpleName() + ": " + err.get().getMessage());
    }
    r("== 二:几种溢出策略。快生产者一口气 Flux.create 发 5000 个(create 自带缓冲),消费者(publishOn 预取 16)每个处理 1 ms");
    String[] names = {"onBackpressureBuffer()(无界)", "onBackpressureBuffer(100)(满了报错)", "onBackpressureBuffer(100, DROP_OLDEST)", "onBackpressureDrop()", "onBackpressureLatest()"};
    for (int k = 0; k < names.length; k++) {
      final int kk = k; AtomicInteger recv = new AtomicInteger(), drop = new AtomicInteger(); AtomicLong last = new AtomicLong(-1); CountDownLatch done = new CountDownLatch(1); AtomicReference<String> err = new AtomicReference<>("无");
      Flux<Integer> src = Flux.<Integer>create(sink -> { for (int i = 1; i <= 5000; i++) sink.next(i); sink.complete(); }, FluxSink.OverflowStrategy.IGNORE);
      Flux<Integer> f = switch (kk) { case 0 -> src.onBackpressureBuffer(); case 1 -> src.onBackpressureBuffer(100); case 2 -> src.onBackpressureBuffer(100, i -> drop.incrementAndGet(), BufferOverflowStrategy.DROP_OLDEST); case 3 -> src.onBackpressureDrop(i -> drop.incrementAndGet()); default -> src.onBackpressureLatest(); };
      Scheduler s = Schedulers.newSingle("c" + k);
      f.publishOn(s, 16).subscribe(v -> { recv.incrementAndGet(); last.set(v); nap(1); }, e -> { err.set(e.getClass().getSimpleName()); done.countDown(); }, done::countDown);
      done.await(20, TimeUnit.SECONDS); s.dispose();
      r(String.format("%-40s 消费者收到 %4d 个,最后一个是 %4d,回调里统计的丢弃数 %4d,错误:%s", names[k], recv.get(), last.get(), drop.get(), err.get()));
    }
    r("== 三:需求(request)是怎么往上游传的:Flux.range(1, 1000) 之上 doOnRequest 记录收到的 request(n)");
    class Rec { static String run(String label, Function<Flux<Integer>, Flux<?>> down, int wait) throws Exception {
      List<String> reqs = Collections.synchronizedList(new ArrayList<>()); CountDownLatch done = new CountDownLatch(1);
      Flux<Integer> up = Flux.range(1, 1000).doOnRequest(n -> reqs.add(n == Long.MAX_VALUE ? "无限" : "" + n));
      down.apply(up).subscribe(v -> {}, e -> done.countDown(), done::countDown); done.await(wait, TimeUnit.SECONDS);
      List<String> c = new ArrayList<>(reqs); return String.format("%-34s 上游收到的 request(n) 序列(共 %d 次):%s", label, c.size(), c.size() > 12 ? c.subList(0, 12) + " …" : c); } }
    r(Rec.run("直接 subscribe(v -> ...)", f -> f, 5));
    r(Rec.run("publishOn(单线程)(默认预取 256)", f -> f.publishOn(Schedulers.single()), 5));
    r(Rec.run("publishOn(单线程, 32)", f -> f.publishOn(Schedulers.single(), 32), 5));
    r(Rec.run("limitRate(100)", f -> f.limitRate(100), 5));
    r(Rec.run("limitRate(100, 10)", f -> f.limitRate(100, 10), 5));
    r(Rec.run("flatMap(x -> Mono.just(x))", f -> f.flatMap(x -> Mono.just(x)), 5));
    r(Rec.run("flatMap(..., 4)(并发 4)", f -> f.flatMap(x -> Mono.just(x), 4), 5));
    r(Rec.run("concatMap(x -> Mono.just(x))", f -> f.concatMap(x -> Mono.just(x)), 5));
    r(Rec.run("buffer(10)", f -> f.buffer(10), 5));
    r("BaseSubscriber 手动控制:每次 request(3),处理完 3 个再 request 3 个:");
    {
      List<String> log = Collections.synchronizedList(new ArrayList<>()); CountDownLatch done = new CountDownLatch(1);
      Flux.range(1, 10).doOnRequest(n -> log.add("上游收到 request(" + n + ")")).subscribe(new BaseSubscriber<Integer>() { int c = 0;
        protected void hookOnSubscribe(Subscription s) { request(3); } protected void hookOnNext(Integer v) { log.add("收到 " + v); if (++c % 3 == 0) request(3); } protected void hookFinally(SignalType t) { done.countDown(); } });
      done.await(3, TimeUnit.SECONDS); r("  " + String.join(" | ", log));
    }
    r("== 四:无界缓冲的代价:生产者 200000 个一口气发完,消费者每个处理 1 ms;每 200 ms 看一次已生产 / 已消费 / 堆积");
    {
      AtomicInteger prod = new AtomicInteger(), cons = new AtomicInteger(); CountDownLatch go = new CountDownLatch(1);
      Flux.range(1, 200000).doOnNext(i -> prod.incrementAndGet()).onBackpressureBuffer().publishOn(Schedulers.newSingle("c4"), 16).subscribe(v -> { cons.incrementAndGet(); nap(1); });
      for (int t = 1; t <= 4; t++) { nap(200); r(String.format("  %4d ms:已生产 %6d,已消费 %4d,堆积在缓冲里 %6d", t * 200, prod.get(), cons.get(), prod.get() - cons.get())); }
      Flux.range(1, 200000).doOnNext(i -> {}).limitRate(100);
      AtomicInteger prod2 = new AtomicInteger(), cons2 = new AtomicInteger();
      Flux.range(1, 200000).doOnNext(i -> prod2.incrementAndGet()).publishOn(Schedulers.newSingle("c4b"), 16).subscribe(v -> { cons2.incrementAndGet(); nap(1); });
      r("  对照:不加 onBackpressureBuffer,publishOn(预取 16)"); for (int t = 1; t <= 3; t++) { nap(200); r(String.format("  %4d ms:已生产 %6d,已消费 %4d,生产领先消费 %6d", t * 200, prod2.get(), cons2.get(), prod2.get() - cons2.get())); }
    }
    r("== 五:Sinks 的缓冲溢出:multicast().onBackpressureBuffer(8),慢订阅者,一口气 tryEmitNext 30 个");
    {
      Sinks.Many<Integer> sink = Sinks.many().multicast().onBackpressureBuffer(8, false); AtomicInteger recv = new AtomicInteger(); CountDownLatch started = new CountDownLatch(1);
      sink.asFlux().publishOn(Schedulers.newSingle("c5"), 1).subscribe(v -> { recv.incrementAndGet(); nap(50); });
      Map<String, Integer> codes = new TreeMap<>(); for (int i = 1; i <= 30; i++) codes.merge(sink.tryEmitNext(i).toString(), 1, Integer::sum);
      r("  30 次 tryEmitNext 的返回值统计:" + codes); nap(1500); r("  1.5 秒后订阅者实际收到 " + recv.get() + " 个");
    }
    nap(100); System.exit(0);
  }
}
'''
b, rr = build_run('x56', {'src/demo/Main.java': MAIN}, CP, timeout=120)
print('Reactor 版本:' + [j.split('/')[-1] for j in CP.split(':') if 'reactor-core' in j][0])
print('\n'.join(res(rr)) if rr['rc'] is not None else rr['out'])
