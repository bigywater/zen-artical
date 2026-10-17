import sys, os, re, time, csv, io, glob, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j288'); R = {}
PIT = mcp('org.pitest:pitest-command-line:1.17.1', 'org.pitest:pitest-junit5-plugin:1.2.1'); JUP = mcp('org.junit.jupiter:junit-jupiter:5.9.2')
CONSOLE = mcp('org.junit.platform:junit-platform-console-standalone:1.9.2').split(':')[0]
AGENT = str(JT / 'cov' / 'org.jacoco.agent-0.8.12-runtime.jar'); CLI = str(JT / 'cov' / 'org.jacoco.cli-0.8.12-nodeps.jar')
d = jdir('j288a'); E = jenv('21')
def w(p, c): f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(c)
w('src/Pricing.java', '''public class Pricing {
  public static double price(double base, int qty, boolean member, String country) {
    double p = base * qty;
    if (qty >= 10) p *= 0.9;
    if (member && qty > 1) p -= 5;
    if (country.equals("DE")) p *= 1.19; else if (country.equals("US")) p *= 1.07;
    return Math.round(p * 100) / 100.0;
  }
  public static int tier(int a, int b) { return a > 0 && b > 0 ? 1 : 2; }
  public static int sign(int x) { if (x > 0) return 1; if (x < 0) return -1; return 0; }
}''')
w('src/Dto.java', '''public class Dto { private String name; private int age; private String city; private boolean active; private long id; private String email; private String phone; private String note;
  public String getName() { return name; } public void setName(String n) { name = n; } public int getAge() { return age; } public void setAge(int a) { age = a; } public String getCity() { return city; } public void setCity(String c) { city = c; }
  public boolean isActive() { return active; } public void setActive(boolean a) { active = a; } public long getId() { return id; } public void setId(long i) { id = i; } public String getEmail() { return email; } public void setEmail(String e) { email = e; }
  public String getPhone() { return phone; } public void setPhone(String p) { phone = p; } public String getNote() { return note; } public void setNote(String n) { note = n; } }''')
W = 'import org.junit.jupiter.api.*; import static org.junit.jupiter.api.Assertions.*;\n'
w('test/NoAssertTest.java', W + '''public class NoAssertTest { @Test void runsEverything() { Pricing.price(10, 1, false, "CN"); Pricing.price(10, 10, true, "DE"); Pricing.price(10, 2, true, "US"); Pricing.price(10, 1, true, "FR"); Pricing.tier(1, 1); Pricing.tier(0, 1); Pricing.tier(1, 0); Pricing.sign(5); Pricing.sign(-5); Pricing.sign(0);
    Dto d = new Dto(); d.setName("a"); d.getName(); d.setAge(1); d.getAge(); d.setCity("c"); d.getCity(); d.setActive(true); d.isActive(); d.setId(1); d.getId(); d.setEmail("e"); d.getEmail(); d.setPhone("p"); d.getPhone(); d.setNote("n"); d.getNote(); } }''')
w('test/ThinTest.java', W + '''public class ThinTest { @Test void oneScenarioWithAssert() { assertEquals(10.0, Pricing.price(10, 1, false, "CN")); } @Test void tierOnce() { assertEquals(1, Pricing.tier(1, 1)); } }''')
w('test/RealTest.java', W + '''public class RealTest { @Test void plain() { assertEquals(10.0, Pricing.price(10, 1, false, "CN")); } @Test void bulkDiscount() { assertEquals(90.0, Pricing.price(10, 10, false, "CN")); } @Test void bulkBoundary() { assertEquals(90.0, Pricing.price(10, 10, false, "CN")); assertEquals(90.0, Pricing.price(10, 9, false, "CN")); }
  @Test void memberBoundary() { assertEquals(15.0, Pricing.price(10, 2, true, "CN")); assertEquals(10.0, Pricing.price(10, 1, true, "CN")); } @Test void memberOnly() { assertEquals(20.0, Pricing.price(10, 2, false, "CN")); }
  @Test void tax() { assertEquals(11.9, Pricing.price(10, 1, false, "DE")); assertEquals(10.7, Pricing.price(10, 1, false, "US")); assertEquals(10.0, Pricing.price(10, 1, false, "FR")); }
  @Test void tier() { assertEquals(1, Pricing.tier(1, 1)); assertEquals(2, Pricing.tier(0, 1)); assertEquals(2, Pricing.tier(1, 0)); assertEquals(2, Pricing.tier(0, 0)); } @Test void sign() { assertEquals(1, Pricing.sign(5)); assertEquals(-1, Pricing.sign(-5)); assertEquals(0, Pricing.sign(0)); }
  @Test void dtoOne() { Dto d = new Dto(); d.setName("a"); assertEquals("a", d.getName()); } }''')
