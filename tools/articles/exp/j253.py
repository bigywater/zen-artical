import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j253'); R = {}
G = JDKS['25g']; E = jenv('25g'); NI = G + '/bin/native-image'
d = jdir('j253a')
def w(p, c): (d / p).parent.mkdir(parents=True, exist_ok=True); (d / p).write_text(c)
w('Hello.java', 'public class Hello { public static void main(String[] a) { System.out.println("hello " + a.length); } }\n')
w('Target.java', 'public class Target { public String toString() { return "Target 被反射创建了"; } }\n')
w('Refl.java', 'public class Refl { public static void main(String[] a) throws Exception { Object o = Class.forName(a[0]).getDeclaredConstructor().newInstance(); System.out.println(o); } }\n')
w('InitTime.java', 'public class InitTime { static final long T = System.currentTimeMillis(); static { System.out.println("[静态初始化执行] T = " + T); } public static void main(String[] a) throws Exception { Thread.sleep(1500); System.out.println("main 运行:现在 - T = " + (System.currentTimeMillis() - T) + " ms"); } }\n')
w('Bench.java', r'''import java.util.*; import java.util.stream.*;
public class Bench { static long acc; interface Shape { int area(int k); } record Sq(int s) implements Shape { public int area(int k) { return s * s + k; } } record Rc(int w, int h) implements Shape { public int area(int k) { return w * h + k; } }
  static final List<Integer> LIST = IntStream.range(0, 1000).boxed().collect(Collectors.toList()); static final Shape[] BI = new Shape[1024]; static { for (int i = 0; i < BI.length; i++) BI[i] = i % 2 == 0 ? new Sq(i % 7 + 1) : new Rc(i % 5 + 1, i % 3 + 1); }
  static long work(String name) { switch (name) { case "stream": return LIST.stream().mapToInt(x -> x * x % 7).filter(x -> x > 2).sum(); case "poly2": { long s = 0; for (int i = 0; i < BI.length; i++) s += BI[i].area(i); return s; } default: { HashMap<Integer, Integer> m = new HashMap<>(); for (int i = 0; i < 500; i++) m.merge(i % 97, 1, Integer::sum); return m.size(); } } }
  static double run(String name, long ms) { long end = System.nanoTime() + ms * 1_000_000L, n = 0, s = 0; long t0 = System.nanoTime(); while (System.nanoTime() < end) { for (int i = 0; i < 200; i++) s += work(name); n += 200; } acc += s; return n / ((System.nanoTime() - t0) / 1e6); }
  public static void main(String[] a) { for (String name : new String[]{"stream", "poly2", "hash"}) { for (int w = 0; w < 3; w++) run(name, 300); double[] r = new double[5]; for (int k = 0; k < 5; k++) r[k] = run(name, 300); Arrays.sort(r); System.out.printf("RES %-7s 每毫秒 %.1f 次(中位数)%n", name, r[2]); } } }
''')
rc = subprocess.run([G + '/bin/javac', '-d', 'out', *[str(p.name) for p in d.glob('*.java')]], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def build(name, main, extra=(), out=None):
    t0 = time.perf_counter(); r = subprocess.run([NI, '-cp', 'out', main, '-o', out or name, '--no-fallback', *extra], cwd=d, env=E, capture_output=True, text=True, timeout=900); t = time.perf_counter() - t0
    return r.returncode, t, r.stdout + r.stderr
def runs(cmd, n=20):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); subprocess.run(cmd, cwd=d, env=E, capture_output=True, text=True, timeout=60); ts.append((time.perf_counter() - t0) * 1000)
    ts.sort(); return statistics.median(ts), ts[0], ts[-1]
def rss(cmd):
    r = subprocess.run(['/usr/bin/time', '-l', *cmd], cwd=d, env=E, capture_output=True, text=True, timeout=60); return int(re.search(r'(\d+)\s+maximum resident set size', r.stderr).group(1)) / 1048576
print('== 一:把 Hello(一行 println)编译成原生可执行文件:构建用时与文件大小')
rc, t, o = build('hello', 'Hello'); print(f'  native-image 退出码 {rc},构建用时 {t:.1f} s')
for l in o.splitlines():
    if re.search(r'Produced artifacts|Finished generating|Garbage collector|\[total\]|reachable|Image|code area|image heap', l) and 'Writing' not in l: print('    ' + re.sub(r'/private/tmp/\S+/(py40|scratchpad)/', '<scratch>/', l.strip())[:150])
