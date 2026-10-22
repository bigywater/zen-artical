import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x29'); CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.sql.*; import java.util.*; import javax.sql.DataSource;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.context.annotation.*; import org.springframework.transaction.*; import org.springframework.transaction.annotation.*; import org.springframework.transaction.support.DefaultTransactionStatus; import org.springframework.transaction.support.TransactionSynchronizationManager;
public class Main {
  static final List<String> seq = new ArrayList<>(); static void ev(String s) { seq.add(s); }
  static void flush(String t) { System.out.println("RES --- " + t); int i = 1; for (String s : seq) System.out.println("RES " + i++ + ". " + s); seq.clear(); }
  public static class Tm extends DataSourceTransactionManager {
    Tm(DataSource ds) { super(ds); }
    @Override protected Object doGetTransaction() { ev("  doGetTransaction()"); return super.doGetTransaction(); }
    @Override protected void doBegin(Object t, TransactionDefinition d) { ev("  doBegin(" + d.getName().replace("demo.Main$", "") + ",传播 " + d.getPropagationBehavior() + ",只读 " + d.isReadOnly() + "):从连接池拿连接、setAutoCommit(false)、把连接绑定到当前线程"); super.doBegin(t, d); }
    @Override protected void doCommit(DefaultTransactionStatus s) { ev("  doCommit():connection.commit()"); super.doCommit(s); }
    @Override protected void doRollback(DefaultTransactionStatus s) { ev("  doRollback():connection.rollback()"); super.doRollback(s); }
    @Override protected void doCleanupAfterCompletion(Object t) { ev("  doCleanupAfterCompletion():解除绑定、恢复 autoCommit、把连接还给连接池"); super.doCleanupAfterCompletion(t); }
  }
  public static class Svc {
    final JdbcTemplate jt; Svc(JdbcTemplate jt) { this.jt = jt; }
    @Transactional public void place(boolean fail) {
      ev("进入 place():事务活跃=" + TransactionSynchronizationManager.isActualTransactionActive() + ",事务名=" + TransactionSynchronizationManager.getCurrentTransactionName().replace("demo.Main$", "") + ",绑定的资源=" + TransactionSynchronizationManager.getResourceMap().keySet().stream().map(k -> k.getClass().getSimpleName()).toList());
      jt.update("insert into t(v) values ('a')"); Long c1 = jt.queryForObject("select connection_id()", Long.class); jt.update("insert into t(v) values ('b')"); Long c2 = jt.queryForObject("select connection_id()", Long.class);
      ev("两条 insert 之间 connection_id():" + c1 + " 和 " + c2 + (c1.equals(c2) ? "(同一个连接)" : "(不同连接)")); if (fail) throw new IllegalStateException("业务失败"); }
    public void noTx() { ev("进入 noTx()(没有 @Transactional):事务活跃=" + TransactionSynchronizationManager.isActualTransactionActive()); jt.update("insert into t(v) values ('x')"); jt.update("insert into t(v) values ('y')"); }
  }
  @Configuration @EnableTransactionManagement static class Conf {
    static String url, port;
    @Bean DataSource ds() { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(5); d.setMinimumIdle(5); return d; }
    @Bean JdbcTemplate jt(DataSource ds) { return new JdbcTemplate(ds); } @Bean Tm tm(DataSource ds) { return new Tm(ds); } @Bean Svc svc(JdbcTemplate jt) { return new Svc(jt); } }
  public static void main(String[] args) throws Exception {
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Svc s = c.getBean(Svc.class); JdbcTemplate jt = c.getBean(JdbcTemplate.class); String m = args[0];
    jt.execute("create table if not exists t(id int auto_increment primary key, v varchar(10)) engine=innodb"); jt.update("truncate t"); jt.execute("set global general_log = 'ON'"); jt.execute("set global log_output = 'TABLE'"); jt.execute("truncate mysql.general_log");
    seq.clear();
    switch (m) {
      case "tx" -> { try { s.place(false); } catch (Exception e) { } flush("事务管理器被调用的过程(正常提交)"); try { s.place(true); } catch (Exception e) { ev("调用者收到 " + e.getClass().getSimpleName()); } flush("事务管理器被调用的过程(业务异常回滚)"); System.out.println("RES 两次调用之后表 t 里有 " + jt.queryForObject("select count(*) from t", Integer.class) + " 行(place(false) 提交了 2 行,place(true) 的 2 行回滚了)"); }
      case "log" -> { jt.execute("truncate mysql.general_log"); s.place(false); Thread.sleep(200);
        List<String> rows = jt.query("select thread_id, command_type, argument from mysql.general_log where argument not like '%general_log%' order by event_time, thread_id", (rs, i) -> rs.getString(1) + " " + rs.getString(2) + " " + rs.getString(3).replaceAll("\\s+", " ")); System.out.println("RES 一次 @Transactional place(false) 在 MySQL general_log 里留下的语句(只取执行这个事务的那一个连接 thread_id;连接池后台新建的其它连接的握手语句略去):"); String first = rows.isEmpty() ? "" : rows.get(0).split(" ")[0]; for (String r : rows) if (r.startsWith(first + " ")) System.out.println("RES   " + r);
        jt.execute("truncate mysql.general_log"); s.noTx(); Thread.sleep(200);
        rows = jt.query("select thread_id, command_type, argument from mysql.general_log where argument not like '%general_log%' order by event_time, thread_id", (rs, i) -> rs.getString(1) + " " + rs.getString(2) + " " + rs.getString(3).replaceAll("\\s+", " ")); System.out.println("RES 没有 @Transactional 的 noTx()(两条 insert)留下的语句:"); first = rows.isEmpty() ? "" : rows.get(0).split(" ")[0]; for (String r : rows) if (r.startsWith(first + " ")) System.out.println("RES   " + r); }
      case "outside" -> { System.out.println("RES 事务外:isSynchronizationActive=" + TransactionSynchronizationManager.isSynchronizationActive() + ";isActualTransactionActive=" + TransactionSynchronizationManager.isActualTransactionActive() + ";资源 " + TransactionSynchronizationManager.getResourceMap().keySet()); s.noTx(); flush("noTx()"); }
    }
    c.close(); System.exit(0);
  }
}
'''
b = sbuild('x29', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x29'); URL = jdbc(my)
def run(m): r = srun(b, 'demo.Main', args=[m], props={'url': URL}); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1500:]]
print('Spring Framework 7.0.9 + HikariCP + MySQL 26.7.0(自己起的实例) + mysql-connector-j。@Transactional 到底做了什么')
print('== 一:事务管理器被调用的过程。把 DataSourceTransactionManager 的几个关键方法重写成带日志的版本,place() 里两条 insert(正常提交与业务异常回滚各一次)')
[print('  ' + l) for l in run('tx')]
print('== 二:MySQL 的 general_log 里能看到什么。同一个 place(false):语句序列;对比没有 @Transactional 的 noTx() 里两条 insert')
[print('  ' + l) for l in run('log')]
print('== 三:事务外')
[print('  ' + l) for l in run('outside')]
my.stop()
