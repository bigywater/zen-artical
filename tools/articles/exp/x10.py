import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x10'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.context.annotation.*; import org.springframework.core.type.AnnotatedTypeMetadata; import org.springframework.beans.factory.support.BeanDefinitionRegistry;
public class Main {
  public static class Bean1 { }
  // ---- 一 Profile ----
  @Configuration static class Prof {
    @Bean @Profile("dev") Bean1 dev() { return new Bean1(); }
    @Bean @Profile("prod") Bean1 prod() { return new Bean1(); }
    @Bean @Profile("!prod") Bean1 notProd() { return new Bean1(); }
    @Bean @Profile("default") Bean1 onlyDefault() { return new Bean1(); }
    @Bean @Profile("dev & !cloud") Bean1 devNotCloud() { return new Bean1(); }
    @Bean @Profile("prod | cloud") Bean1 prodOrCloud() { return new Bean1(); }
    @Bean Bean1 always() { return new Bean1(); }
  }
  // ---- 二/四 注册表条件 ----
  static final List<String> trace = new ArrayList<>();
  public static class MissingDs implements Condition {
    public boolean matches(ConditionContext c, AnnotatedTypeMetadata m) { boolean has = c.getRegistry().containsBeanDefinition("dataSource"); trace.add("MissingDs(REGISTER_BEAN 阶段)被求值:registry 里已有 dataSource = " + has); return !has; } }
  public static class MissingDsParse implements ConfigurationCondition {
    public ConfigurationPhase getConfigurationPhase() { return ConfigurationPhase.PARSE_CONFIGURATION; }
    public boolean matches(ConditionContext c, AnnotatedTypeMetadata m) { boolean has = c.getRegistry().containsBeanDefinition("dataSource"); trace.add("MissingDsParse(PARSE_CONFIGURATION 阶段)被求值:registry 里已有 dataSource = " + has); return !has; } }
  @Configuration static class User { @Bean Bean1 dataSource() { return new Bean1(); } }
  @Configuration static class FallbackBean { @Bean @Conditional(MissingDs.class) Bean1 fallbackDs() { return new Bean1(); } }
  @Configuration @Conditional(MissingDsParse.class) static class FallbackParse { @Bean Bean1 fallbackDsParse() { return new Bean1(); } }
  // ---- 三 类级别 vs 方法级别 ----
  public static class Off implements Condition { public boolean matches(ConditionContext c, AnnotatedTypeMetadata m) { return false; } }
  public static class On implements Condition { public boolean matches(ConditionContext c, AnnotatedTypeMetadata m) { return true; } }
  @Configuration @Conditional(Off.class) @Import(Imported.class) static class ClassOff { @Bean Bean1 inOff() { return new Bean1(); } @Configuration static class Nested { @Bean Bean1 nestedBean() { return new Bean1(); } } }
  @Configuration static class Imported { @Bean Bean1 importedBean() { return new Bean1(); } }
  @Configuration static class MethodOff { @Bean Bean1 keep() { return new Bean1(); } @Bean @Conditional(Off.class) Bean1 dropped() { return new Bean1(); } }
  static String names(AnnotationConfigApplicationContext c) { List<String> l = new ArrayList<>(); for (String n : c.getBeanDefinitionNames()) if (!n.startsWith("org.springframework") && !n.startsWith("main.")) l.add(n); Collections.sort(l); return l.toString(); }
  public static void main(String[] args) {
    String mode = args[0]; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext();
    switch (mode) {
      case "profile" -> { String how = args[1]; String ps = args.length > 2 ? args[2] : ""; 
        if (how.equals("env") && !ps.isEmpty()) c.getEnvironment().setActiveProfiles(ps.split(","));
        if (how.equals("default")) c.getEnvironment().setDefaultProfiles(ps.split(","));
        c.register(Prof.class); c.refresh(); System.out.println("RES 激活 " + Arrays.toString(c.getEnvironment().getActiveProfiles()) + ",默认 " + Arrays.toString(c.getEnvironment().getDefaultProfiles()) + " → " + names(c)); }
      case "order" -> { Class<?>[] cs = args[1].equals("userFirst") ? new Class<?>[]{User.class, FallbackBean.class} : new Class<?>[]{FallbackBean.class, User.class};
        c.register(cs); c.refresh(); System.out.println("RES 注册顺序 " + Arrays.stream(cs).map(x -> x.getSimpleName()).toList() + " → " + names(c)); trace.forEach(t -> System.out.println("RES     · " + t)); }
      case "phase" -> { Class<?>[] cs = args[1].equals("userFirst") ? new Class<?>[]{User.class, FallbackParse.class} : new Class<?>[]{FallbackParse.class, User.class};
        c.register(cs); c.refresh(); System.out.println("RES 注册顺序 " + Arrays.stream(cs).map(x -> x.getSimpleName()).toList() + " → " + names(c)); trace.forEach(t -> System.out.println("RES     · " + t)); }
      case "level" -> { c.register(ClassOff.class, MethodOff.class); c.refresh(); System.out.println("RES 类上 @Conditional(false)、方法上 @Conditional(false) 之后剩下 → " + names(c)); }
    }
  }
}
'''
b = sbuild('x10', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(*a, props=None): r = srun(b, 'demo.Main', args=list(a), props=props); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-400:]]
print('Spring Framework 7.0.9。@Profile 与 @Conditional')
print('== 一:@Profile。7 个 @Bean:dev、prod、!prod、default、"dev & !cloud"、"prod | cloud"、没有 @Profile 的 always。不同激活方式下容器里留下哪些(每个 Bean 的方法名就是 Bean 名)')
for lab, a, props in (('什么都不激活', ('profile', 'none'), None), ('setActiveProfiles(dev)', ('profile', 'env', 'dev'), None), ('setActiveProfiles(prod)', ('profile', 'env', 'prod'), None), ('setActiveProfiles(dev, cloud)', ('profile', 'env', 'dev,cloud'), None), ('-Dspring.profiles.active=dev', ('profile', 'none'), {'spring.profiles.active': 'dev'}), ('setDefaultProfiles(base),没有激活', ('profile', 'default', 'base'), None)):
    print(f'  {lab}:' + run(*a, props=props)[0])
print('== 二:条件对注册顺序敏感。FallbackBean 里的 @Bean 带自定义 @Conditional:registry 里没有 dataSource 才注册 fallbackDs;User 里有一个 dataSource。两种注册顺序')
for o in ('userFirst', 'fallbackFirst'): [print('  ' + l) for l in run('order', o)]
print('== 三:配置类上的条件(PARSE_CONFIGURATION 阶段,ConfigurationCondition)与 @Bean 方法上的条件(REGISTER_BEAN 阶段)的求值时机不同。同样是“registry 里没有 dataSource 才生效”,FallbackParse 把条件放在 @Configuration 类上')
for o in ('userFirst', 'fallbackFirst'): [print('  ' + l) for l in run('phase', o)]
print('== 四:条件放在类上还是方法上。ClassOff(类上 @Conditional(false),带 @Import 和嵌套配置类),MethodOff(一个 @Bean 正常,一个 @Bean 上有 @Conditional(false))')
[print('  ' + l) for l in run('level')]
