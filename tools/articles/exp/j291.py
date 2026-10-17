import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j291'); R = {}
GR = pathlib.Path(HERE.parent / 'gradle/gradle-9.8.0'); GH = HERE.parent / 'gradle/home'; shutil.rmtree(GH, ignore_errors=True); GH.mkdir()
d = jdir('j291a'); E = jenv('21', GRADLE_USER_HOME=str(GH))
def w(p, c): f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(textwrap.dedent(c).lstrip('\n'))
w('settings.gradle', "rootProject.name = 'inc'\ninclude 'lib', 'app'\n")
w('gradle.properties', 'org.gradle.caching=false\norg.gradle.vfs.watch=false\n')
w('lib/build.gradle', "plugins { id 'java-library' }\njava { sourceCompatibility = 17; targetCompatibility = 17 }\ntasks.withType(JavaCompile) { options.release = 17 }\n")
w('app/build.gradle', "plugins { id 'java' }\ntasks.withType(JavaCompile) { options.release = 17 }\ndependencies { implementation project(':lib') }\n")
LIB = '''public class Lib {
  public int api(int x) { return helper(x) + 1; }
  private int helper(int x) { return x * 2; }
}
'''
w('lib/src/main/java/Lib.java', LIB)
w('app/src/main/java/Main.java', 'public class Main { public static void main(String[] a) { System.out.println(new Lib().api(2)); } }\n')
for i in range(40):
    prev = f'(int) new C{i-1}().f(x)' if i else 'x'
    ref = ' + C0.K' if i in (5, 9) else ''
    w(f'lib/src/main/java/C{i}.java', f'public class C{i} {{ public int f(int x) {{ return x + {i}; }} int g(int x) {{ return {prev}{ref}; }} }}\n' if i else 'public class C0 { public static final int K = 1; public int f(int x) { return x + 0; } int g(int x) { return x; } }\n')
w('build.gradle', '''
def v = providers.gradleProperty('ver').orElse('1')
tasks.register('genVersion') { inputs.property('ver', v); def out = layout.buildDirectory.file('ver.txt'); outputs.file(out); doLast { out.get().asFile.parentFile.mkdirs(); out.get().asFile.text = 'version=' + v.get(); println 'genVersion executed' } }
tasks.register('noOutputs') { doLast { println 'noOutputs executed' } }
tasks.register('undeclaredInput') { def out = layout.buildDirectory.file('copy.txt'); outputs.file(out); doLast { out.get().asFile.parentFile.mkdirs(); out.get().asFile.text = new File(projectDir, 'in.txt').text; println 'undeclaredInput executed' } }
''')
w('in.txt', 'old')
def gr(*args, tmo=600):
    t = time.time(); r = subprocess.run([str(GR / 'bin/gradle'), '--console=plain', '--offline', '--info', '-p', str(d), *args], env=E, capture_output=True, text=True, timeout=tmo, cwd=d); wall = time.time() - t
    txt = tidy(r.stdout + r.stderr); tasks = {}
    for m in re.finditer(r'^> Task (:\S+?)(?: (UP-TO-DATE|NO-SOURCE|FROM-CACHE|SKIPPED))?$', txt, re.M): tasks[m.group(1)] = m.group(2) or 'EXECUTED'
    reasons = {m.group(1): m.group(2).strip() for m in re.finditer(r"Task '(:\S+?)' is not up-to-date because:\n\s*(.+)", txt)}
    return dict(rc=r.returncode, txt=txt, tasks=tasks, reasons=reasons, wall=wall)
def cnt(r): 
    from collections import Counter; c = Counter(r['tasks'].values()); return f"执行 {c['EXECUTED']} 个,UP-TO-DATE {c['UP-TO-DATE']} 个,NO-SOURCE {c['NO-SOURCE']} 个,FROM-CACHE {c['FROM-CACHE']} 个,共 {len(r['tasks'])} 个"
def st(r, *names): return ','.join(f"{n.lstrip(':')}={r['tasks'].get(n, '未出现')}" for n in names)
def inc(r, proj=':lib'):
    m = re.findall(r'Incremental compilation of (\d+) classes completed', r['txt']); full = re.findall(r'Full recompilation is required because ([^\n.]*)', r['txt'])
    return ('增量编译 ' + m[-1] + ' 个类' if m else '没有增量编译日志') + ('(日志:Full recompilation is required because ' + full[-1] + ')' if full else '')
