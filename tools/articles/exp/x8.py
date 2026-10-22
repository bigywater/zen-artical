import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x8'); CP = scp('org.springframework.boot:spring-boot-starter')
MAIN = r'''
package demo;
import java.util.*; import java.lang.management.ManagementFactory;
import org.springframework.context.annotation.*; import org.springframework.stereotype.Component;
public class Main {
  static int made = 0;
  public static class A { final int id = ++made; }
  public static class B { final A a; B(A a) { this.a = a; } }
  @Configuration static class Full { @Bean A a() { return new A(); } @Bean B b1() { return new B(a()); } @Bean B b2() { return new B(a()); } }
  @Configuration(proxyBeanMethods = false) static class Lite { @Bean A a() { return new A(); } @Bean B b1() { return new B(a()); } @Bean B b2() { return new B(a()); } }
  @Component static class AsComponent { @Bean A a() { return new A(); } @Bean B b1() { return new B(a()); } @Bean B b2() { return new B(a()); } }
  @Configuration(proxyBeanMethods = false) static class LiteParam { @Bean A a() { return new A(); } @Bean B b1(A a) { return new B(a); } @Bean B b2(A a) { return new B(a); } }
  @Configuration static class StaticBean { @Bean static A a() { return new A(); } @Bean B b1() { return new B(a()); } @Bean B b2() { return new B(a()); } }
  @Configuration static final class Fin { @Bean A a() { return new A(); } }
  static void show(String label, Class<?> c) {
    made = 0;
    try {
      AnnotationConfigApplicationContext x = new AnnotationConfigApplicationContext(c);
      Map<String, B> bs = x.getBeansOfType(B.class); Set<A> as = new HashSet<>(); bs.values().forEach(b -> as.add(b.a));
      Object cfg = x.getBean(c);
      System.out.println("RES " + label + ":A 被构造了 " + made + " 次;b1 和 b2 持有" + (as.size() == 1 ? "同一个 A(单例语义保住了)" : "不同的 A(" + as.size() + " 个,单例语义没了)") + ";容器里 A 类型的 Bean 数 " + x.getBeansOfType(A.class).size() + ";配置类的实际类型 " + cfg.getClass().getSimpleName().replaceAll("\\$\\$SpringCGLIB.*", "") + (cfg.getClass().getName().contains("CGLIB") ? "$$SpringCGLIB$$…(CGLIB 子类)" : "(原类)"));
      x.close();
    } catch (Exception e) { Throwable t = e; while (t.getCause() != null) t = t.getCause(); System.out.println("RES " + label + " → " + t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).split("\n")[0].replace("demo.Main$", "")); }
  }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    if (m.equals("modes")) { show("(a)@Configuration(默认,full 模式)", Full.class); show("(b)@Configuration(proxyBeanMethods = false)", Lite.class); show("(c)@Component 里写 @Bean(lite 模式)", AsComponent.class); show("(d)lite 模式但用方法参数注入", LiteParam.class); show("(e)full 模式,但 a() 是 static @Bean", StaticBean.class); show("(f)final 的 @Configuration 类", Fin.class); }
    else if (m.equals("boot")) {
      Class<?> ac = org.springframework.boot.autoconfigure.AutoConfiguration.class; Configuration cfg = ac.getAnnotation(Configuration.class);
      System.out.println("RES @AutoConfiguration 上的元注解 @Configuration 的 proxyBeanMethods = " + cfg.proxyBeanMethods());
      try (var in = ac.getClassLoader().getResourceAsStream("META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports")) { long n = new String(in.readAllBytes()).lines().filter(l -> !l.isBlank() && !l.startsWith("#")).count(); System.out.println("RES spring-boot-autoconfigure 的 AutoConfiguration.imports 里登记了 " + n + " 个自动配置类(Boot 4 的自动配置大多放在各个功能模块自己的 jar 里,其它模块我没有统计)"); }
    }
    else if (m.equals("many")) {
      int n = Integer.parseInt(args[1]); List<Class<?>> cs = new ArrayList<>(); for (int i = 0; i < n; i++) cs.add(Class.forName("demo.gen.Cfg" + i));
      var cl = ManagementFactory.getClassLoadingMXBean(); long c0 = cl.getTotalLoadedClassCount(); long t0 = System.nanoTime();
      AnnotationConfigApplicationContext x = new AnnotationConfigApplicationContext(); x.register(cs.toArray(new Class<?>[0])); x.refresh();
      long ms = (System.nanoTime() - t0) / 1_000_000; System.out.println("RES " + ms + " " + (cl.getTotalLoadedClassCount() - c0) + " " + x.getBeanDefinitionCount() + " " + (cs.size() > 0 && x.getBean(cs.get(0)).getClass().getName().contains("CGLIB")));
    }
  }
}
'''
N = 300
files = {'src/demo/Main.java': MAIN, 'logback.xml': '<configuration><root level="ERROR"/></configuration>'}
def gen(pbm):
    f = {}
    for i in range(N):
        beans = ''.join(f'  @Bean public Object b{i}_{j}() {{ return new Object(); }}\n' for j in range(5))
        f[f'src/demo/gen/Cfg{i}.java'] = f'package demo.gen;\nimport org.springframework.context.annotation.*;\n@Configuration(proxyBeanMethods = {pbm})\npublic class Cfg{i} {{\n{beans}}}\n'
    return f
