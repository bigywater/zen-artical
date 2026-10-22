import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x87'); CP = scp('org.springframework.boot:spring-boot-starter-data-jpa', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.*; import org.springframework.data.jpa.repository.*; import org.springframework.data.repository.*; import jakarta.persistence.*; import org.springframework.stereotype.Component; import org.springframework.transaction.support.TransactionSynchronizationManager; import org.springframework.aop.framework.Advised; import org.springframework.aop.support.AopUtils; import java.util.*;\n'
FILES = {
 'src/demo/User.java': HDR + '@Entity @Table(name = "users") public class User { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String name; public User() {} public User(String n) { name = n; } public Long getId() { return id; } public String getName() { return name; } }\n',
 'src/demo/UserRepo.java': HDR + '''
public interface UserRepo extends JpaRepository<User, Long>, UserRepoCustom {
  List<User> findByName(String name);
  default String hello() { return "default 方法:" + count(); }
}
''',
 'src/demo/UserRepoCustom.java': HDR + 'public interface UserRepoCustom { String custom(); }\n',
 'src/demo/UserRepoCustomImpl.java': HDR + '@Component("userRepoCustomImpl") public class UserRepoCustomImpl implements UserRepoCustom { public String custom() { Rec.mark("custom"); return "来自 UserRepoCustomImpl"; } }\n',
 'src/demo/Rec.java': HDR + '''
public class Rec {
  static String last = "";
  static void mark(String s) { last = s; Rec.tx(s); }
  static String txInfo() { return "事务激活=" + TransactionSynchronizationManager.isActualTransactionActive() + ",只读=" + TransactionSynchronizationManager.isCurrentTransactionReadOnly(); }
  static final List<String> LOG = new ArrayList<>();
  static void tx(String s) { LOG.add(s + " → " + txInfo()); }
}
''',
 'src/demo/Insp.java': HDR + '''
import org.hibernate.resource.jdbc.spi.StatementInspector; import org.springframework.boot.hibernate.autoconfigure.HibernatePropertiesCustomizer;
@Component public class Insp implements StatementInspector, HibernatePropertiesCustomizer {
  static volatile boolean on; static final List<String> STACKS = new ArrayList<>();
  public String inspect(String sql) { if (on) { String frames = Arrays.stream(new Throwable().getStackTrace()).map(f -> f.getClassName() + "." + f.getMethodName()).filter(n -> n.startsWith("org.springframework.data") || n.startsWith("jdk.proxy") || n.startsWith("org.springframework.aop") || n.startsWith("org.springframework.transaction") || n.startsWith("demo.")).limit(40).reduce((a, b) -> a + " ⇒ " + b).orElse(""); STACKS.add("[" + sql.split(" ")[0] + "] 事务激活=" + TransactionSynchronizationManager.isActualTransactionActive() + ",只读=" + TransactionSynchronizationManager.isCurrentTransactionReadOnly() + " | " + frames); } return sql; }
  public void customize(Map<String, Object> p) { p.put("hibernate.session_factory.statement_inspector", this); }
}
''',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    ConfigurableApplicationContext c = app.run(a); UserRepo repo = c.getBean(UserRepo.class);
    r("== 一:这个 Bean 是什么");
    r("repo.getClass() = " + repo.getClass().getName() + ";AopUtils.isJdkDynamicProxy = " + AopUtils.isJdkDynamicProxy(repo));
    r("实现的接口:" + Arrays.stream(repo.getClass().getInterfaces()).map(Class::getSimpleName).toList());
    Advised adv = (Advised) repo; r("代理的目标对象(Advised.getTargetSource().getTarget()):" + adv.getTargetSource().getTarget().getClass().getName());
    var bd = c.getBeanFactory() instanceof org.springframework.beans.factory.support.DefaultListableBeanFactory f ? f.getBeanDefinition("userRepo") : null; r("BeanDefinition 的类:" + (bd == null ? "?" : bd.getBeanClassName()));
    r("容器里 UserRepo 类型的 Bean 个数:" + c.getBeansOfType(UserRepo.class).size() + ";FactoryBean 的 Bean:" + Arrays.toString(c.getBeanNamesForType(org.springframework.data.repository.core.support.RepositoryFactoryBeanSupport.class)));
    r("== 二:代理上挂了哪些拦截器(Advised.getAdvisors)");
    for (var ad : adv.getAdvisors()) r("  " + ad.getAdvice().getClass().getName().replace("org.springframework.", "…"));
    r("== 三:不同方法的调用栈和事务状态(在 SQL 发出的瞬间取)");
    repo.save(new User("a")); repo.save(new User("b"));
    Insp.on = true;
    String[] names = {"findAll()(继承自 CrudRepository)", "findById(1L)", "save(new User)", "findByName(\\"a\\")(派生查询)", "count()", "custom()(自定义片段 UserRepoCustomImpl)", "hello()(接口 default 方法,里面调 count())"};
    for (int i = 0; i < names.length; i++) {
      Insp.STACKS.clear(); Rec.LOG.clear(); String ret = "";
      switch (i) { case 0 -> repo.findAll(); case 1 -> repo.findById(1L); case 2 -> repo.save(new User("c")); case 3 -> repo.findByName("a"); case 4 -> repo.count(); case 5 -> ret = repo.custom(); default -> ret = repo.hello(); }
      r("  " + names[i] + (ret.isEmpty() ? "" : " → 返回 " + ret) + ":");
      if (Insp.STACKS.isEmpty()) r("    没有发出 SQL");
      for (String s : Insp.STACKS.stream().limit(1).toList()) {
        String head = s.substring(0, s.indexOf(" | ")); String[] fr = s.substring(s.indexOf(" | ") + 3).split(" ⇒ ");
        List<String> key = new ArrayList<>(); for (String f : fr) { String n = f.substring(f.lastIndexOf('.', f.lastIndexOf('.') - 1) + 1); if (f.startsWith("demo.Insp")) continue; if (f.contains("SimpleJpaRepository") || f.contains("QueryExecutorMethodInterceptor.invoke") || f.contains("ImplementationMethodExecutionInterceptor") || f.contains("TransactionInterceptor") || f.contains("JdkDynamicAopProxy") || f.contains("AbstractJpaQuery.execute") || f.contains("DefaultMethodInvokingMethodInterceptor.invoke") || f.contains("PartTreeJpaQuery") || f.contains("jdk.proxy") || f.contains("RepositoryFragmentMethodInvoker")) if (!key.contains(n)) key.add(n); }
        r("    SQL 发出时:" + head); r("    调用栈里的关键帧(从里到外):" + key);
      }
      for (String s : Rec.LOG) r("    自定义方法体里的事务状态:" + s);
    }
    Insp.on = false;
    r("== 四:没有事务的调用方直接调用,事务状态");
    r("  外面(调用方)当前:" + Rec.txInfo());
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x87', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x87'); URL = jdbc(my)
r = srun(b, 'demo.Main', props={'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app', 'spring.jpa.hibernate.ddl-auto': 'create'}, timeout=120)
L = res(r)
print('Spring Boot 4.0.8 / Hibernate 7(随 starter)/ MySQL 26.7.0(自己起的实例)/ JDK 21;一个实体 User、一个 UserRepo(extends JpaRepository,含派生查询、default 方法和自定义片段)')
for l in L: print(l)
if not L: print(r['out'][-2500:])
my.stop()
