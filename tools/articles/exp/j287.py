import sys, os, re, time, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j287'); R = {}
JU = mcp('org.junit.platform:junit-platform-console-standalone:1.11.3').split(':')[0]
d = jdir('j287a'); E = jenv('21'); NCPU = os.cpu_count()
def w(p, c): f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(c)
w('Flaky.java', r'''
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Flaky {
  // 类型 1:并发:检查再执行的竞争(两个线程同时第一次取单例)
  static volatile Object inst; static final AtomicInteger created = new AtomicInteger();
  static boolean race() throws Exception { inst = null; created.set(0); CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(2);
    Runnable r = () -> { try { go.await(); } catch (InterruptedException e) { } if (inst == null) { Object o = new Object(); created.incrementAndGet(); inst = o; } done.countDown(); };
    Thread a = new Thread(r), b = new Thread(r); a.start(); b.start(); go.countDown(); done.await(); return created.get() == 1; }
  // 类型 2:时序:断言“一个约 15 ms 的计算在 40 ms 内完成”
  static long ITER = Long.getLong("iter", 30_000_000L); static long sink;
  static boolean timing() { long t0 = System.nanoTime(); long x = 88172645463325252L; for (long i = 0; i < ITER; i++) { x ^= x << 13; x ^= x >>> 7; x ^= x << 17; } sink += x; return (System.nanoTime() - t0) < 40_000_000L; }
  // 类型 3:顺序:共享静态状态,与执行顺序有关(随机顺序下 1/6 概率失败)
  static int shared; static boolean order(Random r) { List<Integer> order = new ArrayList<>(List.of(0, 1, 2)); Collections.shuffle(order, r); int p0 = order.indexOf(0), p1 = order.indexOf(1), p2 = order.indexOf(2); return !(p0 < p2 && p2 < p1); }
  public static void main(String[] a) throws Exception {
    String kind = a[0]; int N = Integer.parseInt(a[1]); int fail = 0; Random r = new Random(1); long t0 = System.nanoTime();
    if (kind.equals("calib")) { long best = Long.MAX_VALUE; for (int i = 0; i < 30; i++) { long s0 = System.nanoTime(); long x = 88172645463325252L; for (long k = 0; k < ITER; k++) { x ^= x << 13; x ^= x >>> 7; x ^= x << 17; } sink += x; best = Math.min(best, System.nanoTime() - s0); } System.out.println("RES calib " + best / 1000); System.exit(0); }
    if (kind.equals("retry")) { int[] at = new int[4]; int firstFail = 0; for (int i = 0; i < N; i++) { int k = 0; boolean ok = false; while (k < 3 && !ok) { k++; ok = race(); } if (ok) at[k]++; else at[0]++; if (k > 1 || !ok) firstFail++; } System.out.println("RES retry " + N + " 次测试运行(每次最多 3 次尝试):第 1 次就通过 " + at[1] + ",第 2 次通过 " + at[2] + ",第 3 次通过 " + at[3] + ",3 次都失败 " + at[0] + ";第一次尝试失败的有 " + firstFail + " 次(被重试“治好”的有 " + (firstFail - at[0]) + " 次)"); System.exit(0); }
    for (int i = 0; i < N; i++) { boolean ok = switch (kind) { case "race" -> race(); case "timing" -> timing(); default -> order(r); }; if (!ok) fail++; }
    System.out.println("RES " + kind + " " + N + " 次,失败 " + fail + " 次(" + String.format("%.2f", 100.0 * fail / N) + "%),用时 " + (System.nanoTime() - t0) / 1_000_000 + " ms");
    System.exit(0);
  }
}''')
w('RetryTest.java', r'''
import org.junit.jupiter.api.extension.*; import org.junit.jupiter.api.TestTemplate; import org.opentest4j.TestAbortedException; import java.lang.annotation.*; import java.util.*; import java.util.stream.*;
@Target(ElementType.METHOD) @Retention(RetentionPolicy.RUNTIME) @TestTemplate @ExtendWith(RetryTest.Ext.class) public @interface RetryTest { int value() default 3;
  class Ext implements TestTemplateInvocationContextProvider, TestExecutionExceptionHandler, AfterTestExecutionCallback { static final Map<String, Integer> attempts = new HashMap<>();
    public boolean supportsTestTemplate(ExtensionContext c) { return true; }
    public Stream<TestTemplateInvocationContext> provideTestTemplateInvocationContexts(ExtensionContext c) { int max = c.getRequiredTestMethod().getAnnotation(RetryTest.class).value(); return IntStream.rangeClosed(1, max).mapToObj(i -> new TestTemplateInvocationContext() { public String getDisplayName(int idx) { return "尝试 " + i + "/" + max; } public List<Extension> getAdditionalExtensions() { return List.of(new Gate(i, max)); } }); }
    public void handleTestExecutionException(ExtensionContext c, Throwable t) throws Throwable { throw t; } public void afterTestExecution(ExtensionContext c) { }
    static class Gate implements TestExecutionExceptionHandler, ExecutionCondition { final int i, max; static final Set<String> passed = new HashSet<>(); Gate(int i, int max) { this.i = i; this.max = max; }
      public ConditionEvaluationResult evaluateExecutionCondition(ExtensionContext c) { return passed.contains(c.getRequiredTestMethod().toString()) ? ConditionEvaluationResult.disabled("前一次尝试已经通过") : ConditionEvaluationResult.enabled("尝试"); }
      public void handleTestExecutionException(ExtensionContext c, Throwable t) throws Throwable { if (i < max) throw new TestAbortedException("第 " + i + " 次尝试失败,重试:" + t.getMessage(), t); throw t; } } } }''')
