import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j285'); R = {}
JU = mcp('org.junit.platform:junit-platform-console-standalone:1.11.3').split(':')[0]
d = jdir('j285a'); E = jenv('21')
def w(p, c): f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(c)
W = 'import org.junit.jupiter.api.*; import org.junit.jupiter.api.extension.*; import static org.junit.jupiter.api.Assertions.*; import java.util.*; import java.util.concurrent.atomic.*;\n'
w('H.java', 'import java.util.concurrent.atomic.*; class H { static final AtomicInteger inst = new AtomicInteger(); static void log(String s) { System.out.println("EV " + s); } }\n')
w('Shop.java', W + '''public class Shop { final int id = H.inst.incrementAndGet(); Shop() { H.log("构造 Shop #" + id); }
  @BeforeEach void shopSetup() { H.log("  @BeforeEach Shop(外层)#" + id); } @AfterEach void shopTeardown() { H.log("  @AfterEach  Shop(外层)#" + id); }
  @Test void shopTest() { H.log("    测试 shopTest(外层)#" + id); }
  @Nested class WithCart { final int cid = H.inst.incrementAndGet(); WithCart() { H.log("构造 WithCart #" + cid + "(外层 Shop #" + Shop.this.id + ")"); }
    @BeforeEach void cartSetup() { H.log("  @BeforeEach WithCart(第 2 层)#" + cid); } @AfterEach void cartTeardown() { H.log("  @AfterEach  WithCart(第 2 层)#" + cid); }
    @Test void cartTest() { H.log("    测试 cartTest(第 2 层)#" + cid); }
    @Nested class WithItem { final int iid = H.inst.incrementAndGet(); WithItem() { H.log("构造 WithItem #" + iid + "(外层 WithCart #" + WithCart.this.cid + ",最外层 Shop #" + Shop.this.id + ")"); }
      @BeforeEach void itemSetup() { H.log("  @BeforeEach WithItem(第 3 层)#" + iid); } @AfterEach void itemTeardown() { H.log("  @AfterEach  WithItem(第 3 层)#" + iid); }
      @Test void itemTest1() { H.log("    测试 itemTest1(第 3 层)#" + iid); } @Test void itemTest2() { H.log("    测试 itemTest2(第 3 层)#" + iid); } } }
  @Nested @DisplayName("空购物车") class EmptyCart { @Test @DisplayName("总价为 0") void total() { H.log("    测试 EmptyCart.total"); } } }''')
w('WithStatic.java', W + '''public class WithStatic { @Test void outerTest() { H.log("    测试 WithStatic.outerTest"); }
  static class NotNested { @Test void staticNestedTest() { H.log("    测试 WithStatic.NotNested.staticNestedTest(没有 @Nested 的静态嵌套类)"); } }
  @Nested class IsNested { @Test void nestedTest() { H.log("    测试 WithStatic.IsNested.nestedTest"); } } }''')
w('BeforeAllNested.java', W + '''public class BeforeAllNested { @BeforeAll static void outerAll() { H.log("@BeforeAll(外层,static)"); } @AfterAll static void outerAllAfter() { H.log("@AfterAll(外层,static)"); }
  @Test void outerTest() { H.log("    测试 outerTest"); }
  @Nested class StaticAll { @BeforeAll static void nestedAll() { H.log("@BeforeAll(嵌套类里的 static 方法)"); } @Test void t1() { H.log("    测试 StaticAll.t1"); } @Test void t2() { H.log("    测试 StaticAll.t2"); } }
  @Nested @TestInstance(TestInstance.Lifecycle.PER_CLASS) class PerClassAll { int counter = 0; @BeforeAll void nestedAll() { H.log("@BeforeAll(PER_CLASS 嵌套类里的实例方法)"); } @Test void t1() { counter++; H.log("    测试 PerClassAll.t1 counter=" + counter); } @Test void t2() { counter++; H.log("    测试 PerClassAll.t2 counter=" + counter); } } }''')
w('ExtOuter.java', W + '''public class ExtOuter { static class Counter implements BeforeEachCallback, AfterEachCallback { static final AtomicInteger before = new AtomicInteger(), after = new AtomicInteger(); public void beforeEach(ExtensionContext c) { before.incrementAndGet(); H.log("  扩展 beforeEach:" + c.getTestClass().get().getSimpleName() + "." + c.getDisplayName() + "(第 " + before + " 次)"); } public void afterEach(ExtensionContext c) { after.incrementAndGet(); } }
  @ExtendWith(Counter.class) @Tag("slow") @Nested class WithExt { @Test void a() { H.log("    测试 WithExt.a"); } @Nested class Deeper { @Test void b() { H.log("    测试 WithExt.Deeper.b(继承了外层的 @ExtendWith 与 @Tag)"); } } }
  @Nested class NoExt { @Test void c() { H.log("    测试 NoExt.c(没有扩展)"); } }
  @Nested @Disabled("整个嵌套类禁用") class Off { @Test void d() { H.log("    测试 Off.d(不应该运行)"); } }
  @Test void plain() { H.log("    测试 ExtOuter.plain"); } }''')
