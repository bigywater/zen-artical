import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j258'); R = {}
MAIN_A = r'''import java.lang.invoke.*; import java.lang.reflect.*; import java.util.*; import sun.misc.Unsafe;
public class Main {
  record R(int x) {} static class P { volatile long v; int plain; }
  static Unsafe U; static { try { Field f = Unsafe.class.getDeclaredField("theUnsafe"); f.setAccessible(true); U = (Unsafe) f.get(null); } catch (Exception e) { throw new RuntimeException(e); } }
  static long sink;
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    if (mode.equals("unsafe")) {
      long p = U.allocateMemory(16); U.putLong(p, 42L); System.out.println("RES allocateMemory/putLong/getLong:getLong = " + U.getLong(p)); U.freeMemory(p);
    } else if (mode.equals("offsets")) {
      try { System.out.println("RES 普通类的字段:objectFieldOffset = " + U.objectFieldOffset(P.class.getDeclaredField("plain"))); } catch (Throwable t) { System.out.println("RES 普通类的字段:" + t); }
      try { System.out.println("RES record 的字段:objectFieldOffset = " + U.objectFieldOffset(R.class.getDeclaredField("x"))); } catch (Throwable t) { System.out.println("RES record 的字段:" + t.getClass().getSimpleName() + ":" + t.getMessage()); }
      int cap = 5; Runnable lam = () -> sink += cap; Field[] fs = lam.getClass().getDeclaredFields(); try { System.out.println("RES lambda(隐藏类)的捕获字段 " + fs[0].getName() + ":objectFieldOffset = " + U.objectFieldOffset(fs[0])); } catch (Throwable t) { System.out.println("RES lambda(隐藏类)的捕获字段:" + t.getClass().getSimpleName() + ":" + t.getMessage()); }
      MethodHandles.Lookup l = MethodHandles.privateLookupIn(R.class, MethodHandles.lookup()); VarHandle vh = l.findVarHandle(R.class, "x", int.class); R r = new R(7); System.out.println("RES VarHandle 读 record 字段 x = " + (int) vh.get(r)); try { vh.set(r, 9); System.out.println("RES VarHandle 写 record 字段成功"); } catch (Throwable t) { System.out.println("RES VarHandle 写 record 字段:" + t.getClass().getSimpleName() + ":" + t.getMessage()); }
      VarHandle pv = MethodHandles.lookup().findVarHandle(P.class, "v", long.class); P pp = new P(); System.out.println("RES VarHandle 对普通 volatile 字段 compareAndSet(0, 5) = " + pv.compareAndSet(pp, 0L, 5L) + ",值 " + pp.v);
    }
  }
}
'''
MAIN_B = r'''
import java.lang.foreign.*; import java.lang.invoke.*; import java.lang.reflect.*; import java.nio.*; import java.util.*; import java.util.concurrent.atomic.*; import sun.misc.Unsafe;
public class Main {
  record R(int x) {} static class P { volatile long v; int plain; }
  static Unsafe U; static { try { Field f = Unsafe.class.getDeclaredField("theUnsafe"); f.setAccessible(true); U = (Unsafe) f.get(null); } catch (Exception e) { throw new RuntimeException(e); } }
  static long sink; static final VarHandle BAV = MethodHandles.byteArrayViewVarHandle(long[].class, ByteOrder.nativeOrder()); static final VarHandle SEGV = ValueLayout.JAVA_LONG.varHandle();
  static double med(double[] r) { Arrays.sort(r); return r[r.length / 2]; }
  static long rssKb() throws Exception { Process p = new ProcessBuilder("ps", "-o", "rss=", "-p", String.valueOf(ProcessHandle.current().pid())).start(); String s = new String(p.getInputStream().readAllBytes()).trim(); p.waitFor(); return Long.parseLong(s); }
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    if (mode.equals("perf")) {
      int N = 1 << 20; long bytes = (long) N * 8;
      try (Arena arena = Arena.ofConfined()) {
        MemorySegment seg = arena.allocate(bytes, 8); long addr = U.allocateMemory(bytes); ByteBuffer bb = ByteBuffer.allocateDirect((int) bytes).order(ByteOrder.nativeOrder()); LongBuffer lb = bb.asLongBuffer(); long[] arr = new long[N]; byte[] ba = new byte[(int) bytes];
        
        String[] names = {"long[](堆内数组)", "Unsafe(堆外地址)", "MemorySegment.get(JAVA_LONG, offset)", "MemorySegment 的 VarHandle", "DirectByteBuffer.getLong", "LongBuffer.get(i)", "byte[] + byteArrayViewVarHandle"};
        for (int w = 0; w < 3; w++) for (int m = 0; m < names.length; m++) one(m, N, seg, addr, bb, lb, arr, ba, BAV, SEGV);
        double[][] res = new double[names.length][7]; for (int rr = 0; rr < 7; rr++) for (int m = 0; m < names.length; m++) res[m][rr] = one(m, N, seg, addr, bb, lb, arr, ba, BAV, SEGV);
        for (int m = 0; m < names.length; m++) System.out.printf("RES %-40s 写 + 读各 %d 个 long:每个元素约 %.2f ns(7 轮中位数)%n", names[m], N, med(res[m]) / N);
        U.freeMemory(addr);
      }
    } else if (mode.equals("cas")) {
      int N = 20_000_000; P p = new P(); VarHandle vh = MethodHandles.lookup().findVarHandle(P.class, "v", long.class); long off = U.objectFieldOffset(P.class.getDeclaredField("v")); AtomicLong al = new AtomicLong(); Object lock = new Object(); LongAdder la = new LongAdder();
      String[] names = {"AtomicLong.incrementAndGet", "VarHandle.getAndAdd", "VarHandle.compareAndSet 循环", "Unsafe.compareAndSwapLong 循环", "synchronized + long++", "LongAdder.increment"};
      for (int th : new int[]{1, 4}) { double[][] res = new double[names.length][5];
        for (int rr = 0; rr < 8; rr++) for (int m = 0; m < names.length; m++) { double t = runThreads(th, N, m, p, vh, off, al, lock, la); if (rr >= 3) res[m][rr - 3] = t; }
        for (int m = 0; m < names.length; m++) System.out.printf("RES %d 线程 %-30s 每次约 %.1f ns(= 总耗时 ÷ 总次数 %d,5 轮中位数)%n", th, names[m], med(res[m]), N); }
    } else if (mode.equals("life")) {
      long base = rssKb(); int N = 100; int SZ = 4 << 20;
      for (int i = 0; i < N; i++) { long p = U.allocateMemory(SZ); U.setMemory(p, SZ, (byte) 1); } long afterUnsafe = rssKb(); System.gc(); Thread.sleep(300); long afterGc = rssKb();
      System.out.printf("RES Unsafe.allocateMemory %d × %d MiB 并写满、不 freeMemory:RSS %d MiB → %d MiB;System.gc() 之后 %d MiB(增加 %d MiB)%n", N, SZ >> 20, base / 1024, afterUnsafe / 1024, afterGc / 1024, (afterGc - base) / 1024);
    } else if (mode.equals("life2")) {
      long base = rssKb(); int N = 100; int SZ = 4 << 20; long peak = base;
      for (int i = 0; i < N; i++) { try (Arena ar = Arena.ofConfined()) { MemorySegment s = ar.allocate(SZ, 8); s.fill((byte) 1); } peak = Math.max(peak, rssKb()); } System.gc(); Thread.sleep(300); long end = rssKb();
      System.out.printf("RES Arena.ofConfined 分配 %d × %d MiB 并写满、每次 close:RSS %d MiB → 峰值 %d MiB → 结束 %d MiB(增加 %d MiB)%n", N, SZ >> 20, base / 1024, peak / 1024, end / 1024, (end - base) / 1024);
      base = rssKb(); for (int i = 0; i < N; i++) { MemorySegment s = Arena.ofAuto().allocate(SZ, 8); s.fill((byte) 1); } long afterAuto = rssKb(); for (int k = 0; k < 5; k++) { System.gc(); Thread.sleep(200); } long afterAutoGc = rssKb();
      System.out.printf("RES Arena.ofAuto 同样 %d × %d MiB、不 close:RSS %d MiB → %d MiB;System.gc() 之后 %d MiB(增加 %d MiB)%n", N, SZ >> 20, base / 1024, afterAuto / 1024, afterAutoGc / 1024, (afterAutoGc - base) / 1024);
      try { MemorySegment s2; try (Arena ar = Arena.ofConfined()) { s2 = ar.allocate(16, 8); } s2.get(ValueLayout.JAVA_LONG, 0); } catch (Throwable t) { System.out.println("RES 访问已 close 的 Arena 的 MemorySegment:" + t.getClass().getSimpleName() + ":" + t.getMessage()); }
      try (Arena ar = Arena.ofConfined()) { MemorySegment s3 = ar.allocate(16, 8); s3.get(ValueLayout.JAVA_LONG, 16); } catch (Throwable t) { System.out.println("RES 越界读 MemorySegment:" + t.getClass().getSimpleName() + ":" + t.getMessage().replaceAll("\\s+", " ")); }
      long p = U.allocateMemory(16); U.freeMemory(p); System.out.println("RES 对照:Unsafe 释放后再 getLong 不会抛异常(这里不执行,避免崩溃)");
    }
  }
  static double one(int m, int N, MemorySegment seg, long addr, ByteBuffer bb, LongBuffer lb, long[] arr, byte[] ba, VarHandle bav, VarHandle segv) {
    long t0 = System.nanoTime(); long s = switch (m) { case 0 -> mArr(N, arr); case 1 -> mUnsafe(N, addr); case 2 -> mSeg(N, seg); case 3 -> mSegVh(N, seg); case 4 -> mBb(N, bb); case 5 -> mLb(N, lb); default -> mBav(N, ba); };
    sink += s; return System.nanoTime() - t0; }
  static long mArr(int N, long[] arr) { long s = 0; for (int i = 0; i < N; i++) arr[i] = i; for (int i = 0; i < N; i++) s += arr[i]; return s; }
  static long mUnsafe(int N, long addr) { long s = 0; for (int i = 0; i < N; i++) U.putLong(addr + 8L * i, i); for (int i = 0; i < N; i++) s += U.getLong(addr + 8L * i); return s; }
  static long mSeg(int N, MemorySegment seg) { long s = 0; for (int i = 0; i < N; i++) seg.set(ValueLayout.JAVA_LONG, 8L * i, i); for (int i = 0; i < N; i++) s += seg.get(ValueLayout.JAVA_LONG, 8L * i); return s; }
  static long mSegVh(int N, MemorySegment seg) { long s = 0; for (long i = 0; i < N; i++) SEGV.set(seg, 8L * i, (long) i); for (long i = 0; i < N; i++) s += (long) SEGV.get(seg, 8L * i); return s; }
  static long mBb(int N, ByteBuffer bb) { long s = 0; for (int i = 0; i < N; i++) bb.putLong(8 * i, i); for (int i = 0; i < N; i++) s += bb.getLong(8 * i); return s; }
  static long mLb(int N, LongBuffer lb) { long s = 0; for (int i = 0; i < N; i++) lb.put(i, i); for (int i = 0; i < N; i++) s += lb.get(i); return s; }
  static long mBav(int N, byte[] ba) { long s = 0; for (int i = 0; i < N; i++) BAV.set(ba, 8 * i, (long) i); for (int i = 0; i < N; i++) s += (long) BAV.get(ba, 8 * i); return s; }
  static double runThreads(int th, int N, int m, P p0, VarHandle vh, long off, AtomicLong al, Object lock, LongAdder la) throws Exception {
    final P p = new P(); final AtomicLong alx = new AtomicLong(); final LongAdder lax = new LongAdder(); final long[] box = new long[1]; int per = N / th; Thread[] ts = new Thread[th]; long t0 = System.nanoTime();
    for (int t = 0; t < th; t++) { ts[t] = new Thread(() -> { for (int i = 0; i < per; i++) { switch (m) {
        case 0 -> alx.incrementAndGet(); case 1 -> vh.getAndAdd(p, 1L);
        case 2 -> { long c; do { c = (long) vh.getVolatile(p); } while (!vh.compareAndSet(p, c, c + 1)); }
        case 3 -> { long c; do { c = U.getLongVolatile(p, off); } while (!U.compareAndSwapLong(p, off, c, c + 1)); }
        case 4 -> { synchronized (box) { box[0]++; } } default -> lax.increment(); } } }); ts[t].start(); }
    for (Thread t : ts) t.join(); long el = System.nanoTime() - t0; return el / (double) N * (th == 1 ? 1 : 1) * 1.0; }
}
'''
def one(jdk, mode, flags=(), preview=False, name=None):
    r = jrun(name or f'j258_{jdk}_{mode}', {'Main.java': MAIN_A if mode in ('unsafe', 'offsets') else MAIN_B}, jdk=jdk, args=(mode,), jopts=flags, copts=(), timeout=600, clean=True)
    if r['crc'] != 0: print(r['cout'][:2500]); sys.exit()
    return r['out']
