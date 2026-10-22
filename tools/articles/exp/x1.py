import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x1'); CP = scp('org.springframework:spring-context', 'jakarta.annotation:jakarta.annotation-api')
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.beans.factory.SmartInitializingSingleton; import org.springframework.beans.factory.config.BeanFactoryPostProcessor; import org.springframework.beans.factory.config.BeanPostProcessor; import org.springframework.beans.factory.config.ConfigurableListableBeanFactory; import org.springframework.context.*; import org.springframework.context.annotation.*; import org.springframework.context.event.*;
import jakarta.annotation.PreDestroy;
public class Main {
  static String cur = "(未开始)"; static final List<String> log = new ArrayList<>(); static long t0;
  static void ev(String s) { log.add(String.format("%-26s %s", cur, s)); }
  static class Ctx extends AnnotationConfigApplicationContext {
    <T> T step(String n, java.util.function.Supplier<T> s) {
      String prev = cur; cur = n; int d0 = getBeanDefinitionCount(); int s0 = getBeanFactory().getSingletonCount(); long t = System.nanoTime();
      T r = s.get(); long us = (System.nanoTime() - t) / 1000;
      System.out.println(String.format("RES STEP %-34s BeanDefinition %2d→%2d  单例 %2d→%2d  %6d µs", n, d0, getBeanDefinitionCount(), s0, getBeanFactory().getSingletonCount(), us)); cur = prev; return r;
    }
    @Override protected void prepareRefresh() { step("prepareRefresh", () -> { super.prepareRefresh(); return null; }); }
    @Override protected ConfigurableListableBeanFactory obtainFreshBeanFactory() { return step("obtainFreshBeanFactory", () -> super.obtainFreshBeanFactory()); }
    @Override protected void prepareBeanFactory(ConfigurableListableBeanFactory bf) { step("prepareBeanFactory", () -> { super.prepareBeanFactory(bf); return null; }); System.out.println("RES SINGLES prepareBeanFactory 之后的单例:" + Arrays.toString(bf.getSingletonNames())); }
    @Override protected void postProcessBeanFactory(ConfigurableListableBeanFactory bf) { step("postProcessBeanFactory", () -> { super.postProcessBeanFactory(bf); return null; }); }
    @Override protected void invokeBeanFactoryPostProcessors(ConfigurableListableBeanFactory bf) { step("invokeBeanFactoryPostProcessors", () -> { super.invokeBeanFactoryPostProcessors(bf); return null; }); }
    @Override protected void registerBeanPostProcessors(ConfigurableListableBeanFactory bf) { step("registerBeanPostProcessors", () -> { super.registerBeanPostProcessors(bf); return null; }); }
    @Override protected void initMessageSource() { step("initMessageSource", () -> { super.initMessageSource(); return null; }); }
    @Override protected void initApplicationEventMulticaster() { step("initApplicationEventMulticaster", () -> { super.initApplicationEventMulticaster(); return null; }); }
    @Override protected void onRefresh() { step("onRefresh", () -> { super.onRefresh(); return null; }); }
    @Override protected void registerListeners() { step("registerListeners", () -> { super.registerListeners(); return null; }); }
    @Override protected void finishBeanFactoryInitialization(ConfigurableListableBeanFactory bf) { step("finishBeanFactoryInitialization", () -> { super.finishBeanFactoryInitialization(bf); return null; }); }
    @Override protected void finishRefresh() { step("finishRefresh", () -> { super.finishRefresh(); return null; }); }
  }
  public static class A { public A() { ev("构造 A"); } @PreDestroy void bye() { ev("A.@PreDestroy"); } }
  public static class B { public B(A a) { ev("构造 B(依赖 A)"); } @PreDestroy void bye() { ev("B.@PreDestroy"); } }
  public static class Proto { public Proto() { ev("构造 Proto(prototype)"); } }
  public static class LazyOne { public LazyOne() { ev("构造 LazyOne(@Lazy)"); } }
  public static class Needs { public Needs(Missing m) { ev("构造 Needs"); } }
  public static class Missing { }
  public static class Life implements SmartLifecycle { boolean run; public Life() { ev("构造 Life(SmartLifecycle)"); }
    public void start() { run = true; ev("Life.start()"); } public void stop() { run = false; ev("Life.stop()"); } public boolean isRunning() { return run; } }
  public static class Init implements SmartInitializingSingleton { public Init() { ev("构造 Init"); } public void afterSingletonsInstantiated() { ev("SmartInitializingSingleton.afterSingletonsInstantiated()"); } }
  public static class Bfpp implements BeanFactoryPostProcessor { public Bfpp() { ev("构造 Bfpp(BeanFactoryPostProcessor)"); }
    public void postProcessBeanFactory(ConfigurableListableBeanFactory bf) { ev("Bfpp.postProcessBeanFactory:此时 BeanDefinition 共 " + bf.getBeanDefinitionCount() + " 个,单例 " + bf.getSingletonCount() + " 个"); } }
  public static class Bpp implements BeanPostProcessor { public Bpp() { ev("构造 Bpp(BeanPostProcessor)"); }
    public Object postProcessAfterInitialization(Object b, String n) { if (b.getClass().getName().startsWith("demo.Main$")) ev("Bpp 处理 " + n); return b; } }
  public static class Listener { @org.springframework.context.event.EventListener void on(ContextRefreshedEvent e) { ev("ContextRefreshedEvent"); } }
  @Configuration static class Conf {
    @Bean static Bfpp bfpp() { return new Bfpp(); } @Bean static Bpp bpp() { return new Bpp(); }
    @Bean A a() { return new A(); } @Bean B b(A a) { return new B(a); } @Bean @Scope("prototype") Proto proto() { return new Proto(); }
    @Bean @Lazy LazyOne lazyOne() { return new LazyOne(); } @Bean Life life() { return new Life(); } @Bean Init init() { return new Init(); } @Bean Listener listener() { return new Listener(); }
  }
  @Configuration static class Bad { @Bean A a() { return new A(); } @Bean Needs needs(Missing m) { return new Needs(m); } }
  public static void main(String[] args) throws Exception {
    String mode = args[0];
    if (mode.equals("ok")) {
      Ctx c = new Ctx(); c.register(Conf.class); System.out.println("RES NAMES0 refresh 之前的 BeanDefinition:" + Arrays.toString(c.getBeanDefinitionNames())); c.refresh();
      System.out.println("RES NAMES1 refresh 之后新增的:" + Arrays.stream(c.getBeanDefinitionNames()).filter(n -> n.startsWith("org.springframework") == false).toList());
      System.out.println("RES --- 事件时间线"); log.forEach(l -> System.out.println("RES EV " + l)); log.clear();
      System.out.println("RES --- refresh 完成后:getBean(Proto) 两次、getBean(LazyOne) 一次"); cur = "refresh 之后"; c.getBean(Proto.class); c.getBean(Proto.class); c.getBean(LazyOne.class);
      log.forEach(l -> System.out.println("RES EV " + l)); log.clear(); cur = "close()"; c.close(); log.forEach(l -> System.out.println("RES EV " + l));
      System.out.println("RES isActive=" + c.isActive() + " isRunning=" + c.isRunning());
    } else if (mode.equals("fail")) {
      Ctx c = new Ctx(); c.register(Bad.class);
      try { c.refresh(); } catch (Exception e) { System.out.println("RES 异常 " + e.getClass().getSimpleName() + ": " + e.getMessage().split("\n")[0]); }
      log.forEach(l -> System.out.println("RES EV " + l)); System.out.println("RES 失败后 isActive=" + c.isActive());
    } else if (mode.equals("twice")) {
      Ctx c = new Ctx(); c.register(Conf.class); c.refresh(); try { c.refresh(); } catch (Exception e) { System.out.println("RES 第二次 refresh:" + e.getClass().getSimpleName() + ": " + e.getMessage()); }
    }
  }
}
'''
b = sbuild('x1', {'src/demo/Main.java': MAIN}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
print('Spring Framework(不带 Boot)的 AnnotationConfigApplicationContext。把 refresh() 里每一个受保护的步骤方法都重写一遍,在前后记录 BeanDefinition 与单例的数量,再让 Bean 的构造器、BeanFactoryPostProcessor、BeanPostProcessor、SmartLifecycle 等回调往同一个时间线里记事件')
print('== 一:refresh() 的各个步骤。配置里有 9 个 @Bean(A、B 依赖 A、prototype 的 Proto、@Lazy 的 LazyOne、SmartLifecycle、SmartInitializingSingleton、监听器,以及 BeanFactoryPostProcessor 和 BeanPostProcessor 各一个)。每步一行:BeanDefinition 数 前→后,单例数 前→后,耗时')
r = srun(b, 'demo.Main', args=['ok']); L = res(r)
for l in L:
    if l.startswith('STEP '): print('  ' + l[5:])
for l in L:
    if l.startswith(('NAMES', 'SINGLES')): print('  ' + l.split(' ', 1)[1])
print('== 二:回调和 Bean 的创建分别发生在哪一步(左边一列是当时正在执行的 refresh 步骤)')
for l in L:
    if l.startswith('EV ') or l.startswith('---'): print('  ' + (l[3:] if l.startswith('EV ') else l))
print('  isActive/isRunning:' + [l for l in L if l.startswith('isActive')][0])
print('  BeanFactoryPostProcessor 和 BeanPostProcessor 本身也是 Bean,而且要最早被创建(分别在 invokeBeanFactoryPostProcessors、registerBeanPostProcessors 里);普通单例都在 finishBeanFactoryInitialization 里按定义顺序创建,依赖会先于使用者创建;prototype 与 @Lazy 的 Bean 在 refresh 期间不创建;SmartLifecycle.start() 与 ContextRefreshedEvent 在 finishRefresh 里')
print('== 三:refresh 失败时(Needs 依赖一个没有注册的 Missing)。前面已经创建的单例 A 会怎样')
r = srun(b, 'demo.Main', args=['fail']); L = res(r); st = [l for l in L if l.startswith('STEP ')]
print(f'  失败之前完成了 {len(st)} 个步骤,最后完成的是 {st[-1].split()[1]}(下一步 finishBeanFactoryInitialization 抛出了异常)')
[print('  ' + l[3:] if l.startswith('EV ') else '  ' + l) for l in L if not l.startswith(('STEP ', 'NAMES', 'SINGLES'))]
print('== 四:同一个上下文 refresh 两次')
r = srun(b, 'demo.Main', args=['twice']); [print('  ' + l) for l in res(r) if not l.startswith(('STEP ', 'NAMES', 'SINGLES'))]
