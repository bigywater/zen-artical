import sys, os, re, time, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j262'); R = {}
MAIN = r'''
import java.io.*; import java.time.*; import java.util.*; import java.util.concurrent.*; import java.util.stream.*;
public class Main {
  static long T0 = System.nanoTime(); static long ms() { return (System.nanoTime() - T0) / 1_000_000; }
  static void say(String s) { System.out.println("RES " + s); }
  static String d(ProcessHandle h) { ProcessHandle.Info i = h.info(); return "pid " + h.pid() + " 命令 " + i.command().map(c -> c.replaceAll(".*/", "")).orElse("(空)") + " 参数 " + i.arguments().map(x -> String.join(" ", x)).orElse("(空)"); }
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    if (mode.equals("info")) {
      ProcessHandle me = ProcessHandle.current(); ProcessHandle.Info i = me.info();
      say("pid = " + me.pid() + ",isAlive = " + me.isAlive() + ",supportsNormalTermination = " + me.supportsNormalTermination());
      say("info.command = " + i.command().map(c -> c.replaceAll("/[^ ]*/(.*)", "…/$1")).orElse("Optional.empty"));
      say("info.commandLine = " + i.commandLine().map(c -> c.length() > 90 ? c.substring(0, 90) + "…" : c).orElse("Optional.empty"));
      say("info.arguments = " + i.arguments().map(x -> Arrays.toString(x)).orElse("Optional.empty"));
      say("info.startInstant 有值 = " + i.startInstant().isPresent() + ",info.totalCpuDuration = " + i.totalCpuDuration().map(x -> x.toMillis() + " ms").orElse("Optional.empty") + ",info.user = " + i.user().orElse("Optional.empty"));
      say("parent = " + me.parent().map(p -> d(p)).orElse("Optional.empty"));
      try { me.destroy(); } catch (Throwable t) { say("对当前进程 destroy():" + t.getClass().getSimpleName() + ":" + t.getMessage()); }
      long t0 = System.nanoTime(); long n = ProcessHandle.allProcesses().count(); say("allProcesses().count() = " + n + ",用时 " + (System.nanoTime() - t0) / 1_000_000 + " ms");
      long t1 = System.nanoTime(); List<ProcessHandle.Info> infos = ProcessHandle.allProcesses().map(ProcessHandle::info).toList(); long withCmd = infos.stream().filter(x -> x.command().isPresent()).count(); say("对其中每个进程调用 info():有 command 的 " + withCmd + " / " + infos.size() + " 个,用时 " + (System.nanoTime() - t1) / 1_000_000 + " ms(没有权限的进程 command 为空)");
    } else if (mode.equals("tree")) {
      Process p = new ProcessBuilder("sh", "-c", "sleep 61 & sleep 62 & sh -c 'sleep 63 & wait' & wait").start(); Thread.sleep(500); ProcessHandle h = p.toHandle();
      say("父 shell:" + d(h)); say("children() = " + h.children().map(c -> d(c)).collect(Collectors.toList())); say("descendants() 共 " + h.descendants().count() + " 个:" + h.descendants().map(c -> "pid " + c.pid() + " " + c.info().command().map(x -> x.replaceAll(".*/", "")).orElse("?") + " " + c.info().arguments().map(x -> String.join(" ", x)).orElse("")).collect(Collectors.toList()));
      List<ProcessHandle> kids = h.descendants().toList(); p.destroyForcibly(); p.waitFor(); Thread.sleep(300);
      say("destroyForcibly 只杀父 shell 之后:父 isAlive = " + h.isAlive() + ";原来的 " + kids.size() + " 个后代里仍然存活 " + kids.stream().filter(ProcessHandle::isAlive).count() + " 个;它们现在的 parent = " + kids.stream().filter(ProcessHandle::isAlive).map(k -> k.parent().map(pp -> "pid " + pp.pid()).orElse("?")).distinct().collect(Collectors.toList()));
      kids.stream().filter(ProcessHandle::isAlive).forEach(ProcessHandle::destroyForcibly); Thread.sleep(300); say("逐个 destroyForcibly 之后仍然存活 " + kids.stream().filter(ProcessHandle::isAlive).count() + " 个");
    } else if (mode.equals("exit")) {
      Process p = new ProcessBuilder("sleep", "1").start(); ProcessHandle h = p.toHandle(); long t0 = System.nanoTime(); CompletableFuture<ProcessHandle> f = h.onExit(); ProcessHandle r = f.get(); long el = (System.nanoTime() - t0) / 1_000_000;
      say("子进程 sleep 1:onExit() 在 " + el + " ms 时完成,isAlive = " + r.isAlive() + ",Process.exitValue = " + p.exitValue());
      Process shell = new ProcessBuilder("sh", "-c", "sleep 1 & echo $!").start(); long pid = Long.parseLong(new BufferedReader(new InputStreamReader(shell.getInputStream())).readLine().trim()); shell.waitFor(); ProcessHandle hh = ProcessHandle.of(pid).get(); t0 = System.nanoTime();
      say("非子进程(由已退出的 shell 派生,pid " + pid + "):isAlive = " + hh.isAlive() + ",parent = " + hh.parent().map(x -> "pid " + x.pid()).orElse("?")); hh.onExit().get(); el = (System.nanoTime() - t0) / 1_000_000; say("它的 onExit() 完成:从调用起 " + el + " ms(sleep 1 剩余约 1000 ms 减去派生后经过的时间)");
      List<Long> lat = new ArrayList<>(); for (int i = 0; i < 10; i++) { Process q = new ProcessBuilder("sleep", "0.3").start(); long s = System.nanoTime(); q.toHandle().onExit().get(); lat.add((System.nanoTime() - s) / 1_000_000); } Collections.sort(lat); say("10 次 sleep 0.3 的 onExit 延迟(毫秒,排序):" + lat + ",中位数 " + lat.get(5));
      ProcessHandle gone = ProcessHandle.of(pid).orElse(null); say("进程已退出后 ProcessHandle.of(pid) = " + (gone == null ? "Optional.empty" : "有值,isAlive = " + gone.isAlive()));
    } else if (mode.equals("destroy")) {
      Process p = new ProcessBuilder("sh", "-c", "trap '' TERM; echo ready; while true; do sleep 1; done").start(); new BufferedReader(new InputStreamReader(p.getInputStream())).readLine(); ProcessHandle h = p.toHandle();
      boolean r1 = h.destroy(); Thread.sleep(1500); say("忽略 SIGTERM 的进程:destroy() 返回 " + r1 + "(只表示请求已发出),1.5 s 后 isAlive = " + h.isAlive());
      long t0 = System.nanoTime(); boolean r2 = h.destroyForcibly(); int code = p.waitFor(); say("destroyForcibly() 返回 " + r2 + ",waitFor 返回退出码 " + code + "(= 128 + 信号 " + (code - 128) + "),用时 " + (System.nanoTime() - t0) / 1_000_000 + " ms,isAlive = " + h.isAlive());
      Process q = new ProcessBuilder("sleep", "30").start(); q.destroy(); int c2 = q.waitFor(); say("普通 sleep 30 被 destroy():退出码 " + c2 + "(= 128 + " + (c2 - 128) + ",SIGTERM)");
      say("对已退出的进程再次 destroy():" + q.toHandle().destroy() + ",destroyForcibly():" + q.toHandle().destroyForcibly());
      ProcessHandle init = ProcessHandle.of(1).get(); say("对 pid 1(launchd)destroy():" + safe(() -> init.destroy()) + "(没有权限)");
    }
    System.exit(0);
  }
  static String safe(Callable<Boolean> c) { try { return String.valueOf(c.call()); } catch (Throwable t) { return t.getClass().getSimpleName() + ":" + t.getMessage(); } }
}
'''
d = jdir('j262a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def jv(mode, timeout=60):
    r = subprocess.run(['java', '-cp', 'out', 'Main', mode], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); o = r.stdout + r.stderr; return [l[4:] for l in o.splitlines() if l.startswith('RES ')] or [o.strip()[:400]]
print('== 一:ProcessHandle.current() 与 info()(macOS,JDK 21.0.12)')
for l in jv('info'): print('  ' + l)
print('== 二:children() / descendants(),以及只杀父进程之后后代的去向')
for l in jv('tree'): print('  ' + l)
print('== 三:onExit():子进程与非子进程,完成延迟')
for l in jv('exit'): print('  ' + l)
print('== 四:destroy() 与 destroyForcibly()')
for l in jv('destroy'): print('  ' + l)
left = subprocess.run(['pgrep', '-f', 'sleep 6[123]'], capture_output=True, text=True).stdout.split(); print('  清理检查:实验结束后 pgrep 还能找到的 sleep 61/62/63 进程 ' + str(len(left)) + ' 个')
for pid in left: os.kill(int(pid), signal.SIGKILL)