def lines(o): return [l for l in o.splitlines() if l.startswith('RES ') or l.startswith('WARNING')]
print('== 一:同一段 Unsafe 代码(allocateMemory / putLong / getLong / freeMemory)在 JDK 17 / 21 / 27 上,以及 JDK 27 的 --sun-misc-unsafe-memory-access 选项')
for jdk in ('17', '21', '27'):
    o = one(jdk, 'unsafe'); print(f'  [JDK {jdk}] ' + ' | '.join(l.replace('RES ', '')[:100] for l in lines(o)))
for opt in ('allow', 'warn', 'debug', 'deny'):
    o = one('27', 'unsafe', ('--sun-misc-unsafe-memory-access=' + opt,)); ls = [l.strip() for l in o.splitlines() if l.strip()]
    print(f'  [JDK 27 --sun-misc-unsafe-memory-access={opt}] ' + ' | '.join(re.sub(r'\s+', ' ', l.replace('RES ', ''))[:110] for l in ls[:4]))
print('== 二:objectFieldOffset 对 record 与 lambda(隐藏类)的限制,以及 VarHandle 作为替代')
for jdk in ('17', '21', '27'):
    o = one(jdk, 'offsets', ('--sun-misc-unsafe-memory-access=allow',) if jdk == '27' else ()); print(f'  [JDK {jdk}]'); [print('      ' + l.replace('RES ', '')[:190]) for l in lines(o)]
print('== 三:堆外 / 堆内读写 100 多万个 long 的成本(JDK 27,7 轮中位数,每种访问方式 写 + 读 各 1,048,576 次)')
o = one('27', 'perf', ('--sun-misc-unsafe-memory-access=allow',)); [print('  ' + l.replace('RES ', '')) for l in lines(o)]
print('== 四:计数器的几种写法:2,000 万次自增,JDK 27(5 轮中位数)')
o = one('27', 'cas', ('--sun-misc-unsafe-memory-access=allow',)); [print('  ' + l.replace('RES ', '')) for l in lines(o)]
print('== 五:堆外内存的生命周期:100 块 4 MiB 并写满,RSS 的变化(JDK 27)')
o = one('27', 'life', ('--sun-misc-unsafe-memory-access=allow',)); [print('  ' + l.replace('RES ', '')) for l in lines(o)]
o = one('27', 'life2', ('--sun-misc-unsafe-memory-access=allow',)); [print('  ' + l.replace('RES ', '')) for l in lines(o)]
