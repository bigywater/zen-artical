import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x36'); CP = scp('org.springframework.boot:spring-boot-starter-data-jpa', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*; import javax.sql.DataSource;
import jakarta.persistence.*;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.jdbc.datasource.DataSourceTransactionManager; import org.springframework.orm.jpa.*; import org.springframework.orm.jpa.vendor.HibernateJpaVendorAdapter;
import org.springframework.context.annotation.*; import org.springframework.transaction.*; import org.springframework.transaction.annotation.*;
public class Main {
  @Entity(name = "Acct") @Table(name = "acct") public static class Acct { @Id public Long id; public int balance; public Acct() { } }
  public static class Inner { final JdbcTemplate jt; Inner(JdbcTemplate jt) { this.jt = jt; }
    @Transactional(propagation = Propagation.NESTED) public void nested(boolean fail) { jt.update("insert into t(v) values ('inner')"); if (fail) throw new IllegalStateException("inner 失败"); }
    @Transactional(propagation = Propagation.REQUIRED) public void required() { jt.update("insert into t(v) values ('inner')"); } }
  public static class Outer { final JdbcTemplate jt; final Inner inner; Outer(JdbcTemplate jt, Inner inner) { this.jt = jt; this.inner = inner; }
    @Transactional public void run(boolean innerFail) { jt.update("insert into t(v) values ('outer-1')"); try { inner.nested(innerFail); } catch (Exception e) { } jt.update("insert into t(v) values ('outer-2')"); }
    @Transactional public void loopNested(int n) { for (int i = 0; i < n; i++) inner.nested(false); }
    @Transactional public void loopRequired(int n) { for (int i = 0; i < n; i++) inner.required(); } }
  public static class JpaInner { @PersistenceContext EntityManager em; @Transactional(propagation = Propagation.NESTED) public void nested() { Acct a = new Acct(); a.id = 1L; em.persist(a); } }
  public static class JpaOuter { final JpaInner inner; JpaOuter(JpaInner inner) { this.inner = inner; } @Transactional public void run() { inner.nested(); } }
  @Configuration @EnableTransactionManagement(proxyTargetClass = true) static class Conf {
    @Bean DataSource ds() { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(4); return d; }
    @Bean JdbcTemplate jt(DataSource ds) { return new JdbcTemplate(ds); } @Bean DataSourceTransactionManager tm(DataSource ds) { return new DataSourceTransactionManager(ds); } @Bean Inner inner(JdbcTemplate jt) { return new Inner(jt); } @Bean Outer outer(JdbcTemplate jt, Inner inner) { return new Outer(jt, inner); } }
  @Configuration @EnableTransactionManagement(proxyTargetClass = true) static class JpaConf {
    @Bean DataSource ds() { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(4); return d; }
    @Bean LocalContainerEntityManagerFactoryBean emf(DataSource ds) { LocalContainerEntityManagerFactoryBean f = new LocalContainerEntityManagerFactoryBean(); f.setDataSource(ds); f.setPackagesToScan("demo"); f.setJpaVendorAdapter(new HibernateJpaVendorAdapter()); f.setJpaPropertyMap(Map.of("hibernate.hbm2ddl.auto", "create", "hibernate.dialect", "org.hibernate.dialect.MySQLDialect")); return f; }
    @Bean JpaTransactionManager tm(jakarta.persistence.EntityManagerFactory emf) { JpaTransactionManager t = new JpaTransactionManager(emf); t.setNestedTransactionAllowed(Boolean.getBoolean("nested")); return t; }
    @Bean JpaInner inner() { return new JpaInner(); } @Bean JpaOuter outer(JpaInner i) { return new JpaOuter(i); } }
  static String rows(JdbcTemplate jt) { List<String> r = jt.queryForList("select v from t order by id", String.class); return r.isEmpty() ? "(空)" : String.join("+", r); }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    if (m.equals("jpa")) { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(JpaConf.class); try { c.getBean(JpaOuter.class).run(); System.out.println("RES JpaTransactionManager + setNestedTransactionAllowed(" + Boolean.getBoolean("nested") + ") + NESTED:调用成功"); } catch (Throwable e) { Throwable r = e; while (r.getCause() != null) r = r.getCause(); System.out.println("RES JpaTransactionManager(setNestedTransactionAllowed(" + Boolean.getBoolean("nested") + "))+ Hibernate 里调用 NESTED 方法 → " + e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()).split("\n")[0]); } c.close(); System.exit(0); }
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Outer o = c.getBean(Outer.class); JdbcTemplate jt = c.getBean(JdbcTemplate.class); jt.execute("create table if not exists t(id int auto_increment primary key, v varchar(10)) engine=innodb"); jt.update("truncate t");
    switch (m) {
      case "log" -> { jt.execute("set global general_log = 'ON'"); jt.execute("set global log_output = 'TABLE'");
        for (boolean fail : new boolean[]{false, true}) { jt.update("truncate t"); jt.execute("truncate mysql.general_log"); o.run(fail); Thread.sleep(200);
          List<String> g = jt.query("select thread_id, argument from mysql.general_log where command_type = 'Query' and argument not like '%general_log%' order by event_time, thread_id", (rs, i) -> rs.getString(1) + "|" + rs.getString(2).replaceAll("\\s+", " ")); String th = g.stream().filter(x -> x.contains("outer-1")).findFirst().get().split("\\|")[0];
          System.out.println("RES inner " + (fail ? "失败" : "成功") + ":提交后表里的行 " + rows(jt) + ";那个连接上的语句:"); g.stream().filter(x -> x.startsWith(th + "|")).forEach(x -> System.out.println("RES   " + x.substring(x.indexOf('|') + 1))); } }
      case "cost" -> { int n = 2000; for (int i = 0; i < 3; i++) { o.loopRequired(50); o.loopNested(50); } jt.update("truncate t"); long t0 = System.nanoTime(); o.loopRequired(n); double r = (System.nanoTime() - t0) / 1e6; jt.update("truncate t"); t0 = System.nanoTime(); o.loopNested(n); double ne = (System.nanoTime() - t0) / 1e6;
        System.out.println(String.format("RES 一个事务里调用内层方法 %d 次:REQUIRED %.0f ms(每次 %.0f µs);NESTED %.0f ms(每次 %.0f µs)", n, r, r * 1000 / n, ne, ne * 1000 / n)); }
    }
    c.close(); System.exit(0);
  }
}
'''
b = sbuild('x36', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x36'); URL = jdbc(my)
def run(m): r = srun(b, 'demo.Main', args=[m], props={'url': URL}, timeout=180); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1500:]]
print('Spring Framework 7.0.9 + MySQL 26.7.0。嵌套事务 NESTED 与 JDBC Savepoint')
print('== 一:inner 成功 / 失败时 MySQL 那个连接上的语句(outer 先插 outer-1,调 NESTED 的 inner,再插 outer-2;inner 失败被 outer 捕获)')
[print('  ' + l) for l in run('log')]
print('== 二:NESTED 每次要多花多少。一个事务里调用内层方法 2000 次(REQUIRED 与 NESTED),各跑 3 次')
for _ in range(3): [print('  ' + l) for l in run('cost')]
print('== 三:JpaTransactionManager 能不能用 NESTED')
[print('  ' + l) for l in run('jpa')]
r = srun(b, 'demo.Main', args=['jpa'], props={'url': URL, 'nested': 'true'}, timeout=180); [print('  ' + l[4:]) for l in r['out'].splitlines() if l.startswith('RES ')] or print(r['out'][-800:])
my.stop()
