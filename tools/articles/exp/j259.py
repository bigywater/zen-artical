import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j259'); R = {}
MAIN = r'''
import java.io.*; import java.nio.file.*; import java.security.*; import java.util.*; import java.util.concurrent.ThreadLocalRandom;
public class Main {
  static Path dir; static long sink;
  static void write(Path p, byte[] b) throws IOException { Files.write(p, b); }
  static double med(double[] r) { Arrays.sort(r); return r[r.length / 2]; }
  interface Op { long run() throws Exception; }
  static double time(Op op, int reps) throws Exception { double[] r = new double[reps]; for (int i = 0; i < reps; i++) { long t0 = System.nanoTime(); sink += op.run(); r[i] = (System.nanoTime() - t0) / 1e6; } return med(r); }
  static long customCompare(Path a, Path b, int buf) throws IOException { try (InputStream x = Files.newInputStream(a); InputStream y = Files.newInputStream(b)) { byte[] bx = new byte[buf], by = new byte[buf]; long pos = 0; while (true) { int nx = x.readNBytes(bx, 0, buf), ny = y.readNBytes(by, 0, buf); int m = Arrays.mismatch(bx, 0, nx, by, 0, ny); if (m >= 0) return pos + m; if (nx < buf) return -1; pos += nx; } } }
  static byte[] sha(Path p) throws Exception { MessageDigest md = MessageDigest.getInstance("SHA-256"); try (InputStream in = Files.newInputStream(p)) { byte[] buf = new byte[1 << 20]; int n; while ((n = in.read(buf)) > 0) md.update(buf, 0, n); } return md.digest(); }
  public static void main(String[] a) throws Exception {
    dir = Path.of(a[0]); String mode = a[1];
    if (mode.equals("sem")) {
      Path e1 = dir.resolve("e1"), e2 = dir.resolve("e2"), x = dir.resolve("x"), y = dir.resolve("y"), p = dir.resolve("p"), l = dir.resolve("l"); write(e1, new byte[0]); write(e2, new byte[0]);
      write(x, "hello world".getBytes()); write(y, "hello_world".getBytes()); write(p, "hello".getBytes()); write(l, "hello world!!".getBytes());
      System.out.println("RES 两个空文件:" + Files.mismatch(e1, e2));
      System.out.println("RES 内容相同的两个文件(hello world vs hello world):" + Files.mismatch(x, x.resolveSibling("x2")) + "(x2 不存在会怎样见下)");
    } else if (mode.equals("sem2")) {
      Path x = dir.resolve("x"), x2 = dir.resolve("x2"), y = dir.resolve("y"), p = dir.resolve("p"), l = dir.resolve("l"), e1 = dir.resolve("e1");
      Files.copy(x, x2, StandardCopyOption.REPLACE_EXISTING);
      System.out.println("RES 内容相同的两个文件:" + Files.mismatch(x, x2));
      System.out.println("RES \"hello world\" vs \"hello_world\"(第 5 个字节不同,下标从 0 起):" + Files.mismatch(x, y));
      System.out.println("RES \"hello world\" vs \"hello\"(后者是前者的前缀):" + Files.mismatch(x, p) + "(= 较短文件的长度 " + Files.size(p) + ")");
      System.out.println("RES 参数顺序对调:" + Files.mismatch(p, x) + "、" + Files.mismatch(y, x));
      System.out.println("RES 空文件 vs 非空文件:" + Files.mismatch(e1, x));
      System.out.println("RES 同一个路径与自己比较:" + Files.mismatch(x, x));
      Path sym = dir.resolve("sym"); Files.deleteIfExists(sym); Files.createSymbolicLink(sym, x); System.out.println("RES 符号链接与它指向的文件:" + Files.mismatch(sym, x));
      try { Files.mismatch(x, dir.resolve("nope")); } catch (Exception e) { System.out.println("RES 其中一个文件不存在:" + e.getClass().getSimpleName() + ":" + e.getMessage().replace(dir.toString(), "<dir>")); }
      try { Files.mismatch(x, dir); System.out.println("RES 文件与目录:没有抛异常"); } catch (Exception e) { System.out.println("RES 文件与目录:" + e.getClass().getSimpleName() + ":" + e.getMessage().replace(dir.toString(), "<dir>")); }
      Path nul = Path.of("/dev/null"); System.out.println("RES 空文件与 /dev/null:" + Files.mismatch(e1, nul));
    } else if (mode.equals("gen")) {
      long size = Long.parseLong(a[2]); Path base = dir.resolve("A"); byte[] buf = new byte[1 << 20]; Random rnd = new Random(1);
      try (OutputStream o = Files.newOutputStream(base)) { for (long w = 0; w < size; w += buf.length) { rnd.nextBytes(buf); o.write(buf, 0, (int) Math.min(buf.length, size - w)); } }
      for (String name : new String[]{"B_same", "B_start", "B_mid", "B_end", "B_longer"}) Files.copy(base, dir.resolve(name), StandardCopyOption.REPLACE_EXISTING);
      flip(dir.resolve("B_start"), 0); flip(dir.resolve("B_mid"), size / 2); flip(dir.resolve("B_end"), size - 1); try (OutputStream o = Files.newOutputStream(dir.resolve("B_longer"), StandardOpenOption.APPEND)) { o.write(7); }
      System.out.println("RES 生成 A 与 5 个变体,每个 " + size / (1 << 20) + " MiB");
    } else if (mode.equals("pos")) {
      Path A = dir.resolve("A"); long size = Files.size(A);
      for (String v : new String[]{"B_start", "B_mid", "B_end", "B_same", "B_longer"}) { Path B = dir.resolve(v); long r = Files.mismatch(A, B); double ms = time(() -> Files.mismatch(A, B), 5); long scanned = r < 0 ? size : r; System.out.printf("RES %-9s Files.mismatch = %-10d 中位数 %.1f ms;需要比较的字节数 %d MiB(两个文件各一份)%n", v, r, ms, scanned >> 20); }
    } else if (mode.equals("strat")) {
      Path A = dir.resolve("A"); long size = Files.size(A);
      for (String v : new String[]{"B_same", "B_start"}) { Path B = dir.resolve(v); System.out.println("RES [" + v + "]");
        String[] names = {"Files.mismatch", "readAllBytes × 2 + Arrays.equals", "SHA-256 两个文件再比较摘要", "自写循环 8 KiB 缓冲", "自写循环 64 KiB 缓冲", "自写循环 1 MiB 缓冲"};
        Op[] ops = {() -> Files.mismatch(A, B), () -> Arrays.equals(Files.readAllBytes(A), Files.readAllBytes(B)) ? -1 : 1, () -> Arrays.equals(sha(A), sha(B)) ? -1 : 1, () -> customCompare(A, B, 8192), () -> customCompare(A, B, 65536), () -> customCompare(A, B, 1 << 20)};
        for (int i = 0; i < ops.length; i++) { Op op = ops[i]; time(op, 1); Runtime rt = Runtime.getRuntime(); System.gc(); long used0 = rt.totalMemory() - rt.freeMemory(); com.sun.management.ThreadMXBean tm = (com.sun.management.ThreadMXBean) java.lang.management.ManagementFactory.getThreadMXBean(); long b0 = tm.getThreadAllocatedBytes(Thread.currentThread().threadId()); double ms = time(op, 5); long b1 = tm.getThreadAllocatedBytes(Thread.currentThread().threadId());
          System.out.printf("RES     %-34s 中位数 %7.1f ms;每次调用线程分配约 %.1f MiB%n", names[i], ms, (b1 - b0) / 6.0 / 1048576); } }
    } else if (mode.equals("prefix")) {
      Path A = dir.resolve("A"), B = dir.resolve("B_longer"); System.out.println("RES A 与 B_longer 的大小:" + Files.size(A) + " / " + Files.size(B) + "(B 只比 A 多 1 字节,前缀相同)");
      double m1 = time(() -> Files.mismatch(A, B), 5); double m2 = time(() -> Files.size(A) != Files.size(B) ? 0 : Files.mismatch(A, B), 5);
      System.out.printf("RES Files.mismatch(A, B) 返回 %d,中位数 %.1f ms;先比 Files.size 再决定要不要 mismatch(大小不同就认为不相同,返回 0 的占位):中位数 %.3f ms%n", Files.mismatch(A, B), m1, m2);
      System.out.println("RES 结论:Files.mismatch 返回的是第一个差异的位置,所以大小不同、前缀相同的两个文件它也要读完较短的那个;只想知道“是否相同”时,先比较 Files.size 可以省掉这次读取");
    }
  }
  static void flip(Path p, long pos) throws IOException { try (RandomAccessFile r = new RandomAccessFile(p.toFile(), "rw")) { r.seek(pos); int b = r.read(); r.seek(pos); r.write(b ^ 0xFF); } }
}
'''
d = jdir('j259a'); (d / 'Main.java').write_text(MAIN); E = jenv('21'); data = JT / 'j259data'
import shutil; shutil.rmtree(data, ignore_errors=True); data.mkdir(parents=True)
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2000]); sys.exit()
def jv(*args, timeout=900):
    r = subprocess.run(['java', '-Xmx3g', '-cp', 'out', 'Main', str(data), *args], cwd=d, env=E, capture_output=True, text=True, timeout=timeout)
    return [l[4:] for l in r.stdout.splitlines() if l.startswith('RES ')], r.stdout + r.stderr
print('== 一:Files.mismatch 的返回值与边界情况(JDK 21.0.12)')
jv('sem'); o, raw = jv('sem2'); [print('  ' + l) for l in o] or print(raw[:500])
print('== 二:差异的位置决定耗时:A 与 5 个变体(各 128 MiB 随机数据),变体在开头 / 中间 / 末尾改 1 个字节、完全相同、末尾多 1 个字节')
o, raw = jv('gen', str(128 << 20)); print('  ' + o[0])
o, raw = jv('pos'); [print('  ' + l) for l in o]
print('== 三:比较两个文件的几种写法(128 MiB):完全相同的 B_same 与差异在开头的 B_start,各 5 次取中位数')
o, raw = jv('strat'); [print('  ' + l) for l in o]
print('== 四:大小不同但前缀相同:Files.mismatch 要读完较短的文件')
o, raw = jv('prefix'); [print('  ' + l) for l in o]
shutil.rmtree(data, ignore_errors=True)
