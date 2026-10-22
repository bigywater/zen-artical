import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x62'); CP = scp('io.projectreactor:reactor-core', 'io.micrometer:context-propagation')
MAIN = r'''
package demo;
import java.time.Duration; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*; import java.util.function.*;
import reactor.core.publisher.*; import reactor.core.scheduler.*; import reactor.util.context.*;
import io.micrometer.context.*;
public class Main {
  static void r(String s) { System.out.println("RES " + s); System.out.flush(); }
  static String t() { return Thread.currentThread().getName(); }
  static final ThreadLocal<String> TL = new ThreadLocal<>();
  static <T> T await(Mono<T> m) { return m.block(Duration.ofSeconds(5)); }
  public static void main(String[] a) throws Exception {
    r("== 一:ThreadLocal 在 Reactor 里:同一线程能读到,切了线程读不到");
    TL.set("user-42");
    r("  主线程直接读 = " + TL.get());
    r("  Mono.just(1).map(读 TL).block()(没有切线程,在 " + t() + " 上执行)= " + await(Mono.just(1).map(x -> String.valueOf(TL.get()))));
    r("  Mono.just(1).publishOn(parallel).map(读 TL)= " + await(Mono.just(1).publishOn(Schedulers.parallel()).map(x -> t() + " 读到 " + TL.get())));
    r("  Mono.delay(10ms).map(读 TL)= " + await(Mono.delay(Duration.ofMillis(10)).map(x -> t() + " 读到 " + TL.get())));
    r("  Mono.fromCallable(读 TL).subscribeOn(boundedElastic)= " + await(Mono.fromCallable(() -> t() + " 读到 " + TL.get()).subscribeOn(Schedulers.boundedElastic())));
    TL.remove();

    r("== 二:Reactor Context:写入、读取和方向(contextWrite 只影响它「上游」的操作符)");
    r("  contextWrite 放在链的末尾,上游的 deferContextual 读到 = " + await(Mono.deferContextual(ctx -> Mono.just(ctx.getOrDefault("user", "(无)"))).contextWrite(Context.of("user", "alice"))));
    r("  contextWrite 放在 deferContextual 之前(上游)= " + await(Mono.just("x").contextWrite(Context.of("user", "alice")).flatMap(v -> Mono.deferContextual(ctx -> Mono.just(ctx.getOrDefault("user", "(无)"))))));
    r("  两个 contextWrite 写同一个 key,离订阅者近的先写、离源近的后写 —— 最终上游看到 = " + await(Mono.deferContextual(ctx -> Mono.just(ctx.getOrDefault("user", "(无)"))).contextWrite(Context.of("user", "inner")).contextWrite(Context.of("user", "outer"))));
    r("  Context 经过 publishOn 切线程 = " + await(Mono.deferContextual(ctx -> Mono.just(t() + " 读到 " + ctx.getOrDefault("user", "(无)"))).publishOn(Schedulers.parallel()).contextWrite(Context.of("user", "alice")).subscribeOn(Schedulers.boundedElastic())));
    r("  在 delay 之后的 map 里通过 transformDeferredContextual 读 = " + await(Mono.delay(Duration.ofMillis(10)).transformDeferredContextual((m, ctx) -> m.map(x -> t() + " 读到 " + ctx.getOrDefault("user", "(无)"))).contextWrite(Context.of("user", "alice"))));
    r("  Context 是不可变的:ctx.put 返回新对象,原来的不变 = " + (Context.of("k", 1).put("k", 2).get("k")) + " / " + (Context.of("k", 1).get("k")));

    r("== 三:Context 的边界:flatMap 内层、手动 subscribe()");
    r("  flatMap 内层读外层的 Context = " + await(Mono.just(1).flatMap(x -> Mono.deferContextual(ctx -> Mono.just(ctx.getOrDefault("user", "(无)")))).contextWrite(Context.of("user", "alice"))));
    r("  内层 flatMap 里手动 subscribe() 一个新链(读不到外层 Context)= " + await(Mono.just(1).flatMap(x -> { CompletableFuture<String> f = new CompletableFuture<>(); Mono.deferContextual(ctx -> Mono.just(ctx.getOrDefault("user", "(无)"))).subscribe(f::complete); return Mono.fromFuture(f); }).contextWrite(Context.of("user", "alice"))));
    r("  订阅者各自的 Context 互不影响:同一个 Mono 用两个 Context 订阅 = " + await(Mono.deferContextual(ctx -> Mono.just("读到 " + ctx.getOrDefault("user", "(无)"))).contextWrite(Context.of("user", "A"))) + " / " + await(Mono.deferContextual(ctx -> Mono.just("读到 " + ctx.getOrDefault("user", "(无)"))).contextWrite(Context.of("user", "B"))));
    Mono<String> shared = Mono.deferContextual(ctx -> Mono.just("读到 " + ctx.getOrDefault("user", "(无)"))).cache();
    r("  cache() 之后:第一个订阅者的 Context 被缓存的结果带给了第二个 = " + await(shared.contextWrite(Context.of("user", "A"))) + " / " + await(shared.contextWrite(Context.of("user", "B"))));

    r("== 四:让 ThreadLocal 跟着走:Hooks.enableAutomaticContextPropagation() + ThreadLocalAccessor + contextCapture()");
    TL.set("user-42");
    Function<Void, Mono<String>> pipeline = v -> Mono.just(1).publishOn(Schedulers.parallel()).map(x -> t() + " 读到 " + TL.get());
    r("  1) 什么都没配置:" + await(pipeline.apply(null)));
    ContextRegistry.getInstance().registerThreadLocalAccessor("user", TL::get, TL::set, TL::remove);
    r("  2) 只注册了 ThreadLocalAccessor,没开 Hook,也没 contextCapture:" + await(pipeline.apply(null)));
    r("  3) 注册了 + 链尾加 contextCapture(),但没开 Hook:" + await(pipeline.apply(null).contextCapture()));
    Hooks.enableAutomaticContextPropagation();
    r("  4) 注册了 + 开了 Hook,没有 contextCapture:" + await(pipeline.apply(null)));
    r("  5) 注册了 + 开了 Hook + 链尾 contextCapture():" + await(pipeline.apply(null).contextCapture()));
    r("  6) 同上,再用 Mono.delay 和 subscribeOn(boundedElastic):" + await(Mono.delay(Duration.ofMillis(10)).map(x -> t() + " 读到 " + TL.get()).contextCapture()) + " | " + await(Mono.fromCallable(() -> t() + " 读到 " + TL.get()).subscribeOn(Schedulers.boundedElastic()).contextCapture()));
    TL.remove();
    r("  7) 订阅线程上没有设置 TL 时,下游读到 = " + await(pipeline.apply(null).contextCapture()));
    r("  8) 线程池里的任务:普通 Runnable / ContextSnapshot.wrap:");
    TL.set("user-42"); ExecutorService ex = Executors.newSingleThreadExecutor(rr -> new Thread(rr, "my-pool"));
    r("      普通提交 = " + ex.submit(() -> t() + " 读到 " + TL.get()).get() + ";ContextSnapshot.captureAll().wrap(...) 提交 = " + ex.submit(ContextSnapshotFactory.builder().build().captureAll().wrap(() -> t() + " 读到 " + TL.get())).get());
    ex.shutdown(); System.exit(0);
  }
}
'''
b, rr = build_run('x62', {'src/demo/Main.java': MAIN}, CP, timeout=60)
print('Reactor 版本:' + [j.split('/')[-1] for j in CP.split(':') if 'reactor-core' in j][0] + ';context-propagation 版本:' + [j.split('/')[-1] for j in CP.split(':') if 'context-propagation' in j][0])
print('\n'.join(res(rr)) if rr['rc'] is not None else rr['out'])
if rr['rc'] not in (0, None): print(rr['out'][-1500:])