cpj = f'{CONSOLE}'
r = subprocess.run([JDKS['21'] + '/bin/javac', '-g', '-d', 'out/classes', *[str(p) for p in (d / 'src').glob('*.java')]], cwd=d, env=E, capture_output=True, text=True)
r2 = subprocess.run([JDKS['21'] + '/bin/javac', '-g', '-d', 'out/test', '-cp', f'out/classes:{JUP}', *[str(p) for p in (d / 'test').glob('*.java')]], cwd=d, env=E, capture_output=True, text=True)
if r.returncode or r2.returncode: print(r.stderr[:1500], r2.stderr[:1500]); sys.exit()
def run_suite(test, cov=True):
    ex = d / f'jacoco_{test}.exec'; ex.unlink(missing_ok=True)
    args = ['java'] + ([f'-javaagent:{AGENT}=destfile={ex},includes=*'] if cov else []) + ['-cp', f'out/classes:out/test:{CONSOLE}', 'org.junit.platform.console.ConsoleLauncher', '--disable-banner', '--disable-ansi-colors', '--details=summary', '--select-class', test]
    H = subprocess.run(args, cwd=d, env=E, capture_output=True, text=True, timeout=200); o = H.stdout + H.stderr
    ok = re.search(r'(\d+) tests successful', o); fl = re.search(r'(\d+) tests failed', o)
    return ex, int(ok.group(1)) if ok else -1, int(fl.group(1)) if fl else -1
def report(ex):
    csvf = d / f'cov_{ex.stem}.csv'; subprocess.run(['java', '-jar', CLI, 'report', str(ex), '--classfiles', str(d / 'out/classes'), '--sourcefiles', str(d / 'src'), '--csv', str(csvf)], cwd=d, env=E, capture_output=True, text=True, timeout=120)
    rows = list(csv.DictReader(open(csvf))); out = {}
    for r in rows: out[r['CLASS']] = {k: int(r[k]) for k in ('INSTRUCTION_MISSED', 'INSTRUCTION_COVERED', 'BRANCH_MISSED', 'BRANCH_COVERED', 'LINE_MISSED', 'LINE_COVERED', 'METHOD_MISSED', 'METHOD_COVERED')}
    return out
def pct(c, m): return 100.0 * c / (c + m) if c + m else 0.0
def pit(test, target='Pricing'):
    rd = d / f'pit_{test}_{target}'; shutil.rmtree(rd, ignore_errors=True)
    cp = ','.join([str(d / 'out/classes'), str(d / 'out/test')] + JUP.split(':'))
    args = ['java', '-cp', PIT, 'org.pitest.mutationtest.commandline.MutationCoverageReport', '--reportDir', str(rd), '--targetClasses', target, '--targetTests', test, '--sourceDirs', str(d / 'src'), '--classPath', cp, '--outputFormats', 'CSV', '--timestampedReports', 'false', '--threads', '2', '--verbose', 'false']
    H = subprocess.run(args, cwd=d, env=E, capture_output=True, text=True, timeout=600)
    f = rd / 'mutations.csv'
    if not f.exists(): return None, (H.stdout + H.stderr)[-600:]
    st = {}; rows = []
    for l in f.read_text().splitlines():
        p = l.split(',')
        if len(p) >= 6: st[p[5]] = st.get(p[5], 0) + 1; rows.append(p)
    return st, rows
