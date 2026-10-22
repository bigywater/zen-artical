import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x2'); CP = scp('org.springframework.boot:spring-boot-starter')
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.beans.factory.config.*; import org.springframework.beans.factory.support.*; import org.springframework.beans.MutablePropertyValues;
import org.springframework.context.annotation.AnnotationConfigApplicationContext; import org.springframework.context.annotation.Bean; import org.springframework.context.annotation.Configuration; import org.springframework.stereotype.Component;
public class Main {
  public static class Greeter { String greeting = "default"; public void setGreeting(String g) { greeting = g; } public void init() { }
    public String toString() { return "Greeter(" + greeting + ")#" + Integer.toHexString(System.identityHashCode(this)).substring(0, 3); } }
  @Component public static class Scanned { }
  @Configuration public static class Conf { @Bean(initMethod = "init") public Greeter viaBean() { Greeter g = new Greeter(); g.setGreeting("来自 @Bean"); return g; } }
  static String d(DefaultListableBeanFactory bf, String n) {
    BeanDefinition bd = bf.getBeanDefinition(n);
    return String.format("%-10s 定义类型=%s 类=%s scope=%s lazy=%s factoryMethod=%s 来源=%s", n, bd.getClass().getSimpleName(), bd.getBeanClassName() == null ? "null" : bd.getBeanClassName().replace("demo.", ""), bd.getScope().isEmpty() ? "(空=singleton)" : bd.getScope(), bd.isLazyInit(), bd.getFactoryMethodName(), String.valueOf(bd.getResourceDescription()).replaceAll(".*[/\\[]", "").replaceAll("\\]$", ""));
  }
  public static void main(String[] args) throws Exception {
    String mode = args[0];
    if (mode.equals("src")) {
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(); DefaultListableBeanFactory bf = c.getDefaultListableBeanFactory();
      GenericBeanDefinition g = new GenericBeanDefinition(); g.setBeanClass(Greeter.class); g.setInitMethodName("init"); g.getPropertyValues().add("greeting", "手写的定义"); g.setLazyInit(true);
      bf.registerBeanDefinition("manual", g);
      c.scan("demo"); c.refresh();
      for (String n : new String[]{"manual", "main.Scanned", "main.Conf", "viaBean"}) System.out.println("RES " + d(bf, n));
      System.out.println("RES 创建之前 manual 的单例已创建吗?" + bf.containsSingleton("manual") + "(lazy=true);getBean 之后 " + c.getBean("manual") + " 已创建=" + bf.containsSingleton("manual"));
      System.out.println("RES viaBean 的实例:" + c.getBean("viaBean") + ";@Bean 的 initMethod 属性在定义里:" + bf.getBeanDefinition("viaBean").getInitMethodName());
    } else if (mode.equals("bfpp")) {
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(); DefaultListableBeanFactory bf = c.getDefaultListableBeanFactory();
      GenericBeanDefinition g = new GenericBeanDefinition(); g.setBeanClass(Greeter.class); g.getPropertyValues().add("greeting", "原值"); bf.registerBeanDefinition("g", g);
      c.addBeanFactoryPostProcessor(f -> { BeanDefinition bd = f.getBeanDefinition("g"); System.out.println("RES BFPP 看到的定义:scope=" + (bd.getScope().isEmpty() ? "singleton" : bd.getScope()) + " greeting=" + bd.getPropertyValues().get("greeting"));
        ((MutablePropertyValues) bd.getPropertyValues()).add("greeting", "被 BFPP 改过"); bd.setScope("prototype"); });
      c.refresh();
      Object a = c.getBean("g"), b = c.getBean("g"); System.out.println("RES refresh 之后两次 getBean:" + a + " 与 " + b + ";同一个对象?" + (a == b) + "(定义里的 scope 被改成了 prototype)");
    } else if (mode.equals("merge")) {
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(); DefaultListableBeanFactory bf = c.getDefaultListableBeanFactory();
      GenericBeanDefinition parent = new GenericBeanDefinition(); parent.setBeanClass(Greeter.class); parent.setAbstract(true); parent.setInitMethodName("init"); parent.getPropertyValues().add("greeting", "父定义的值"); bf.registerBeanDefinition("parentDef", parent);
      GenericBeanDefinition child = new GenericBeanDefinition(); child.setParentName("parentDef"); bf.registerBeanDefinition("child", child);
      GenericBeanDefinition child2 = new GenericBeanDefinition(); child2.setParentName("parentDef"); child2.getPropertyValues().add("greeting", "子定义覆盖"); bf.registerBeanDefinition("child2", child2);
      c.refresh();
      BeanDefinition m = bf.getMergedBeanDefinition("child");
      System.out.println("RES child 自己的定义:beanClassName=" + bf.getBeanDefinition("child").getBeanClassName() + " initMethod=" + bf.getBeanDefinition("child").getInitMethodName() + " 属性数=" + bf.getBeanDefinition("child").getPropertyValues().size());
      System.out.println("RES child 合并后:类=" + m.getBeanClassName().replace("demo.", "") + " initMethod=" + m.getInitMethodName() + " greeting=" + m.getPropertyValues().get("greeting") + ";合并后的类型 " + m.getClass().getSimpleName());
      System.out.println("RES getBean(child)=" + c.getBean("child") + " getBean(child2)=" + c.getBean("child2"));
      try { c.getBean("parentDef"); } catch (Exception e) { System.out.println("RES getBean(abstract 的 parentDef):" + e.getClass().getSimpleName()); }
      System.out.println("RES 容器里 Greeter 类型的 Bean 个数:" + c.getBeansOfType(Greeter.class).size() + "(abstract 的定义不会被创建)");
    } else if (mode.equals("boot")) {
      org.springframework.boot.SpringApplication app = new org.springframework.boot.SpringApplication(Conf.class); app.setWebApplicationType(org.springframework.boot.WebApplicationType.NONE); app.setBannerMode(org.springframework.boot.Banner.Mode.OFF);
      org.springframework.context.ConfigurableApplicationContext c = app.run(); System.out.println("RES SpringApplication 创建的上下文(" + c.getClass().getSimpleName() + ")的 isAllowBeanDefinitionOverriding = " + ((DefaultListableBeanFactory) c.getBeanFactory()).isAllowBeanDefinitionOverriding()); c.close();
    } else if (mode.equals("override")) {
      boolean dflt = args[1].equals("default"); boolean allow = dflt ? true : Boolean.parseBoolean(args[1]);
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(); DefaultListableBeanFactory bf = c.getDefaultListableBeanFactory(); if (!dflt) bf.setAllowBeanDefinitionOverriding(allow); else System.out.println("RES 纯 Spring Framework 的 DefaultListableBeanFactory 默认 isAllowBeanDefinitionOverriding = " + bf.isAllowBeanDefinitionOverriding());
      GenericBeanDefinition a = new GenericBeanDefinition(); a.setBeanClass(Greeter.class); a.getPropertyValues().add("greeting", "第一个"); bf.registerBeanDefinition("dup", a);
      GenericBeanDefinition b2 = new GenericBeanDefinition(); b2.setBeanClass(Greeter.class); b2.getPropertyValues().add("greeting", "第二个"); 
      try { bf.registerBeanDefinition("dup", b2); c.refresh(); System.out.println("RES allowBeanDefinitionOverriding=" + allow + ":没有报错,getBean(dup)=" + c.getBean("dup")); }
      catch (Exception e) { System.out.println("RES allowBeanDefinitionOverriding=" + allow + ":" + e.getClass().getSimpleName() + ": " + e.getMessage().split("\n")[0]); }
    }
  }
}
'''
b = sbuild('x2', {'src/demo/Main.java': MAIN}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(*a):
    r = srun(b, 'demo.Main', args=list(a)); return res(r), r
print('Spring Framework 7.0.9 的 AnnotationConfigApplicationContext。用代码直接读 BeanDefinition 的各个属性,不创建 Bean 就能看到的东西')
print('== 一:三种来源的 BeanDefinition。(1)手写 GenericBeanDefinition 注册(lazy、init-method、属性值);(2)@Component 经 scan 扫描得到;(3)@Configuration 里的 @Bean 方法')
L, r = run('src'); [print('  ' + l) for l in L]
print('== 二:创建之前能改。BeanFactoryPostProcessor 在 Bean 创建之前拿到定义:把属性值 greeting 改掉,并把 scope 改成 prototype')
L, r = run('bfpp'); [print('  ' + l) for l in L]
print('== 三:定义合并。abstract 的 parentDef(init-method=init,greeting=父定义的值);child 只写 parentName;child2 写了 parentName 并覆盖 greeting')
L, r = run('merge'); [print('  ' + l) for l in L]
print('== 四:同名的 BeanDefinition 注册两次。allowBeanDefinitionOverriding=true与 false,另外读出两种上下文各自的默认值')
L, r = run('override', 'default'); [print('  ' + l) for l in L if l.startswith('纯')]
for v in ('true', 'false'): L, r = run('override', v); [print('  ' + l) for l in L]
L, r = run('boot'); [print('  ' + l) for l in L]
print('  纯 Spring Framework 里后注册的定义悄悄覆盖前面的;SpringApplication 创建的上下文把它设成 false(上面最后一行是实际读出来的值)')
