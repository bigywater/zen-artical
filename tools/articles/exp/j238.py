import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j238'); R = {}
MAIN = r'''
import java.io.*; import java.lang.management.*; import java.nio.file.*; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static final com.sun.management.UnixOperatingSystemMXBean OS = (com.sun.management.UnixOperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean();
  static long fds() { return OS.getOpenFileDescriptorCount(); }
  static int thr() { return ManagementFactory.getThreadMXBean().getThreadCount(); }
  static Path file;
  static String leakyRead(int i) throws IOException {
    FileInputStream in = new FileInputStream(file.toFile()); byte[] b = in.readNBytes(8);
    if (i % 7 == 0) throw new IOException("解析失败 " + i);   // 异常路径没有关闭
    in.close(); return new String(b);
  }
  static String fixedRead(int i) throws IOException {
    try (FileInputStream in = new FileInputStream(file.toFile())) { byte[] b = in.readNBytes(8); if (i % 7 == 0) throw new IOException("解析失败 " + i); return new String(b); }
  }
  interface Call { String run(int i) throws Exception; }
  static int[] hammer(Call c, int calls, int threads) throws Exception {
    ExecutorService ex = Executors.newFixedThreadPool(threads); AtomicInteger fail = new AtomicInteger(), ok = new AtomicInteger(); List<Future<?>> fs = new ArrayList<>();
    for (int i = 1; i <= calls; i++) { int k = i; fs.add(ex.submit(() -> { try { c.run(k); ok.incrementAndGet(); } catch (Exception e) { fail.incrementAndGet(); } })); }
    for (Future<?> f : fs) f.get(); ex.shutdown(); ex.awaitTermination(10, TimeUnit.SECONDS); return new int[]{ok.get(), fail.get()};
  }
  static int leakyThreads(int i) throws Exception { ExecutorService ex = Executors.newFixedThreadPool(2); Future<Integer> a = ex.submit(() -> i * 2), b = ex.submit(() -> i * 3); return a.get() + b.get(); }
  static int fixedThreads(int i) throws Exception { ExecutorService ex = Executors.newFixedThreadPool(2); try { Future<Integer> a = ex.submit(() -> i * 2), b = ex.submit(() -> i * 3); return a.get() + b.get(); } finally { ex.shutdown(); ex.awaitTermination(5, TimeUnit.SECONDS); } }
  static int shutdownOnly(int i) throws Exception { ExecutorService ex = Executors.newFixedThreadPool(2); ex.submit(() -> { try { Thread.sleep(30); } catch (InterruptedException e) { } }); ex.submit(() -> { try { Thread.sleep(30); } catch (InterruptedException e) { } }); ex.shutdown(); return i; }
  static final AtomicInteger TO = new AtomicInteger();
  static class Pool { final Semaphore s; Pool(int n) { s = new Semaphore(n); }
    String use(int i, boolean fixed) throws Exception { if (!s.tryAcquire(50, TimeUnit.MILLISECONDS)) { TO.incrementAndGet(); throw new TimeoutException("拿不到连接"); }
      if (fixed) { try { if (i % 7 == 0) throw new IOException("失败"); return "ok"; } finally { s.release(); } }
      if (i % 7 == 0) throw new IOException("失败"); s.release(); return "ok"; } }
  public static void main(String[] a) throws Exception {
    file = Files.createTempFile("leak", ".txt"); Files.writeString(file, "0123456789abcdef"); String mode = a[0];
    if (mode.equals("fd")) {
      long base = fds(); int calls = Integer.parseInt(a[1]); boolean single = a.length > 2 && a[2].equals("single");
      int[] r;
      if (single) { int ok = 0, fail = 0; for (int i = 1; i <= calls; i++) try { leakyRead(i); ok++; } catch (Exception e) { fail++; } r = new int[]{ok, fail}; } else r = hammer(Main::leakyRead, calls, 16);
      long after = fds(); long t0 = System.nanoTime(); long gcd = after; for (int k = 0; k < 20 && gcd > base + 3; k++) { System.gc(); Thread.sleep(100); gcd = fds(); }
      System.out.println("RES calls=" + calls + (single ? " 单线程" : " 16线程") + " 成功" + r[0] + " 失败" + r[1] + " fd基线" + base + " 之后" + after + " 增量" + (after - base) + " | System.gc()后" + gcd + " 增量" + (gcd - base));
    } else if (mode.equals("fdfixed")) {
      long base = fds(); int[] r = hammer(Main::fixedRead, Integer.parseInt(a[1]), 16); long after = fds();
      System.out.println("RES fixed calls=" + a[1] + " 成功" + r[0] + " 失败" + r[1] + " fd基线" + base + " 之后" + after + " 增量" + (after - base));
    } else if (mode.equals("thr")) {
      int n = Integer.parseInt(a[1]); int base = thr();
      for (int i = 1; i <= n; i++) leakyThreads(i);
      int after = thr(); for (int k = 0; k < 5; k++) { System.gc(); Thread.sleep(100); } int g = thr();
      System.out.println("RES leaky n=" + n + " 线程基线" + base + " 之后" + after + " 增量" + (after - base) + " | System.gc()后" + g + " 增量" + (g - base));
      int base2 = thr(); for (int i = 1; i <= n; i++) fixedThreads(i); System.out.println("RES fixed n=" + n + " 线程基线" + base2 + " 之后" + thr() + " 增量" + (thr() - base2));
      System.exit(0);
    } else if (mode.equals("settle")) {
      int base = thr(); int n = Integer.parseInt(a[1]); List<Integer> immediate = new ArrayList<>();
      for (int i = 1; i <= n; i++) { shutdownOnly(i); if (i % 50 == 0) immediate.add(thr() - base); }
      int imm = thr() - base; long t0 = System.nanoTime(); int waited = 0; while (thr() - base > 0 && waited < 2000) { Thread.sleep(5); waited += 5; }
      System.out.println("RES shutdown() 后不等待:每 50 次调用后立即测到的线程增量 " + immediate + ";最后一次调用后立即 " + imm + ";再等到增量归零用了约 " + waited + " ms,归零后增量 " + (thr() - base));
      System.exit(0);
    } else if (mode.equals("pool")) {
      Pool p = new Pool(10); int[] r = hammer(i -> p.use(i, false), 200, 16); System.out.println("RES 泄漏版 200 次并发调用:成功" + r[0] + " 失败" + r[1] + "(其中拿不到连接而超时 " + TO.get() + ")空闲连接 " + p.s.availablePermits() + "/10"); TO.set(0);
      int ok = 0, to = 0; for (int i = 1; i <= 5; i++) try { p.use(1, false); ok++; } catch (TimeoutException e) { to++; } catch (Exception e) { }
      System.out.println("RES 之后再调用 5 次(都是不会失败的 i=1):成功" + ok + " 超时" + to);
      Pool q = new Pool(10); int[] r2 = hammer(i -> q.use(i, true), 200, 16); System.out.println("RES 修复版 200 次并发调用:成功" + r2[0] + " 失败" + r2[1] + "(其中拿不到连接而超时 " + TO.get() + ")空闲连接 " + q.s.availablePermits() + "/10");
    }
    System.exit(0);
  }
}
'''
def run(*args, jopts=()):
    r = jrun('j238a', {'Main.java': MAIN}, jopts=jopts, args=args, clean=False, timeout=180)
    if r['crc'] != 0: print(r['cout'][:2500]); sys.exit()
    return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')], r['out']