print('== 一:三套测试(同一份被测代码 Pricing 与 Dto)的覆盖率(JaCoCo 0.8.12)与变异测试得分(PIT 1.17.1,默认变异算子)')
res = {}
for test, desc in (('NoAssertTest', '没有任何断言的测试(只是调用了所有方法)'), ('ThinTest', '只有 2 个断言的薄测试'), ('RealTest', '为每个分支与边界写了断言的测试')):
    ex, ok, fl = run_suite(test); cov = report(ex); p = cov['Pricing']; dt = cov['Dto']; st, rows = pit(test)
    kill = st.get('KILLED', 0) if st else 0; tot = sum(st.values()) if st else 0; surv = st.get('SURVIVED', 0) if st else 0; nocov = st.get('NO_COVERAGE', 0) if st else 0
    res[test] = (cov, st); print(f'  [{test}:{desc}] 通过 {ok}、失败 {fl}')
    print(f'      Pricing:行覆盖 {pct(p["LINE_COVERED"], p["LINE_MISSED"]):.0f}%({p["LINE_COVERED"]}/{p["LINE_COVERED"] + p["LINE_MISSED"]}),分支覆盖 {pct(p["BRANCH_COVERED"], p["BRANCH_MISSED"]):.0f}%({p["BRANCH_COVERED"]}/{p["BRANCH_COVERED"] + p["BRANCH_MISSED"]}),指令覆盖 {pct(p["INSTRUCTION_COVERED"], p["INSTRUCTION_MISSED"]):.0f}%;Dto:行覆盖 {pct(dt["LINE_COVERED"], dt["LINE_MISSED"]):.0f}%,方法覆盖 {pct(dt["METHOD_COVERED"], dt["METHOD_MISSED"]):.0f}%')
    print(f'      Pricing 的变异测试:共 {tot} 个变异,被杀死 {kill} 个(得分 {100.0 * kill / tot:.0f}%),存活 {surv} 个,没有覆盖 {nocov} 个' if tot else f'      PIT 失败:{rows}')
print('== 二:一行代码 return a > 0 && b > 0 ? 1 : 2;,行覆盖是 100%,分支覆盖要看测试怎么写')
for test in ('ThinTest', 'RealTest'):
    ex = d / f'jacoco_{test}.exec'; xml = d / f'cov_{test}.xml'; subprocess.run(['java', '-jar', CLI, 'report', str(ex), '--classfiles', str(d / 'out/classes'), '--sourcefiles', str(d / 'src'), '--xml', str(xml)], cwd=d, env=E, capture_output=True, text=True)
    t = xml.read_text(); m = re.search(r'<method name="tier".*?</method>', t, re.S); mm = m.group(0)
    lc = re.search(r'<counter type="LINE" missed="(\d+)" covered="(\d+)"', mm); bc = re.search(r'<counter type="BRANCH" missed="(\d+)" covered="(\d+)"', mm)
    print(f'  [{test}] 方法 tier(a, b):行 覆盖 {lc.group(2)} / 遗漏 {lc.group(1)};分支 覆盖 {bc.group(2)} / 遗漏 {bc.group(1)}(a > 0 与 b > 0 各 2 个分支,共 4 个)')
print('== 三:被杀死的变异与存活的变异分别是什么(NoAssertTest 与 RealTest,按变异算子汇总)')
for test in ('NoAssertTest', 'RealTest'):
    st, rows = res[test][1], None
    _, rows = pit(test)
    by = {}
    for p in rows:
        key = p[2].split('.')[-1] if len(p) > 2 else '?'; by.setdefault(p[5], []).append(p[2].split('.')[-1] + ' 第 ' + p[4] + ' 行')
    print(f'  [{test}]' + ';'.join(f' {k} {len(v)} 个' for k, v in sorted(by.items())))
    for k, v in sorted(by.items()):
        if k != 'KILLED': print(f'      {k}:' + ', '.join(v[:6]) + (' …' if len(v) > 6 else ''))
print('== 四:JaCoCo 探针对运行速度的影响:同一个 CPU 型循环,有无 -javaagent')
src = 'public class Spin { static int f(int x) { if (x % 3 == 0) return x / 3; else if (x % 5 == 0) return x * 2; return x + 1; } public static void main(String[] a) { long t0 = System.nanoTime(); long s = 0; for (int r = 0; r < 20; r++) for (int i = 0; i < 20_000_000; i++) s += f(i); System.out.println("RES " + (System.nanoTime() - t0) / 1_000_000 + " " + s); } }'
w('spin/Spin.java', src); subprocess.run([JDKS['21'] + '/bin/javac', '-d', 'out/spin', str(d / 'spin/Spin.java')], cwd=d, env=E, check=True)
def spin(agent):
    ms = []
    for _ in range(5):
        o = subprocess.run(['java'] + ([f'-javaagent:{AGENT}=destfile={d}/spin.exec,includes=Spin'] if agent else []) + ['-cp', 'out/spin', 'Spin'], cwd=d, env=E, capture_output=True, text=True, timeout=300).stdout; ms.append(int(re.search(r'RES (\d+)', o).group(1)))
    ms.sort(); return ms[2]
a0 = spin(False); a1 = spin(True); print(f'  没有 agent 的中位数 {a0} ms;有 JaCoCo agent(includes=Spin)的中位数 {a1} ms,慢 {a1 / a0:.2f} 倍')
