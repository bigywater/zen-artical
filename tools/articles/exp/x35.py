import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x35'); CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*; import java.util.concurrent.*; import javax.sql.DataSource;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.context.annotation.*; import org.springframework.transaction.*; import org.springframework.transaction.annotation.*; import org.springframework.transaction.support.*;
public class Main {
  public static class Svc {
    final JdbcTemplate jt; final TransactionTemplate tt; Svc(JdbcTemplate jt, TransactionTemplate tt) { this.jt = jt; this.tt = tt; }
    void ins() { jt.update("insert into t(v) values ('x')"); }
    public String basic() { return tt.execute(st -> { ins(); return "返回值"; }); }
    public void throwing() { tt.executeWithoutResult(st -> { ins(); throw new IllegalStateException("回调里抛 RuntimeException"); }); }
    public void marked() { tt.executeWithoutResult(st -> { ins(); st.setRollbackOnly(); }); }
    public void checkedInCallback() throws Exception { tt.execute(st -> { ins(); try { throw new java.io.IOException("受检异常"); } catch (java.io.IOException e) { throw new RuntimeException(e); } }); }
    public void inSelf() { selfDeclared(); } @Transactional public void selfDeclared() { ins(); throw new IllegalStateException("x"); }
    public void inSelfTemplate() { inner(); } void inner() { tt.executeWithoutResult(st -> { ins(); throw new IllegalStateException("x"); }); }
    public void timeoutTx() { TransactionTemplate t = new TransactionTemplate(tt.getTransactionManager()); t.setTimeout(1); t.executeWithoutResult(st -> { jt.queryForObject("select sleep(3)", Integer.class); }); }
    public void customIso() { TransactionTemplate t = new TransactionTemplate(tt.getTransactionManager()); t.setIsolationLevel(TransactionDefinition.ISOLATION_SERIALIZABLE); t.setReadOnly(true); t.executeWithoutResult(st -> { Main.seen = "事务内:隔离级别=" + TransactionSynchronizationManager.getCurrentTransactionIsolationLevel() + "(8 = SERIALIZABLE),只读=" + TransactionSynchronizationManager.isCurrentTransactionReadOnly(); }); }
    @Transactional public void declarativeSlow() throws Exception { ins(); Thread.sleep(300); }
    public void templateSlow() throws Exception { Thread.sleep(300); tt.executeWithoutResult(st -> ins()); }
  }
  static String seen;
  @Configuration @EnableTransactionManagement(proxyTargetClass = true) static class Conf {
    @Bean DataSource ds() { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(2); d.setMinimumIdle(2); return d; }
    @Bean JdbcTemplate jt(DataSource ds) { return new JdbcTemplate(ds); } @Bean DataSourceTransactionManager tm(DataSource ds) { return new DataSourceTransactionManager(ds); } @Bean TransactionTemplate tt(DataSourceTransactionManager tm) { return new TransactionTemplate(tm); }
    @Bean Svc svc(JdbcTemplate jt, TransactionTemplate tt) { return new Svc(jt, tt); } }
  interface Call { Object run() throws Exception; }
  static void t(JdbcTemplate jt, String label, Call c) { jt.update("truncate t"); String ex; try { Object o = c.run(); ex = "正常返回" + (o != null ? " " + o : ""); } catch (Throwable e) { Throwable r = e; while (r.getCause() != null && !(e instanceof TransactionException)) r = r.getCause(); ex = e.getClass().getSimpleName() + (e.getCause() != null ? " ← " + e.getCause().getClass().getSimpleName() : ""); }
    int n = jt.queryForObject("select count(*) from t", Integer.class); System.out.println("RES " + String.format("%-40s → %-52s 表里剩 %d 行 → %s", label, ex, n, n == 1 ? "提交" : "回滚")); }
  public static void main(String[] args) throws Exception {
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Svc s = c.getBean(Svc.class); JdbcTemplate jt = c.getBean(JdbcTemplate.class); jt.execute("create table if not exists t(id int auto_increment primary key, v varchar(10)) engine=innodb"); String m = args[0];
    switch (m) {
      case "basic" -> { t(jt, "execute 返回值", s::basic); t(jt, "回调里抛 RuntimeException", () -> { s.throwing(); return null; }); t(jt, "回调里 status.setRollbackOnly()", () -> { s.marked(); return null; }); t(jt, "受检异常包成 RuntimeException", () -> { s.checkedInCallback(); return null; }); }
      case "self" -> { t(jt, "@Transactional 方法被同类方法 this 调用", () -> { s.inSelf(); return null; }); t(jt, "TransactionTemplate 在同类方法里使用", () -> { s.inSelfTemplate(); return null; }); }
      case "attrs" -> { s.customIso(); System.out.println("RES " + seen); long t0 = System.nanoTime(); String r; try { s.timeoutTx(); r = "没有超时"; } catch (Throwable e) { Throwable x = e; while (x.getCause() != null) x = x.getCause(); r = e.getClass().getSimpleName() + (e.getCause() != null ? " ← " + x.getClass().getSimpleName() + ": " + String.valueOf(x.getMessage()).split("\n")[0] : ""); } System.out.println("RES setTimeout(1) 的事务里执行 select sleep(3):" + r + "(用时 " + (System.nanoTime() - t0) / 1_000_000 + " ms)"); }
      case "hold" -> { for (String k : new String[]{"declarative", "template"}) { int N = 8; ExecutorService ex = Executors.newFixedThreadPool(N); CountDownLatch go = new CountDownLatch(1); List<Future<?>> fs = new ArrayList<>();
          for (int i = 0; i < N; i++) fs.add(ex.submit(() -> { go.await(); if (k.equals("declarative")) s.declarativeSlow(); else s.templateSlow(); return null; })); long t0 = System.nanoTime(); go.countDown(); for (Future<?> f : fs) f.get(); long ms = (System.nanoTime() - t0) / 1_000_000; ex.shutdown();
          System.out.println("RES   " + (k.equals("declarative") ? "@Transactional 包住整个方法(300 ms 的非数据库工作在事务里)" : "TransactionTemplate 只包数据库那一步(300 ms 的非数据库工作在事务外)") + ":8 个线程并发,连接池只有 2 个连接 → 全部完成用了 " + ms + " ms"); } }
    }
    c.close(); System.exit(0);
  }
}
'''
b = sbuild('x35', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x35'); URL = jdbc(my)
def run(m): r = srun(b, 'demo.Main', args=[m], props={'url': URL}); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-1500:]]
print('Spring Framework 7.0.9 + MySQL 26.7.0。编程式事务 TransactionTemplate')
for t_, k_, tt in (('一', 'basic', 'execute 的基本行为'), ('二', 'self', '与自调用的关系'), ('三', 'attrs', '隔离级别、只读与超时'), ('四', 'hold', '事务范围缩小到只包数据库操作')):
    print(f'== {t_}:{tt}'); [print('  ' + l) for l in run(k_)]
my.stop()
