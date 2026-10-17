import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j251'); R = {}
MAIN = r'''
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*; import java.util.function.*;
public class Main {
  static String n(Throwable t) { if (t == null) return "null"; return t.getClass().getSimpleName() + (t.getCause() != null ? "(原因 " + t.getCause().getClass().getSimpleName() + ":" + t.getCause().getMessage() + ")" : ":" + t.getMessage()); }
  static void sleep(long m) { try { Thread.sleep(m); } catch (InterruptedException e) { } }
  static long T0; static long ms() { return (System.nanoTime() - T0) / 1_000_000; }
  public static void main(String[] a) throws Exception {
    System.out.println("== 一:异常在不同位置被观察到时的形状(原始异常 IllegalStateException(\"boom\"))");
    CompletableFuture<Integer> src = CompletableFuture.supplyAsync(() -> { throw new IllegalStateException("boom"); }); src.handle((v, e) -> 0).join();
    System.out.println("  supplyAsync 里抛出:handle 拿到的异常 = " + n(src.handle((v, e) -> e).join()));
    try { src.join(); } catch (Throwable t) { System.out.println("  join() 抛出:" + n(t)); }
    try { src.get(); } catch (Throwable t) { System.out.println("  get() 抛出:" + n(t)); }
    CompletableFuture<Integer> manual = new CompletableFuture<>(); manual.completeExceptionally(new IllegalStateException("boom"));
    System.out.println("  completeExceptionally(原始异常) 的那个 future:handle 拿到的异常 = " + n(manual.handle((v, e) -> e).join()));
    System.out.println("  它的下游 thenApply 的 future:handle 拿到的异常 = " + n(manual.thenApply(x -> x + 1).handle((v, e) -> e).join()));
    try { manual.join(); } catch (Throwable t) { System.out.println("  completeExceptionally 的 future 上 join() 抛出:" + n(t)); }
    try { manual.get(); } catch (Throwable t) { System.out.println("  completeExceptionally 的 future 上 get() 抛出:" + n(t)); }
    CompletableFuture<Integer> stage = CompletableFuture.completedFuture(1).thenApply(x -> { if (x == 1) throw new IllegalStateException("boom"); return x; });
    System.out.println("  thenApply 里抛出:handle 拿到的异常 = " + n(stage.handle((v, e) -> e).join()));
    src.exceptionally(e -> { System.out.println("  exceptionally 在 supplyAsync 的 future 上收到的异常类型 = " + e.getClass().getSimpleName() + "(不是原始异常)"); return 0; }).join();
    manual.exceptionally(e -> { System.out.println("  exceptionally 在 completeExceptionally 的 future 上收到的异常类型 = " + e.getClass().getSimpleName()); return 0; }).join();
    System.out.println("== 二:没人观察的异常:fire-and-forget");
    AtomicInteger handlerCalls = new AtomicInteger(); Thread.setDefaultUncaughtExceptionHandler((t, e) -> handlerCalls.incrementAndGet());
    CompletableFuture<Void> lost = CompletableFuture.runAsync(() -> { throw new IllegalStateException("没人看"); }); Thread.sleep(300);
    System.out.println("  runAsync 抛出异常、没有 join / handle:isCompletedExceptionally() = " + lost.isCompletedExceptionally() + ",默认 UncaughtExceptionHandler 被调用 " + handlerCalls.get() + " 次,标准错误输出里没有任何堆栈(本进程到这里没有任何异常信息输出)");
    CompletableFuture<Void> chain = CompletableFuture.runAsync(() -> { throw new IllegalStateException("链首异常"); }).thenRun(() -> System.out.println("  (这一行不会打印)")); Thread.sleep(200);
    System.out.println("  thenRun 链上的后续阶段:isCompletedExceptionally() = " + chain.isCompletedExceptionally() + ",没有被执行");
    ExecutorService ex = Executors.newFixedThreadPool(1); ex.execute(() -> { throw new IllegalStateException("execute 里的异常"); }); Thread.sleep(300); System.out.println("  对照:ExecutorService.execute 里抛出异常,默认 UncaughtExceptionHandler 被调用 " + handlerCalls.get() + " 次(累计)"); ex.shutdown();
    System.out.println("== 三:whenComplete / handle / exceptionally 的语义");
    CompletableFuture<Integer> bad = CompletableFuture.supplyAsync(() -> { throw new IllegalStateException("A"); }); CompletableFuture<Integer> good = CompletableFuture.completedFuture(5);
    System.out.println("  whenComplete(只观察)在失败的 future 上:结果仍然失败 = " + bad.whenComplete((v, e) -> { }).isCompletedExceptionally());
    System.out.println("  whenComplete 的回调在成功的 future 上抛出 RuntimeException(\"B\"):结果 = " + n(good.whenComplete((v, e) -> { throw new RuntimeException("B"); }).handle((v, e) -> e).join()));
    CompletableFuture<Integer> both = bad.whenComplete((v, e) -> { throw new RuntimeException("B"); }); Throwable bt = both.handle((v, e) -> e).join(); System.out.println("  whenComplete 的回调在失败的 future 上又抛出 B:结果的异常 = " + n(bt) + ",被抑制的异常数 = " + bt.getCause().getSuppressed().length + "(原异常保留,B 被丢弃或抑制)");
    System.out.println("  handle 可以恢复:handle((v, e) -> e != null ? -1 : v) = " + bad.handle((v, e) -> e != null ? -1 : v).join() + ";exceptionally(e -> -2) = " + bad.exceptionally(e -> -2).join());
    System.out.println("  exceptionallyCompose(JDK 12)用另一个 future 恢复:" + bad.exceptionallyCompose(e -> CompletableFuture.supplyAsync(() -> 77)).join());
    System.out.println("  handle 回调自己抛异常:" + n(bad.handle((v, e) -> { throw new RuntimeException("C"); }).handle((v, e) -> e).join()));
    System.out.println("== 四:allOf 不会快速失败;anyOf 取第一个完成者(包括失败)");
    T0 = System.nanoTime(); CompletableFuture<Void> fast = CompletableFuture.runAsync(() -> { sleep(100); throw new IllegalStateException("100 ms 时失败"); }); CompletableFuture<Void> slow = CompletableFuture.runAsync(() -> sleep(1000)); CompletableFuture<Void> all = CompletableFuture.allOf(fast, slow);
    sleep(300); System.out.println("  300 ms 时:fast 已失败 = " + fast.isCompletedExceptionally() + ",allOf 是否已完成 = " + all.isDone());
    try { all.join(); } catch (Throwable t) { System.out.println("  all.join() 在 " + ms() + " ms 时抛出:" + n(t)); }
    T0 = System.nanoTime(); CompletableFuture<Object> any = CompletableFuture.anyOf(CompletableFuture.supplyAsync(() -> { sleep(100); throw new IllegalStateException("先失败的"); }), CompletableFuture.supplyAsync(() -> { sleep(400); return "后成功的"; }));
    try { any.join(); } catch (Throwable t) { System.out.println("  anyOf 的结果在 " + ms() + " ms 时是:" + n(t) + "(第一个完成的是失败的,第二个成功的结果被忽略)"); }
    System.out.println("== 五:cancel 与 orTimeout 不会停止底层任务");
    AtomicBoolean ran = new AtomicBoolean(), interrupted = new AtomicBoolean(); CompletableFuture<String> task = CompletableFuture.supplyAsync(() -> { try { Thread.sleep(600); ran.set(true); } catch (InterruptedException e) { interrupted.set(true); } return "done"; }); sleep(100);
    CompletableFuture<String> dep = task.thenApply(s -> s + "!"); boolean c = task.cancel(true); sleep(800);
    System.out.println("  cancel(true) 返回 " + c + ",isCancelled() = " + task.isCancelled() + ";底层任务照常跑完 = " + ran.get() + ",被中断 = " + interrupted.get() + ";下游 thenApply 的结果:" + n(dep.handle((v, e) -> e).join()));
    AtomicBoolean ran2 = new AtomicBoolean(); T0 = System.nanoTime(); CompletableFuture<String> slowTask = CompletableFuture.supplyAsync(() -> { sleep(600); ran2.set(true); return "late"; }).orTimeout(200, TimeUnit.MILLISECONDS);
    try { slowTask.join(); } catch (Throwable t) { System.out.println("  orTimeout(200 ms):在 " + ms() + " ms 时 join() 抛出 " + n(t)); } sleep(700); System.out.println("  700 ms 后底层任务仍然执行完了 = " + ran2.get());
    System.out.println("  completeOnTimeout(\"fallback\", 200 ms):" + CompletableFuture.supplyAsync(() -> { sleep(600); return "late"; }).completeOnTimeout("fallback", 200, TimeUnit.MILLISECONDS).join());
    System.exit(0);
  }
  static String checkedUnused() { CompletableFuture<Integer> f = CompletableFuture.supplyAsync(() -> { try { throw new java.io.IOException("io"); } catch (java.io.IOException e) { throw new CompletionException(e); } }); return n(f.handle((v, e) -> e).join()); }
}
'''
r = jrun('j251a', {'Main.java': MAIN}, timeout=120)
if r['crc'] != 0: print(r['cout'][:2500]); sys.exit()
print(r['out'])
