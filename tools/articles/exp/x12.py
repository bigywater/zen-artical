import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x12'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.beans.factory.*; import org.springframework.context.annotation.*; import org.springframework.core.annotation.Order;
public class Main {
  static final List<String> seq = new ArrayList<>(); static void ev(String s) { seq.add(s); }
  public static class Conn { final int id; static int n; Conn() { id = ++n; ev("创建产品 Conn#" + id); } }
  public static class ConnFactory implements FactoryBean<Conn> {
    final boolean single, typed; ConnFactory(boolean single, boolean typed) { this.single = single; this.typed = typed; ev("创建 FactoryBean 本体(singleton=" + single + ",getObjectType=" + (typed ? "Conn" : "null") + ")"); }
    public Conn getObject() { return new Conn(); } public Class<?> getObjectType() { return typed ? Conn.class : null; } public boolean isSingleton() { return single; } }
  public static class EagerFactory extends ConnFactory implements SmartFactoryBean<Conn> { EagerFactory() { super(true, true); } public boolean isEagerInit() { return true; } }
  public static class Eager2 implements SmartFactoryBean<Conn> { Eager2() { ev("创建 FactoryBean 本体(Eager2:直接实现 SmartFactoryBean,isSingleton 与 isEagerInit 都写成 true)"); } public Conn getObject() { return new Conn(); } public Class<?> getObjectType() { return Conn.class; } public boolean isSingleton() { return true; } public boolean isEagerInit() { return true; } }
  @Configuration static class Eager2Conf { @Bean Eager2 conn() { return new Eager2(); } }
  @Configuration static class SingleConf { @Bean ConnFactory conn() { return new ConnFactory(true, true); } }
  @Configuration static class ProtoConf { @Bean ConnFactory conn() { return new ConnFactory(false, true); } }
  @Configuration static class NullTypeConf { @Bean ConnFactory conn() { return new ConnFactory(true, false); } }
  @Configuration static class EagerConf { @Bean EagerFactory conn() { return new EagerFactory(); } }
  public interface Pay { String n(); }
  public static class P1 implements Pay { public P1() { ev("构造 P1"); } public String n() { return "p1"; } }
  public static class P2 implements Pay { public P2() { ev("构造 P2"); } public String n() { return "p2"; } }
  public static class Lazy1 { public Lazy1() { ev("构造 Lazy1(被 ObjectProvider 引用的 prototype)"); } }
  public static class User { final ObjectProvider<Pay> pay; final ObjectProvider<Lazy1> lazy; User(ObjectProvider<Pay> pay, ObjectProvider<Lazy1> lazy) { this.pay = pay; this.lazy = lazy; ev("构造 User(拿到了 ObjectProvider,还没有解析任何 Pay)"); } }
  @Configuration static class None { @Bean User user(ObjectProvider<Pay> p, ObjectProvider<Lazy1> l) { return new User(p, l); } }
  @Configuration static class One { @Bean User user(ObjectProvider<Pay> p, ObjectProvider<Lazy1> l) { return new User(p, l); } @Bean Pay p1() { return new P1(); } @Bean @Scope("prototype") Lazy1 lazy1() { return new Lazy1(); } }
  @Configuration static class Two { @Bean User user(ObjectProvider<Pay> p, ObjectProvider<Lazy1> l) { return new User(p, l); } @Bean @Order(2) Pay p1() { return new P1(); } @Bean @Order(1) Pay p2() { return new P2(); } @Bean @Scope("prototype") Lazy1 lazy1() { return new Lazy1(); } }
  static void flush(String t) { System.out.println("RES --- " + t); int i = 1; for (String s : seq) System.out.println("RES " + i++ + ". " + s); seq.clear(); }
  static String tryIt(java.util.concurrent.Callable<Object> c) { try { Object o = c.call(); return String.valueOf(o instanceof Pay p ? p.n() : o); } catch (Exception e) { return e.getClass().getSimpleName(); } }
  public static void main(String[] args) throws Exception {
    String m = args[0]; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext();
    switch (m) {
      case "fb" -> { c.register(args[1].equals("single") ? SingleConf.class : args[1].equals("proto") ? ProtoConf.class : args[1].equals("eager2") ? Eager2Conf.class : EagerConf.class); c.refresh(); flush("refresh 完成时(" + args[1] + ")");
        Object a = c.getBean("conn"), b = c.getBean("conn"); Object f = c.getBean("&conn"); flush("getBean(\"conn\") 两次之后");
        System.out.println("RES getBean(\"conn\") 的类型 " + a.getClass().getSimpleName() + ";getBean(\"&conn\") 的类型 " + f.getClass().getSimpleName() + ";两次是同一个产品?" + (a == b) + ";getBeansOfType(Conn.class).size() = " + c.getBeansOfType(Conn.class).size()); }
      case "nulltype" -> { c.register(NullTypeConf.class); c.refresh(); System.out.println("RES getObjectType() 返回 null:getBeanNamesForType(Conn.class) = " + Arrays.toString(c.getBeanNamesForType(Conn.class)) + ";getBean(\"conn\") 照样能拿到 " + c.getBean("conn").getClass().getSimpleName() + ";getBean(Conn.class) → " + tryIt(() -> c.getBean(Conn.class))); }
      case "op" -> { c.register(args[1].equals("none") ? None.class : args[1].equals("one") ? One.class : Two.class); c.refresh(); User u = c.getBean(User.class); flush("refresh 完成时(" + args[1] + ")");
        System.out.println("RES getIfAvailable() → " + tryIt(() -> u.pay.getIfAvailable()) + ";getIfUnique() → " + tryIt(() -> u.pay.getIfUnique()) + ";getObject() → " + tryIt(() -> u.pay.getObject()) + ";getIfAvailable(默认) → " + tryIt(() -> u.pay.getIfAvailable(() -> () -> "默认")));
        System.out.println("RES stream() 的顺序 → " + tryIt(() -> u.pay.stream().map(Pay::n).toList()) + ";orderedStream() 的顺序 → " + tryIt(() -> u.pay.orderedStream().map(Pay::n).toList())); flush("上面这些调用的过程中");
        if (args[1].equals("one")) { u.lazy.getObject(); u.lazy.getObject(); flush("两次 lazy.getObject()"); } }
    }
  }
}
'''
b = sbuild('x12', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(*a): r = srun(b, 'demo.Main', args=list(a)); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-500:]]
print('Spring Framework 7.0.9。FactoryBean 与 ObjectProvider')
print('== 一:FactoryBean(singleton 产品)。FactoryBean 本体什么时候创建、产品什么时候创建;getBean("conn") 和 getBean("&conn") 分别是什么')
[print('  ' + l) for l in run('fb', 'single')]
print('== 二:isSingleton() 返回 false 时,每次 getBean 都会调用 getObject 吗')
[print('  ' + l) for l in run('fb', 'proto')]
print('== 三:SmartFactoryBean.isEagerInit() 返回 true:产品也在 refresh 时创建')
[print('  ' + l) for l in run('fb', 'eager')]
print('== 四:SmartFactoryBean 的产品容器缓存吗?这次直接实现 SmartFactoryBean(不经过继承),isSingleton() 与 isEagerInit() 都明确写 true。(查了 spring-beans-7.0.9-sources.jar 里 FactoryBeanRegistrySupport.getObjectFromFactoryBean 的源码:对 SmartFactoryBean 有一句注释 “A SmartFactoryBean may return multiple object types -> do not cache.”)')
[print('  ' + l) for l in run('fb', 'eager2')]
print('== 五:getObjectType() 返回 null')
[print('  ' + l) for l in run('nulltype')]
print('== 六:ObjectProvider<Pay>:(a)没有任何 Pay;(b)只有一个;(c)有两个(p1 的 @Order 是 2,p2 的 @Order 是 1)。User 拿的是 ObjectProvider,看 refresh 时有没有创建 Pay,以及各个取法的结果')
for k_ in ('none', 'one', 'two'): print(f'  ({k_})'); [print('    ' + l) for l in run('op', k_)]
