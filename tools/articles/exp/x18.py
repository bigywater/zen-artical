import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x18'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.beans.factory.annotation.Autowired; import org.springframework.boot.*; import org.springframework.context.*; import org.springframework.context.annotation.*; import org.springframework.context.event.ContextRefreshedEvent; import org.springframework.context.event.EventListener;
public class Main {
  static final List<String> seq = new ArrayList<>(); static void ev(String s) { seq.add(s); }
  static void flush(String t) { System.out.println("RES --- " + t); int i = 1; for (String s : seq) System.out.println("RES " + i++ + ". " + s); seq.clear(); }
  public static class Heavy { Heavy(int i) { try { Thread.sleep(20); } catch (InterruptedException e) { } } public String hi() { return "hi"; } }
  public static class Fails { public Fails(Missing m) { } } public static class Missing { }
  public static class Lis { public Lis() { ev("构造 Lis(带 @EventListener 方法)"); } @EventListener void on(ContextRefreshedEvent e) { ev("Lis 收到 ContextRefreshedEvent"); } @EventListener void on2(String s) { ev("Lis 收到自定义事件 " + s); } }
  public static class User { @Autowired @Lazy Heavy heavy; User() { ev("构造 User(heavy 字段是 @Lazy 注入)"); } void use() { ev("User 第一次调用 heavy.hi() 之前"); heavy.hi(); ev("User 调用完 heavy.hi()"); } }
  public static class HeavyBean { HeavyBean() { ev("构造 HeavyBean"); try { Thread.sleep(50); } catch (InterruptedException e) { } } }
  public static class UserPlain { @Autowired Heavy heavy; UserPlain() { ev("构造 UserPlain(heavy 字段是普通 @Autowired)"); } void use() { ev("UserPlain 第一次调用 heavy.hi() 之前"); heavy.hi(); ev("UserPlain 调用完 heavy.hi()"); } }
  @Configuration static class UserConf { @Bean(name = "heavy") HeavyForUser heavy() { ev("构造 Heavy(目标 Bean 是普通单例)"); return new HeavyForUser(); } @Bean User user() { return new User(); } }
  @Configuration static class UserConfLazyTarget { @Bean(name = "heavy") @Lazy HeavyForUser heavy() { ev("构造 Heavy(目标 Bean 标了 @Lazy)"); return new HeavyForUser(); } @Bean User user() { return new User(); } }
  @Configuration static class UserConfPlainInject { @Bean(name = "heavy") @Lazy HeavyForUser heavy() { ev("构造 Heavy(目标 Bean 标了 @Lazy)"); return new HeavyForUser(); } @Bean UserPlain user() { return new UserPlain(); } }
  public static class HeavyForUser extends Heavy { HeavyForUser() { super(0); } }
  @Configuration static class WithBadLazy { @Bean @Lazy Fails fails(Missing m) { return new Fails(m); } @Bean String ok() { return "ok"; } }
  @Configuration static class WithBadEager { @Bean Fails fails(Missing m) { return new Fails(m); } @Bean String ok() { return "ok"; } }
  @Configuration static class LisEager { @Bean Lis lis() { return new Lis(); } }
  @Configuration static class LisLazy { @Bean @Lazy Lis lis() { return new Lis(); } }
  @Configuration @Lazy static class AllLazyConf { @Bean HeavyBean a() { return new HeavyBean(); } @Bean Lis lis() { return new Lis(); } }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    switch (m) {
      case "time" -> { boolean lazy = args[1].equals("lazy"); int n = Integer.parseInt(args[2]); AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext();
        for (int i = 0; i < n; i++) { int k = i; c.registerBean("h" + i, Heavy.class, () -> new Heavy(k), bd -> bd.setLazyInit(lazy)); }
        long t0 = System.nanoTime(); c.refresh(); long ref = (System.nanoTime() - t0) / 1_000_000; t0 = System.nanoTime(); for (int i = 0; i < 5; i++) c.getBean("h" + i); long first = (System.nanoTime() - t0) / 1_000_000; t0 = System.nanoTime(); for (int i = 0; i < 5; i++) c.getBean("h" + i); long again = (System.nanoTime() - t0) / 1_000_000;
        System.out.println("RES " + (lazy ? "懒加载" : "饿汉") + " " + n + " 个 Heavy(构造器各睡 20 ms):refresh() " + ref + " ms;之后第一次取其中 5 个 " + first + " ms;再取这 5 个 " + again + " ms;已创建的单例数 " + c.getBeanFactory().getSingletonCount()); }
      case "fail" -> { Class<?> k = args[1].equals("lazy") ? WithBadLazy.class : WithBadEager.class; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext();
        try { c.register(k); c.refresh(); System.out.println("RES " + args[1] + ":refresh() 成功(没有发现 Missing 缺失)"); try { c.getBean("fails"); } catch (Exception e) { Throwable t = e; while (t.getCause() != null) t = t.getCause(); System.out.println("RES   第一次 getBean(\"fails\") 才失败:" + e.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).split("\n")[0].replace("demo.Main$", "")); } }
        catch (Exception e) { System.out.println("RES " + args[1] + ":refresh() 就失败了:" + e.getClass().getSimpleName()); } }
      case "inject" -> { String v = args[1]; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(v.equals("a") ? UserConf.class : v.equals("b") ? UserConfLazyTarget.class : UserConfPlainInject.class);
        ev("--- refresh 完成,调用 use()"); if (v.equals("c")) c.getBean(UserPlain.class).use(); else { User u = c.getBean(User.class); u.use(); ev("heavy 字段的类型:" + u.heavy.getClass().getSimpleName().split("\\$\\$")[0] + "$$…(CGLIB 代理)"); } flush("场景 " + v); }
      case "listener" -> { Class<?> k = args[1].equals("lazy") ? LisLazy.class : args[1].equals("all") ? AllLazyConf.class : LisEager.class; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(k); ev("--- refresh 完成,现在发布自定义事件"); c.publishEvent("E1"); flush("监听器 Bean 的懒加载情况:" + args[1]); }
      case "boot" -> { boolean lazy = args[1].equals("true"); SpringApplication app = new SpringApplication(BootConf.class); app.setWebApplicationType(WebApplicationType.NONE); app.setBannerMode(Banner.Mode.OFF); app.setLazyInitialization(lazy); ConfigurableApplicationContext c = app.run();
        System.out.println("RES SpringApplication.setLazyInitialization(" + lazy + "):启动后单例 " + c.getBeanFactory().getSingletonCount() + " 个;HeavyBean 已构造?" + seq.contains("构造 HeavyBean")); c.close(); }
    }
  }
  @Configuration static class BootConf { @Bean HeavyBean hb() { return new HeavyBean(); } }
}
'''
b = sbuild('x18', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(*a): r = srun(b, 'demo.Main', args=list(a)); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-700:]]
print('Spring Framework 7.0.9。@Lazy 与懒加载')
print('== 一:启动时间。n 个 Heavy 单例,每个构造器睡 20 ms,用 registerBean 注册。饿汉(默认)与懒加载(每个 BeanDefinition 设 lazyInit)各跑 n = 10、50')
for n in (10, 50):
    for lz in ('eager', 'lazy'): [print('  ' + l) for l in run('time', lz, str(n))]
print('== 二:错误什么时候被发现。一个 @Bean 依赖了一个没有注册的 Missing 类型')
for k_ in ('eager', 'lazy'): [print('  ' + l) for l in run('fail', k_)]
print('== 三:注入点上的 @Lazy。(a)目标 Heavy 是普通单例,User 里的 heavy 字段是 @Autowired @Lazy;(b)目标 Heavy 也标 @Lazy,注入点 @Lazy;(c)目标 Heavy 标 @Lazy,但注入点是普通 @Autowired')
for v in 'abc': [print('  ' + l) for l in run('inject', v)]
print('== 四:懒加载的 Bean 上的 @EventListener。Lis 有两个监听方法(ContextRefreshedEvent 和 String 事件)')
for k_ in ('eager', 'lazy', 'all'): [print('  ' + l) for l in run('listener', k_)]
print('== 五:SpringApplication.setLazyInitialization(true)(对应 Boot 的 spring.main.lazy-initialization)')
for v in ('false', 'true'): [print('  ' + l) for l in run('boot', v)]
