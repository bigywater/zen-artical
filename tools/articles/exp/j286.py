import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j286'); R = {}
JU = mcp('org.junit.platform:junit-platform-console-standalone:1.11.3').split(':')[0]
d = jdir('j286a'); E = jenv('21'); NCPU = os.cpu_count()
def w(p, c): f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(c)
W = 'import org.junit.jupiter.api.*; import org.junit.jupiter.api.parallel.*; import java.util.*; import java.util.concurrent.*;\n'
w('H.java', 'import java.util.*; import java.util.concurrent.*; class H { static final Set<String> threads = ConcurrentHashMap.newKeySet(); static void io(long ms) { threads.add(Thread.currentThread().getName().replaceAll("ForkJoinPool-\\\\d+-", "FJP-")); try { Thread.sleep(ms); } catch (InterruptedException e) { } } static void cpu(long it) { threads.add(Thread.currentThread().getName().replaceAll("ForkJoinPool-\\\\d+-", "FJP-")); long x = 88172645463325252L; for (long i = 0; i < it; i++) { x ^= x << 13; x ^= x >>> 7; x ^= x << 17; } if (x == 1) System.out.print(""); } }\n')
for i in range(1, 5): w(f'Io{i}.java', W + f'public class Io{i} {{ @Test void a() {{ H.io(300); }} @Test void b() {{ H.io(300); }} @Test void c() {{ H.io(300); }} @Test void dd() {{ H.io(300); }} }}')
w('Calib.java', 'public class Calib { public static void main(String[] a) { long best = Long.MAX_VALUE; for (int r = 0; r < 8; r++) { long t0 = System.nanoTime(); long x = 88172645463325252L; for (long i = 0; i < 100_000_000L; i++) { x ^= x << 13; x ^= x >>> 7; x ^= x << 17; } best = Math.min(best, System.nanoTime() - t0); if (x == 1) System.out.print(\"\"); } System.out.println(best / 1_000_000); } }')
subprocess.run([JDKS['21'] + '/bin/javac', '-d', 'calib', str(d / 'Calib.java')], cwd=d, env=E, check=True); (d / 'Calib.java').unlink()
ms100 = int(subprocess.run(['java', '-cp', 'calib', 'Calib'], cwd=d, env=E, capture_output=True, text=True).stdout.strip().splitlines()[-1]); ITER = int(100_000_000 * 300 / ms100)
for i in range(1, 5): w(f'Cpu{i}.java', W + f'public class Cpu{i} {{ @Test void a() {{ H.cpu({ITER}L); }} @Test void b() {{ H.cpu({ITER}L); }} @Test void c() {{ H.cpu({ITER}L); }} @Test void dd() {{ H.cpu({ITER}L); }} }}')
for i in range(1, 5): w(f'Locked{i}.java', W + f'public class Locked{i} {{ @Test @ResourceLock("db") void a() {{ H.io(300); }} @Test @ResourceLock("db") void b() {{ H.io(300); }} @Test @ResourceLock("db") void c() {{ H.io(300); }} @Test @ResourceLock("db") void dd() {{ H.io(300); }} }}')
w('Iso.java', W + '@Isolated public class Iso { @Test void only() { H.io(300); } }')
w('SameThreadClass.java', W + '@Execution(ExecutionMode.SAME_THREAD) public class SameThreadClass { @Test void a() { H.io(300); } @Test void b() { H.io(300); } @Test void c() { H.io(300); } @Test void dd() { H.io(300); } }')
w('Report.java', 'import org.junit.platform.launcher.*; import org.junit.platform.launcher.listeners.*; public class Report { }')
r = subprocess.run([JDKS['21'] + '/bin/javac', '-d', 'out', '-cp', JU, *[str(p) for p in d.glob('*.java')]], cwd=d, env=E, capture_output=True, text=True)
if r.returncode: print(r.stderr[:2500]); sys.exit()
def run(classes, cfg, label, show_threads=False):
    args = ['java', '-cp', f'out:{JU}', 'org.junit.platform.console.ConsoleLauncher', 'execute', '--disable-banner', '--disable-ansi-colors', '--details=summary']
    for c in classes: args += ['--select-class', c]
    for k in cfg: args += ['--config', k]
    # 线程名通过一个 shutdown hook 输出
    t0 = time.perf_counter(); H = subprocess.run(args, cwd=d, env=E, capture_output=True, text=True, timeout=300); wall = time.perf_counter() - t0; o = H.stdout + H.stderr
    m = re.search(r'Test run finished after (\d+) ms', o); ms = int(m.group(1)) if m else -1
    ok = re.search(r'(\d+) tests successful', o); n = int(ok.group(1)) if ok else -1
    print(f'  [{label}] 测试 {n} 个,JUnit 报告的运行时间 {ms} ms'); return ms
