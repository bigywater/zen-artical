import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x31'); CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.io.IOException; import java.util.*; import javax.sql.DataSource;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.context.annotation.*; import org.springframework.transaction.annotation.*; import org.springframework.transaction.interceptor.TransactionAspectSupport;
public class Main {
  public static class MyChecked extends Exception { MyChecked() { super("自定义受检异常"); } }
  public static class MyChild extends MyChecked { }
  public static class MyRuntime extends RuntimeException { MyRuntime() { super("自定义运行时异常"); } }
  public static class Svc {
    final JdbcTemplate jt; Svc(JdbcTemplate jt) { this.jt = jt; } void ins() { jt.update("insert into t(v) values ('x')"); }
    @Transactional public void runtime() { ins(); throw new IllegalStateException("RuntimeException"); }
    @Transactional public void error() { ins(); throw new AssertionError("Error"); }
    @Transactional public void checked() throws IOException { ins(); throw new IOException("受检异常 IOException"); }
    @Transactional(rollbackFor = Exception.class) public void checkedRollbackFor() throws IOException { ins(); throw new IOException("受检异常 IOException"); }
    @Transactional(rollbackFor = IOException.class) public void checkedRollbackForIo() throws IOException { ins(); throw new IOException("IOException"); }
    @Transactional(rollbackForClassName = "java.io.IOException") public void byName() throws IOException { ins(); throw new IOException("IOException"); }
    @Transactional(noRollbackFor = IllegalStateException.class) public void noRollback() { ins(); throw new IllegalStateException("RuntimeException 但声明了 noRollbackFor"); }
    @Transactional public void wrapped() { ins(); try { throw new IOException("底层受检异常"); } catch (IOException e) { throw new RuntimeException("包成 RuntimeException", e); } }
    @Transactional public void swallowed() { ins(); try { throw new IllegalStateException("内部抛的"); } catch (Exception e) { /* 吞掉 */ } }
    @Transactional public void swallowedSetRollbackOnly() { ins(); try { throw new IllegalStateException("内部抛的"); } catch (Exception e) { TransactionAspectSupport.currentTransactionStatus().setRollbackOnly(); } }
    @Transactional(rollbackFor = MyChecked.class) public void childOfRollbackFor() throws MyChecked { ins(); throw new MyChild(); }
    @Transactional(rollbackFor = MyChecked.class, noRollbackFor = MyChild.class) public void childNoRollback() throws MyChecked { ins(); throw new MyChild(); }
    @Transactional(rollbackFor = MyChild.class, noRollbackFor = MyChecked.class) public void parentNoRollback() throws MyChecked { ins(); throw new MyChild(); }
    @Transactional(rollbackFor = RuntimeException.class, noRollbackFor = MyRuntime.class) public void both() { ins(); throw new MyRuntime(); }
  }
  @Configuration @EnableTransactionManagement static class Conf {
    @Bean DataSource ds() { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(4); return d; }
    @Bean JdbcTemplate jt(DataSource ds) { return new JdbcTemplate(ds); } @Bean DataSourceTransactionManager tm(DataSource ds) { return new DataSourceTransactionManager(ds); } @Bean Svc svc(JdbcTemplate jt) { return new Svc(jt); } }
  interface Call { void run() throws Exception; }
  static void t(JdbcTemplate jt, String label, Call c) { jt.update("truncate t"); String ex; try { c.run(); ex = "方法正常返回"; } catch (Throwable e) { ex = e.getClass().getSimpleName() + (e.getCause() != null ? " ← " + e.getCause().getClass().getSimpleName() : ""); }
    int n = jt.queryForObject("select count(*) from t", Integer.class); System.out.println("RES " + String.format("%-46s → 调用者看到 %-44s 表里剩 %d 行 → %s", label, ex, n, n == 1 ? "提交" : "回滚")); }
  public static void main(String[] args) throws Exception {
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Svc s = c.getBean(Svc.class); JdbcTemplate jt = c.getBean(JdbcTemplate.class); jt.execute("create table if not exists t(id int auto_increment primary key, v varchar(10)) engine=innodb"); String m = args[0];
    if (m.equals("default")) { t(jt, "抛 RuntimeException", s::runtime); t(jt, "抛 Error(AssertionError)", s::error); t(jt, "抛受检异常 IOException(默认)", s::checked); t(jt, "抛受检异常,rollbackFor = Exception.class", s::checkedRollbackFor); t(jt, "抛 IOException,rollbackFor = IOException.class", s::checkedRollbackForIo); t(jt, "抛 IOException,rollbackForClassName", s::byName); t(jt, "抛 RuntimeException,noRollbackFor", s::noRollback); }
    else if (m.equals("catch")) { t(jt, "受检异常包成 RuntimeException 再抛", s::wrapped); t(jt, "方法内部 catch 吞掉异常", s::swallowed); t(jt, "吞掉异常,但 setRollbackOnly()", s::swallowedSetRollbackOnly); }
    else { t(jt, "抛 MyChild(rollbackFor = MyChecked.class)", s::childOfRollbackFor); t(jt, "rollbackFor = MyChecked,noRollbackFor = MyChild,抛 MyChild", s::childNoRollback); t(jt, "rollbackFor = MyChild,noRollbackFor = MyChecked,抛 MyChild", s::parentNoRollback); t(jt, "rollbackFor = RuntimeException,noRollbackFor = MyRuntime,抛 MyRuntime", s::both); }
    c.close(); System.exit(0);
  }
}
'''
b = sbuild('x31', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x31'); URL = jdbc(my)
def run(m): r = srun(b, 'demo.Main', args=[m], props={'url': URL}); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1500:]]
print('Spring Framework 7.0.9 + MySQL 26.7.0。事务什么时候回滚。每个方法先 insert 一行,然后按场景抛异常或不抛;表里留下 1 行 = 提交,0 行 = 回滚')
print('== 一:默认规则与 rollbackFor / noRollbackFor')
[print('  ' + l) for l in run('default')]
print('== 二:异常被包装或被吞掉')
[print('  ' + l) for l in run('catch')]
print('== 三:rollbackFor 与 noRollbackFor 同时匹配时听谁的(MyChild 继承 MyChecked)')
[print('  ' + l) for l in run('both')]
my.stop()
