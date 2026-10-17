import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j252'); R = {}
MAIN = r'''
import java.util.*; import java.util.stream.*; import java.lang.management.*;
public class Main {
  record Point(int x, int y) {} static volatile Object sink; static long acc;
  interface Shape { int area(int k); } record Sq(int s) implements Shape { public int area(int k) { return s * s + k; } } record Rc(int w, int h) implements Shape { public int area(int k) { return w * h + k; } } record Tr(int b, int h) implements Shape { public int area(int k) { return b * h / 2 + k; } }
  static int pea(int i) { Point p = new Point(i, i + 1); if ((i & 0xFFFFF) == 0) sink = p; return p.x() + p.y(); }
  static int ea(int i) { Point p = new Point(i, i + 1); return p.x() + p.y(); }
  static final List<Integer> LIST = IntStream.range(0, 1000).boxed().collect(Collectors.toList());
  static final Shape[] SHAPES = new Shape[1024]; static { for (int i = 0; i < SHAPES.length; i++) SHAPES[i] = switch (i % 3) { case 0 -> new Sq(i % 7 + 1); case 1 -> new Rc(i % 5 + 1, i % 3 + 1); default -> new Tr(i % 9 + 2, i % 4 + 2); }; }
  static final Shape[] BI = new Shape[1024]; static { for (int i = 0; i < BI.length; i++) BI[i] = i % 2 == 0 ? new Sq(i % 7 + 1) : new Rc(i % 5 + 1, i % 3 + 1); }
  static long work(String name) {
    switch (name) {
      case "stream": return LIST.stream().mapToInt(x -> x * x % 7).filter(x -> x > 2).sum();
      case "poly3": { long s = 0; for (int i = 0; i < SHAPES.length; i++) s += SHAPES[i].area(i); return s; }
      case "poly2": { long s = 0; for (int i = 0; i < BI.length; i++) s += BI[i].area(i); return s; }
      case "string": { long s = 0; for (int i = 0; i < 100; i++) { String t = "id-" + i + ":" + (i * 31); s += t.length() + Integer.parseInt(t.substring(t.indexOf(':') + 1)); } return s; }
      case "hash": { HashMap<Integer, Integer> m = new HashMap<>(); for (int i = 0; i < 500; i++) m.merge(i % 97, 1, Integer::sum); return m.size(); }
      default: throw new IllegalArgumentException(name); } }
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    com.sun.management.ThreadMXBean tm = (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean(); long tid = Thread.currentThread().threadId();
    if (mode.equals("pea")) {
      for (String name : new String[]{"ea(不逃逸)", "pea(只在罕见分支逃逸)"}) { long z = 0; for (int i = 0; i < 3_000_000; i++) z += name.startsWith("ea") ? ea(i) : pea(i); long b0 = tm.getThreadAllocatedBytes(tid); int N = 20_000_000; for (int i = 0; i < N; i++) z += name.startsWith("ea") ? ea(i) : pea(i); long b1 = tm.getThreadAllocatedBytes(tid); acc += z;
        System.out.printf("RES %s:%d 次调用,线程分配 %d 字节,每次 %.2f 字节%n", name, N, b1 - b0, (b1 - b0) / (double) N); }
    } else if (mode.equals("bench")) {
      for (String name : a[1].split(",")) { for (int w = 0; w < 3; w++) run(name, 400); double[] r = new double[7]; for (int k = 0; k < 7; k++) r[k] = run(name, 400); Arrays.sort(r); System.out.printf("RES %-8s 每毫秒 %.1f 次(中位数;最小 %.1f 最大 %.1f)%n", name, r[3], r[0], r[6]); }
    } else if (mode.equals("warm")) {
      StringBuilder sb = new StringBuilder("RES"); for (int b = 0; b < 40; b++) { long t0 = System.nanoTime(); for (int i = 0; i < 20000; i++) acc += work(a[1]); sb.append(String.format(" %.2f", (System.nanoTime() - t0) / 1e6)); } System.out.println(sb);
    } else if (mode.equals("long")) {
      long end = System.nanoTime() + Long.parseLong(a[2]) * 1_000_000L; long n = 0; while (System.nanoTime() < end) { for (int i = 0; i < 1000; i++) acc += work(a[1]); n += 1000; } System.out.println("RES 完成 " + n + " 次(" + a[1] + ")");
    } else if (mode.equals("flags")) {
      for (String f : new String[]{"UseJVMCICompiler", "EnableJVMCI", "UseJVMCINativeLibrary", "TieredStopAtLevel"}) System.out.println("RES " + f + " = " + ManagementFactory.getPlatformMXBean(com.sun.management.HotSpotDiagnosticMXBean.class).getVMOption(f).getValue());
    }
  }
  static double run(String name, long ms) { long end = System.nanoTime() + ms * 1_000_000L, n = 0, s = 0; long t0 = System.nanoTime(); while (System.nanoTime() < end) { for (int i = 0; i < 200; i++) s += work(name); n += 200; } acc += s; return n / ((System.nanoTime() - t0) / 1e6); }
}
'''
d = jdir('j252a'); (d / 'Main.java').write_text(MAIN); E = jenv('25g')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
CFG = [('C1(TieredStopAtLevel=1)', ['-XX:-UseJVMCICompiler', '-XX:TieredStopAtLevel=1']), ('C2', ['-XX:-UseJVMCICompiler']), ('Graal JIT(默认)', [])]
def jv(flags, *args, timeout=240):
    r = subprocess.run(['java', *flags, '-cp', 'out', 'Main', *args], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); return r.returncode, (r.stdout + r.stderr)
