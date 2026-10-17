import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j249'); R = {}
MAIN = r'''
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static long T0; static long ms() { return (System.nanoTime() - T0) / 1_000_000; }
  static void sleep(long m) { try { Thread.sleep(m); } catch (InterruptedException e) { } }
  static ThreadPoolExecutor pool() { return (ThreadPoolExecutor) Executors.newFixedThreadPool(2); }
  static void fill(ExecutorService ex, AtomicInteger finished, AtomicInteger interrupted) { for (int i = 0; i < 4; i++) ex.submit(() -> { try { Thread.sleep(500); finished.incrementAndGet(); } catch (InterruptedException e) { interrupted.incrementAndGet(); } }); }
  public static void main(String[] a) throws Exception {
    System.out.println("== 一:同一批任务(4 个,各 500 ms,线程池 2 个线程)用四种方式收尾");
    for (String how : new String[]{"shutdown()", "shutdown() + awaitTermination", "shutdownNow()", "close()"}) {
      ThreadPoolExecutor ex = pool(); AtomicInteger fin = new AtomicInteger(), intr = new AtomicInteger(); fill(ex, fin, intr); Thread.sleep(100); T0 = System.nanoTime(); String extra = "";
      switch (how) { case "shutdown()" -> ex.shutdown(); case "shutdown() + awaitTermination" -> { ex.shutdown(); ex.awaitTermination(5, TimeUnit.SECONDS); } case "shutdownNow()" -> extra = ",返回的未开始任务 " + ex.shutdownNow().size() + " 个"; case "close()" -> ex.close(); }
      long call = ms(); Thread.sleep(1200); System.out.println("  " + String.format("%-30s", how) + "调用返回用时 " + call + " ms;1.2 s 后:完成 " + fin.get() + " 个、被中断 " + intr.get() + " 个" + extra + ",isTerminated() = " + ex.isTerminated()); }
    System.out.println("== 二:close() 被调用线程的中断:close() 等待期间调用线程被中断");
    ExecutorService ex2 = Executors.newFixedThreadPool(2); AtomicInteger f2 = new AtomicInteger(), i2 = new AtomicInteger(); fill(ex2, f2, i2); Thread.sleep(100);
    AtomicReference<String> res = new AtomicReference<>(); Thread closer = new Thread(() -> { long s = System.nanoTime(); ex2.close(); res.set("close() 在 " + (System.nanoTime() - s) / 1_000_000 + " ms 后返回,调用线程中断标志 = " + Thread.currentThread().isInterrupted()); });
    closer.start(); Thread.sleep(150); closer.interrupt(); closer.join(); Thread.sleep(800); System.out.println("  150 ms 时中断了正在 close() 的线程:" + res.get() + ";随后完成 " + f2.get() + " 个、被中断 " + i2.get() + " 个、未开始(被丢弃)" + (4 - f2.get() - i2.get()) + " 个");
    System.out.println("== 三:ForkJoinPool.commonPool().close() 与自建 ForkJoinPool.close()");
    ForkJoinPool common = ForkJoinPool.commonPool(); AtomicBoolean done = new AtomicBoolean(); common.submit(() -> { sleep(500); done.set(true); }); long t = System.nanoTime(); common.close();
    System.out.println("  commonPool().close() 用时 " + (System.nanoTime() - t) / 1_000_000 + " ms,返回时任务已完成 = " + done.get() + ",isShutdown() = " + common.isShutdown() + ";再提交一个任务仍然" + (common.submit(() -> 1).get() == 1 ? "能执行" : "?"));
    ForkJoinPool mine = new ForkJoinPool(2); AtomicBoolean done2 = new AtomicBoolean(); mine.submit(() -> { sleep(500); done2.set(true); }); sleep(50); t = System.nanoTime(); mine.close(); System.out.println("  自建 ForkJoinPool.close() 用时 " + (System.nanoTime() - t) / 1_000_000 + " ms,返回时任务已完成 = " + done2.get() + ",isTerminated() = " + mine.isTerminated());
    CompletableFuture<Void> cf = CompletableFuture.runAsync(() -> { sleep(500); done.set(true); }); done.set(false); t = System.nanoTime(); ForkJoinPool.commonPool().close(); System.out.println("  CompletableFuture.runAsync(默认用 commonPool)之后 commonPool().close() 用时 " + (System.nanoTime() - t) / 1_000_000 + " ms,返回时任务已完成 = " + done.get() + "(close 没有等它)"); cf.join();
    System.out.println("== 四:ScheduledThreadPoolExecutor:延迟任务与周期任务在 close() / shutdown() 时");
    ScheduledThreadPoolExecutor sch = new ScheduledThreadPoolExecutor(1); AtomicInteger runs = new AtomicInteger(); AtomicBoolean delayed = new AtomicBoolean();
    sch.scheduleAtFixedRate(() -> runs.incrementAndGet(), 0, 100, TimeUnit.MILLISECONDS); sch.schedule(() -> delayed.set(true), 1500, TimeUnit.MILLISECONDS); Thread.sleep(350);
    System.out.println("  默认策略:getExecuteExistingDelayedTasksAfterShutdownPolicy() = " + sch.getExecuteExistingDelayedTasksAfterShutdownPolicy() + ",getContinueExistingPeriodicTasksAfterShutdownPolicy() = " + sch.getContinueExistingPeriodicTasksAfterShutdownPolicy());
    int before = runs.get(); t = System.nanoTime(); sch.close(); System.out.println("  350 ms 时 close():用时 " + (System.nanoTime() - t) / 1_000_000 + " ms(延迟 1500 ms 的一次性任务被等到);周期任务在 close 前执行了 " + before + " 次、close 后共 " + runs.get() + " 次;延迟任务已执行 = " + delayed.get());
    ScheduledThreadPoolExecutor sch2 = new ScheduledThreadPoolExecutor(1); sch2.setContinueExistingPeriodicTasksAfterShutdownPolicy(true); AtomicInteger runs2 = new AtomicInteger(); sch2.scheduleAtFixedRate(() -> runs2.incrementAndGet(), 0, 100, TimeUnit.MILLISECONDS); Thread.sleep(150); sch2.shutdown(); Thread.sleep(600);
    System.out.println("  setContinueExistingPeriodicTasksAfterShutdownPolicy(true) + shutdown() 后 600 ms:周期任务共执行 " + runs2.get() + " 次,isTerminated() = " + sch2.isTerminated() + "(周期任务不停,池永远不会终止)"); sch2.shutdownNow();
    System.out.println("== 五:任务不响应中断时 shutdownNow() 与 awaitTermination:任务忙等 1500 ms 不检查中断");
    ExecutorService ex5 = Executors.newFixedThreadPool(1); AtomicBoolean busyDone = new AtomicBoolean(); ex5.submit(() -> { long e = System.nanoTime() + 1_500_000_000L; while (System.nanoTime() < e) { } busyDone.set(true); }); Thread.sleep(100);
    t = System.nanoTime(); List<Runnable> left = ex5.shutdownNow(); System.out.println("  shutdownNow() 立即返回(" + (System.nanoTime() - t) / 1_000_000 + " ms),未开始任务 " + left.size() + " 个;此时任务已结束 = " + busyDone.get() + ",isTerminated() = " + ex5.isTerminated());
    long tStart = t; boolean term = ex5.awaitTermination(300, TimeUnit.MILLISECONDS); System.out.println("  awaitTermination(300 ms) = " + term + "(距 shutdownNow 约 " + (System.nanoTime() - tStart) / 1_000_000 + " ms);任务已结束 = " + busyDone.get());
    term = ex5.awaitTermination(5, TimeUnit.SECONDS); System.out.println("  继续 awaitTermination(5 s) = " + term + ",距 shutdownNow 共约 " + (System.nanoTime() - tStart) / 1_000_000 + " ms(任务忙等 1500 ms,从提交后 100 ms 才调用 shutdownNow);任务已结束 = " + busyDone.get());
    System.exit(0);
  }
}
'''
r = jrun('j249a', {'Main.java': MAIN}, timeout=120)
if r['crc'] != 0: print(r['cout'][:2500]); sys.exit()
print(r['out'])
print('  对照:JDK 17 与 JDK 21 上同样的 try-with-resources')
r17 = jrun('j249b', {'Main.java': 'import java.util.concurrent.*; public class Main { public static void main(String[] a) throws Exception { try (ExecutorService ex = Executors.newFixedThreadPool(2)) { ex.submit(() -> 1).get(); } System.out.println("ok"); } }'}, jdk='17')
print('  JDK 17 javac 退出码', r17['crc'], '|', (r17['cout'] or r17['out']).splitlines()[0][:150] if (r17['cout'] or r17['out']) else '')
r21 = jrun('j249c', {'Main.java': 'import java.util.concurrent.*; public class Main { public static void main(String[] a) throws Exception { try (ExecutorService ex = Executors.newFixedThreadPool(2)) { ex.submit(() -> 1).get(); } System.out.println("ok"); } }'}, jdk='21')
print('  JDK 21 javac 退出码', r21['crc'], '运行:', r21['out'])
