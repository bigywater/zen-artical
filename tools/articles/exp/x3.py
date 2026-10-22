import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x3'); CP = scp('org.springframework.boot:spring-boot-starter')
MAIN = r'''
package demo;
import java.util.*;
import jakarta.annotation.*;
import org.springframework.beans.*; import org.springframework.beans.factory.*; import org.springframework.beans.factory.config.*;
import org.springframework.context.*; import org.springframework.context.annotation.AnnotationConfigApplicationContext; import org.springframework.context.annotation.Bean; import org.springframework.context.annotation.Configuration; import org.springframework.context.annotation.Scope;
import org.springframework.beans.factory.annotation.Autowired; import org.springframework.core.env.Environment;
public class Main {
  static final List<String> seq = new ArrayList<>();
  static void ev(String s) { seq.add(s); }
  static void flush(String title) { System.out.println("RES --- " + title); int i = 1; for (String s : seq) System.out.println("RES " + String.format("%2d. ", i++) + s); seq.clear(); }
  public static class Dep { }
  public static class Life implements BeanNameAware, BeanClassLoaderAware, BeanFactoryAware, ApplicationContextAware, EnvironmentAware, InitializingBean, DisposableBean {
    Dep dep2;
    public Life(Dep ctorDep) { ev("构造器 Life(Dep)"); }
    @Autowired public void setDep2(Dep d) { dep2 = d; ev("@Autowired setter setDep2"); }
    public void setBeanName(String n) { ev("BeanNameAware.setBeanName(" + n + ")"); }
    public void setBeanClassLoader(ClassLoader cl) { ev("BeanClassLoaderAware.setBeanClassLoader"); }
    public void setBeanFactory(BeanFactory bf) { ev("BeanFactoryAware.setBeanFactory"); }
    public void setEnvironment(Environment e) { ev("EnvironmentAware.setEnvironment"); }
    public void setApplicationContext(ApplicationContext c) { ev("ApplicationContextAware.setApplicationContext"); }
    @PostConstruct public void pc() { ev("@PostConstruct"); }
    public void afterPropertiesSet() { ev("InitializingBean.afterPropertiesSet"); }
    public void customInit() { ev("@Bean(initMethod) customInit"); }
    @PreDestroy public void pd() { ev("@PreDestroy"); }
    public void destroy() { ev("DisposableBean.destroy"); }
    public void customDestroy() { ev("@Bean(destroyMethod) customDestroy"); }
  }
  public static class Tracer implements InstantiationAwareBeanPostProcessor {
    public Object postProcessBeforeInstantiation(Class<?> c, String n) { if (n.equals("life")) ev("  [BPP] postProcessBeforeInstantiation"); return null; }
    public boolean postProcessAfterInstantiation(Object b, String n) { if (n.equals("life")) ev("  [BPP] postProcessAfterInstantiation"); return true; }
    public PropertyValues postProcessProperties(PropertyValues pv, Object b, String n) { if (n.equals("life")) ev("  [BPP] postProcessProperties"); return pv; }
    public Object postProcessBeforeInitialization(Object b, String n) { if (n.equals("life")) ev("  [BPP] postProcessBeforeInitialization"); return b; }
    public Object postProcessAfterInitialization(Object b, String n) { if (n.equals("life")) ev("  [BPP] postProcessAfterInitialization"); return b; }
  }
  public static class Closer { boolean closed; public void close() { ev("Closer.close() 被调用(没有任何配置)"); } }
  public static class Closer2 { public void close() { ev("Closer2.close() 被调用(destroyMethod=\"\")"); } }
  public static class Boom { public Boom() { ev("构造器 Boom"); } @PostConstruct void init() { ev("Boom.@PostConstruct 抛异常"); throw new IllegalStateException("初始化失败"); } @PreDestroy void pd() { ev("Boom.@PreDestroy"); } }
  @Configuration static class Conf {
    @Bean static Tracer tracer() { return new Tracer(); } @Bean Dep dep() { return new Dep(); }
    @Bean(initMethod = "customInit", destroyMethod = "customDestroy") Life life(Dep d) { return new Life(d); }
  }
  @Configuration static class ProtoConf { @Bean @Scope("prototype") Life life(Dep d) { return new Life(d); } @Bean Dep dep() { return new Dep(); } }
  @Configuration static class InferConf { @Bean Closer closer() { return new Closer(); } @Bean(destroyMethod = "") Closer2 closer2() { return new Closer2(); } }
  @Configuration static class BoomConf { @Bean Dep dep() { return new Dep(); } @Bean Boom boom() { return new Boom(); } }
  public static void main(String[] args) {
    String mode = args[0]; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext();
    if (mode.equals("full")) { c.register(Conf.class); c.refresh(); flush("创建阶段(从构造器到 BeanPostProcessor.after)"); c.close(); flush("c.close() 之后"); }
    else if (mode.equals("proto")) { c.register(ProtoConf.class); c.refresh(); Object a = c.getBean(Life.class); Object b = c.getBean(Life.class); flush("两次 getBean(prototype)"); c.close(); flush("c.close() 之后(prototype 的销毁回调)"); }
    else if (mode.equals("infer")) { c.register(InferConf.class); c.refresh(); c.close(); flush("c.close() 之后"); }
    else if (mode.equals("boom")) { c.register(BoomConf.class); try { c.refresh(); } catch (Exception e) { ev("refresh 抛出 " + e.getClass().getSimpleName() + " ← " + e.getCause().getClass().getSimpleName() + ": " + e.getCause().getMessage()); } flush("初始化抛异常的 Bean"); }
  }
}
'''
b = sbuild('x3', {'src/demo/Main.java': MAIN}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): r = srun(b, 'demo.Main', args=[m]); return res(r)
print('Spring Framework 7.0.9。一个 Bean 同时带上所有常见的回调(各种 Aware、@PostConstruct、InitializingBean、init-method,@PreDestroy、DisposableBean、destroy-method),再加一个 InstantiationAwareBeanPostProcessor 把前后阶段也记下来。每个回调往同一个列表里记一条')
print('== 一:一个 singleton Bean 的完整生命周期(缩进两格并带 [BPP] 的是 BeanPostProcessor 的回调)')
[print('  ' + l) for l in run('full')]
print('== 二:prototype 的 Bean:getBean 两次,然后关闭容器。容器会不会调用它们的销毁回调?')
[print('  ' + l) for l in run('proto')]
print('== 三:destroyMethod 的推断。@Bean 返回的对象有一个 public 的无参 close() 方法,没有写任何销毁配置,关闭容器时会不会被调用?destroyMethod="" 呢?')
[print('  ' + l) for l in run('infer')]
print('== 四:初始化抛异常。@PostConstruct 里抛 IllegalStateException,这个 Bean 的 @PreDestroy 会被调用吗')
[print('  ' + l) for l in run('boom')]
