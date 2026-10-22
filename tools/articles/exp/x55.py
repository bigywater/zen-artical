import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x55'); CP = scp('io.projectreactor:reactor-core')
MAIN = r'''
package demo;
import java.time.Duration; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
import reactor.core.publisher.*;
public class Main {
  static void r(String s) { System.out.println("RES " + s); System.out.flush(); }
  static AtomicInteger n = new AtomicInteger();
  static String expensive(String tag) { r("    (expensive(" + tag + ") 被执行了)"); return tag; }
  static final List<String> DB = Collections.synchronizedList(new ArrayList<>());
  static Mono<Void> save(String x) { return Mono.fromRunnable(() -> { DB.add(x); r("    (save(" + x + ") 真正写入)"); }); }
  static Mono<String> audit(String x) { return Mono.fromSupplier(() -> { r("    (audit(" + x + ") 真正执行)"); return "audited-" + x; }); }
  public static void main(String[] a) throws Exception {
    r("== 一:组装不执行,订阅才执行");
    r("构造 Mono.fromSupplier(...).map(...).doOnNext(...)");
    Mono<String> m = Mono.fromSupplier(() -> { r("    (supplier 被执行)"); return "v"; }).map(s -> { r("    (map 被执行)"); return s + "!"; }).doOnNext(s -> r("    (doOnNext 被执行:" + s + ")"));
    r("构造完成,到这里为止上面没有任何输出;现在 subscribe");
    m.subscribe(s -> r("    (subscriber 收到 " + s + ")"));
    r("对照 Mono.just(expensive(\"A\")):参数在构造时就算了");
    Mono<String> j = Mono.just(expensive("A")); r("Mono.just(...) 构造完成,尚未订阅");
    r("对照 Mono.fromSupplier(() -> expensive(\"B\")):"); Mono<String> fs = Mono.fromSupplier(() -> expensive("B")); r("构造完成,尚未订阅"); fs.subscribe();
    r("对照 Mono.defer(() -> Mono.just(expensive(\"C\"))):"); Mono<String> df = Mono.defer(() -> Mono.just(expensive("C"))); r("构造完成,尚未订阅"); df.subscribe();

    r("== 二:每次订阅重新执行(冷),cache() 与 share()");
    n.set(0); Mono<Integer> cold = Mono.fromSupplier(() -> { int v = n.incrementAndGet(); r("    (源被执行,第 " + v + " 次)"); return v; });
    r("同一个 Mono 订阅 3 次:"); for (int i = 0; i < 3; i++) cold.subscribe(v -> r("    订阅者收到 " + v));
    n.set(0); Mono<Integer> cached = cold.cache(); r("cache() 之后订阅 3 次:"); for (int i = 0; i < 3; i++) cached.subscribe(v -> r("    订阅者收到 " + v));
    n.set(0); Flux<Integer> fcold = Flux.defer(() -> { int v = n.incrementAndGet(); r("    (Flux 源被执行,第 " + v + " 次)"); return Flux.just(v * 10, v * 10 + 1); });
    r("Flux 同一个源被两个订阅者各订阅一次:"); fcold.subscribe(v -> r("    订阅者 1 收到 " + v)); fcold.subscribe(v -> r("    订阅者 2 收到 " + v));
    n.set(0); Flux<Integer> shared = fcold.delayElements(Duration.ofMillis(50)).share(); r("share() + 两个订阅者几乎同时订阅:");
    CountDownLatch l = new CountDownLatch(2); shared.doOnComplete(l::countDown).subscribe(v -> r("    订阅者 1 收到 " + v)); shared.doOnComplete(l::countDown).subscribe(v -> r("    订阅者 2 收到 " + v)); l.await(2, TimeUnit.SECONDS);

    r("== 三:丢掉返回值 = 没有执行");
    DB.clear(); r("调用 save(\"x1\") 但不订阅也不返回:"); save("x1"); r("DB = " + DB);
    r("调用 save(\"x2\").subscribe():"); save("x2").subscribe(); r("DB = " + DB);
    r("在 map 里调用返回 Mono 的 audit(x),不订阅:"); Mono.just("p").map(x -> { audit(x); return x; }).subscribe(v -> r("    结果 " + v));
    r("改成 flatMap(x -> audit(x).thenReturn(x)):"); Mono.just("p").flatMap(x -> audit(x).thenReturn(x)).subscribe(v -> r("    结果 " + v));
    r("doOnNext(x -> audit(x))(同样丢了返回值):"); Mono.just("p").doOnNext(x -> audit(x)).subscribe(v -> r("    结果 " + v));
    r("doOnNext(x -> audit(x).subscribe())(手动订阅,线程/错误都脱离了主链):"); Mono.just("p").doOnNext(x -> audit(x).subscribe()).subscribe(v -> r("    结果 " + v));

    r("== 四:热源与订阅时机");
    Sinks.Many<Integer> sink = Sinks.many().multicast().onBackpressureBuffer(); Flux<Integer> hot = sink.asFlux();
    sink.tryEmitNext(1); sink.tryEmitNext(2); r("multicast 先发了 1、2,然后才订阅,再发 3:"); hot.subscribe(v -> r("    订阅者收到 " + v)); sink.tryEmitNext(3);
    Sinks.Many<Integer> sink2 = Sinks.many().multicast().directBestEffort(); sink2.tryEmitNext(1); sink2.tryEmitNext(2); r("directBestEffort(没有订阅者时发送)先发 1、2,再订阅,再发 3:"); sink2.asFlux().subscribe(v -> r("    订阅者收到 " + v)); sink2.tryEmitNext(3);
    Sinks.Many<Integer> sink3 = Sinks.many().replay().all(); sink3.tryEmitNext(1); sink3.tryEmitNext(2); r("replay().all() 先发 1、2,再订阅,再发 3:"); sink3.asFlux().subscribe(v -> r("    订阅者收到 " + v)); sink3.tryEmitNext(3);
    Flux<Long> iv = Flux.interval(Duration.ofMillis(100)).take(3); r("Flux.interval 是冷的:订阅者 B 晚 150 ms 订阅,也从 0 开始:");
    CountDownLatch l2 = new CountDownLatch(2); iv.doOnComplete(l2::countDown).subscribe(v -> r("    A 收到 " + v)); Thread.sleep(150); iv.doOnComplete(l2::countDown).subscribe(v -> r("    B 收到 " + v)); l2.await(2, TimeUnit.SECONDS);

    r("== 五:\"看起来惰性,其实已经开始了\":CompletableFuture");
    r("构造 CompletableFuture.supplyAsync(...)(还没有任何订阅):"); CompletableFuture<String> cf = CompletableFuture.supplyAsync(() -> { r("    (future 的任务在 " + Thread.currentThread().getName() + " 上被执行)"); return "cf"; }); Thread.sleep(150);
    r("Mono.fromFuture(cf) 构造完成但还没订阅 —— 上面的任务其实早已执行");
    Mono<String> fromF = Mono.fromFuture(cf);
    r("Mono.fromFuture(Supplier)(惰性):"); Mono<String> lazyF = Mono.fromFuture(() -> CompletableFuture.supplyAsync(() -> { r("    (惰性的 future 任务被执行)"); return "lazy"; })); r("构造完成,尚未订阅"); Thread.sleep(150); r("现在订阅:"); lazyF.block();
    r("订阅 2 次 Mono.fromFuture(cf):"); fromF.subscribe(v -> r("    收到 " + v)); fromF.subscribe(v -> r("    收到 " + v));

    r("== 六:订阅的几种方式");
    r("subscribe() 不会等待:"); long t0 = System.currentTimeMillis(); Mono.delay(Duration.ofMillis(300)).subscribe(v -> r("    (300 ms 的 delay 完成)")); r("    subscribe() 返回,用时 " + (System.currentTimeMillis() - t0) + " ms"); Thread.sleep(400);
    r("block() 会等待并抛出异常:"); t0 = System.currentTimeMillis(); Mono.delay(Duration.ofMillis(300)).block(); r("    block() 返回,用时 " + (System.currentTimeMillis() - t0) + " ms");
    try { Mono.error(new IllegalStateException("boom")).block(); } catch (Exception e) { r("    block() 抛出 " + e.getClass().getSimpleName() + ": " + e.getMessage()); }
    r("没有 error 回调的 subscribe():"); try { Mono.error(new IllegalStateException("boom2")).subscribe(); r("    subscribe() 正常返回"); } catch (Throwable e) { r("    subscribe() 抛出 " + e.getClass().getSimpleName() + ",cause=" + (e.getCause() == null ? null : e.getCause().getClass().getSimpleName() + ": " + e.getCause().getMessage())); }
    r("有 error 回调的 subscribe(onNext, onError):"); Mono.error(new IllegalStateException("boom3")).subscribe(v -> {}, e -> r("    onError 收到 " + e.getMessage()));
    Thread.sleep(200);
  }
}
'''
b, rr = build_run('x55', {'src/demo/Main.java': MAIN}, CP, timeout=60)
print('Reactor 版本(Boot 4.0.8 BOM 里的 reactor-core)' + ':' + [j.split('/')[-1] for j in CP.split(':') if 'reactor-core' in j][0])
show(rr['out'] if False else '\n'.join(res(rr)), n=200, w=200, ind='')

nr = [l.strip() for l in rr['out'].splitlines() if not l.startswith('RES ') and l.strip()]
print('-- 程序打在标准错误 / 标准输出上的非 RES 行(共 %d 行),前 3 行:' % len(nr)); [print('  ' + l[:200]) for l in nr[:3]]
