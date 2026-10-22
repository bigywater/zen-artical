import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x34'); CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.sql.*; import java.util.*; import java.util.concurrent.*; import javax.sql.DataSource;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.jdbc.datasource.*;
import org.springframework.context.annotation.*; import org.springframework.transaction.annotation.*; import org.springframework.transaction.support.*;
public class Main {
  static final List<String> seq = new ArrayList<>(); static void ev(String s) { seq.add(s); }
  static void flush(String t) { System.out.println("RES --- " + t); int i = 1; for (String s : seq) System.out.println("RES " + i++ + ". " + s); seq.clear(); }
  public static class Svc {
    final JdbcTemplate jt; final DataSource ds, proxyDs; Svc(JdbcTemplate jt, DataSource ds, DataSource proxyDs) { this.jt = jt; this.ds = ds; this.proxyDs = proxyDs; }
    @Transactional(isolation = org.springframework.transaction.annotation.Isolation.READ_COMMITTED) public void inspect() {
      ev("isSynchronizationActive=" + TransactionSynchronizationManager.isSynchronizationActive() + ",isActualTransactionActive=" + TransactionSynchronizationManager.isActualTransactionActive());
      ev("事务名=" + TransactionSynchronizationManager.getCurrentTransactionName().replace("demo.Main$", "") + ",隔离级别=" + TransactionSynchronizationManager.getCurrentTransactionIsolationLevel() + "(2 = READ_COMMITTED),只读=" + TransactionSynchronizationManager.isCurrentTransactionReadOnly());
      Map<Object, Object> rm = TransactionSynchronizationManager.getResourceMap(); for (Map.Entry<Object, Object> e : rm.entrySet()) ev("线程上绑定的资源:键 " + e.getKey().getClass().getSimpleName() + " → 值 " + e.getValue().getClass().getSimpleName() + ",持有连接 " + ((ConnectionHolder) e.getValue()).getConnection().getClass().getSimpleName().replaceAll("^Hikari.*Wrap.*", "HikariProxyConnection"));
      ev("已注册的同步器数:" + TransactionSynchronizationManager.getSynchronizations().size() + "(JdbcTemplate 之类的在需要时注册)"); }
    @Transactional public void callbacks(boolean fail, boolean failInAfterCommit) {
      TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
        public void beforeCommit(boolean ro) { ev("beforeCommit(readOnly=" + ro + ")"); } public void beforeCompletion() { ev("beforeCompletion()"); }
        public void afterCommit() { ev("afterCommit():事务已经提交了,但连接还没还给连接池"); if (failInAfterCommit) throw new IllegalStateException("afterCommit 里抛异常"); }
        public void afterCompletion(int status) { ev("afterCompletion(status=" + (status == STATUS_COMMITTED ? "COMMITTED" : status == STATUS_ROLLED_BACK ? "ROLLED_BACK" : "UNKNOWN") + ")"); } });
      jt.update("insert into t(v) values ('x')"); ev("方法体里"); if (fail) throw new IllegalStateException("业务失败"); }
    @Transactional public void threadCheck() throws Exception { ExecutorService ex = Executors.newSingleThreadExecutor(); try { String r = ex.submit(() -> "子线程 isActualTransactionActive=" + TransactionSynchronizationManager.isActualTransactionActive() + ",资源 " + TransactionSynchronizationManager.getResourceMap().size() + " 个").get(); ev("主线程 isActualTransactionActive=" + TransactionSynchronizationManager.isActualTransactionActive() + ",资源 " + TransactionSynchronizationManager.getResourceMap().size() + " 个;" + r); } finally { ex.shutdown(); } }
    @Transactional public void rawConn(boolean useProxy) throws Exception { Connection c = DataSourceUtils.getConnection(ds); Connection d = (useProxy ? proxyDs : ds).getConnection();
      long a = id(c), b = id(d); ev((useProxy ? "经 TransactionAwareDataSourceProxy" : "直接 ds.getConnection()") + ":得到的连接 id " + b + ",事务连接 id " + a + (a == b ? "(同一个连接)" : "(不同的连接)")); try (Statement st = d.createStatement()) { st.executeUpdate("insert into t(v) values ('raw')"); } d.close(); DataSourceUtils.releaseConnection(c, ds); throw new IllegalStateException("回滚吧"); }
    long id(Connection c) throws SQLException { try (Statement st = c.createStatement(); ResultSet rs = st.executeQuery("select connection_id()")) { rs.next(); return rs.getLong(1); } }
  }
  @Configuration @EnableTransactionManagement(proxyTargetClass = true) static class Conf {
    @Bean DataSource ds() { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(5); return d; }
    @Bean JdbcTemplate jt(DataSource ds) { return new JdbcTemplate(ds); } @Bean DataSourceTransactionManager tm(DataSource ds) { return new DataSourceTransactionManager(ds); }
    @Bean Svc svc(JdbcTemplate jt, DataSource ds) { return new Svc(jt, ds, new TransactionAwareDataSourceProxy(ds)); } }
  public static void main(String[] args) throws Exception {
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Svc s = c.getBean(Svc.class); JdbcTemplate jt = c.getBean(JdbcTemplate.class); jt.execute("create table if not exists t(id int auto_increment primary key, v varchar(10)) engine=innodb"); jt.update("truncate t"); String m = args[0];
    switch (m) {
      case "inspect" -> { s.inspect(); flush("@Transactional(isolation = READ_COMMITTED) 方法里"); ev("事务外 isSynchronizationActive=" + TransactionSynchronizationManager.isSynchronizationActive() + ",资源 " + TransactionSynchronizationManager.getResourceMap().size() + " 个"); flush("事务外"); }
      case "cb" -> { s.callbacks(false, false); flush("正常提交"); try { s.callbacks(true, false); } catch (Exception e) { ev("调用者收到 " + e.getClass().getSimpleName()); } flush("回滚"); try { s.callbacks(false, true); } catch (Exception e) { ev("调用者收到 " + e.getClass().getSimpleName() + ": " + e.getMessage() + ";表里行数 " + jt.queryForObject("select count(*) from t", Integer.class)); } flush("afterCommit 里抛异常(方法本身成功)"); }
      case "thread" -> { s.threadCheck(); flush("事务线程与子线程"); }
      case "raw" -> { for (boolean px : new boolean[]{false, true}) { jt.update("truncate t"); try { s.rawConn(px); } catch (Exception e) { } ev("方法抛了异常之后,表里有 " + jt.queryForObject("select count(*) from t", Integer.class) + " 行(0 表示 insert 跟着回滚了)"); } flush("在 @Transactional 里自己拿连接写入"); }
    }
    c.close(); System.exit(0);
  }
}
'''
b = sbuild('x34', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x34'); URL = jdbc(my)
def run(m): r = srun(b, 'demo.Main', args=[m], props={'url': URL}); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1500:]]
print('Spring Framework 7.0.9 + MySQL 26.7.0。TransactionSynchronizationManager:事务的资源与回调都绑在当前线程上')
for t_, k_, tt in (('一', 'inspect', '事务里线程上绑着什么'), ('二', 'cb', '事务同步回调的顺序(提交、回滚、afterCommit 抛异常)'), ('三', 'thread', '换一个线程'), ('四', 'raw', '自己拿连接写入')):
    print(f'== {t_}:{tt}'); [print('  ' + l) for l in run(k_)]
my.stop()
