import sys, os, re, time, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j264'); R = {}
MAIN = r'''
import java.util.*; import java.util.function.*; import java.lang.System.Logger; import java.lang.System.Logger.Level;
public class Main {
  static final Logger LOG = System.getLogger("demo.app"); static int evals;
  static String expensive() { evals++; return "昂贵的消息 " + evals; }
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    if (mode.equals("levels")) {
      for (Level l : new Level[]{Level.TRACE, Level.DEBUG, Level.INFO, Level.WARNING, Level.ERROR}) { LOG.log(l, "消息 level=" + l); }
      System.err.println("RES isLoggable:TRACE=" + LOG.isLoggable(Level.TRACE) + " DEBUG=" + LOG.isLoggable(Level.DEBUG) + " INFO=" + LOG.isLoggable(Level.INFO) + " WARNING=" + LOG.isLoggable(Level.WARNING) + " ERROR=" + LOG.isLoggable(Level.ERROR) + " ALL=" + LOG.isLoggable(Level.ALL) + " OFF=" + LOG.isLoggable(Level.OFF) + ";Logger 实现类 " + LOG.getClass().getName() + ";名字 " + LOG.getName());
    } else if (mode.equals("lazy")) {
      evals = 0; for (int i = 0; i < 1000; i++) LOG.log(Level.DEBUG, () -> expensive()); System.out.println("RES DEBUG 被禁用:1000 次 log(level, Supplier) 调用后 Supplier 被执行了 " + evals + " 次");
      evals = 0; for (int i = 0; i < 1000; i++) LOG.log(Level.DEBUG, expensive()); System.out.println("RES DEBUG 被禁用:1000 次 log(level, String) 里直接调用 expensive():被执行了 " + evals + " 次");
      evals = 0; for (int i = 0; i < 1000; i++) LOG.log(Level.INFO, () -> expensive()); System.out.println("RES INFO 启用:1000 次 log(level, Supplier):Supplier 被执行了 " + evals + " 次(且每次都会输出到 stderr)");
    } else if (mode.equals("cost")) {
      int N = 5_000_000; int[] vals = {1, 2, 3}; long sink = 0;
      String[] names = {"log(DEBUG, Supplier)", "log(DEBUG, \"x=\" + i) 字符串拼接", "log(DEBUG, \"x={0}\", i) 参数形式", "if (isLoggable) log(...)", "不调用(空循环)"};
      for (int rep = 0; rep < 3; rep++) { double[] t = new double[names.length]; for (int m = 0; m < names.length; m++) { long t0 = System.nanoTime(); for (int i = 0; i < N; i++) { final int k = i; switch (m) { case 0 -> LOG.log(Level.DEBUG, () -> "x=" + k); case 1 -> LOG.log(Level.DEBUG, "x=" + i); case 2 -> LOG.log(Level.DEBUG, "x={0}", i); case 3 -> { if (LOG.isLoggable(Level.DEBUG)) LOG.log(Level.DEBUG, "x=" + i); } default -> sink += vals[i % 3]; } } t[m] = (System.nanoTime() - t0) / 1e6; } if (rep == 2) for (int m = 0; m < names.length; m++) System.out.printf("RES DEBUG 被禁用,%,d 次调用:%-34s %.0f ms(每次约 %.1f ns)%n", N, names[m], t[m], t[m] * 1e6 / N); }
      if (sink == 7) System.out.println();
    } else if (mode.equals("format")) {
      LOG.log(Level.INFO, "带占位符 {0} 和 {1}", "A", 42); LOG.log(Level.INFO, "用 %s 和 %d 占位", "A", 42); LOG.log(Level.INFO, "引号 ''单引号'' 与 {0}", "x"); LOG.log(Level.INFO, "{0,number,#.##} 与 {1}", 3.14159, new Date(0).getTime());
      LOG.log(Level.WARNING, "带异常", new IllegalStateException("出错了")); LOG.log(Level.INFO, "没有参数但含 {0}");
      LOG.log(Level.INFO, (String) null); LOG.log(Level.INFO, "{0} 的参数是数组", new Object[]{"p1", "p2"}); 
    } else if (mode.equals("custom")) {
      LOG.log(Level.INFO, "用自定义 LoggerFinder 记录的消息"); LOG.log(Level.DEBUG, "DEBUG 级别的消息"); Logger other = System.getLogger("other.name"); other.log(Level.WARNING, "另一个 logger"); System.out.println("RES finder = " + System.LoggerFinder.getLoggerFinder().getClass().getName());
      if (a.length > 1 && a[1].equals("exit")) { System.exit(3); }
    }
  }
}
'''
LF = r'''
import java.lang.System.*; import java.lang.System.Logger.Level; import java.util.*;
public class MyFinder extends System.LoggerFinder {
  public System.Logger getLogger(String name, Module module) { return new System.Logger() { public String getName() { return name; } public boolean isLoggable(Level l) { return l.getSeverity() >= Level.DEBUG.getSeverity(); }
    public void log(Level l, ResourceBundle b, String msg, Throwable t) { System.out.println("[CUSTOM " + l + "] " + name + " (模块 " + (module.isNamed() ? module.getName() : "未命名") + ") : " + (msg == null ? "null" : msg.replace("\n", "\\n")) + (t != null ? " + 异常 " + t : "")); }
    public void log(Level l, ResourceBundle b, String fmt, Object... params) { System.out.println("[CUSTOM " + l + "] " + name + " : " + java.text.MessageFormat.format(fmt, params)); } }; }
}
'''
d = jdir('j264a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def jv(mode, flags=(), extra=(), cp='out', timeout=300):
    r = subprocess.run(['java', *flags, '-cp', cp, 'Main', mode, *extra], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); return r.returncode, r.stdout, r.stderr
def show(o, e, keep=True):
    for l in (e.splitlines() + o.splitlines()):
        l = l.rstrip()
        if l.strip(): print('      ' + l.replace('RES ', '(RES) ')[:200])
print('== 一:默认后端(没有任何配置):各级别的输出与 isLoggable')
rc, o, e = jv('levels'); show(o, e)
print('== 二:用 java.util.logging 的配置文件打开 DEBUG / TRACE')
(d / 'logging.properties').write_text('handlers=java.util.logging.ConsoleHandler\n.level=INFO\ndemo.app.level=ALL\njava.util.logging.ConsoleHandler.level=ALL\njava.util.logging.SimpleFormatter.format=[%4$s] %3$s: %5$s%n\n')
rc, o, e = jv('levels', ('-Djava.util.logging.config.file=logging.properties',)); show(o, e)
print('== 三:惰性消息:Supplier 在级别被禁用时不会被执行')
rc, o, e = jv('lazy'); show(o.replace('RES ', ''), '')
print('== 四:消息格式:占位符是 java.text.MessageFormat 的 {0},不是 %s')
rc, o, e = jv('format', ('-Djava.util.logging.SimpleFormatter.format=[%4$s] %5$s%6$s%n',)); show('', e)
print('== 五:禁用的日志调用的成本(5,000,000 次,第 3 轮)')
rc, o, e = jv('cost'); show(o.replace('RES ', ''), '')
print('== 六:自定义 System.LoggerFinder(服务提供者,放在 classpath 上)')
sd = d / 'svc'; (sd / 'META-INF' / 'services').mkdir(parents=True, exist_ok=True); (sd / 'MyFinder.java').write_text(LF); (sd / 'META-INF' / 'services' / 'java.lang.System$LoggerFinder').write_text('MyFinder\n')
rc2 = subprocess.run(['javac', '-d', 'svc_out', 'svc/MyFinder.java'], cwd=d, env=E, capture_output=True, text=True); assert rc2.returncode == 0, rc2.stderr
shutil.copytree(sd / 'META-INF', d / 'svc_out' / 'META-INF', dirs_exist_ok=True)
rc, o, e = jv('custom', cp='out:svc_out'); print('    不带 System.exit:'); show(o.replace('RES ', ''), e)
rc, o, e = jv('custom', cp='out:svc_out', extra=('exit',)); print(f'    调用 System.exit(3),退出码 {rc}:'); show(o.replace('RES ', ''), e)
