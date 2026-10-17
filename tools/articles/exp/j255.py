import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j255'); R = {}
MAIN = r'''
import java.lang.management.*; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static final com.sun.management.ThreadMXBean TM = (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean();
  static volatile long done;
  static long[] worker(int size, double warm, double secs, CountDownLatch go) throws Exception {
    Object[] sink = new Object[64]; int len = Math.max(0, size - 16); long end = System.nanoTime() + (long) (warm * 1e9); long i = 0;
    while (System.nanoTime() < end) { for (int k = 0; k < 1000; k++) sink[(int) (i++ & 63)] = new byte[len]; }
    long tid = Thread.currentThread().threadId(); long b0 = TM.getThreadAllocatedBytes(tid); long t0 = System.nanoTime(); end = t0 + (long) (secs * 1e9); long n = 0;
    while (System.nanoTime() < end) { for (int k = 0; k < 1000; k++) sink[(int) (n++ & 63)] = new byte[len]; }
    long t1 = System.nanoTime(); long b1 = TM.getThreadAllocatedBytes(tid); done += sink.length; return new long[]{n, b1 - b0, t1 - t0}; }
  public static void main(String[] a) throws Exception {
    if (a[0].equals("flags")) { for (String f : new String[]{"AllocatePrefetchStyle", "AllocatePrefetchDistance", "AllocatePrefetchLines", "AllocatePrefetchStepSize", "AllocatePrefetchInstr", "AllocateInstancePrefetchLines", "TLABSize", "UseTLAB", "ZeroTLAB"}) { try { System.out.println("RES " + f + " = " + ManagementFactory.getPlatformMXBean(com.sun.management.HotSpotDiagnosticMXBean.class).getVMOption(f).getValue()); } catch (Exception e) { System.out.println("RES " + f + " = (无此选项)"); } } return; }
    if (a[0].equals("sizes")) { for (int size : new int[]{16, 32, 64, 128, 256, 1024, 4096, 16384}) { long[] r = worker(size, 0.5, 1.0, null); System.out.printf("RES %5d 字节:每次分配 %.1f ns,%.2f GB/s%n", size, r[2] / (double) r[0], r[1] / (double) r[2]); } return; }
    int size = Integer.parseInt(a[1]), threads = Integer.parseInt(a[2]); double secs = Double.parseDouble(a[3]); ExecutorService ex = Executors.newFixedThreadPool(threads); List<Future<long[]>> fs = new ArrayList<>();
    for (int t = 0; t < threads; t++) fs.add(ex.submit(() -> worker(size, 1.0, secs, null))); long n = 0, b = 0, ns = 0; for (Future<long[]> f : fs) { long[] r = f.get(); n += r[0]; b += r[1]; ns = Math.max(ns, r[2]); } ex.shutdown();
    System.out.printf("RES %d 字节 × %d 线程:总计 %.2f GB/s,每线程 %.2f GB/s,每次分配约 %.1f ns(按线程)%n", size, threads, b / (double) ns, b / (double) ns / threads, ns * (double) threads / n);
  }
}
'''
d = jdir('j255a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2000]); sys.exit()
BASE = ['-XX:+UseParallelGC', '-Xms3g', '-Xmx3g', '-Xmn2g', '-XX:-UseAdaptiveSizePolicy']
def run(flags, *args, timeout=200):
    r = subprocess.run(['java', *BASE, *flags, '-cp', 'out', 'Main', *args], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); return [l[4:] for l in r.stdout.splitlines() if l.startswith('RES ')], r.stdout + r.stderr
def gbs(line): return float(re.search(r'([\d.]+) GB/s', line).group(1))
def nsa(line): return float(re.search(r'每次分配约 ([\d.]+) ns', line).group(1))
print('== 一:本机(macOS arm64,JDK 21.0.12)默认的分配预取与 TLAB 相关 JVM 选项(ParallelGC,3 GB 堆,2 GB 年轻代)')
o, raw = run([], 'flags'); [print('  ' + l) for l in o]
print('== 二:AllocatePrefetchStyle 对分配速度的影响:1 个线程连续分配,64 字节与 1024 字节的 byte[](预热 1 s,测 2 s,每种 3 次取中位数)')
for style in (None, 0, 1, 2, 3):
    row = []
    for size in (64, 1024):
        rs = []
        for _ in range(3): o, raw = run(([] if style is None else [f'-XX:AllocatePrefetchStyle={style}']), 'one', str(size), '1', '2'); rs.append(o[0] if o else raw[:100])
        rs.sort(key=lambda l: gbs(l) if 'GB/s' in l else 0); m = rs[1]; row.append(f'{size} 字节:{gbs(m):.2f} GB/s(三次 {gbs(rs[0]):.2f}–{gbs(rs[2]):.2f})、{nsa(m):.1f} ns/次')
    print(f'  AllocatePrefetchStyle=' + ('默认' if style is None else str(style)) + ':' + ';  '.join(row))
print('== 三:AllocatePrefetchDistance(预取距离)对 64 字节与 1024 字节分配的影响:style 用默认值,每种 3 次取中位数')
for dist in (None, 0, 64, 128, 256, 384, 512):
    row = []
    for size in (64, 1024):
        rs = []
        for _ in range(3): o, raw = run(([] if dist is None else [f'-XX:AllocatePrefetchDistance={dist}']), 'one', str(size), '1', '2'); rs.append(o[0] if o else raw[:100])
        rs.sort(key=lambda l: gbs(l) if 'GB/s' in l else 0); m = rs[1]; row.append(f'{size} 字节:{gbs(m):.2f} GB/s(三次 {gbs(rs[0]):.2f}–{gbs(rs[2]):.2f})')
    print(f'  AllocatePrefetchDistance=' + ('默认' if dist is None else str(dist)) + ':' + ';  '.join(row))
r = subprocess.run(['java', *BASE, '-XX:AllocatePrefetchDistance=1024', '-cp', 'out', 'Main', 'flags'], cwd=d, env=E, capture_output=True, text=True); print('  AllocatePrefetchDistance=1024:' + ' '.join((r.stdout + r.stderr).split('\n')[0:2])[:200])
print('== 四:对象大小:1 个线程,默认选项,从 16 字节到 16 KiB 的 byte[]')
o, raw = run([], 'sizes'); [print('  ' + l) for l in o]
print('== 五:线程数:256 字节的 byte[],默认选项(预热 1 s,测 3 s)')
for t in (1, 2, 4, 8, 10):
    o, raw = run([], 'one', '256', str(t), '3'); print('  ' + (o[0] if o else raw[:200]))
