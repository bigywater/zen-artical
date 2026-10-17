import sys, os, re, time, signal, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j256'); R = {}
MAIN = r'''
import java.io.*; import java.nio.file.*; import java.util.*; import java.util.concurrent.*;
public class Main {
  static Path mark; static long T0 = System.nanoTime();
  static void log(String s) { try { Files.writeString(mark, String.format("[%5d ms] %s%n", (System.nanoTime() - T0) / 1_000_000, s), StandardOpenOption.CREATE, StandardOpenOption.APPEND); } catch (IOException e) { } }
  static void waitForever() { System.out.println("READY"); System.out.flush(); try { Thread.sleep(600_000); } catch (InterruptedException e) { } }
  public static void main(String[] a) throws Exception {
    mark = Path.of(a[1]); String mode = a[0];
    Runtime.getRuntime().addShutdownHook(new Thread(() -> { log("hook 开始,线程 " + Thread.currentThread().getName()); 
      if (mode.equals("slow")) for (int i = 1; i <= 10; i++) { try { Thread.sleep(300); } catch (InterruptedException e) { } log("清理步骤 " + i); }
      if (mode.equals("block")) { try { Thread.sleep(30_000); } catch (InterruptedException e) { } }
      if (mode.equals("lateadd")) { try { Runtime.getRuntime().addShutdownHook(new Thread(() -> { })); log("关机期间 addShutdownHook 成功"); } catch (Exception e) { log("关机期间 addShutdownHook 抛出 " + e.getClass().getSimpleName() + ":" + e.getMessage()); } }
      if (mode.equals("exitinhook")) { log("hook 里调用 System.exit(9)"); System.exit(9); log("System.exit 返回了(不应该)"); }
      if (mode.equals("haltinhook")) { log("hook 里调用 Runtime.halt(9)"); Runtime.getRuntime().halt(9); }
      if (mode.equals("daemon")) { try { Thread.sleep(700); } catch (InterruptedException e) { } }
      log("hook 结束"); }, "my-hook"));
    switch (mode) {
      case "normal" -> { log("main 返回"); }
      case "exit3" -> { log("main 调用 System.exit(3)"); System.exit(3); }
      case "uncaught" -> throw new IllegalStateException("main 里的未捕获异常");
      case "halt" -> { log("main 调用 Runtime.halt(4)"); Runtime.getRuntime().halt(4); }
      case "multi" -> { for (int i = 1; i <= 5; i++) { int k = i; Runtime.getRuntime().addShutdownHook(new Thread(() -> { log("附加 hook " + k + " 开始,线程 " + Thread.currentThread().getName()); try { Thread.sleep(200); } catch (InterruptedException e) { } log("附加 hook " + k + " 结束"); }, "extra-" + i)); } }
      case "nondaemon" -> { Thread t = new Thread(() -> { try { Thread.sleep(1500); } catch (InterruptedException e) { } log("非 daemon 线程结束"); }); t.start(); log("main 返回,非 daemon 线程还在跑"); }
      case "daemon" -> { Thread d = new Thread(() -> { while (true) { log("daemon 线程仍在运行"); try { Thread.sleep(250); } catch (InterruptedException e) { } } }); d.setDaemon(true); d.start(); waitForever(); }
      default -> waitForever(); // wait / slow / block / lateadd / exitinhook / haltinhook
    }
  }
}
'''
d = jdir('j256a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2000]); sys.exit()
def scen(mode, sig=None, delay=0.8, kill_after=None, wait=6):
    mk = d / f'mark_{mode}_{sig}.txt'; mk.unlink(missing_ok=True)
    p = subprocess.Popen(['java', '-cp', 'out', 'Main', mode, str(mk)], cwd=d, env=E, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True); t0 = time.time()
    if sig is not None:
        while True:
            l = p.stdout.readline()
            if 'READY' in l or p.poll() is not None: break
        time.sleep(delay); os.kill(p.pid, sig)
        if kill_after is not None:
            time.sleep(kill_after); 
            if p.poll() is None: os.kill(p.pid, signal.SIGKILL)
    try: p.wait(timeout=wait); alive = False
    except subprocess.TimeoutExpired: alive = True; p.kill(); p.wait()
    lines = mk.read_text().splitlines() if mk.exists() else []
    return p.returncode, alive, lines, time.time() - t0
def desc(rc): return f'退出码 {rc}' if rc >= 0 else f'被信号 {-rc} 杀死({signal.Signals(-rc).name})'
print('== 一:哪些退出方式会运行 shutdown hook(每次新 JVM;hook 往文件里写 “hook 开始 / hook 结束”)')
rows = [('main 正常返回', 'normal', None), ('System.exit(3)', 'exit3', None), ('main 抛出未捕获异常', 'uncaught', None), ('Runtime.halt(4)', 'halt', None), ('SIGINT(Ctrl-C)', 'wait', signal.SIGINT), ('SIGTERM(kill)', 'wait', signal.SIGTERM), ('SIGHUP(终端关闭)', 'wait', signal.SIGHUP), ('SIGQUIT(kill -3,线程转储)', 'wait', signal.SIGQUIT), ('SIGKILL(kill -9)', 'wait', signal.SIGKILL)]
for lab, mode, sig in rows:
    rc, alive, lines, t = scen(mode, sig, wait=4)
    ran = any('hook 结束' in l for l in lines); started = any('hook 开始' in l for l in lines)
    print(f'  {lab:<24} → {"进程仍然活着(被我杀掉)" if alive else desc(rc)};hook {"运行完了" if ran else ("开始了但没结束" if started else "没有运行")}')
print('== 二:多个 hook:主 hook + 5 个附加 hook,各 sleep 200 ms;连续 3 次')
for k in range(3):
    rc, alive, lines, t = scen('multi'); st = sorted(re.findall(r'\[ *(\d+) ms\] (附加 hook \d 开始)', '\n'.join(lines)), key=lambda x: int(x[0]))
    starts = [int(x[0]) for x in st]; mn = min(starts); print(f'  第 {k + 1} 次:启动顺序 ' + ' → '.join(x[1].split(' ')[2] for x in st) + f';各 hook 开始时刻的跨度 {max(starts) - mn} ms;线程名 ' + ','.join(sorted(set(re.findall(r'线程 (extra-\d)', '\n'.join(lines))))))
print('== 三:hook 做得慢:SIGTERM 之后清理要 3 秒(每 300 ms 一步),但调度器 1 秒后 kill -9')
rc, alive, lines, t = scen('slow', signal.SIGTERM, kill_after=1.0, wait=8); steps = [l for l in lines if '清理步骤' in l]
print(f'  {desc(rc)};hook 完成的清理步骤 {len(steps)} / 10;最后一条:' + (steps[-1] if steps else '无') + ';hook 是否结束 = ' + str(any('hook 结束' in l for l in lines)))
rc, alive, lines, t = scen('slow', signal.SIGTERM, wait=8); steps = [l for l in lines if '清理步骤' in l]; print(f'  对照:不 kill -9:{desc(rc)},用时 {t:.1f} s,清理步骤 {len(steps)} / 10,hook 是否结束 = {any("hook 结束" in l for l in lines)}')
rc, alive, lines, t = scen('block', signal.SIGTERM, wait=3); print(f'  hook 里 sleep 30 秒:SIGTERM 后 3 秒,进程{"仍然活着" if alive else "已退出"};hook 日志 {lines}')
print('== 四:关机期间能做什么')
rc, alive, lines, t = scen('lateadd', signal.SIGTERM, wait=5); print('  hook 里再 addShutdownHook:' + ' | '.join(l.split('] ', 1)[1] for l in lines if '关机期间' in l))
rc, alive, lines, t = scen('exitinhook', signal.SIGTERM, wait=4); print(f'  hook 里调用 System.exit(9):{"进程仍然活着(死锁,被我杀掉)" if alive else desc(rc)};日志 ' + ' | '.join(l.split('] ', 1)[1] for l in lines))
rc, alive, lines, t = scen('haltinhook', signal.SIGTERM, wait=4); print(f'  hook 里调用 Runtime.halt(9):{"进程仍然活着" if alive else desc(rc)};日志 ' + ' | '.join(l.split('] ', 1)[1] for l in lines))
rc, alive, lines, t = scen('daemon', signal.SIGTERM, wait=5); dl = [l for l in lines if 'daemon 线程仍在运行' in l]; hs = [l for l in lines if 'hook 开始' in l][0]; he = [l for l in lines if 'hook 结束' in l]
hs_t = int(re.search(r'\[ *(\d+)', hs).group(1)); he_t = int(re.search(r'\[ *(\d+)', he[0]).group(1)) if he else None; during = [l for l in dl if hs_t <= int(re.search(r'\[ *(\d+)', l).group(1)) <= (he_t or 10**9)]
print(f'  daemon 线程在 hook 运行期间({hs_t}–{he_t} ms):daemon 线程仍然写了 {len(during)} 条日志(没有被停掉)')
print('== 五:非 daemon 线程与退出:main 返回后还有一个 1.5 秒的非 daemon 线程')
rc, alive, lines, t = scen('nondaemon', wait=6); print(f'  {desc(rc)},用时 {t:.1f} s;日志 ' + ' | '.join(l for l in lines))
