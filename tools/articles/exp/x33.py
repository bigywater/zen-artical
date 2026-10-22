import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x33'); CP = scp('org.springframework.boot:spring-boot-starter-data-jpa', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*; import javax.sql.DataSource;
import jakarta.persistence.*;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.orm.jpa.*; import org.springframework.orm.jpa.vendor.HibernateJpaVendorAdapter;
import org.springframework.context.annotation.*; import org.springframework.transaction.annotation.*; import org.springframework.transaction.support.TransactionSynchronizationManager;
public class Main {
  @Entity(name = "Acct") @Table(name = "acct") public static class Acct { @Id public Long id; public int balance; public Acct() { } Acct(Long id, int b) { this.id = id; this.balance = b; } }
  public static class Svc {
    @PersistenceContext EntityManager em; final JdbcTemplate jt; Svc(JdbcTemplate jt) { this.jt = jt; }
    @Transactional(readOnly = true) public int readOnlyRead() { return jt.queryForObject("select balance from acct where id = 1", Integer.class); }
    @Transactional(readOnly = true) public void readOnlyWriteJdbc() { jt.update("update acct set balance = 999 where id = 1"); }
    @Transactional public void rwWriteJdbc() { jt.update("update acct set balance = 500 where id = 1"); }
    @Transactional(readOnly = true) public void roModifyEntity() { Acct a = em.find(Acct.class, 1L); a.balance = 777; }
    @Transactional public void rwModifyEntity() { Acct a = em.find(Acct.class, 1L); a.balance = 777; }
    @Transactional(readOnly = true) public void roModifyThenFlush() { Acct a = em.find(Acct.class, 1L); a.balance = 777; em.flush(); }
    @Transactional(readOnly = true) public String roFlag() { return "readOnly=" + TransactionSynchronizationManager.isCurrentTransactionReadOnly(); }
    @Transactional public String innerRoInsideRw(Svc proxy) { proxy.roInner(); return "外层读写,里层 readOnly=true 的方法写成功了"; }
    @Transactional(readOnly = true) public void roInner() { jt.update("update acct set balance = 321 where id = 1"); }
    public int balance() { return jt.queryForObject("select balance from acct where id = 1", Integer.class); }
  }
  @Configuration @EnableTransactionManagement(proxyTargetClass = true) static class Conf {
    @Bean DataSource ds() { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(4); return d; }
    @Bean JdbcTemplate jt(DataSource ds) { return new JdbcTemplate(ds); }
    @Bean LocalContainerEntityManagerFactoryBean emf(DataSource ds) { LocalContainerEntityManagerFactoryBean f = new LocalContainerEntityManagerFactoryBean(); f.setDataSource(ds); f.setPackagesToScan("demo"); f.setJpaVendorAdapter(new HibernateJpaVendorAdapter()); f.setJpaPropertyMap(Map.of("hibernate.hbm2ddl.auto", "create", "hibernate.dialect", "org.hibernate.dialect.MySQLDialect")); return f; }
    @Bean JpaTransactionManager tm(jakarta.persistence.EntityManagerFactory emf) { return new JpaTransactionManager(emf); }
    @Bean Svc svc(JdbcTemplate jt) { return new Svc(jt); } }
  interface Call { Object run() throws Exception; }
  static String t(Call c) { try { Object o = c.run(); return o == null ? "成功" : "成功,返回 " + o; } catch (Throwable e) { Throwable r = e; while (r.getCause() != null) r = r.getCause(); return "失败 " + e.getClass().getSimpleName() + " ← " + r.getClass().getSimpleName() + ": " + String.valueOf(r.getMessage()).split("\n")[0]; } }
  static List<String> glog(JdbcTemplate jt) { return jt.query("select thread_id, argument from mysql.general_log where command_type = 'Query' and argument not like '%general_log%' and argument not like '%connection_id%' order by event_time, thread_id", (rs, i) -> rs.getString(1) + "|" + rs.getString(2).replaceAll("\\s+", " ")); }
  public static void main(String[] args) throws Exception {
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Svc s = c.getBean(Svc.class); JdbcTemplate jt = c.getBean(JdbcTemplate.class); String m = args[0];
    jt.update("delete from acct"); jt.update("insert into acct(id, balance) values (1, 100)");
    jt.execute("set global general_log = 'ON'"); jt.execute("set global log_output = 'TABLE'");
    switch (m) {
      case "jdbc" -> {
        jt.execute("truncate mysql.general_log"); s.readOnlyRead(); Thread.sleep(200); List<String> g = glog(jt); String th = g.stream().filter(x -> x.contains("select balance")).findFirst().get().split("\\|")[0]; System.out.println("RES readOnly = true 的方法执行时,那个连接上的语句:"); g.stream().filter(x -> x.startsWith(th + "|")).forEach(x -> System.out.println("RES   " + x.substring(x.indexOf('|') + 1)));
        System.out.println("RES readOnly = true 里用 JdbcTemplate 写:" + t(() -> { s.readOnlyWriteJdbc(); return null; }) + ";表里 balance = " + s.balance());
        System.out.println("RES readOnly = false(默认)里用 JdbcTemplate 写:" + t(() -> { s.rwWriteJdbc(); return null; }) + ";表里 balance = " + s.balance());
      }
      case "jpa" -> {
        s.roModifyEntity(); System.out.println("RES readOnly = true:修改受管实体 a.balance = 777,事务结束 → 表里 balance = " + s.balance() + "(100 表示没有写进去)");
        jt.update("update acct set balance = 100 where id = 1"); jt.execute("truncate mysql.general_log"); s.roModifyEntity(); Thread.sleep(200); List<String> g = glog(jt); System.out.println("RES   这次的 SQL 里有 UPDATE 吗?" + g.stream().anyMatch(x -> x.toLowerCase().contains("update acct")));
        jt.update("update acct set balance = 100 where id = 1"); jt.execute("truncate mysql.general_log"); s.rwModifyEntity(); Thread.sleep(200); g = glog(jt); System.out.println("RES readOnly = false:同样的修改 → 表里 balance = " + s.balance() + ";SQL 里有 UPDATE 吗?" + g.stream().anyMatch(x -> x.toLowerCase().contains("update acct")));
        jt.update("update acct set balance = 100 where id = 1"); System.out.println("RES readOnly = true 里修改实体后手动 em.flush():" + t(() -> { s.roModifyThenFlush(); return null; }) + ";表里 balance = " + s.balance());
      }
      case "join" -> { System.out.println("RES 外层读写事务里调用 readOnly = true 的内层方法(REQUIRED 加入外层事务):" + t(() -> s.innerRoInsideRw(s)) + ";表里 balance = " + s.balance()+ ";(内层方法是经过代理调用的,不是自调用)"); System.out.println("RES 单独调用 readOnly = true 的 roFlag():" + s.roFlag()); }
    }
    c.close(); System.exit(0);
  }
}
'''
b = sbuild('x33', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x33'); URL = jdbc(my)
def run(m): r = srun(b, 'demo.Main', args=[m], props={'url': URL}, timeout=180); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1500:]]
print('Spring Framework 7.0.9 + Hibernate(Boot 4.0.8 的 BOM 带的版本)+ MySQL 26.7.0。@Transactional(readOnly = true) 到底做了什么')
print('== 一:JDBC 一侧(这个例子的事务管理器是 JpaTransactionManager,JdbcTemplate 用的是同一个事务里的连接)。readOnly 方法在连接上留下什么语句;在里面用 JdbcTemplate 写会怎样')
[print('  ' + l) for l in run('jdbc')]
print('== 二:JPA / Hibernate。readOnly = true 里修改受管实体')
[print('  ' + l) for l in run('jpa')]
print('== 三:加入外层事务')
[print('  ' + l) for l in run('join')]
my.stop()
