import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x30'); CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*; import javax.sql.DataSource;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.context.annotation.*; import org.springframework.transaction.*; import org.springframework.transaction.annotation.*; import org.springframework.transaction.support.TransactionSynchronizationManager;
public class Main {
  public static class Inner {
    final JdbcTemplate jt; static final ThreadLocal<String> info = new ThreadLocal<>(); Inner(JdbcTemplate jt) { this.jt = jt; }
    void body(boolean fail) { Long cid = jt.queryForObject("select connection_id()", Long.class); jt.update("insert into t(v) values ('inner')"); info.set("inner 事务活跃=" + TransactionSynchronizationManager.isActualTransactionActive() + ",inner 连接 " + cid); if (fail) throw new IllegalStateException("inner 失败"); }
    @Transactional(propagation = Propagation.REQUIRED) public void required(boolean f) { body(f); }
    @Transactional(propagation = Propagation.REQUIRES_NEW) public void requiresNew(boolean f) { body(f); }
    @Transactional(propagation = Propagation.NESTED) public void nested(boolean f) { body(f); }
    @Transactional(propagation = Propagation.SUPPORTS) public void supports(boolean f) { body(f); }
    @Transactional(propagation = Propagation.NOT_SUPPORTED) public void notSupported(boolean f) { body(f); }
    @Transactional(propagation = Propagation.MANDATORY) public void mandatory(boolean f) { body(f); }
    @Transactional(propagation = Propagation.NEVER) public void never(boolean f) { body(f); }
  }
  public static class Outer {
    final JdbcTemplate jt; final Inner inner; Outer(JdbcTemplate jt, Inner inner) { this.jt = jt; this.inner = inner; }
    void call(String p, boolean f) { switch (p) { case "REQUIRED" -> inner.required(f); case "REQUIRES_NEW" -> inner.requiresNew(f); case "NESTED" -> inner.nested(f); case "SUPPORTS" -> inner.supports(f); case "NOT_SUPPORTED" -> inner.notSupported(f); case "MANDATORY" -> inner.mandatory(f); default -> inner.never(f); } }
    @Transactional public void withTx(String p, boolean outerFail, boolean innerFail, boolean catchInner) {
      Long cid = jt.queryForObject("select connection_id()", Long.class); jt.update("insert into t(v) values ('outer')"); Inner.info.set(null);
      try { call(p, innerFail); } catch (RuntimeException e) { if (!catchInner) throw e; Main.note = "outer 捕获了 " + e.getClass().getSimpleName(); }
      Main.outerConn = cid; if (outerFail) throw new IllegalStateException("outer 失败");
    }
    public void noTx(String p, boolean innerFail) { jt.update("insert into t(v) values ('outer')"); Inner.info.set(null); call(p, innerFail); }
  }
  static String note; static Long outerConn;
  @Configuration @EnableTransactionManagement static class Conf {
    @Bean DataSource ds() { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(5); d.setMinimumIdle(2); return d; }
    @Bean JdbcTemplate jt(DataSource ds) { return new JdbcTemplate(ds); } @Bean DataSourceTransactionManager tm(DataSource ds) { return new DataSourceTransactionManager(ds); }
    @Bean Inner inner(JdbcTemplate jt) { return new Inner(jt); } @Bean Outer outer(JdbcTemplate jt, Inner inner) { return new Outer(jt, inner); } }
  static String rows(JdbcTemplate jt) { List<String> r = jt.queryForList("select v from t order by id", String.class); return r.isEmpty() ? "(空)" : String.join("+", r); }
  public static void main(String[] args) throws Exception {
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Outer o = c.getBean(Outer.class); JdbcTemplate jt = c.getBean(JdbcTemplate.class);
    jt.execute("create table if not exists t(id int auto_increment primary key, v varchar(10)) engine=innodb");
    String[] ps = {"REQUIRED", "REQUIRES_NEW", "NESTED", "SUPPORTS", "NOT_SUPPORTED", "MANDATORY", "NEVER"}; String mode = args[0];
    for (String p : ps) {
      jt.update("truncate t");
      if (mode.equals("s1")) { // 外面有事务,一切正常
        note = null; String res; try { o.withTx(p, false, false, false); res = rows(jt); } catch (Exception e) { res = "✗ " + e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()).split("\n")[0]; }
        System.out.println("RES " + String.format("%-14s 外有事务、都成功 → 提交后的行 %-18s %s", p, res, Inner.info.get() == null ? "" : Inner.info.get() + "(outer 连接 " + outerConn + ")")); }
      else if (mode.equals("s2")) { // 外面失败
        String res; try { o.withTx(p, true, false, false); res = "?"; } catch (Exception e) { res = rows(jt); if (!e.getClass().getSimpleName().equals("IllegalStateException")) res = "✗ " + e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()).split("\n")[0]; }
        System.out.println("RES " + String.format("%-14s 外有事务、inner 成功后 outer 抛异常 → 剩下的行 %s", p, res)); }
      else if (mode.equals("s3")) { // 里面失败,外面捕获
        note = null; String res; try { o.withTx(p, false, true, true); res = "outer 正常结束,行 " + rows(jt); } catch (Exception e) { res = "outer 结束时 " + e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()).split("\n")[0].replaceAll("demo.Main\\$", "") + ";行 " + rows(jt); }
        System.out.println("RES " + String.format("%-14s 外有事务、inner 抛异常被 outer 捕获 → %s", p, res)); }
      else { // 外面没有事务
        String res; try { o.noTx(p, false); res = "行 " + rows(jt) + ";" + Inner.info.get(); } catch (Exception e) { res = "✗ " + e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()).split("\n")[0]; }
        System.out.println("RES " + String.format("%-14s 外面没有事务 → %s", p, res)); }
    }
    c.close(); System.exit(0);
  }
}
'''
b = sbuild('x30', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x30'); URL = jdbc(my)
def run(m): r = srun(b, 'demo.Main', args=[m], props={'url': URL}); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1500:]]
print('Spring Framework 7.0.9 + MySQL 26.7.0。事务传播行为(Propagation)7 种。Outer.withTx 是 @Transactional(REQUIRED),里面往表 t 插入 outer,再通过另一个 Bean 调用 Inner 的某个传播行为的方法(插入 inner)')
print('== 一:外面有事务,里面也成功。最后提交后表里有哪些行;inner 是不是在 outer 的连接上、事务是否活跃')
[print('  ' + l) for l in run('s1')]
print('== 二:外面有事务,inner 成功之后 outer 抛异常(回滚)。表里还剩什么')
[print('  ' + l) for l in run('s2')]
print('== 三:外面有事务,inner 抛异常,outer 把它捕获后继续并正常返回')
[print('  ' + l) for l in run('s3')]
print('== 四:外面没有事务(Outer.noTx 没有 @Transactional),调用 inner 的各种传播行为')
[print('  ' + l) for l in run('s4')]
my.stop()
