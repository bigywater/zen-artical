import sys, os, re, time, signal, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j257'); R = {}
MAIN = r'''
import java.util.*; import java.util.concurrent.*;
public class Main {
  static List<byte[]> hog = new ArrayList<>();
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    switch (mode) {
      case "exit" -> System.exit(Integer.parseInt(a[1]));
      case "main-throws" -> throw new IllegalStateException("main 抛出");
      case "thread-throws" -> { Thread t = new Thread(() -> { throw new IllegalStateException("子线程抛出"); }); t.start(); t.join(); System.out.println("main 正常结束"); }
      case "main-throws-other-running" -> { new Thread(() -> { try { Thread.sleep(800); } catch (InterruptedException e) { } System.out.println("子线程(非 daemon)正常结束"); }).start(); throw new IllegalStateException("main 抛出"); }
      case "thread-throws-main-ok" -> { Thread t = new Thread(() -> { try { Thread.sleep(200); } catch (InterruptedException e) { } throw new RuntimeException("子线程稍后抛出"); }); t.start(); System.out.println("main 返回"); }
      case "race" -> { CountDownLatch go = new CountDownLatch(1); for (int i = 1; i <= 2; i++) { int k = i; new Thread(() -> { try { go.await(); } catch (InterruptedException e) { } System.exit(k); }).start(); } Thread.sleep(100); go.countDown(); Thread.sleep(5000); }
      case "oom" -> { while (true) hog.add(new byte[1024 * 1024]); }
      case "oom-caught" -> { try { while (true) hog.add(new byte[1024 * 1024]); } catch (OutOfMemoryError e) { hog = null; System.out.println("main 捕获了 OutOfMemoryError,继续运行并正常结束"); } }
      case "oom-thread" -> { Thread t = new Thread(() -> { while (true) hog.add(new byte[1024 * 1024]); }); t.start(); t.join(); hog.clear(); System.out.println("main 在子线程 OOM 之后继续:join 返回"); }
      case "so" -> { rec(0); }
      case "ok" -> { }
    }
  }
  static int rec(int n) { return rec(n + 1) + 1; }
}
'''
d = jdir('j257a'); (d / 'Main.java').write_text(MAIN); (d / 'NoMain.java').write_text('public class NoMain { }'); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java', 'NoMain.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2000]); sys.exit()
def jrunx(args, flags=(), timeout=60):
    r = subprocess.run(['java', *flags, '-cp', 'out', 'Main', *args], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); return r.returncode, r.stdout + r.stderr
def code(rc): return f'{rc}' if rc >= 0 else f'(被信号 {-rc} 杀死)'
def first(o, n=1): return ' / '.join(l.strip()[:90] for l in o.strip().splitlines()[:n])
print('== 一:退出码:System.exit(n) 的取值范围,以及异常发生在哪个线程')
for n in (0, 1, 3, 255, 256, 257, 300, -1, -2):
    rc, o = jrunx(['exit', str(n)]); print(f'  System.exit({n}) → shell 看到的退出码 {code(rc)}')
for lab, mode in (('main 抛出未捕获异常', 'main-throws'), ('子线程抛出未捕获异常,main join 后正常结束', 'thread-throws'), ('main 返回,稍后(200 ms)非 daemon 子线程抛出未捕获异常', 'thread-throws-main-ok'), ('main 抛出异常,但另一个非 daemon 线程还要跑 800 ms', 'main-throws-other-running')):
    rc, o = jrunx([mode]); lines = [l.strip() for l in o.strip().splitlines()]; print(f'  {lab} → 退出码 {code(rc)};输出:' + ' | '.join(re.sub(r'\s+', ' ', l)[:70] for l in lines if not l.startswith('at ')))
print('== 二:多个线程同时调用 System.exit:2 个线程分别 exit(1) 与 exit(2),重复 30 次')
cnt = collections.Counter(); 
for _ in range(30): rc, o = jrunx(['race']); cnt[rc] += 1
print(f'  30 次的退出码分布:{dict(sorted(cnt.items()))}(每次只有一个调用生效,另一个调用被阻塞;哪个先到由线程调度决定)')
print('== 三:OutOfMemoryError(-Xmx16m)与退出码')
cases = [('默认:main 里不捕获', ['oom'], ['-Xmx16m']), ('默认:main 捕获后继续', ['oom-caught'], ['-Xmx16m']), ('默认:子线程 OOM 后 main 继续', ['oom-thread'], ['-Xmx16m']), ('-XX:+ExitOnOutOfMemoryError', ['oom'], ['-Xmx16m', '-XX:+ExitOnOutOfMemoryError']), ('-XX:+ExitOnOutOfMemoryError,子线程 OOM', ['oom-thread'], ['-Xmx16m', '-XX:+ExitOnOutOfMemoryError']), ('-XX:+CrashOnOutOfMemoryError', ['oom'], ['-Xmx16m', '-XX:+CrashOnOutOfMemoryError', '-XX:ErrorFile=hs_err_oom.log', '-XX:-CreateCoredumpOnCrash']), ('-XX:OnOutOfMemoryError="echo ...;"', ['oom'], ['-Xmx16m', '-XX:OnOutOfMemoryError=echo 外部命令被执行了'])]
for lab, args, fl in cases:
    rc, o = jrunx(args, fl); lines = [l.strip() for l in o.strip().splitlines() if l.strip() and not l.strip().startswith('at ')]
    extra = ''
    if (d / 'hs_err_oom.log').exists(): extra = f';生成了 hs_err_oom.log({(d / "hs_err_oom.log").stat().st_size // 1024} KiB)'; (d / 'hs_err_oom.log').unlink()
    print(f'  [{lab}] 退出码 {code(rc)};输出:' + ' | '.join(re.sub(r'\s+', ' ', l)[:75] for l in lines[:4]) + extra)
print('== 四:java 启动器自己的错误:退出码')
for lab, cmd in (('主类不存在', ['java', '-cp', 'out', 'NoSuchMain']), ('主类存在但没有 main 方法', ['java', '-cp', 'out', 'NoMain']), ('无效的堆大小 -Xmx0m', ['java', '-Xmx0m', '-cp', 'out', 'Main', 'ok']), ('未知的 JVM 选项', ['java', '-XX:+NoSuchFlag', '-cp', 'out', 'Main', 'ok']), ('-version', ['java', '-version']), ('栈溢出(main 无限递归)', ['java', '-cp', 'out', 'Main', 'so'])):
    r = subprocess.run(cmd, cwd=d, env=E, capture_output=True, text=True, timeout=60); o = [l.strip() for l in (r.stdout + r.stderr).strip().splitlines() if l.strip() and not l.strip().startswith('at ')]
    print(f'  {lab} → 退出码 {code(r.returncode)};输出首行:' + re.sub(r'\s+', ' ', o[0])[:100])