P = 'junit.jupiter.execution.parallel.'
IO = [f'Io{i}' for i in range(1, 5)]; CPU = [f'Cpu{i}' for i in range(1, 5)]
print(f'== 一:16 个各 sleep 300 ms 的测试(4 个类 × 4 个方法,I/O 型),本机 {NCPU} 个逻辑 CPU:并行配置对总时间的影响')
base = run(IO, [], '默认(没有启用并行)')
a = run(IO, [P + 'enabled=true', P + 'mode.default=concurrent'], 'enabled=true + mode.default=concurrent(mode.classes.default 没设,继承 mode.default),动态并行度')
b = run(IO, [P + 'enabled=true', P + 'mode.default=concurrent', P + 'mode.classes.default=concurrent'], 'enabled=true + 显式写出两者都是 concurrent(动态并行度,factor = 1.0)')
c = run(IO, [P + 'enabled=true', P + 'mode.default=same_thread', P + 'mode.classes.default=concurrent'], '只有类并发:mode.default=same_thread,mode.classes.default=concurrent')
d1 = run(IO, [P + 'enabled=true', P + 'mode.default=concurrent', P + 'mode.classes.default=concurrent', P + 'config.strategy=fixed', P + 'config.fixed.parallelism=1'], 'fixed 并行度 1')
for par in (2, 4, 8, 16):
    run(IO, [P + 'enabled=true', P + 'mode.default=concurrent', P + 'mode.classes.default=concurrent', P + 'config.strategy=fixed', P + 'config.fixed.parallelism=' + str(par)], f'fixed 并行度 {par}')
print(f'== 二:CPU 型测试(16 个各做固定量的计算,单核约 300 ms:1 亿次计算 {ms100} ms,取 {ITER} 次)的并行度不能超过核数')
run(CPU, [], '默认(串行)')
for par in (4, NCPU, 16):
    run(CPU, [P + 'enabled=true', P + 'mode.default=concurrent', P + 'mode.classes.default=concurrent', P + 'config.strategy=fixed', P + 'config.fixed.parallelism=' + str(par)], f'fixed 并行度 {par}')
print('== 三:@ResourceLock、@Isolated 与 @Execution(SAME_THREAD) 会把并行变回串行')
PAR = [P + 'enabled=true', P + 'mode.default=concurrent', P + 'mode.classes.default=concurrent', P + 'config.strategy=fixed', P + 'config.fixed.parallelism=16']
run(IO, PAR, '对照:16 个 I/O 测试,fixed 并行度 16')
run([f'Locked{i}' for i in range(1, 5)], PAR, '16 个测试都加 @ResourceLock("db"),fixed 并行度 16')
run(IO + ['Iso'], PAR, '4 个并发的类 + 1 个 @Isolated 的类(只有 1 个 300 ms 的测试),fixed 并行度 16')
run(['SameThreadClass'], PAR, 'SameThreadClass:@Execution(SAME_THREAD) 的类,4 个测试,fixed 并行度 16')
run(IO + ['SameThreadClass'], PAR, '4 个并发的类 + 1 个 SAME_THREAD 的类')
print('== 四:并行度用到了多少个线程')
tmain = d / 'Threads.java'; tmain.write_text('import org.junit.platform.launcher.*; import org.junit.platform.launcher.core.*; import org.junit.platform.launcher.listeners.*; import org.junit.platform.engine.discovery.*; import java.util.*; public class Threads { public static void main(String[] a) { String[] cls = a[0].split(","); LauncherDiscoveryRequestBuilder b = LauncherDiscoveryRequestBuilder.request(); for (String c : cls) b.selectors(DiscoverySelectors.selectClass(c)); for (int i = 1; i < a.length; i++) { String[] kv = a[i].split("=", 2); b.configurationParameter(kv[0], kv[1]); } Launcher l = LauncherFactory.create(); SummaryGeneratingListener s = new SummaryGeneratingListener(); l.execute(b.build(), s); System.out.println("RES 完成 " + s.getSummary().getTestsSucceededCount() + " 个测试,实际用到的线程数 " + H.threads.size() + ":" + new TreeSet<>(H.threads).stream().limit(6).toList() + (H.threads.size() > 6 ? "…" : "")); } }')
r = subprocess.run([JDKS['21'] + '/bin/javac', '-d', 'out', '-cp', f'out:{JU}', str(tmain)], cwd=d, env=E, capture_output=True, text=True)
if r.returncode: print(r.stderr[:1500]); sys.exit()
for lab, cfg in (('默认(串行)', []), ('fixed 并行度 4', [P + 'enabled=true', P + 'mode.default=concurrent', P + 'mode.classes.default=concurrent', P + 'config.strategy=fixed', P + 'config.fixed.parallelism=4']), ('fixed 并行度 16', PAR)):
    x = subprocess.run(['java', '-cp', f'out:{JU}', 'Threads', ','.join(IO), *cfg], cwd=d, env=E, capture_output=True, text=True, timeout=120); print(f'  [{lab}] ' + ' '.join(l[4:] for l in (x.stdout + x.stderr).splitlines() if l.startswith('RES ')))
