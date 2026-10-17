import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j240'); R = {}
JU = mcp('org.junit.platform:junit-platform-console-standalone:1.11.3').split(':')[0]
d = jdir('j240a'); E = jenv('21')
def w(p, c): f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(c)
W = 'import org.junit.jupiter.api.*; import static org.junit.jupiter.api.Assertions.*; import java.time.Duration; import java.util.concurrent.*; import java.util.concurrent.atomic.*; import java.util.concurrent.TimeUnit;\n'
w('H.java', 'class H { static final long T0 = System.nanoTime(); static long ms() { return (System.nanoTime() - T0) / 1_000_000; } static void log(String s) { System.out.println("EV [" + String.format("%5d", ms()) + " ms] " + s); }\n static long work(long it) { long x = 88172645463325252L; for (long i = 0; i < it; i++) { x ^= x << 13; x ^= x >>> 7; x ^= x << 17; } return x; }\n static void busy(long ms) { long end = System.nanoTime() + ms * 1_000_000L; long x = 0; while (System.nanoTime() < end) x++; if (x == -1) System.out.println(); } }\n')
w('SleepTO.java', W + '''public class SleepTO { @Test @Timeout(1) void sleeps3s() throws Exception { H.log("sleep 开始"); try { Thread.sleep(3000); } catch (InterruptedException e) { H.log("sleep 被中断"); throw e; } } }''')
w('BusyTO.java', W + '''public class BusyTO { @Test @Timeout(1) void busy3s() { H.log("忙等 3 秒开始(不检查中断)"); H.busy(3000); H.log("忙等结束,方法返回"); } }''')
w('SepTO.java', W + '''public class SepTO { @Test @Timeout(value = 1, threadMode = Timeout.ThreadMode.SEPARATE_THREAD) void busy3s() { H.log("忙等 3 秒开始,线程 " + (Thread.currentThread().getName().startsWith("main") ? "main" : "非 main 线程")); H.busy(3000); H.log("忙等结束(测试早已被判失败)"); } }''')
w('TlTO.java', W + '''public class TlTO { static final ThreadLocal<String> TL = new ThreadLocal<>(); static String thr() { return Thread.currentThread().getName().startsWith("main") ? "main" : "另一个线程"; }
  @BeforeEach void be() { TL.set("事务上下文"); H.log("@BeforeEach 在 " + thr() + " 里设置 ThreadLocal"); }
  @Test @Timeout(5) void sameThread() { H.log("SAME_THREAD(默认):在 " + thr() + " 里读到 ThreadLocal = " + TL.get()); }
  @Test @Timeout(value = 5, threadMode = Timeout.ThreadMode.SEPARATE_THREAD) void separate() { H.log("SEPARATE_THREAD:在 " + thr() + " 里读到 ThreadLocal = " + TL.get()); } }''')
w('AssertTO.java', W + '''public class AssertTO { @Test void nonPreemptive() { H.log("assertTimeout 开始(sleep 3 秒)"); assertTimeout(Duration.ofSeconds(1), () -> { Thread.sleep(3000); H.log("assertTimeout 的 lambda 跑完了"); }); }
  @Test void preemptive() { H.log("assertTimeoutPreemptively 开始(sleep 3 秒)"); assertTimeoutPreemptively(Duration.ofSeconds(1), () -> { try { Thread.sleep(3000); } catch (InterruptedException e) { H.log("lambda 被中断"); throw e; } }); } }''')
w('NoAnno.java', W + '''public class NoAnno { @BeforeEach void hangs() throws Exception { H.log("@BeforeEach 卡住 3 秒(没有任何 @Timeout)"); Thread.sleep(3000); H.log("@BeforeEach 结束"); } @Test void t() { H.log("test 运行"); } }''')
w('AfterTO.java', W + '''public class AfterTO { @Test void another() throws Exception { H.log("另一个测试开始(sleep 3.5 秒,模拟后面的测试)"); Thread.sleep(3500); H.log("另一个测试结束"); } }''')
w('Load.java', W + '''public class Load { @RepeatedTest(300) @Timeout(value = 60, unit = TimeUnit.MILLISECONDS) void work() { if (H.work(ITER) == 1) System.out.print(""); }
 static final long ITER = Long.getLong("iter", 100_000_000L); }''')
