import sys, os, re, time, signal, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j260'); R = {}
MAIN = r'''
import java.io.*; import java.nio.channels.*; import java.nio.file.*; import java.nio.file.StandardOpenOption;
public class Main {
  static long T0 = System.nanoTime(); static long ms() { return (System.nanoTime() - T0) / 1_000_000; }
  static void say(String s) { System.out.println("[" + ms() + " ms] " + s); System.out.flush(); }
  public static void main(String[] a) throws Exception {
    String mode = a[0]; Path p = Path.of(a[1]); boolean shared = a.length > 2 && a[2].equals("shared"); long pos = a.length > 3 ? Long.parseLong(a[3]) : 0, size = a.length > 4 ? Long.parseLong(a[4]) : Long.MAX_VALUE; long hold = a.length > 5 ? Long.parseLong(a[5]) : 1000;
    StandardOpenOption[] opts = shared ? new StandardOpenOption[]{StandardOpenOption.CREATE, StandardOpenOption.READ} : new StandardOpenOption[]{StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.READ};
    switch (mode) {
      case "hold" -> { try (FileChannel ch = FileChannel.open(p, opts); FileLock l = ch.lock(pos, size, shared)) { say("LOCKED " + (shared ? "共享" : "独占") + " [" + pos + ", " + (size == Long.MAX_VALUE ? "∞" : pos + size) + ")"); Thread.sleep(hold); } say("RELEASED"); }
      case "try" -> { try (FileChannel ch = FileChannel.open(p, opts)) { FileLock l = ch.tryLock(pos, size, shared); say("TRY " + (shared ? "共享" : "独占") + " [" + pos + ", " + (size == Long.MAX_VALUE ? "∞" : pos + size) + ") → " + (l == null ? "null(被别的进程持有)" : "拿到了")); if (l != null) l.release(); } }
      case "block" -> { try (FileChannel ch = FileChannel.open(p, opts)) { say("WAITING"); long t = System.nanoTime(); try (FileLock l = ch.lock(pos, size, shared)) { say("ACQUIRED,等了 " + (System.nanoTime() - t) / 1_000_000 + " ms"); } } }
      case "write" -> { try (FileOutputStream o = new FileOutputStream(p.toFile(), true)) { o.write("无视锁写入".getBytes()); } say("WROTE(没有申请锁),文件现在 " + Files.size(p) + " 字节"); }
      case "samejvm" -> { try (FileChannel c1 = FileChannel.open(p, opts); FileChannel c2 = FileChannel.open(p, opts)) { FileLock l1 = c1.lock(0, 100, false); say("c1 独占 [0, 100)");
          try { c2.tryLock(0, 100, false); say("c2 独占 [0, 100) 拿到了"); } catch (OverlappingFileLockException e) { say("c2 独占 [0, 100):OverlappingFileLockException(同一个 JVM 内重叠)"); }
          try { FileLock l = c2.tryLock(50, 100, false); say("c2 独占 [50, 150):" + (l == null ? "null" : "拿到了")); } catch (OverlappingFileLockException e) { say("c2 独占 [50, 150):OverlappingFileLockException"); }
          try { FileLock l = c2.tryLock(100, 100, false); say("c2 独占 [100, 200):" + (l == null ? "null" : "拿到了(不重叠的区域)")); if (l != null) l.release(); } catch (OverlappingFileLockException e) { say("c2 独占 [100, 200):OverlappingFileLockException"); }
          try { c2.tryLock(0, 100, true); say("c2 共享 [0, 100) 拿到了"); } catch (OverlappingFileLockException e) { say("c2 共享 [0, 100):OverlappingFileLockException"); }
          say("c1 的锁 isValid = " + l1.isValid() + ",isShared = " + l1.isShared()); l1.release(); say("释放后 isValid = " + l1.isValid()); } }
      case "closeother" -> { FileChannel c1 = FileChannel.open(p, opts); FileLock l = c1.lock(0, Long.MAX_VALUE, false); say("c1 持有独占锁,isValid = " + l.isValid()); FileChannel c2 = FileChannel.open(p, StandardOpenOption.READ); c2.close(); say("关闭同一个文件的另一个通道 c2 之后:c1 的 FileLock.isValid = " + l.isValid() + "(JDK 自己的状态)"); say("HOLDING"); Thread.sleep(hold); l.release(); c1.close(); say("RELEASED"); }
      case "holddelete" -> { FileChannel c1 = FileChannel.open(p, opts); FileLock l = c1.lock(0, Long.MAX_VALUE, false); say("LOCKED 独占 " + p.getFileName()); Thread.sleep(300); Files.delete(p); say("DELETED(锁文件被删除)"); Thread.sleep(hold); say("A 的锁 isValid = " + l.isValid()); l.release(); c1.close(); say("RELEASED"); }
    }
  }
}
'''
d = jdir('j260a'); (d / 'Main.java').write_text(MAIN); E = jenv('21'); data = JT / 'j260data'
import shutil; shutil.rmtree(data, ignore_errors=True); data.mkdir(parents=True)
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2000]); sys.exit()
def start(*args):
    return subprocess.Popen(['java', '-cp', 'out', 'Main', *args], cwd=d, env=E, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
def readto(p, key, timeout=15):
    out = []; t0 = time.time()
    while time.time() - t0 < timeout:
        l = p.stdout.readline()
        if not l: break
        out.append(l.strip())
        if key in l: break
    return out
def finish(p, timeout=20):
    try: o = p.communicate(timeout=timeout)[0]
    except subprocess.TimeoutExpired: p.kill(); o = p.communicate()[0]
    return [l.strip() for l in o.splitlines() if l.strip()]
def show(label, lines): print(f'  {label}:' + ' | '.join(lines))
F = str(data / 'f.lock')
print('== 一:两个 JVM 进程之间:A 持有独占锁 2 秒;B 用 tryLock 与阻塞的 lock')
a = start('hold', F, 'excl', '0', str(2**63 - 1), '2000'); readto(a, 'LOCKED')
b = start('try', F, 'excl'); bl = finish(b); show('B tryLock(独占,整个文件)', bl)
b2 = start('block', F, 'excl'); t0 = time.time(); bl2 = finish(b2); show('B lock()(阻塞)', bl2); print(f'      B 进程整体 {time.time() - t0:.1f} s;A:' + ' | '.join(finish(a)))
a = start('hold', F, 'shared', '0', str(2**63 - 1), '1500'); readto(a, 'LOCKED')
show('A 持有共享锁时 B 申请共享', finish(start('try', F, 'shared'))); show('A 持有共享锁时 B 申请独占', finish(start('try', F, 'excl'))); finish(a)
a = start('hold', F, 'excl', '0', '100', '1500'); readto(a, 'LOCKED')
show('A 独占 [0, 100) 时 B 申请 [100, 200)', finish(start('try', F, 'excl', '100', '100'))); show('A 独占 [0, 100) 时 B 申请 [50, 150)', finish(start('try', F, 'excl', '50', '100'))); finish(a)
print('== 二:同一个 JVM 内:两个通道申请重叠区域')
show('同一个 JVM', finish(start('samejvm', F)))
print('== 三:锁是“建议性”的:A 持有独占锁时,B 不申请锁直接往文件里写')
(data / 'g.dat').write_text('')
a = start('hold', str(data / 'g.dat'), 'excl', '0', str(2**63 - 1), '1500'); readto(a, 'LOCKED'); show('B 直接写', finish(start('write', str(data / 'g.dat')))); finish(a)
print('  文件最终内容:' + (data / 'g.dat').read_text())
print('== 四:锁什么时候被释放')
a = start('hold', F, 'excl', '0', str(2**63 - 1), '30000'); readto(a, 'LOCKED'); time.sleep(0.3); show('A 持有时 B tryLock', finish(start('try', F, 'excl')))
t0 = time.time(); a.send_signal(signal.SIGKILL); a.wait(); show(f'kill -9 A 之后 B tryLock(间隔 {time.time() - t0:.2f} s)', finish(start('try', F, 'excl')))
a = start('closeother', F, 'excl', '0', str(2**63 - 1), '3000'); lines = readto(a, 'HOLDING'); show('A(同一个进程里关闭了同一个文件的另一个通道)', lines)
show('A 还在 HOLDING 时 B tryLock', finish(start('try', F, 'excl'))); finish(a)
print('== 五:锁文件被删除再重建:两个进程各自以为持有独占锁')
lf = str(data / 'app.lock'); a = start('holddelete', lf, 'excl', '0', str(2**63 - 1), '1500'); lines = readto(a, 'DELETED'); show('A', lines)
show('B 在 A 删除锁文件之后 tryLock 同一个路径', finish(start('try', lf, 'excl'))); show('A 之后', finish(a))
shutil.rmtree(data, ignore_errors=True)
