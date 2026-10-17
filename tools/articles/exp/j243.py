import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j243'); R = {}
AU = mcp('com.tngtech.archunit:archunit:1.3.0')
d = jdir('j243a'); E = jenv('21')
def w(p, c): f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(c)
w('provider/module-info.java', 'module provider { exports api; }\n')
w('provider/api/Greeter.java', 'package api;\npublic class Greeter { public static String hello() { return "hello " + impl.Secret.name(); } }\n')
w('provider/impl/Secret.java', 'package impl;\npublic class Secret { private String hidden = "h-" + 42; public Secret() {} public static String name() { return "world"; } public static String token() { return "s3cret"; } }\n')
w('consumer/module-info.java', 'module consumer { requires provider; }\n')
w('consumer/app/Good.java', 'package app;\npublic class Good { public static void main(String[] a) { System.out.println(api.Greeter.hello()); } }\n')
w('consumer/app/Bad.java', 'package app;\npublic class Bad { public static void main(String[] a) { System.out.println("取到:" + impl.Secret.token()); } }\n')
w('consumer/app/Reflect.java', '''package app;
import java.lang.reflect.*;
public class Reflect { public static void main(String[] a) throws Exception {
  Class<?> c = Class.forName("impl.Secret");
  try { System.out.println("反射调用公有静态方法 token():" + c.getMethod("token").invoke(null)); } catch (Throwable t) { System.out.println("反射调用公有静态方法 token() 失败:" + t.getClass().getSimpleName() + ": " + t.getMessage().replaceAll("\\\\s+", " ")); }
  try { Field f = c.getDeclaredField("hidden"); f.setAccessible(true); System.out.println("setAccessible 读私有字段 hidden:" + f.get(c.getConstructor().newInstance())); } catch (Throwable t) { System.out.println("setAccessible 读私有字段 hidden 失败:" + t.getClass().getSimpleName() + ": " + t.getMessage().replaceAll("\\\\s+", " ")); }
} }
''')
def sh(args, cwd=d, label=None, show=True, env=None):
    r = subprocess.run(args, cwd=cwd, env=env or E, capture_output=True, text=True, timeout=120); o = '\n'.join(l for l in tidy(r.stdout + r.stderr).splitlines() if not l.startswith('SLF4J'))
    if show: print(f'  $ {label or " ".join(args[:1] + [a for a in args[1:4]])}  → 退出码 {r.returncode}'); [print('      ' + l) for l in o.splitlines()[:8]]
    return r.returncode, o