EPS = ['-XX:+UnlockExperimentalVMOptions', '-XX:+UseEpsilonGC']
print('== 一:文件描述符泄漏:异常路径没关流(每 7 次调用有 1 次抛 IOException)。单线程测 3 次、300 次,与 16 线程并发 2000 次(默认 GC)')
for args in (('fd', '3', 'single'), ('fd', '300', 'single'), ('fd', '2000')):
    o, raw = run(*args); [print('  ' + l) for l in o] or print(raw[:500])
print('== 二:同样的 2000 次并发,默认 GC 重复 3 次与 Epsilon GC(不回收)3 次;修复版(try-with-resources)2000 次')
print('  默认 GC:')
for _ in range(3): o, raw = run('fd', '2000'); [print('    ' + l) for l in o]
print('  -XX:+UseEpsilonGC:')
for _ in range(3): o, raw = run('fd', '2000', jopts=EPS); [print('    ' + l) for l in o]
o, raw = run('fdfixed', '2000'); [print('  ' + l) for l in o]
print('== 三:线程泄漏:每次请求新建 newFixedThreadPool(2) 且不 shutdown。n = 1 / 10 / 50 / 200 次调用')
for n in (1, 10, 50, 200):
    o, raw = run('thr', str(n)); [print('  ' + l) for l in o]
print('== 四:每次请求建池、提交 2 个各耗时 30 ms 的任务、调 shutdown() 但不等待(调用方不 get):线程什么时候消失?')
for _ in range(3): o, raw = run('settle', '200'); [print('  ' + l) for l in o]
print('== 五:连接池泄漏:容量 10 的信号量池,异常路径没 release')
o, raw = run('pool'); [print('  ' + l) for l in o]
