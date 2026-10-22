import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x37'); CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*; import javax.sql.DataSource;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.context.annotation.*; import org.springframework.transaction.*; import org.springframework.transaction.annotation.*; import org.springframework.transaction.support.*;
public class Main {
  public static class Svc {
    final JdbcTemplate a, b; final TransactionTemplate ttA, ttB; final DataSource dsA;
    Svc(JdbcTemplate a, JdbcTemplate b, TransactionTemplate ttA, TransactionTemplate ttB, DataSource dsA) { this.a = a; this.b = b; this.ttA = ttA; this.ttB = ttB; this.dsA = dsA; }
    void insA() { a.update("insert into t(v) values ('A')"); } void insB() { b.update("insert into t(v) values ('B')"); }
    public void killBLast() { ttB.executeWithoutResult(sb -> { insB(); Long id = b.queryForObject("select connection_id()", Long.class); ttA.executeWithoutResult(sa -> insA()); Main.killConn(id); }); }
    @Transactional("txA") public void declarative(boolean fail) { insA(); insB(); if (fail) throw new IllegalStateException("业务失败"); }
    public void nested(boolean failAfterInner) { ttA.executeWithoutResult(sa -> { insA(); ttB.executeWithoutResult(sb -> insB()); if (failAfterInner) throw new IllegalStateException("内层 B 已经提交之后,外层 A 抛异常"); }); }
    public void killBeforeCommit() { ttA.executeWithoutResult(sa -> { insA(); Long id = a.queryForObject("select connection_id()", Long.class); ttB.executeWithoutResult(sb -> insB()); Main.killConn(id); }); }
    public void killBeforeCommitReverse() { ttB.executeWithoutResult(sb -> { insB(); ttA.executeWithoutResult(sa -> { insA(); Long id = a.queryForObject("select connection_id()", Long.class); Main.killConn(id); }); }); }
  }
  static JdbcTemplate admin;
  static void killConn(Long id) { admin.execute("kill " + id); }
  @Configuration @EnableTransactionManagement(proxyTargetClass = true) static class Conf {
    HikariDataSource mk(String db) { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url").replace("/demo?", "/" + db + "?")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(4); return d; }
    @Bean(name = "dsA") DataSource dsA() { return mk("demo"); } @Bean(name = "dsB") DataSource dsB() { return mk("demo2"); }
    @Bean JdbcTemplate jtA(DataSource dsA) { return new JdbcTemplate(dsA); } @Bean JdbcTemplate jtB(DataSource dsB) { return new JdbcTemplate(dsB); }
    @Bean(name = "txA") DataSourceTransactionManager txA(DataSource dsA) { return new DataSourceTransactionManager(dsA); } @Bean(name = "txB") DataSourceTransactionManager txB(DataSource dsB) { return new DataSourceTransactionManager(dsB); }
    @Bean Svc svc(JdbcTemplate jtA, JdbcTemplate jtB, DataSource dsA, @org.springframework.beans.factory.annotation.Qualifier("txA") DataSourceTransactionManager txA, @org.springframework.beans.factory.annotation.Qualifier("txB") DataSourceTransactionManager txB) { return new Svc(jtA, jtB, new TransactionTemplate(txA), new TransactionTemplate(txB), dsA); } }
  interface Call { void run() throws Exception; }
  static void t(JdbcTemplate a, JdbcTemplate b, String label, Call c) { a.update("truncate t"); b.update("truncate t"); String ex; try { c.run(); ex = "正常返回"; } catch (Throwable e) { Throwable r = e; while (r.getCause() != null) r = r.getCause(); ex = e.getClass().getSimpleName() + " ← " + r.getClass().getSimpleName(); }
    int na = a.queryForObject("select count(*) from t", Integer.class), nb = b.queryForObject("select count(*) from t", Integer.class); System.out.println("RES " + String.format("%-48s → %-48s A 库 %d 行,B 库 %d 行 → %s", label, ex, na, nb, na == nb ? "一致" : "不一致")); }
  public static void main(String[] args) throws Exception {
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Svc s = c.getBean(Svc.class); JdbcTemplate a = c.getBean("jtA", JdbcTemplate.class), b = c.getBean("jtB", JdbcTemplate.class); admin = a;
    a.execute("create table if not exists t(id int auto_increment primary key, v varchar(10)) engine=innodb"); b.execute("create table if not exists t(id int auto_increment primary key, v varchar(10)) engine=innodb");
    t(a, b, "(0)@Transactional(txA) 写 A 和 B,成功", () -> s.declarative(false)); t(a, b, "(1)@Transactional(txA) 写 A 和 B,最后抛异常", () -> s.declarative(true));
    t(a, b, "(2)嵌套模板:A 外 B 内,都成功", () -> s.nested(false)); t(a, b, "(3)嵌套模板:B 内层提交之后,A 外层抛异常", () -> s.nested(true));
    t(a, b, "(4)嵌套模板:A 在提交前连接被杀(B 先提交)", s::killBeforeCommit); t(a, b, "(5)反过来:B 外 A 内,A 的连接在 A 提交前被杀", s::killBeforeCommitReverse); t(a, b, "(6)B 外 A 内,A 先提交,B 的连接在 B 提交前被杀", s::killBLast);
    c.close(); System.exit(0);
  }
}
'''
b = sbuild('x37', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x37'); my.q('create database if not exists demo2'); URL = jdbc(my)
r = srun(b, 'demo.Main', props={'url': URL}); L = [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1500:]]
print('Spring Framework 7.0.9 + MySQL 26.7.0(同一个实例里的两个库 demo 与 demo2,各配一个 DataSource 和一个事务管理器)。多数据源时的事务边界')
print('== 一:一个事务管理器只管一个数据源。七个场景之后,A 库和 B 库各剩几行(两边的行数相同 = 一致)')
[print('  ' + l) for l in L]
my.stop()
