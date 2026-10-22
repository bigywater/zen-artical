import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x28'); CP = scp('org.springframework.boot:spring-boot-starter', 'org.springframework.boot:spring-boot-starter-aspectj')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.aspectj.lang.ProceedingJoinPoint; import org.aspectj.lang.annotation.*;
import org.springframework.aop.*; import org.springframework.aop.framework.*; import org.springframework.aop.support.AopUtils; import org.springframework.aop.target.SingletonTargetSource;
import org.springframework.context.annotation.*; import org.springframework.core.annotation.AnnotatedElementUtils; import org.springframework.core.annotation.AnnotationUtils; import org.springframework.util.ClassUtils; import org.springframework.scheduling.annotation.*;
public class Main {
  @java.lang.annotation.Retention(java.lang.annotation.RetentionPolicy.RUNTIME) public @interface Tag { String value(); }
  public interface Greeter { String hi(); }
  @Tag("on-class") public static class JdkTarget implements Greeter { public String hi() { return "hi"; } }
  @Tag("on-class") public static class CglibTarget { public String hi() { return "hi"; } @Async public void later() { } }
  @Aspect public static class A1 { @Around("execution(* demo.Main.CglibTarget.hi())") public Object a(ProceedingJoinPoint pj) throws Throwable { return pj.proceed(); } }
  @Aspect public static class A2 { @Around("execution(* demo.Main.CglibTarget.hi())") public Object a(ProceedingJoinPoint pj) throws Throwable { return pj.proceed(); } }
  @Configuration @EnableAspectJAutoProxy(proxyTargetClass = true) @EnableAsync static class Conf { @Bean CglibTarget c() { return new CglibTarget(); } @Bean A1 a1() { return new A1(); } @Bean A2 a2() { return new A2(); } }
  static String nm(Object o) { return o == null ? "null" : o.getClass().getName().replace("demo.Main$", "").replaceAll("\\$\\$SpringCGLIB\\$\\$\\d+", "·CGLIB").replaceAll("jdk.proxy\\d+.", ""); }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    ProxyFactory jf = new ProxyFactory(new JdkTarget()); jf.setInterfaces(Greeter.class); jf.addAdvice((org.aopalliance.intercept.MethodInterceptor) inv -> inv.proceed()); Object jp = jf.getProxy();
    ProxyFactory cf = new ProxyFactory(new CglibTarget()); cf.setProxyTargetClass(true); cf.addAdvice((org.aopalliance.intercept.MethodInterceptor) inv -> inv.proceed()); Object cp = cf.getProxy();
    // 两层:对 CGLIB 代理再包一层 JDK 代理(用 ProxyFactory 手工叠)
    switch (m) {
      case "unwrap" -> {
        for (Object[] x : new Object[][]{{"JDK 代理", jp}, {"CGLIB 代理", cp}}) { Object p = x[1];
          System.out.println("RES " + x[0] + ":getClass() = " + nm(p) + ";AopUtils.getTargetClass = " + AopUtils.getTargetClass(p).getSimpleName() + ";AopProxyUtils.ultimateTargetClass = " + AopProxyUtils.ultimateTargetClass(p).getSimpleName() + ";ClassUtils.getUserClass = " + ClassUtils.getUserClass(p).getSimpleName());
          Object tgt = ((Advised) p).getTargetSource().getTarget(); System.out.println("RES   ((Advised) proxy).getTargetSource().getTarget() = " + nm(tgt) + ";proxy == target ? " + (p == tgt) + ";isAopProxy(target) = " + AopUtils.isAopProxy(tgt)); }
        // 嵌套: 把 jp 作为目标再代理一层
        ProxyFactory outer = new ProxyFactory(jp); outer.setInterfaces(Greeter.class); outer.addAdvice((org.aopalliance.intercept.MethodInterceptor) inv -> inv.proceed()); Object two = outer.getProxy();
        Object t1 = ((Advised) two).getTargetSource().getTarget(); System.out.println("RES 两层代理:最外层 → getTarget() 得到 " + nm(t1) + "(还是个代理:" + AopUtils.isAopProxy(t1) + ");AopProxyUtils.getSingletonTarget(最外层) = " + nm(AopProxyUtils.getSingletonTarget(two)) + ";ultimateTargetClass = " + AopProxyUtils.ultimateTargetClass(two).getSimpleName() + ";AopUtils.getTargetClass = " + AopUtils.getTargetClass(two).getSimpleName());
        Object t2 = AopProxyUtils.getSingletonTarget(two); Object t3 = AopProxyUtils.getSingletonTarget(t2); System.out.println("RES   getSingletonTarget 连续两次 → " + nm(t3));
      }
      case "anno" -> {
        Object p = cp; Class<?> pc = p.getClass();
        System.out.println("RES CGLIB 代理 " + nm(p) + ":pc.getAnnotation(Tag.class) = " + pc.getAnnotation(Tag.class) + ";pc.isAnnotationPresent(Tag) = " + pc.isAnnotationPresent(Tag.class));
        Tag f1 = AnnotationUtils.findAnnotation(pc, Tag.class); Tag f2 = AnnotatedElementUtils.findMergedAnnotation(pc, Tag.class);
        System.out.println("RES   AnnotationUtils.findAnnotation(pc, Tag.class) = " + (f1 == null ? "null" : "@Tag(" + f1.value() + ")") + ";AnnotatedElementUtils.findMergedAnnotation = " + (f2 == null ? "null" : "@Tag(" + f2.value() + ")") + ";getAnnotation(AopUtils.getTargetClass(p)) = " + AopUtils.getTargetClass(p).getAnnotation(Tag.class));
        Object j = jp; Class<?> jc = j.getClass(); System.out.println("RES JDK 代理 " + nm(j) + ":jc.getAnnotation(Tag.class) = " + jc.getAnnotation(Tag.class) + ";findAnnotation(jc) = " + AnnotationUtils.findAnnotation(jc, Tag.class) + ";findAnnotation(AopUtils.getTargetClass(j)) = " + (AnnotationUtils.findAnnotation(AopUtils.getTargetClass(j), Tag.class) == null ? "null" : "@Tag(" + AnnotationUtils.findAnnotation(AopUtils.getTargetClass(j), Tag.class).value() + ")"));
      }
      case "identity" -> {
        Object t = new CglibTarget(); ProxyFactory f = new ProxyFactory(t); f.setProxyTargetClass(true); Object p1 = f.getProxy(); Object p2 = f.getProxy();
        System.out.println("RES CGLIB 代理:p1.equals(p1) = " + p1.equals(p1) + ";p1.equals(target) = " + p1.equals(t) + ";target.equals(p1) = " + t.equals(p1) + ";p1.hashCode() == target.hashCode() ? " + (p1.hashCode() == t.hashCode()) + ";p1.toString() 以 " + nm(t).substring(0, 11) + " 开头?" + p1.toString().startsWith("demo.Main$CglibTarget@"));
        ProxyFactory jf2 = new ProxyFactory(new JdkTarget()); jf2.setInterfaces(Greeter.class); Object j1 = jf2.getProxy(); Object tt = ((Advised) j1).getTargetSource().getTarget();
        System.out.println("RES JDK 代理:j1.equals(j1) = " + j1.equals(j1) + ";j1.equals(target) = " + j1.equals(tt) + ";j1.hashCode() == target.hashCode() ? " + (j1.hashCode() == tt.hashCode()) + ";HashSet 里放 target 再用 j1 查 contains = " + new HashSet<>(List.of(tt)).contains(j1));
      }
      case "layers" -> {
        AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Object b = c.getBean(CglibTarget.class); Advised ad = (Advised) b;
        System.out.println("RES 同时有两个切面 A1、A2 和 @Async 作用在 CglibTarget 上:Bean 是代理?" + AopUtils.isAopProxy(b) + ";Advised.getAdvisors().length = " + ad.getAdvisors().length + ";advisors = " + Arrays.stream(ad.getAdvisors()).map(a -> nm(a.getAdvice()).replaceAll(".*\\.", "")).toList());
        Object t = ad.getTargetSource().getTarget(); System.out.println("RES   getTarget() = " + nm(t) + "(是代理:" + AopUtils.isAopProxy(t) + ");说明多个切面和 @Async 被合并进了同一个代理对象的拦截链,不是一层套一层");
      }
    }
  }
}
'''
b = sbuild('x28', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): r = srun(b, 'demo.Main', args=[m]); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1200:]]
print('Spring Framework 7.0.9。代理对象与原始对象')
for t_, k_, tt in (('一', 'unwrap', '拿到原始对象的几种办法'), ('二', 'anno', '在代理类上找注解'), ('三', 'identity', '代理对象的 equals / hashCode / toString'), ('四', 'layers', '多个切面和 @Async 是一层还是多层代理')):
    print(f'== {t_}:{tt}'); [print('  ' + l) for l in run(k_)]
