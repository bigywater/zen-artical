import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x32'); CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*; import java.util.concurrent.*; import javax.sql.DataSource;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.context.annotation.*; import org.springframework.transaction.annotation.*;
public class Main {
  public interface Api { void viaInterface(); }
  public static class Svc implements Api {
    final JdbcTemplate jt, jtB; Svc(JdbcTemplate jt, JdbcTemplate jtB) { this.jt = jt; this.jtB = jtB; }
    void ins() { jt.update("insert into t(v) values ('x')"); } void boom() { throw new IllegalStateException("失败"); }
    @Transactional public void ok() { ins(); boom(); }
    public void outerNoTx() { selfTx(); }
    @Transactional public void selfTx() { ins(); boom(); }
    @Transactional void pkgPrivate() { ins(); boom(); }
    @Transactional protected void prot() { ins(); boom(); }
    @Transactional private void priv() { ins(); boom(); }
    public void callPriv() { priv(); }
    @Transactional public final void fin() { ins(); boom(); }
    @Transactional public void swallow() { try { ins(); boom(); } catch (Exception e) { } }
    @Transactional public void threaded() throws Exception { ExecutorService ex = Executors.newSingleThreadExecutor(); try { ex.submit(this::ins).get(); } finally { ex.shutdown(); } boom(); }
    @Transactional public void wrongTm() { jtB.update("insert into t(v) values ('x')"); boom(); }
    @Transactional public void myisam() { jt.update("insert into t_myisam(v) values ('x')"); boom(); }
    @Transactional public void viaInterface() { ins(); boom(); }
  }
  public static class Raw extends Svc { Raw(JdbcTemplate a, JdbcTemplate b) { super(a, b); } }
  @Configuration @EnableTransactionManagement(proxyTargetClass = true) static class Conf extends Base { }
  @Configuration @EnableTransactionManagement static class ConfJdk extends Base { }
  static class Base {
    @Bean(name = "ds") DataSource ds() { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(4); return d; }
    @Bean(name = "dsB") DataSource dsB() { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url").replace("/demo?", "/demo2?")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(4); return d; }
    @Bean JdbcTemplate jt(DataSource ds) { return new JdbcTemplate(ds); } @Bean JdbcTemplate jtB(DataSource dsB) { return new JdbcTemplate(dsB); }
    @Bean DataSourceTransactionManager tm(DataSource ds) { return new DataSourceTransactionManager(ds); } @Bean Svc svc(JdbcTemplate jt, JdbcTemplate jtB) { return new Svc(jt, jtB); } }
  static String tryBean(AnnotationConfigApplicationContext c) { try { c.getBean(Svc.class); return "成功"; } catch (Exception e) { return e.getClass().getSimpleName(); } }
  interface Call { void run() throws Exception; }
  static void t(JdbcTemplate jt, JdbcTemplate jtB, String label, Call c, String tbl, boolean onB) { jt.update("truncate t"); jtB.update("truncate t"); jt.update("truncate t_myisam"); String ex; try { c.run(); ex = "正常返回"; } catch (Throwable e) { ex = e.getClass().getSimpleName(); }
    int n = onB ? jtB.queryForObject("select count(*) from t", Integer.class) : jt.queryForObject("select count(*) from " + tbl, Integer.class); System.out.println("RES " + String.format("%-54s → 调用者看到 %-22s 表里剩 %d 行 → %s", label, ex, n, n == 0 ? "回滚了(事务生效)" : "没回滚(事务没生效)")); }
  public static void main(String[] args) throws Exception {
    String m = args[0]; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(m.equals("jdk") ? ConfJdk.class : Conf.class); JdbcTemplate jt = c.getBean("jt", JdbcTemplate.class), jtB = c.getBean("jtB", JdbcTemplate.class);
    jt.execute("create table if not exists t(id int auto_increment primary key, v varchar(10)) engine=innodb"); jtB.execute("create table if not exists t(id int auto_increment primary key, v varchar(10)) engine=innodb"); jt.execute("create table if not exists t_myisam(id int auto_increment primary key, v varchar(10)) engine=myisam");
    if (m.equals("a")) { Svc s = c.getBean(Svc.class);
      t(jt, jtB, "(0)对照:public 方法,通过代理调用", s::ok, "t", false); t(jt, jtB, "(1)自调用:未加注解的 outerNoTx() 里调 this.selfTx()", s::outerNoTx, "t", false);
      t(jt, jtB, "(2)package-private 的 @Transactional 方法", s::pkgPrivate, "t", false); t(jt, jtB, "(3)protected 的 @Transactional 方法", s::prot, "t", false);
      t(jt, jtB, "(4)private 的 @Transactional 方法(经 callPriv 调用)", s::callPriv, "t", false); t(jt, jtB, "(5)final 的 @Transactional 方法", s::fin, "t", false);
      t(jt, jtB, "(6)方法里 catch 吞掉异常", s::swallow, "t", false); t(jt, jtB, "(7)在 @Transactional 里开线程做 insert,之后主线程抛异常", s::threaded, "t", false);
      t(jt, jtB, "(8)事务管理器绑定的是 A 库,方法却写 B 库", s::wrongTm, "t", true); t(jt, jtB, "(9)表是 MyISAM 引擎(不支持事务)", s::myisam, "t_myisam", false);
      Svc raw = new Raw(jt, jtB); t(jt, jtB, "(10)自己 new 出来的对象(不是 Spring 管理的)", raw::ok, "t", false); t(jt, jtB, "(11)注解写在类的方法上,经接口类型 Api 调用(CGLIB 模式)", ((Api) s)::viaInterface, "t", false);
    }
    if (m.equals("jdk")) { Api api = c.getBean(Api.class); System.out.println("RES JDK 代理(默认,Svc 实现了接口 Api):Bean 的类 " + api.getClass().getSimpleName() + ";getBean(Svc.class) → " + tryBean(c)); t(jt, jtB, "通过接口调用 viaInterface()(接口里声明了这个方法)", api::viaInterface, "t", false); }
    c.close(); System.exit(0);
  }
}
'''
b = sbuild('x32', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x32'); my.q('create database if not exists demo2'); URL = jdbc(my)
def run(m): r = srun(b, 'demo.Main', args=[m], props={'url': URL}); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1500:]]
print('Spring Framework 7.0.9 + MySQL 26.7.0。@Transactional 不生效的场景。每个场景:方法先 insert 一行,再抛 IllegalStateException(或类似),表里 0 行 = 事务生效,1 行 = 没生效')
print('== 一:CGLIB 代理(proxyTargetClass = true)下的十二个场景')
[print('  ' + l) for l in run('a')]
print('== 二:默认的 JDK 代理(Svc 实现了接口 Api)')
[print('  ' + l) for l in run('jdk')]
my.stop()