print('== 一:模块边界在编译期:provider 只 exports api;consumer 的 Bad 直接引用 impl.Secret')
rc, _ = sh(['javac', '-d', 'out/provider', 'provider/module-info.java', 'provider/api/Greeter.java', 'provider/impl/Secret.java'], label='javac provider')
rc, _ = sh(['javac', '--module-path', 'out', '-d', 'out/consumer', 'consumer/module-info.java', 'consumer/app/Good.java', 'consumer/app/Reflect.java'], label='javac consumer(Good + Reflect)')
rc, o = sh(['javac', '--module-path', 'out', '-d', 'badout/consumer_bad', 'consumer/module-info.java', 'consumer/app/Bad.java'], label='javac consumer(Bad,引用 impl.Secret)')
rc, o = sh(['java', '--module-path', 'out', '--module', 'consumer/app.Good'], label='java --module consumer/app.Good')
print('== 二:同样的代码放在 classpath 上(没有 module-info):边界还在吗')
rc, _ = sh(['javac', '-d', 'out/cp', 'provider/api/Greeter.java', 'provider/impl/Secret.java', 'consumer/app/Bad.java', 'consumer/app/Good.java', 'consumer/app/Reflect.java'], label='javac(全部 classpath)')
rc, o = sh(['java', '-cp', 'out/cp', 'app.Bad'], label='java -cp out/cp app.Bad')
print('== 三:运行时反射:公有类在未导出的包里(模块路径运行 consumer/app.Reflect)')
rc, o = sh(['java', '--module-path', 'out', '--module', 'consumer/app.Reflect'], label='默认')
rc, o = sh(['java', '--add-exports', 'provider/impl=consumer', '--module-path', 'out', '--module', 'consumer/app.Reflect'], label='--add-exports provider/impl=consumer')
rc, o = sh(['java', '--add-opens', 'provider/impl=consumer', '--module-path', 'out', '--module', 'consumer/app.Reflect'], label='--add-opens provider/impl=consumer')
rc, o = sh(['java', '--add-opens', 'provider/impl=ALL-UNNAMED', '-cp', 'out/cp', 'app.Reflect'], label='classpath 上运行(不加参数)', env=E) if False else (0, '')
rc, o = sh(['java', '-cp', 'out/cp', 'app.Reflect'], label='classpath 上运行(不加参数)')
print('== 四:测试放在哪:与被测代码同模块(--patch-module)与独立的测试模块')
w('test/impl/SecretTest.java', 'package impl;\npublic class SecretTest { public static void main(String[] a) { System.out.println("同模块测试直接访问 impl.Secret:" + Secret.token()); } }\n')
w('testmod/module-info.java', 'module testmod { requires provider; }\n')
w('testmod/t/ExtTest.java', 'package t;\npublic class ExtTest { public static void main(String[] a) { System.out.println("独立模块测试访问 impl.Secret:" + impl.Secret.token()); } }\n')
rc, o = sh(['javac', '--patch-module', 'provider=test', '--module-path', 'out', '-d', 'out/test_patch', 'test/impl/SecretTest.java'], label='javac --patch-module provider=test')
rc, o = sh(['java', '--patch-module', 'provider=out/test_patch', '--module-path', 'out', '--add-modules', 'provider', '--module', 'provider/impl.SecretTest'], label='java --patch-module provider=out/test_patch ... provider/impl.SecretTest')
rc, o = sh(['javac', '--module-path', 'out', '-d', 'out/testmod', 'testmod/module-info.java', 'testmod/t/ExtTest.java'], label='javac 独立测试模块 testmod(requires provider)')
print('== 五:ArchUnit 1.3.0 在 classpath 上给 impl 包立规则:app 包里的类不得依赖 impl')
w('arch/ArchCheck.java', '''import com.tngtech.archunit.core.importer.ClassFileImporter; import com.tngtech.archunit.core.domain.JavaClasses; import com.tngtech.archunit.lang.*; import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
public class ArchCheck { public static void main(String[] a) { JavaClasses cs = new ClassFileImporter().importPath(a[0]);
  ArchRule rule = noClasses().that().resideInAPackage("app..").should().dependOnClassesThat().resideInAPackage("impl..");
  EvaluationResult r = rule.evaluate(cs); System.out.println("导入类数 " + cs.size() + ";规则违反数 " + r.getFailureReport().getDetails().size());
  r.getFailureReport().getDetails().forEach(s -> System.out.println("  违反:" + s.replaceAll("\\\\(.*?\\\\)", "()").replaceAll("\\\\s+", " "))); } }
''')
CPA = AU
rc, o = sh(['javac', '-cp', CPA, '-d', 'out/arch', 'arch/ArchCheck.java'], label='javac ArchCheck')
rc, o = sh(['java', '-cp', 'out/arch:' + CPA, 'ArchCheck', 'out/cp'], label='ArchUnit 检查 out/cp(含 Bad 的直接引用与 Reflect 的 Class.forName)')
print('  对照:只检查 Good 与 Reflect(没有直接引用 impl,只有字符串 \"impl.Secret\")')
sh(['javac', '-d', 'out/cp2', 'provider/api/Greeter.java', 'provider/impl/Secret.java', 'consumer/app/Good.java', 'consumer/app/Reflect.java'], show=False)
rc, o = sh(['java', '-cp', 'out/arch:' + CPA, 'ArchCheck', 'out/cp2'], label='ArchUnit 检查 out/cp2')