print('== 一:同一个 GraalVM CE 25.0.2 的 JDK 上用哪个编译器,由 -XX:±UseJVMCICompiler 决定')
for lab, fl in CFG:
    rc, o = jv(fl, 'flags'); print(f'  [{lab}] ' + ',  '.join(l[4:] for l in o.splitlines() if l.startswith('RES ')))
PEA_SRC = r'''
import java.lang.management.*;
public class Main { static class P { int x, y; P(int x, int y) { this.x = x; this.y = y; } } static Object sinkPlain; static volatile Object sinkVol; static P holder;
 static int v1(int i) { P p = new P(i, i + 1); if ((i & 0xFFFFF) == 0) sinkPlain = p; return p.x + p.y; }
 static int v2(int i) { P p = new P(i, i + 1); if ((i & 0xFFFFF) == 0) sinkVol = p; return p.x + p.y; }
 static int v3(int i) { P p = new P(i, i + 1); if (i == -5) sinkPlain = p; return p.x + p.y; }
 static int v4(int i) { P p = new P(i, i + 1); if ((i & 0xFFFFF) == 0) { holder = p; } return p.x * 3 + p.y; }
 static int v5(int i) { P p = new P(i, i + 1); int r = p.x + p.y; if ((i & 0xFFFFF) == 0) sinkPlain = new P(p.x, p.y); return r; }
 static int v6(int i) { P p = new P(i, i + 1); int r = p.x + p.y; if ((i & 0xFFFFF) == 0) sinkPlain = p; return r; }
 static int call(int k, int i) { switch (k) { case 1: return v1(i); case 2: return v2(i); case 3: return v3(i); case 4: return v4(i); case 5: return v5(i); default: return v6(i); } }
 public static void main(String[] a) { com.sun.management.ThreadMXBean tm = (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean(); long tid = Thread.currentThread().threadId();
  for (int k = 1; k <= 6; k++) { long z = 0; for (int i = 0; i < 3_000_000; i++) z += call(k, i); long b0 = tm.getThreadAllocatedBytes(tid); int N = 10_000_000; for (int i = 0; i < N; i++) z += call(k, i); long b1 = tm.getThreadAllocatedBytes(tid); System.out.printf("v%d 每次 %.2f 字节 (%d)%n", k, (b1 - b0) / (double) N, z & 1); } } }
'''
dp = jdir('j252p'); (dp / 'Main.java').write_text(PEA_SRC); subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=dp, env=E, check=True)
print('== 二:逃逸分析:每次调用线程分配多少字节(预热 300 万次、测 1000 万次;24 字节 = 对象没有被消除)')
print('  v1:对象在罕见分支(约每 100 万次一次)里存入普通静态字段,分支之后还读 p.x、p.y;v2:同样但存入 volatile 静态字段;v3:分支条件永远不成立(i == -5);v4:罕见分支存入另一个静态字段 holder,之后还读 p;v5:罕见分支里逃逸的是另一个新对象,p 本身不逃逸;v6:先读完 p.x + p.y,罕见分支里再把 p 存入静态字段,分支之后不再用 p')
for lab, fl in CFG[1:] + [('Graal JIT + -Djdk.graal.PartialEscapeAnalysis=false', ['-Djdk.graal.PartialEscapeAnalysis=false'])]:
    r = subprocess.run(['java', *fl, '-cp', 'out', 'Main'], cwd=dp, env=E, capture_output=True, text=True, timeout=240); print(f'  [{lab}] ' + ';  '.join(re.sub(r' \(\d\)', '', l).replace(' 每次 ', ' ') for l in r.stdout.splitlines() if l.startswith('v')))