b = sbuild('x8', {**files, **gen('true')}, CP)
if b['crc'] != 0: print(b['cout'][:1500]); sys.exit()
bl = sbuild('x8lite', {**files, **gen('false')}, CP)
print('Spring Framework 7.0.9。@Configuration 的 full 模式(proxyBeanMethods = true,默认)与 lite 模式')
print('== 一:@Bean 方法互相调用。b1() 和 b2() 都在方法体里调用 a()。六种写法下,A 被构造几次、b1 与 b2 拿到的 A 是不是同一个')
r = srun(b, 'demo.Main', args=['modes']); [print('  ' + l[4:]) for l in r['out'].splitlines() if l.startswith('RES ')]
print(f'== 二:启动代价。{N} 个 @Configuration 类,每个 5 个返回 new Object() 的 @Bean 方法(共 {N * 5} 个 Bean)。同样的代码只改 proxyBeanMethods 的 true / false。每种配置各启动 7 个 JVM,取 refresh() 耗时与 refresh 期间新加载的类数(中位数,括号里是最小和最大)')
rows = []
for lab, bb in (('proxyBeanMethods = true(CGLIB 增强)', b), ('proxyBeanMethods = false', bl)):
    rs = []
    for _ in range(7): o = [l[4:] for l in srun(bb, 'demo.Main', args=['many', str(N)], jopts=['-Xshare:auto'])['out'].splitlines() if l.startswith('RES ')][0].split(); rs.append((int(o[0]), int(o[1]), int(o[2]), o[3]))
    ms = sorted(x[0] for x in rs); cls = sorted(x[1] for x in rs)
    rows.append((lab, f'{statistics.median(ms):.0f} ({ms[0]}~{ms[-1]})', f'{statistics.median(cls):.0f} ({cls[0]}~{cls[-1]})', rs[0][2], rs[0][3]))
table = lambda rows, hdr: [print('  ' + l) for l in ['  |  '.join(hdr)] + ['  |  '.join(map(str, r)) for r in rows]]
table(rows, ['配置', 'refresh 耗时 ms', '新加载的类数', 'BeanDefinition 数', '配置类被 CGLIB 增强'])
print(f'  full 模式给每个配置类生成一个 CGLIB 子类,启动多花时间、多加载类(多出的类数比 {N} 个子类还多,多出来的是什么我没有细查)')
r = srun(b, 'demo.Main', args=['boot']); [print('  ' + l[4:]) for l in r['out'].splitlines() if l.startswith('RES ')]