w('Suite.java', r'''
import org.junit.jupiter.api.*; import static org.junit.jupiter.api.Assertions.*; import java.util.concurrent.atomic.*;
public class Suite { static final AtomicInteger calls = new AtomicInteger();
  @Test void stable() { assertTrue(true); }
  @RetryTest(3) void flakyUntilThird() { int n = calls.incrementAndGet(); System.out.println("EV flakyUntilThird 第 " + n + " 次调用"); assertTrue(n >= 3, "前两次失败"); }
  @RetryTest(3) void alwaysFails() { System.out.println("EV alwaysFails 被调用"); fail("真的有 bug,总是失败"); }
  @Test @Tag("quarantine") void quarantinedFlaky() { fail("已隔离的不稳定测试"); }
  @Test @Tag("quarantine") void quarantinedOk() { }
  @Test void realBug() { fail("没有被隔离的真实失败"); } }''')
r = subprocess.run([JDKS['21'] + '/bin/javac', '-d', 'out', '-cp', JU, *[str(p) for p in d.glob('*.java')]], cwd=d, env=E, capture_output=True, text=True)
if r.returncode: print(r.stderr[:3500]); sys.exit()
def flaky(kind, n, jopts=(), load=0):
    spin = [subprocess.Popen(['python3', '-c', 'while True: pass']) for _ in range(load)]
    try:
        time.sleep(0.6 if load else 0); out = subprocess.run(['java', *jopts, '-cp', 'out', 'Flaky', kind, str(n)], cwd=d, env=E, capture_output=True, text=True, timeout=300).stdout
    finally:
        for p in spin: p.kill()
    m = re.search(r'RES (.*)', out); return m.group(1) if m else out[:200]
print('== 一:三种不稳定的来源:失败概率与环境有关(同一段代码,各重复 N 次,空闲机器与满载机器)')
# 先校准时序测试:把计算调到约 15 ms
cal = subprocess.run(['java', '-Diter=30000000', '-cp', 'out', 'Flaky', 'calib', '1'], cwd=d, env=E, capture_output=True, text=True).stdout; us = int(re.search(r'calib (\d+)', cal).group(1)); ITER = int(30_000_000 * 15000 / us); print(f'  (校准:3000 万次计算最快 {us / 1000:.1f} ms,取 {ITER} 次约 15 ms)')
print('  类型 1 并发(两个线程同时第一次创建单例,检查再创建,没有同步):')
print('    空闲:' + flaky('race', 4000)); print(f'    满载({NCPU * 3} 个空转进程):' + flaky('race', 4000, load=NCPU * 3)); print('    -XX:ActiveProcessorCount=1:' + flaky('race', 4000, ('-XX:ActiveProcessorCount=1',)))
print('  类型 2 时序(断言“一个约 15 ms 的计算在 40 ms 内完成”):')
print('    空闲:' + flaky('timing', 300, (f'-Diter={ITER}',))); print(f'    满载({NCPU * 3} 个空转进程):' + flaky('timing', 300, (f'-Diter={ITER}',), load=NCPU * 3))
print('  类型 3 顺序(共享静态状态,随机顺序;与负载无关):')
print('    空闲:' + flaky('order', 4000)); print(f'    满载({NCPU * 3} 个空转进程):' + flaky('order', 4000, load=NCPU * 3))
print('== 二:重试会把不稳定变成“偶尔通过”:同一个竞争测试(单例竞争,约 8% 失败),最多重试 3 次,2000 次测试运行')
print('  ' + flaky('retry', 2000))
print('== 三:用 JUnit 实现的重试扩展(@RetryTest(3),失败的尝试被标为 aborted):一个“第三次才通过”的测试、一个真有 bug 的测试')
def junit(extra, label):
    args = ['java', '-cp', f'out:{JU}', 'org.junit.platform.console.ConsoleLauncher', 'execute', '--disable-banner', '--disable-ansi-colors', '--details=tree', '--select-class', 'Suite'] + list(extra)
    o = subprocess.run(args, cwd=d, env=E, capture_output=True, text=True, timeout=200); txt = o.stdout + o.stderr
    print(f'  [{label}] 退出码 {o.returncode}')
    for l in txt.splitlines():
        if re.search(r'[├└│]', l) and 'JUnit' not in l: print('      ' + l.strip()[:150])
        elif 'EV ' in l: print('      ' + l.strip())
    summ = ' | '.join(re.sub(r'\s+', ' ', l.strip().lstrip('[').strip().rstrip(']').strip()) for l in txt.splitlines() if re.search(r'\d+ tests (found|successful|failed|aborted|skipped)', l)); print('      → ' + summ)
junit([], '全部运行')
print('== 四:隔离(quarantine):用 @Tag("quarantine") 把不稳定的测试从“合并门禁”里拿出来,单独的任务继续运行并记录')
junit(['--exclude-tag', 'quarantine'], '门禁任务:--exclude-tag quarantine')
junit(['--include-tag', 'quarantine'], '隔离任务:--include-tag quarantine')