sz = os.path.getsize(d / 'hello') / 1048576; jd = sum(f.stat().st_size for f in (d / 'out').glob('*.class')) / 1024
print(f'  可执行文件 hello:{sz:.1f} MiB(Hello.class 只有 {os.path.getsize(d / "out" / "Hello.class")} 字节;它把 JDK 里用到的部分、堆镜像与运行时一起编进去了)')
print('  运行 ./hello:' + subprocess.run(['./hello'], cwd=d, capture_output=True, text=True).stdout.strip())
print('== 二:启动时间与内存:./hello 与 java -cp out Hello(同一个 GraalVM JDK 25),各连续运行 20 次')
n = runs(['./hello']); j = runs([G + '/bin/java', '-cp', 'out', 'Hello']); j2 = runs([G + '/bin/java', '-Xshare:auto', '-XX:TieredStopAtLevel=1', '-cp', 'out', 'Hello'])
print(f'  ./hello:中位数 {n[0]:.0f} ms(最快 {n[1]:.0f},最慢 {n[2]:.0f});峰值常驻内存 {rss(["./hello"]):.1f} MiB')
print(f'  java -cp out Hello:中位数 {j[0]:.0f} ms(最快 {j[1]:.0f},最慢 {j[2]:.0f});峰值常驻内存 {rss([G + "/bin/java", "-cp", "out", "Hello"]):.1f} MiB')
print(f'  java -XX:TieredStopAtLevel=1 -cp out Hello:中位数 {j2[0]:.0f} ms(最快 {j2[1]:.0f},最慢 {j2[2]:.0f})')
print('== 三:反射:Class.forName("Target") 在 JVM 与原生镜像里')
r = subprocess.run([G + '/bin/java', '-cp', 'out', 'Refl', 'Target'], cwd=d, env=E, capture_output=True, text=True); print('  JVM:' + r.stdout.strip())
rc, t, o = build('refl', 'Refl'); print(f'  构建 Refl(没有任何反射配置)退出码 {rc},用时 {t:.1f} s')
r = subprocess.run(['./refl', 'Target'], cwd=d, capture_output=True, text=True); print('  ./refl Target:' + (r.stdout + r.stderr).strip().splitlines()[0][:150] + (' …' if len((r.stdout + r.stderr).strip().splitlines()) > 1 else ''))
cfg = d / 'cfg'; cfg.mkdir(exist_ok=True)
r = subprocess.run([G + '/bin/java', f'-agentlib:native-image-agent=config-output-dir={cfg}', '-cp', 'out', 'Refl', 'Target'], cwd=d, env=E, capture_output=True, text=True); print('  用 native-image-agent 在 JVM 上跑一遍:' + r.stdout.strip() + ';生成的文件 ' + str(sorted(p.name for p in cfg.iterdir())))
rj = (cfg / 'reachability-metadata.json'); txt = rj.read_text() if rj.exists() else (cfg / 'reflect-config.json').read_text(); print('  生成的配置里与 Target 相关的片段:' + re.sub(r'\s+', ' ', txt)[:260])
rc, t, o = build('refl2', 'Refl', extra=[f'-H:ConfigurationFileDirectories={cfg}']); print(f'  带上生成的配置重新构建 退出码 {rc},用时 {t:.1f} s')
r = subprocess.run(['./refl2', 'Target'], cwd=d, capture_output=True, text=True); print('  ./refl2 Target:' + (r.stdout + r.stderr).strip().splitlines()[0][:150])
r = subprocess.run(['./refl2', 'Hello'], cwd=d, capture_output=True, text=True); print('  ./refl2 Hello(没有登记的类):' + (r.stdout + r.stderr).strip().splitlines()[0][:150])
print('== 四:类初始化发生在构建时还是运行时')
rc, t, o = build('init_rt', 'InitTime'); rc2, t2, o2 = build('init_bt', 'InitTime', extra=['--initialize-at-build-time=InitTime'])
print('  默认构建(应用类默认在运行时初始化)的构建输出里' + ('有' if '[静态初始化执行]' in o else '没有') + '静态初始化的打印;--initialize-at-build-time=InitTime 的构建输出里' + ('有' if '[静态初始化执行]' in o2 else '没有') + ':' + ' '.join(l.strip() for l in o2.splitlines() if '[静态初始化执行]' in l))
for nm in ('init_rt', 'init_bt'):
    r = subprocess.run([f'./{nm}'], cwd=d, capture_output=True, text=True); print(f'  ./{nm} 运行:' + ' | '.join(r.stdout.strip().splitlines()))
time.sleep(2); r = subprocess.run(['./init_bt'], cwd=d, capture_output=True, text=True); print('  过 2 秒再运行 ./init_bt:' + ' | '.join(r.stdout.strip().splitlines()) + '(T 与构建时相同,所以“现在 - T”越来越大)')
print('== 五:峰值吞吐:同一个 Bench(stream、poly2、hash,每个预热 3 轮 + 测 5 轮,每轮 300 ms)在原生镜像与 JVM(Graal JIT 与 C2)上')
rc, t, o = build('bench', 'Bench'); print(f'  构建 Bench 用时 {t:.1f} s,文件 {os.path.getsize(d / "bench") / 1048576:.1f} MiB')
for lab, cmd in (('原生镜像', ['./bench']), ('JVM + Graal JIT', [G + '/bin/java', '-cp', 'out', 'Bench']), ('JVM + C2', [G + '/bin/java', '-XX:-UseJVMCICompiler', '-cp', 'out', 'Bench'])):
    r = subprocess.run(cmd, cwd=d, env=E, capture_output=True, text=True, timeout=300); print(f'  [{lab}] ' + ';  '.join(re.sub(r'\s+', ' ', l[4:]) for l in r.stdout.splitlines() if l.startswith('RES ')))
