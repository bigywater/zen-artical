import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x9'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><appender name="O" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{0}: %msg%n</pattern></encoder></appender><root level="ERROR"><appender-ref ref="O"/></root></configuration>'
MAIN = r'''
package demo;
import java.util.*; import java.lang.management.ManagementFactory;
import org.springframework.context.annotation.*;
public class Main {
  public static void main(String[] args) throws Exception {
    String m = args[0]; var cl = ManagementFactory.getClassLoadingMXBean();
    if (m.equals("scan")) {
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(); long c0 = cl.getTotalLoadedClassCount(); long t0 = System.nanoTime();
      c.scan(Arrays.copyOfRange(args, 1, args.length)); long scanMs = (System.nanoTime() - t0) / 1000; long c1 = cl.getTotalLoadedClassCount();
      int defs = c.getBeanDefinitionCount(); long t1 = System.nanoTime(); c.refresh(); long refMs = (System.nanoTime() - t1) / 1000; long c2 = cl.getTotalLoadedClassCount();
      System.out.println("RES " + scanMs + " " + (c1 - c0) + " " + defs + " " + refMs + " " + (c2 - c1));
    } else if (m.equals("filters")) {
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(); c.register(Filt.class); c.refresh();
      List<String> names = new ArrayList<>(); for (String n : c.getBeanDefinitionNames()) if (n.startsWith("svc")) names.add(n); Collections.sort(names); System.out.println("RES " + names);
    }
  }
  @Configuration @ComponentScan(basePackages = "demo.pk", useDefaultFilters = false, includeFilters = @ComponentScan.Filter(type = FilterType.REGEX, pattern = ".*Svc.*"), excludeFilters = @ComponentScan.Filter(type = FilterType.REGEX, pattern = ".*Svc9.*")) static class Filt { }
}
'''
def gen(ncomp, nplain, pkg='pk'):
    f = {}
    for i in range(ncomp): f[f'src/demo/{pkg}/Svc{i}.java'] = f'package demo.{pkg};\nimport org.springframework.stereotype.Component;\n@Component public class Svc{i} {{ }}\n'
    for i in range(nplain): f[f'src/demo/{pkg}/Plain{i}.java'] = f'package demo.{pkg};\npublic class Plain{i} {{ public int x = {i}; }}\n'
    return f
base = {'src/demo/Main.java': MAIN, 'logback.xml': LOG}
def bld(name, ncomp, nplain): 
    b = sbuild(name, {**base, **gen(ncomp, nplain)}, CP)
    if b['crc'] != 0: print(b['cout'][:1500]); sys.exit()
    return b
def runs(b, pkg, n=5):
    rs = []
    for _ in range(n): rs.append([int(x) for x in [l[4:] for l in srun(b, 'demo.Main', args=['scan', pkg])['out'].splitlines() if l.startswith('RES ')][0].split()])
    return rs
med = lambda xs: statistics.median(xs)
def tab(rows, hdr): print('  ' + '  |  '.join(hdr)); [print('  ' + '  |  '.join(map(str, r))) for r in rows]
print('Spring Framework 7.0.9。组件扫描(@ComponentScan / scan())的代价。类都是脚本生成的:@Component 的 SvcN,和没有注解的 PlainN')
print('== 一:扫描一个包的时间,随包里 @Component 的数量变化(没有别的类)。每个规模 5 次,取中位数。scan() 的微秒数、扫描期间新加载的类数、扫描得到的 BeanDefinition 数,以及接下来 refresh() 里实例化这些 Bean 的微秒数与新加载的类数')
rows = []
for n in (100, 1000, 3000):
    rs = runs(bld('x9a', n, 0), 'demo.pk'); rows.append((n, f'{med([r[0] for r in rs]) / 1000:.0f} ms', f'{med([r[1] for r in rs]):.0f}', rs[0][2], f'{med([r[3] for r in rs]) / 1000:.0f} ms', f'{med([r[4] for r in rs]):.0f}'))