w('DisabledOuter.java', W + '''@Disabled("外层被禁用") public class DisabledOuter { @Test void o() { H.log("不应该运行 o"); } @Nested class In { @Test void i() { H.log("不应该运行 i"); } } }''')
r = subprocess.run([JDKS['21'] + '/bin/javac', '-d', 'out', '-cp', JU, *[str(p) for p in d.glob('*.java')]], cwd=d, env=E, capture_output=True, text=True)
if r.returncode: print(r.stderr[:2500]); sys.exit()
def run(sel, label, extra=(), tree=False):
    args = ['java', '-cp', f'out:{JU}', 'org.junit.platform.console.ConsoleLauncher', 'execute', '--disable-banner', '--disable-ansi-colors', '--details=' + ('tree' if tree else 'summary')] + list(sel) + list(extra)
    H = subprocess.run(args, cwd=d, env=E, capture_output=True, text=True, timeout=200); o = H.stdout + H.stderr
    ev = [re.sub(r'^EV ', '', l) for l in o.splitlines() if l.startswith('EV ')]
    summ = ' | '.join(re.sub(r'\s+', ' ', l.strip().lstrip('[').strip().rstrip(']').strip()) for l in o.splitlines() if re.search(r'\d+ tests (found|successful|failed|skipped)', l))
    print(f'  [{label}]'); [print('      ' + l) for l in ev]; print('      → ' + summ); return o, ev
print('== 一:三层 @Nested(Shop → WithCart → WithItem)的生命周期:构造、@BeforeEach、@AfterEach 的顺序')
o, ev = run(['--select-class', 'Shop'], 'Shop 整个类')
n_before = sum(1 for l in ev if '@BeforeEach' in l); n_tests = sum(1 for l in ev if '测试 ' in l); n_ctor = sum(1 for l in ev if l.startswith('构造'))
print(f'  汇总:共 {n_tests} 个测试方法被执行;@BeforeEach 总共执行 {n_before} 次;构造函数总共被调用 {n_ctor} 次;外层 Shop 被构造 {sum(1 for l in ev if l.startswith("构造 Shop"))} 次')
print('== 二:树形输出里的层次与 @DisplayName,以及如何单独运行一个嵌套类')
o, ev = run(['--select-class', 'Shop'], 'tree 输出', tree=True)
tree_lines = [l for l in o.splitlines() if re.search(r'[├└│]', l) and 'EV' not in l]
for l in tree_lines[:20]: print('        ' + l)
print('  想只运行嵌套类里的一部分,控制台启动器的几种选择方式的结果:')
o, ev = run(['--select-class', 'Shop$WithCart$WithItem'], '--select-class Shop$WithCart$WithItem(直接选择最内层类)')
o, ev = run(['--select-method', 'Shop$WithCart#cartTest'], '--select-method Shop$WithCart#cartTest')
o, ev = run(['--select-class', 'Shop', '--include-classname', '.*WithItem'], '--select-class Shop --include-classname \'.*WithItem\'')
o, ev = run(['--select-class', 'Shop', '--include-tag', 'nonexistent'], '--select-class Shop --include-tag nonexistent(对照:标签过滤)')
print('== 三:静态嵌套类(没有 @Nested)不会被当成外层的一部分')
o, ev = run(['--select-class', 'WithStatic'], '--select-class WithStatic')
o2, ev2 = run(['--scan-class-path', 'out', '--include-classname', 'WithStatic.*'], '--scan-class-path 且匹配 WithStatic.*')
print('== 四:@BeforeAll 在嵌套类里')
o, ev = run(['--select-class', 'BeforeAllNested'], 'BeforeAllNested')
print('== 五:扩展、标签与 @Disabled 的继承')
o, ev = run(['--select-class', 'ExtOuter'], 'ExtOuter 全部')
o, ev = run(['--select-class', 'ExtOuter', '--include-tag', 'slow'], 'ExtOuter,--include-tag slow')
o, ev = run(['--select-class', 'DisabledOuter'], 'DisabledOuter(外层 @Disabled,里面有 @Nested)')