r = subprocess.run(['javac', '-d', 'out', '-cp', JU, *[str(p) for p in d.glob('*.java')]], cwd=d, env=E, capture_output=True, text=True)
if r.returncode: print(r.stderr[:2500]); sys.exit()
def run(cls, cfg=(), label=None, quiet=False, jv=()):
    args = ['java', *jv, '-cp', f'out:{JU}', 'org.junit.platform.console.ConsoleLauncher', 'execute', '--disable-banner', '--disable-ansi-colors', '--details=tree', *sum([['--select-class', c] for c in ([cls] if isinstance(cls, str) else cls)], [])]
    for k in cfg: args += ['--config', k]
    t0 = time.perf_counter(); q = subprocess.run(args, cwd=d, env=E, capture_output=True, text=True, timeout=300); wall = time.perf_counter() - t0; o = q.stdout + q.stderr
    ev = [re.sub(r'^EV ', '', l) for l in o.splitlines() if l.startswith('EV ')]
    summ = ' | '.join(re.sub(r'\s+', ' ', l.strip().lstrip('[').strip().rstrip(']').strip()) for l in o.splitlines() if re.search(r'\d+ tests (successful|failed)', l))
    msgs = [re.sub(r'\s+', ' ', l.strip())[:190] for l in o.splitlines() if ('✘' in l and '()' in l) or l.strip().startswith('=> ')]
    if not quiet:
        print(f'  [{label or (cls if isinstance(cls, str) else " + ".join(cls))}]' + (f'(配置 {" ".join(cfg)})' if cfg else '') + f' 整个 JVM 用时 {wall:.1f} s'); [print('      ' + l) for l in ev]
        for m in msgs[:6]: print('      ' + m)
        print('      → ' + summ)
    return o, wall
base = [run('NoAnno', quiet=True)[1] for _ in range(1)]  # warm
t0 = time.perf_counter(); subprocess.run(['java', '-cp', f'out:{JU}', 'org.junit.platform.console.ConsoleLauncher', 'execute', '--disable-banner', '--details=summary', '--select-method', 'NoAnno#t'], cwd=d, env=E, capture_output=True, text=True); 
print('== 一:默认的 @Timeout(1)(在测试线程里执行,靠中断):sleep 3 秒的测试与忙等 3 秒(不检查中断)的测试')
run('SleepTO'); run('BusyTO')
print('== 二:@Timeout(threadMode = SEPARATE_THREAD):忙等 3 秒;以及 ThreadLocal 在两种模式下的可见性')
run('SepTO'); run(['SepTO', 'AfterTO'], label='SepTO + AfterTO 在同一个 JVM 里'); run('TlTO')
print('== 三:assertTimeout 与 assertTimeoutPreemptively(都是 1 秒、lambda 里 sleep 3 秒)')
run('AssertTO')
print('== 四:全局默认超时 junit.jupiter.execution.timeout.default:@BeforeEach 卡住 3 秒、没有任何 @Timeout')
run('NoAnno', label='NoAnno 不设默认超时'); run('NoAnno', cfg=['junit.jupiter.execution.timeout.default=1s'], label='NoAnno 默认超时 1s')
w('Calib.java', 'public class Calib { public static void main(String[] a) { long best = Long.MAX_VALUE; for (int r = 0; r < 8; r++) { long t0 = System.nanoTime(); long x = H.work(100_000_000L); best = Math.min(best, System.nanoTime() - t0); if (x == 1) System.out.print(""); } System.out.println(best / 1_000_000); } }')
subprocess.run(['javac', '-d', 'out', '-cp', f'out:{JU}', str(d / 'Calib.java')], cwd=d, env=E)
ms100 = int(subprocess.run(['java', '-cp', 'out', 'Calib'], cwd=d, env=E, capture_output=True, text=True).stdout.strip().splitlines()[-1]); ITER = int(100_000_000 * 30 / ms100)
print(f'== 五:超时设得太紧:@RepeatedTest(300),每次做固定量的 CPU 计算(空闲时约 30 ms:1 亿次计算 {ms100} ms,取 {ITER} 次),@Timeout(60 ms)——空闲机器与满载机器各跑 3 次')
ncpu = os.cpu_count(); print(f'  逻辑 CPU {ncpu} 个')
def failcount(o):
    m = re.search(r'(\d+) tests failed', o); s = re.search(r'(\d+) tests successful', o); return (int(s.group(1)) if s else -1, int(m.group(1)) if m else -1)
for k in range(3):
    o, wl = run('Load', quiet=True, jv=[f'-Diter={ITER}']); ok, bad = failcount(o); print(f'  空闲机器 第 {k+1} 次:成功 {ok}、失败 {bad}')
spin = [subprocess.Popen(['python3', '-c', 'while True: pass']) for _ in range(ncpu * 4)]
try:
    time.sleep(1)
    for k in range(3):
        o, wl = run('Load', quiet=True, jv=[f'-Diter={ITER}']); ok, bad = failcount(o); print(f'  满载机器({ncpu * 4} 个空转进程)第 {k+1} 次:成功 {ok}、失败 {bad}')
finally:
    for p in spin: p.kill()
