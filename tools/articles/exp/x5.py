import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x5'); CP = scp('org.springframework.boot:spring-boot-starter')
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.beans.factory.*; import org.springframework.beans.factory.annotation.*; import org.springframework.context.annotation.*; import org.springframework.core.annotation.Order;
import jakarta.annotation.Priority;
public class Main {
  public interface Pay { String name(); }
  public static class Alipay implements Pay { public String name() { return "alipay"; } }
  public static class Wechat implements Pay { public String name() { return "wechat"; } }
  public static class Dep { }
  // ---- 一 注入方式 ----
  public static class Ctor { final Dep d; public Ctor(Dep d) { this.d = d; } String ok() { return d == null ? "d=null" : "d 非 null"; } }
  public static class Setter { Dep d; @Autowired public void setD(Dep d) { this.d = d; } String ok() { return d == null ? "d=null" : "d 非 null"; } }
  public static class Field { @Autowired Dep d; String ok() { return d == null ? "d=null" : "d 非 null"; } }
  @Configuration static class C1 { @Bean Dep dep() { return new Dep(); } @Bean Ctor ctor(Dep d) { return new Ctor(d); } @Bean Setter setter() { return new Setter(); } @Bean Field field() { return new Field(); } }
  // ---- 二 多候选 ----
  @Configuration static class Two { @Bean Pay alipay() { return new Alipay(); } @Bean Pay wechat() { return new Wechat(); } }
  public static class NoHint { public NoHint(Pay pay) { } }
  public static class ByName { public ByName(Pay alipay) { System.out.println("RES   参数名 alipay → " + alipay.name()); } }
  public static class ByQual { public ByQual(@Qualifier("wechat") Pay p) { System.out.println("RES   @Qualifier(\"wechat\") → " + p.name()); } }
  public static class ByList { public ByList(List<Pay> ps, Map<String, Pay> m) { System.out.println("RES   List<Pay> → " + ps.stream().map(Pay::name).toList() + ";Map<String,Pay> 的键 → " + m.keySet()); } }
  @Configuration static class WithPrimary { @Bean Pay alipay() { return new Alipay(); } @Bean @Primary Pay wechat() { return new Wechat(); } @Bean ByPrim byPrim(Pay p) { return new ByPrim(p); } }
  public static class ByPrim { public ByPrim(Pay p) { System.out.println("RES   @Primary(wechat 标了) → " + p.name()); } }
  @Configuration static class TwoPrimary { @Bean @Primary Pay alipay() { return new Alipay(); } @Bean @Primary Pay wechat() { return new Wechat(); } @Bean NoHint noHint(Pay p) { return new NoHint(p); } }
  @Configuration static class Ordered2 { @Bean @Order(2) Pay alipay() { return new Alipay(); } @Bean @Order(1) Pay wechat() { return new Wechat(); } @Bean ByList byList(List<Pay> ps, Map<String, Pay> m) { return new ByList(ps, m); } }
  @Configuration static class PrioConf { @Bean Pay alipay() { return new PrioAli(); } @Bean Pay wechat() { return new PrioWe(); } @Bean NoHint2 n(Pay p) { return new NoHint2(p); } }
  @Priority(1) public static class PrioAli extends Alipay { } @Priority(5) public static class PrioWe extends Wechat { }
  public static class NoHint2 { public NoHint2(Pay p) { System.out.println("RES   @Priority(1) 的 alipay vs @Priority(5) 的 wechat,按类型注入 → " + p.name()); } }
  // ---- 五 没有候选 ----
  public static class NeedsPay { public NeedsPay(Pay p) { } }
  public static class NeedsList { public NeedsList(List<Pay> p) { System.out.println("RES   List<Pay> 没有候选 → size=" + p.size()); } }
  public static class OptDep { public OptDep(Optional<Pay> p, ObjectProvider<Pay> op) { System.out.println("RES   Optional<Pay> → isPresent=" + p.isPresent() + ";ObjectProvider.getIfAvailable → " + op.getIfAvailable()); } }
  public static class NotReq { @Autowired(required = false) Pay p; @Autowired(required = false) public void setP2(Pay p2) { } public String toString() { return "字段 p=" + p; } }
  @Configuration static class Empty1 { @Bean NeedsPay n(Pay p) { return new NeedsPay(p); } } @Configuration static class Empty2 { @Bean NeedsList n(List<Pay> p) { return new NeedsList(p); } }
  @Configuration static class Empty3 { @Bean OptDep o(Optional<Pay> p, ObjectProvider<Pay> op) { return new OptDep(p, op); } @Bean NotReq nr() { return new NotReq(); } }
  // ---- 四 泛型 ----
  public interface Repo<T> { String of(); }
  public static class UserRepo implements Repo<String> { public String of() { return "String 仓库"; } }
  public static class IntRepo implements Repo<Integer> { public String of() { return "Integer 仓库"; } }
  public static class GenUse { public GenUse(Repo<Integer> r, Repo<String> s) { System.out.println("RES   Repo<Integer> → " + r.of() + ";Repo<String> → " + s.of()); } }
  @Configuration static class Gen { @Bean UserRepo u() { return new UserRepo(); } @Bean IntRepo i() { return new IntRepo(); } @Bean GenUse g(Repo<Integer> r, Repo<String> s) { return new GenUse(r, s); } }
  static void run(String label, Class<?>... cs) {
    try { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(cs); c.close(); }
    catch (Exception e) { Throwable t = e; while (t.getCause() != null) t = t.getCause(); System.out.println("RES   " + label + " → " + t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).split("\n")[0].replace("demo.Main$", "")); }
  }
  public static void main(String[] args) {
    String m = args[0];
    if (m.equals("styles")) {
      AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(C1.class);
      System.out.println("RES 容器里:构造器注入 " + c.getBean(Ctor.class).ok() + ";setter 注入 " + c.getBean(Setter.class).ok() + ";字段注入 " + c.getBean(Field.class).ok());
      System.out.println("RES 脱离容器直接 new:new Setter() → " + new Setter().ok() + ";new Field() → " + new Field().ok() + ";Ctor 没有无参构造器,必须把 Dep 传进去才能 new,所以不会出现“忘了注入”");
    } else if (m.equals("multi")) {
      System.out.println("RES (a) 两个 Pay,按类型注入,没有任何提示:"); run("NoHint", Two.class, NoHintCfg.class);
      System.out.println("RES (b) 参数名等于 Bean 名(需要 javac -parameters,本实验已加):"); run("ByName", Two.class, ByNameCfg.class);
      System.out.println("RES (c) @Qualifier:"); run("ByQual", Two.class, ByQualCfg.class);
      System.out.println("RES (d) List<Pay> 与 Map<String,Pay>:"); run("ByList", Two.class, ByListCfg.class);
      System.out.println("RES (e) @Primary:"); run("Primary", WithPrimary.class);
      System.out.println("RES (f) 两个都是 @Primary:"); run("TwoPrimary", TwoPrimary.class);
      System.out.println("RES (g) @Order(2) 的 alipay 与 @Order(1) 的 wechat:"); run("Ordered2", Ordered2.class);
      System.out.println("RES (h) @Priority:"); run("Prio", PrioConf.class);
    } else if (m.equals("empty")) {
      System.out.println("RES (a) 构造器参数 Pay,没有任何候选:"); run("NeedsPay", Empty1.class);
      System.out.println("RES (b) 参数 List<Pay>,没有任何候选:"); run("NeedsList", Empty2.class);
      System.out.println("RES (c) Optional / ObjectProvider / required=false:"); try { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Empty3.class); System.out.println("RES   " + c.getBean(NotReq.class)); } catch (Exception e) { System.out.println("RES   异常 " + e); }
    } else if (m.equals("generic")) { run("Gen", Gen.class); }
  }
  @Configuration static class NoHintCfg { @Bean NoHint n(Pay pay) { return new NoHint(pay); } }
  @Configuration static class ByNameCfg { @Bean ByName n(Pay alipay) { return new ByName(alipay); } }
  @Configuration static class ByQualCfg { @Bean ByQual n(@Qualifier("wechat") Pay p) { return new ByQual(p); } }
  @Configuration static class ByListCfg { @Bean ByList n(List<Pay> ps, Map<String, Pay> m) { return new ByList(ps, m); } }
}
'''
b = sbuild('x5', {'src/demo/Main.java': MAIN}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): return res(srun(b, 'demo.Main', args=[m]))
print('Spring Framework 7.0.9(javac 加了 -parameters)。依赖注入的几种写法与候选的解析')
print('== 一:三种注入方式。同一个 Dep 分别用构造器、@Autowired setter、@Autowired 字段注入;再看脱离容器(自己 new)时会怎样')
[print('  ' + l) for l in run('styles')]
print('== 二:同一个类型有两个候选(alipay 与 wechat 都是 Pay)。按类型注入一个 Pay 时的各种情况')
[print('  ' + l) for l in run('multi')]
print('== 三:没有候选时')
[print('  ' + l) for l in run('empty')]
print('== 四:泛型作为限定:两个 Repo<T> 的实现')
[print('  ' + l) for l in run('generic')]