r = subprocess.run(['java', '-XX:-UseJVMCICompiler', '-XX:TieredStopAtLevel=1', '-cp', 'out', 'Main'], cwd=dp, env=E, capture_output=True, text=True, timeout=240); print('  [C1(TieredStopAtLevel=1)] ' + ';  '.join(re.sub(r' \(\d\)', '', l).replace(' 每次 ', ' ') for l in r.stdout.splitlines() if l.startswith('v')))
print('== 三:稳态吞吐(预热 3 轮、测 7 轮取中位数,每轮 400 ms;数字是每毫秒完成的 work() 次数,越大越快)')
tp = {}
for lab, fl in CFG:
    rc, o = jv(fl, 'bench', 'stream,poly3,poly2,string,hash'); print(f'  [{lab}]'); [print('      ' + l[4:]) for l in o.splitlines() if l.startswith('RES ')]
print('== 四:预热曲线:stream 工作负载,每批 20000 次调用的耗时(毫秒),前 40 批')
for lab, fl in CFG:
    rc, o = jv(fl, 'warm', 'stream'); vals = [float(x) for x in o.split('RES')[1].split()]
    print(f'  [{lab}] 第 1 批 {vals[0]:.1f} ms,第 2 批 {vals[1]:.1f},第 5 批 {vals[4]:.1f},第 10 批 {vals[9]:.1f},第 20 批 {vals[19]:.1f},第 40 批 {vals[39]:.1f};前 40 批合计 {sum(vals):.0f} ms')
print('== 五:资源:同一个 6 秒的 stream 负载,/usr/bin/time -l 量到的峰值常驻内存与 CPU 时间')
for lab, fl in CFG:
    r = subprocess.run(['/usr/bin/time', '-l', 'java', *fl, '-cp', 'out', 'Main', 'long', 'stream', '6000'], cwd=d, env=E, capture_output=True, text=True, timeout=120); err = r.stderr
    rss = int(re.search(r'(\d+)\s+maximum resident set size', err).group(1)); m = re.search(r'([\d.]+)\s+real\s+([\d.]+)\s+user\s+([\d.]+)\s+sys', err)
    done = re.search(r'完成 (\d+) 次', r.stdout).group(1)
    print(f'  [{lab}] 6 秒内完成 {int(done):,} 次;峰值常驻内存 {rss / 1048576:.0f} MiB;real {m.group(1)} s,user {m.group(2)} s,sys {m.group(3)} s')