tab(rows, ['@Component 数', 'scan() 耗时', '扫描时新加载的类', 'BeanDefinition 数', 'refresh() 耗时(实例化)', 'refresh 时新加载的类'])
print('== 二:包里没有注解的普通类也要被读。固定 100 个 @Component,往同一个包里再放 0 / 2000 / 8000 个没有注解的普通类。scan() 要多久')
rows = []
for p in (0, 2000, 8000):
    rs = runs(bld('x9b', 100, p), 'demo.pk'); rows.append((p, f'{med([r[0] for r in rs]) / 1000:.0f} ms', f'{med([r[1] for r in rs]):.0f}', rs[0][2]))
tab(rows, ['包里的普通类数', 'scan() 耗时', '扫描时新加载的类', 'BeanDefinition 数'])
print('  扫描用元数据读取(读 .class 文件,不加载类),所以扫描期间新加载的类很少;但每个 .class 文件都要被打开读一遍,不管有没有注解,所以扫描的范围越大越慢;类是在后面实例化的时候才被加载')
print('== 三:过滤器。useDefaultFilters = false,只包含名字匹配 .*Svc.* 的类,并排除 .*Svc9.* 的类;包里有 Svc0 到 Svc19 共 20 个 @Component。看留下哪些(bean 名字)')
b = bld('x9c', 20, 3); L = res(srun(b, 'demo.Main', args=['filters'])); print('  ' + (L[0] if L else '(无输出)'))
print('== 四:默认包的陷阱。@SpringBootApplication 的主类放在默认包(没有 package 声明),组件扫描的范围变成什么')
MAIN_DEF = '''
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication public class Main { public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setWebApplicationType(WebApplicationType.NONE); app.setBannerMode(Banner.Mode.OFF); try { app.run(a).close(); System.out.println("RES 启动成功"); } catch (Throwable t) { Throwable r = t; while (r.getCause() != null) r = r.getCause(); System.out.println("RES 启动失败 " + t.getClass().getSimpleName() + " ← " + r.getClass().getSimpleName() + ": " + String.valueOf(r.getMessage()).split("\\n")[0]); } } }
'''
MAIN_PK = MAIN_DEF.replace('import org.springframework.boot.*;', 'package demo;\nimport org.springframework.boot.*;')
CPW = scp('org.springframework.boot:spring-boot-starter', 'org.springframework.boot:spring-boot-starter-webmvc')
for lab, src, main in (('主类在默认包', MAIN_DEF, 'Main'), ('主类在 demo 包', MAIN_PK, 'demo.Main')):
    p = ('src/Main.java' if main == 'Main' else 'src/demo/Main.java'); bb = sbuild('x9d', {p: src, 'logback.xml': LOG}, CPW)
    r = srun(bb, main); o = r['out']; w = [l for l in o.splitlines() if 'WARN' in l or 'Exception' in l or 'RES' in l]
    print(f'  {lab}:' + ' '.join(l[4:] for l in o.splitlines() if l.startswith('RES '))[:420])
print('== 五:两个包里有同名的 @Component(simple name 相同,默认的 Bean 名字都是 svc)')
f = {'src/demo/p1/Svc.java': 'package demo.p1;\nimport org.springframework.stereotype.Component;\n@Component public class Svc { }\n', 'src/demo/p2/Svc.java': 'package demo.p2;\nimport org.springframework.stereotype.Component;\n@Component public class Svc { }\n', 'src/demo/Main.java': MAIN.replace('c.scan(args[1])', 'c.scan(args[1])'), 'logback.xml': LOG}
bb = sbuild('x9e', f, CP); r = srun(bb, 'demo.Main', args=['scan', 'demo.p1', 'demo.p2'])
mm = re.findall(r'ConflictingBeanDefinitionException: ([^\n]{0,400})', r['out']); print('  ' + ('ConflictingBeanDefinitionException: ' + mm[0] if mm else '(没有冲突异常) ' + r['out'][-300:]))
