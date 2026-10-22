import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x57'); CP = scp('io.projectreactor:reactor-core')
MAIN = r'''
package demo;
import java.time.Duration; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*; import java.util.function.*;
import reactor.core.publisher.*; import reactor.core.scheduler.*;
public class Main {
  static void r(String s) { System.out.println("RES " + s); System.out.flush(); }
  static void nap(long ms) { try { Thread.sleep(ms); } catch (InterruptedException e) { throw new RuntimeException(e); } }
  static String t() { return Thread.currentThread().getName(); }
  static List<String> L = Collections.synchronizedList(new ArrayList<>());
  static <T> Flux<T> mark(Flux<T> f, String stage) { return f.doOnNext(x -> L.add(stage + ":" + t())); }
  static void run(String title, Function<Flux<Integer>, Flux<Integer>> chain) throws Exception {
    L.clear(); CountDownLatch done = new CountDownLatch(1);
    Flux<Integer> src = Flux.defer(() -> { L.add("订阅发生在:" + t()); return Flux.just(1); });
    chain.apply(src.doOnNext(x -> L.add("源发出:" + t()))).doOnNext(x -> L.add("订阅者收到:" + t())).doFinally(s -> done.countDown()).subscribe();
    done.await(3, TimeUnit.SECONDS); r(String.format("%-52s %s", title, String.join(" → ", L)));
  }
  public static void main(String[] a) throws Exception {
    r("== 一:每个阶段在哪个线程(主线程名 = " + t() + ")");
    run("没有任何调度器", f -> f.map(x -> x));
    run("subscribeOn(boundedElastic)(放在链的末尾)", f -> f.map(x -> x).doOnNext(x -> L.add("map 之后:" + t())).subscribeOn(Schedulers.boundedElastic()));
    run("publishOn(parallel) 放在源与 map 之间", f -> f.publishOn(Schedulers.parallel()).doOnNext(x -> L.add("publishOn 之后:" + t())));
    run("subscribeOn(boundedElastic) + publishOn(parallel)", f -> f.subscribeOn(Schedulers.boundedElastic()).publishOn(Schedulers.parallel()).doOnNext(x -> L.add("publishOn 之后:" + t())));
    run("subscribeOn(single) 再 subscribeOn(boundedElastic)", f -> f.subscribeOn(Schedulers.single()).subscribeOn(Schedulers.boundedElastic()));
    run("publishOn(single) 再 publishOn(boundedElastic)", f -> f.publishOn(Schedulers.single()).doOnNext(x -> L.add("第一个 publishOn 之后:" + t())).publishOn(Schedulers.boundedElastic()).doOnNext(x -> L.add("第二个 publishOn 之后:" + t())));
    r("== 二:定时与异步源自带的线程");
    { L.clear(); CountDownLatch d = new CountDownLatch(1); Mono.delay(Duration.ofMillis(50)).doOnNext(x -> L.add("delay 完成后的 doOnNext:" + t())).subscribe(x -> {}, e -> {}, d::countDown); d.await(2, TimeUnit.SECONDS); r("Mono.delay(50ms) 之后的下游:" + L); }
    { L.clear(); CountDownLatch d = new CountDownLatch(1); CompletableFuture<Integer> cf = new CompletableFuture<>(); Mono.fromFuture(cf).doOnNext(x -> L.add("fromFuture 完成后的 doOnNext:" + t())).subscribe(x -> {}, e -> {}, d::countDown); Thread th = new Thread(() -> cf.complete(1), "my-completer"); th.start(); d.await(2, TimeUnit.SECONDS); r("在线程 my-completer 里 complete 一个 CompletableFuture:" + L); }
    r("== 三:阻塞的源放在哪个线程:谁被卡住");
    { long t0 = System.currentTimeMillis(); Mono.fromCallable(() -> { nap(300); return 1; }).subscribe(); r("阻塞源(300 ms),不加 subscribeOn:subscribe() 调用本身用了 " + (System.currentTimeMillis() - t0) + " ms(卡住了调用线程)"); }
    { long t0 = System.currentTimeMillis(); CountDownLatch d = new CountDownLatch(1); Mono.fromCallable(() -> { nap(300); return 1; }).subscribeOn(Schedulers.boundedElastic()).subscribe(x -> {}, e -> {}, d::countDown); long dt = System.currentTimeMillis() - t0; d.await(); r("阻塞源(300 ms),subscribeOn(boundedElastic):subscribe() 调用用了 " + dt + " ms,整体完成用了 " + (System.currentTimeMillis() - t0) + " ms"); }
    r("== 四:publishOn 之后同一条链上的元素是否在同一个线程;flatMap 里的内层 subscribeOn 带来并行");
    { L.clear(); CountDownLatch d = new CountDownLatch(1); Flux.range(1, 6).publishOn(Schedulers.parallel()).map(x -> { L.add(x + "@" + t()); return x; }).subscribe(x -> {}, e -> {}, d::countDown); d.await(2, TimeUnit.SECONDS); r("Flux.range(1, 6).publishOn(parallel).map:" + L); }
    for (boolean on : new boolean[]{false, true}) {
      L.clear(); long t0 = System.currentTimeMillis(); CountDownLatch d = new CountDownLatch(1);
      Flux.range(1, 4).flatMap(x -> { Mono<Integer> m = Mono.fromCallable(() -> { nap(300); L.add(x + "@" + t()); return x; }); return on ? m.subscribeOn(Schedulers.boundedElastic()) : m; }).subscribe(x -> {}, e -> {}, d::countDown); d.await(5, TimeUnit.SECONDS);
      r("flatMap 里 4 个阻塞 300 ms 的内层," + (on ? "内层加 subscribeOn(boundedElastic)" : "内层不加调度器") + ":总耗时 " + (System.currentTimeMillis() - t0) + " ms,线程分布 " + new TreeSet<>(L));
    }
    r("== 五:调度器的线程数与名字");
    { Set<String> names = Collections.synchronizedSet(new TreeSet<>()); CountDownLatch d = new CountDownLatch(1); Flux.range(1, 200).flatMap(i -> Mono.fromCallable(() -> { nap(20); names.add(t()); return i; }).subscribeOn(Schedulers.parallel()), 200).subscribe(x -> {}, e -> {}, d::countDown); d.await(10, TimeUnit.SECONDS); r("availableProcessors = " + Runtime.getRuntime().availableProcessors() + ";200 个阻塞 20 ms 的任务放到 Schedulers.parallel() 上,一共只用了 " + names.size() + " 个线程:" + names); }
    { Set<String> names = Collections.synchronizedSet(new TreeSet<>()); CountDownLatch d = new CountDownLatch(1); Flux.range(1, 40).flatMap(i -> Mono.fromCallable(() -> { nap(20); names.add(t()); return i; }).subscribeOn(Schedulers.boundedElastic()), 40).subscribe(x -> {}, e -> {}, d::countDown); d.await(5, TimeUnit.SECONDS); r("40 个并发阻塞任务在 boundedElastic 上用了 " + names.size() + " 个线程,例如 " + names.stream().limit(3).toList()); }
    System.exit(0);
  }
}
'''
b, rr = build_run('x57', {'src/demo/Main.java': MAIN}, CP, timeout=120)
print('Reactor 版本:' + [j.split('/')[-1] for j in CP.split(':') if 'reactor-core' in j][0])
print('\n'.join(res(rr)) if rr['rc'] is not None else rr['out'])