r = gr('--version'); print('gradle:', next(l for l in r['txt'].splitlines() if l.startswith('Gradle')), '|', next(l for l in r['txt'].splitlines() if l.startswith('Launcher JVM')))
print('== 一:第一次构建与第二次构建:任务的结果标签(gradle build,两个子项目 lib / app,java 插件,JDK 21,守护进程已预热)')
gr('help'); r1 = gr('build'); r2 = gr('build')
print(f'  第一次 gradle build:rc={r1["rc"]},{cnt(r1)};耗时 {r1["wall"]:.1f} 秒'); print(f'  第二次 gradle build(没有任何改动):rc={r2["rc"]},{cnt(r2)};耗时 {r2["wall"]:.1f} 秒')
print('  第二次中 lib 与 app 的 compileJava / jar / test:' + st(r2, ':lib:compileJava', ':lib:jar', ':app:compileJava', ':app:jar', ':app:test'))
print('  --info 里 compileJava 的跳过原因:' + '; '.join(l.strip() for l in r2['txt'].splitlines() if "Skipping task ':lib:compileJava'" in l))
w('lib/src/main/java/Lib.java', LIB); os.utime(d / 'lib/src/main/java/Lib.java', (time.time() + 100, time.time() + 100)); r = gr('build')
print('  只 touch 了 Lib.java(内容不变,修改时间推后):' + st(r, ':lib:compileJava', ':lib:jar', ':app:compileJava') + ';' + cnt(r))
print('== 二:改了上游 lib 之后,下游 app 要不要重新编译(编译避免:下游的 classpath 只看 ABI)')
w('lib/src/main/java/Lib.java', LIB + '// trailing comment\n'); r = gr('build')
print('  (a) 只在 Lib.java 末尾加了一行注释:' + st(r, ':lib:compileJava', ':lib:classes', ':lib:jar', ':app:compileJava', ':app:jar'))
w('lib/src/main/java/Lib.java', LIB.replace('x * 2', 'x * 3')); r = gr('build')
print('  (b) 改了 private 方法体(x * 2 → x * 3):' + st(r, ':lib:compileJava', ':lib:jar', ':app:compileJava', ':app:jar'))
w('lib/src/main/java/Lib.java', LIB.replace('x * 2', 'x * 3').replace('private int helper', 'public int api2() { return 0; }\n  private int helper')); r = gr('build')
print('  (c) 新增了 public 方法 api2():' + st(r, ':lib:compileJava', ':lib:jar', ':app:compileJava', ':app:jar') + ';原因:' + r['reasons'].get(':app:compileJava', '(无)'))
print('== 三:任务声明的输入与输出决定它是否会被跳过(自定义任务,--info 里的原因)')
a = gr('genVersion'); b = gr('genVersion'); c = gr('genVersion', '-Pver=2'); (d / 'build/ver.txt').write_text('tampered'); e = gr('genVersion', '-Pver=2'); os.remove(d / 'build/ver.txt'); f = gr('genVersion', '-Pver=2')
for lab, x in (('第一次', a), ('第二次(没有改动)', b), ('-Pver=2', c), ('手工改了输出文件 ver.txt', e), ('删除输出文件 ver.txt', f)): print(f'  genVersion {lab}:{x["tasks"].get(":genVersion")};原因:{x["reasons"].get(":genVersion", "(无,被跳过)")}')
g1 = gr('noOutputs'); g2 = gr('noOutputs'); print(f'  noOutputs(没有声明输出)第一次 {g1["tasks"].get(":noOutputs")}、第二次 {g2["tasks"].get(":noOutputs")};原因:{g2["reasons"].get(":noOutputs", "(无)")}')
u1 = gr('undeclaredInput'); first = (d / 'build/copy.txt').read_text(); w('in.txt', 'new'); u2 = gr('undeclaredInput')
print(f'  undeclaredInput(读了 in.txt 却没声明为输入):第一次 {u1["tasks"].get(":undeclaredInput")},copy.txt = {first!r};把 in.txt 改成 new 之后第二次 {u2["tasks"].get(":undeclaredInput")},copy.txt = {(d / "build/copy.txt").read_text()!r}(in.txt = {(d / "in.txt").read_text()!r},产物过期了)')
print('== 四:增量编译 lib 里的 40 个互相调用的类(每个类 Ci 的 g 方法调用 C(i-1).f;C5 与 C9 引用常量 C0.K)')
def rc_(): gr('clean'); return gr(':lib:compileJava')
r = rc_(); print(f'  干净后的完整编译:{inc(r)};compileJava={r["tasks"].get(":lib:compileJava")}')
w('lib/src/main/java/C20.java', 'public class C20 { public int f(int x) { return x + 2000; } int g(int x) { return (int) new C19().f(x); } }\n'); r = gr(':lib:compileJava')
print(f'  (a) C20.f 的方法体改了(签名不变):{inc(r)}')
w('lib/src/main/java/C0.java', 'public class C0 { public static final int K = 1; public long f(long x) { return x + 0; } int g(int x) { return x; } }\n'); r = gr(':lib:compileJava')
print(f'  (b) C0.f 的签名改成 long f(long):{inc(r)}')
w('lib/src/main/java/C0.java', 'public class C0 { public static final int K = 2; public long f(long x) { return x + 0; } int g(int x) { return x; } }\n'); r = gr(':lib:compileJava')
print(f'  (c) 常量 C0.K 由 1 改成 2(C5、C9 引用):{inc(r)}')
r = gr(':lib:compileJava'); print(f'  (d) 没有再改:compileJava={r["tasks"].get(":lib:compileJava")}')
print('== 五:构建缓存:clean 之后能不能把任务的输出从缓存里取回来(org.gradle.caching=true,本地缓存在隔离的 GRADLE_USER_HOME)')
w('gradle.properties', 'org.gradle.caching=true\norg.gradle.vfs.watch=false\n')
gr('clean'); c1 = gr('build'); gr('clean'); c2 = gr('build')
print(f'  缓存开启后第一次 clean build:{cnt(c1)};耗时 {c1["wall"]:.1f} 秒'); print(f'  clean 之后第二次 build:{cnt(c2)};耗时 {c2["wall"]:.1f} 秒')
print('  第二次的 FROM-CACHE 任务:' + ','.join(k.lstrip(':') for k, v in c2['tasks'].items() if v == 'FROM-CACHE'))
w('lib/src/main/java/C20.java', 'public class C20 { public int f(int x) { return x + 3000; } int g(int x) { return (int) new C19().f(x); } }\n'); gr('clean'); c3 = gr('build')
print(f'  改了 C20 后 clean build:{cnt(c3)};lib:compileJava={c3["tasks"].get(":lib:compileJava")}(输入变了,缓存键变了),app:compileJava={c3["tasks"].get(":app:compileJava")}')
n = sum(1 for p in (GH / 'caches/build-cache-1').glob('*')) if (GH / 'caches/build-cache-1').exists() else 0; print(f'  本地构建缓存里的条目数 {n}')
subprocess.run([str(GR / 'bin/gradle'), '--stop'], env=E, capture_output=True, cwd=d)
