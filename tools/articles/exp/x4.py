import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x4'); CP = scp('org.springframework.boot:spring-boot-starter')
LOGBACK = '<configuration><appender name="O" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{0}: %msg%n</pattern></encoder></appender><root level="INFO"><appender-ref ref="O"/></root></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.beans.BeansException; import org.springframework.beans.factory.annotation.Autowired; import org.springframework.beans.factory.config.*; import org.springframework.core.*;
import org.springframework.context.annotation.*;
public class Main {
  static final List<String> seq = new ArrayList<>();
  public interface Svc { String hi(); }
  public static class SvcImpl implements Svc { public String hi() { return "hi"; } }
  public static class Wrap implements BeanPostProcessor {
    public Object postProcessAfterInitialization(Object b, String n) {
      if (b instanceof SvcImpl) { Svc target = (Svc) b; return java.lang.reflect.Proxy.newProxyInstance(Main.class.getClassLoader(), new Class<?>[]{Svc.class}, (p, m, a) -> "[包装]" + m.invoke(target, a)); }
      return b; }
  }
  public static class ByIface { public ByIface(Svc s) { System.out.println("RES ByIface 拿到:" + s.getClass().getSimpleName() + " 调用结果 " + s.hi()); } }
  public static class ByClass { public ByClass(SvcImpl s) { System.out.println("RES ByClass 拿到:" + s.getClass().getSimpleName()); } }
  @Configuration static class WrapConf { @Bean static Wrap wrap() { return new Wrap(); } @Bean SvcImpl svc() { return new SvcImpl(); } @Bean ByIface byIface(Svc s) { return new ByIface(s); } }
  @Configuration static class WrapConf2 { @Bean static Wrap wrap() { return new Wrap(); } @Bean SvcImpl svc() { return new SvcImpl(); } @Bean ByClass byClass(SvcImpl s) { return new ByClass(s); } }
  public static class Rec implements BeanPostProcessor { final String id; Rec(String id) { this.id = id; }
    public Object postProcessBeforeInitialization(Object b, String n) { if (n.equals("target")) seq.add(id); return b; } }
  public static class PO extends Rec implements PriorityOrdered { final int o; PO(String id, int o) { super(id); this.o = o; } public int getOrder() { return o; } }
  public static class Ord extends Rec implements Ordered { final int o; Ord(String id, int o) { super(id); this.o = o; } public int getOrder() { return o; } }
  public static class Target { }
  @Configuration static class OrderConf {
    @Bean static Rec plain1() { return new Rec("plain1(无顺序,最先注册)"); } @Bean static Ord ord1() { return new Ord("Ordered(1)", 1); } @Bean static PO po10() { return new PO("PriorityOrdered(10)", 10); }
    @Bean static Rec plain2() { return new Rec("plain2(无顺序,后注册)"); } @Bean static PO po5() { return new PO("PriorityOrdered(5)", 5); } @Bean static Ord ord0() { return new Ord("Ordered(0)", 0); } @Bean Target target() { return new Target(); } }
  public static class Service { public Service() { System.out.println("RES 构造 Service"); } }
  public static class Early implements BeanPostProcessor { public Early(Service s) { System.out.println("RES 构造 Early(BPP,构造器依赖 Service)"); } }
  public static class Late implements BeanPostProcessor { public Object postProcessAfterInitialization(Object b, String n) { if (n.equals("service") || n.equals("plainBean")) System.out.println("RES Late(后注册的 BPP)看到了 " + n); return b; } }
  public static class PlainBean { }
  @Configuration static class EarlyConf { @Bean static Early early(Service s) { return new Early(s); } @Bean static Late late() { return new Late(); } @Bean Service service() { return new Service(); } @Bean PlainBean plainBean() { return new PlainBean(); } }
  @Configuration static class NonStatic {
    @Autowired org.springframework.core.env.Environment env;
    @Bean BeanFactoryPostProcessor bfpp() { System.out.println("RES 非 static 的 BFPP @Bean 方法被调用时,配置类里的 @Autowired Environment 字段 = " + env); return bf -> { }; } }
  @Configuration static class Static {
    @Autowired org.springframework.core.env.Environment env;
    @Bean static BeanFactoryPostProcessor bfpp() { System.out.println("RES static 的 BFPP @Bean 方法被调用(静态方法不需要先创建配置类)"); return bf -> { }; }
    @Bean String x() { System.out.println("RES 配置类被创建后 @Autowired Environment 字段 = " + (env != null ? "已注入" : "null")); return "x"; } }
  public static void main(String[] args) {
    String m = args[0]; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext();
    try {
      if (m.equals("wrap")) c.register(WrapConf.class); else if (m.equals("wrap2")) c.register(WrapConf2.class); else if (m.equals("order")) c.register(OrderConf.class);
      else if (m.equals("early")) c.register(EarlyConf.class); else if (m.equals("nonstatic")) c.register(NonStatic.class); else if (m.equals("static")) c.register(Static.class);
      c.refresh();
      if (m.equals("order")) System.out.println("RES 顺序:" + String.join(" → ", seq));
      if (m.equals("wrap")) System.out.println("RES getBean(\"svc\") 的类型:" + c.getBean("svc").getClass().getSimpleName() + ",是 SvcImpl 的实例?" + (c.getBean("svc") instanceof SvcImpl));
    } catch (Exception e) { Throwable t = e; while (t.getCause() != null) t = t.getCause(); System.out.println("RES 异常 " + e.getClass().getSimpleName() + " ← " + t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).split("\n")[0]); }
  }
}
'''
b = sbuild('x4', {'src/demo/Main.java': MAIN, 'logback.xml': LOGBACK}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): r = srun(b, 'demo.Main', args=[m]); return r['out']
def show_(o, logpat=None):
    for l in o.splitlines():
        if l.startswith('RES '): print('  ' + l[4:])
        elif logpat and re.search(logpat, l): print('  ' + (l if len(l) <= 250 else l[:247] + '…'))
print('Spring Framework 7.0.9。BeanPostProcessor 与 BeanFactoryPostProcessor 的几个容易踩坑的行为。日志用 logback(INFO)输出,只摘出 Spring 自己提示的几行')
print('== 一:BeanPostProcessor 可以把 Bean 换成别的对象。Wrap 把 SvcImpl 换成了一个 JDK 动态代理(只实现 Svc 接口)。(a)ByIface 按接口 Svc 注入;(b)ByClass 按具体类 SvcImpl 注入')
show_(run('wrap')); show_(run('wrap2'))
print('== 二:多个 BeanPostProcessor 的执行顺序。同一个 Bean(target)被 6 个 BPP 处理:PriorityOrdered(10)、PriorityOrdered(5)、Ordered(1)、Ordered(0),以及两个没有顺序的(一个最先注册、一个中间注册)。记录 postProcessBeforeInitialization 的先后')
show_(run('order'))
print('== 三:创建得太早的 Bean 不会被所有 BeanPostProcessor 处理。Early 是 BPP,构造器依赖 Service,所以 Service 在 BPP 注册阶段就被创建了;Late 是另一个 BPP,在 Early 之后注册;PlainBean 是普通的 Bean。看 Late 能看到哪些')
show_(run('early'), r'PostProcessorRegistrationDelegate')
print('== 四:BeanFactoryPostProcessor 的 @Bean 方法要不要 static。(a)非 static,配置类里有一个 @Autowired 字段;(b)static,配置类里也有 @Autowired 字段,另有一个普通 @Bean 方法')
show_(run('nonstatic'), r'ConfigurationClassPostProcessor|non-static'); show_(run('static'))
print('  BFPP 要在其它 Bean 之前就拿到实例,非 static 的 @Bean 方法需要先创建它所在的配置类,这时 BeanPostProcessor 还没注册,@Autowired 之类的注解处理不了;所以 BFPP 和 BPP 的 @Bean 方法都应该写成 static')
