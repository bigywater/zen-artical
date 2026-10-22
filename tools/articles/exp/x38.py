import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x38'); CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><appender name="O" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{0}: %msg%n</pattern></encoder></appender><root level="ERROR"><appender-ref ref="O"/></root></configuration>'
MAIN = r'''
package demo;
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*; import javax.sql.DataSource;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.context.ApplicationEventPublisher; import org.springframework.context.annotation.*; import org.springframework.context.event.EventListener;
import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.scheduling.annotation.*; import org.springframework.transaction.annotation.*; import org.springframework.transaction.event.*;
public class Main {
  static final List<String> seq = Collections.synchronizedList(new ArrayList<>()); static void ev(String s) { seq.add(s); }
  static void flush(String t) { System.out.println("RES --- " + t); synchronized (seq) { int i = 1; for (String s : seq) System.out.println("RES " + i++ + ". " + s); } seq.clear(); }
  public record Placed(int id) { }
  public static class Svc {
    final JdbcTemplate jt; final ApplicationEventPublisher pub; Svc(JdbcTemplate jt, ApplicationEventPublisher pub) { this.jt = jt; this.pub = pub; }
    @Transactional public void place(int id, boolean fail) { jt.update("insert into orders(id) values (?)", id); ev("place():insert 完,发布 Placed 事件"); pub.publishEvent(new Placed(id)); ev("place():publishEvent 返回"); if (fail) throw new IllegalStateException("业务失败"); }
    public void placeNoTx(int id) { jt.update("insert into orders(id) values (?)", id); pub.publishEvent(new Placed(id)); }
  }
  public static class Listeners {
    final JdbcTemplate jt; Listeners(JdbcTemplate jt) { this.jt = jt; }
    @TransactionalEventListener(phase = TransactionPhase.BEFORE_COMMIT) void bc(Placed e) { ev("  [BEFORE_COMMIT] 收到 " + e.id()); }
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT) void ac(Placed e) { ev("  [AFTER_COMMIT] 收到 " + e.id()); }
    @TransactionalEventListener(phase = TransactionPhase.AFTER_ROLLBACK) void ar(Placed e) { ev("  [AFTER_ROLLBACK] 收到 " + e.id()); }
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMPLETION) void acomp(Placed e) { ev("  [AFTER_COMPLETION] 收到 " + e.id()); }
    @EventListener void plain(Placed e) { ev("  [普通 @EventListener] 收到 " + e.id()); }
    @TransactionalEventListener(fallbackExecution = true, phase = TransactionPhase.AFTER_COMMIT) void fb(Placed e) { ev("  [AFTER_COMMIT + fallbackExecution = true] 收到 " + e.id()); }
  }
  public static class WriteListeners {
    final JdbcTemplate jt; WriteListeners(JdbcTemplate jt) { this.jt = jt; }
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT) public void plain(Placed e) { jt.update("insert into audit(oid, kind) values (?, 'PLAIN')", e.id()); }
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT) @Transactional(propagation = Propagation.REQUIRES_NEW) public void requiresNew(Placed e) { jt.update("insert into audit(oid, kind) values (?, 'REQUIRES_NEW')", e.id()); }
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT) @Transactional(propagation = Propagation.NOT_SUPPORTED) public void notSupported(Placed e) { jt.update("insert into audit(oid, kind) values (?, 'NOT_SUPPORTED')", e.id()); }
  }
  public static class BadListener { final JdbcTemplate jt; BadListener(JdbcTemplate jt) { this.jt = jt; }
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT) @Transactional(propagation = Propagation.REQUIRED) public void required(Placed e) { jt.update("insert into audit(oid, kind) values (?, 'REQUIRED')", e.id()); } }
  public static class Race {
    final JdbcTemplate jt; final AtomicInteger seen = new AtomicInteger(), total = new AtomicInteger(); Race(JdbcTemplate jt) { this.jt = jt; } public int seen() { return seen.get(); } public int total() { return total.get(); }
    @Async @EventListener public void asyncPlain(Placed e) { total.incrementAndGet(); Integer n = jt.queryForObject("select count(*) from orders where id = ?", Integer.class, e.id()); if (n > 0) seen.incrementAndGet(); }
  }
  public static class RaceAfter { final JdbcTemplate jt; final AtomicInteger seen = new AtomicInteger(), total = new AtomicInteger(); RaceAfter(JdbcTemplate jt) { this.jt = jt; } public int seen() { return seen.get(); } public int total() { return total.get(); }
    @Async @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT) public void asyncAfter(Placed e) { total.incrementAndGet(); Integer n = jt.queryForObject("select count(*) from orders where id = ?", Integer.class, e.id()); if (n > 0) seen.incrementAndGet(); } }
  public static class BoomAfter { @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT) public void boom(Placed e) { throw new IllegalStateException("AFTER_COMMIT 监听器抛异常"); } }
  @Configuration @EnableTransactionManagement(proxyTargetClass = true) @EnableAsync static class Conf {
    @Bean DataSource ds() { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(System.getProperty("url")); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(10); return d; }
    @Bean JdbcTemplate jt(DataSource ds) { return new JdbcTemplate(ds); } @Bean DataSourceTransactionManager tm(DataSource ds) { return new DataSourceTransactionManager(ds); } @Bean Svc svc(JdbcTemplate jt, ApplicationEventPublisher p) { return new Svc(jt, p); }
    @Bean Listeners listeners(JdbcTemplate jt) { return new Listeners(jt); } @Bean WriteListeners wl(JdbcTemplate jt) { return new WriteListeners(jt); } @Bean BadListener bad(JdbcTemplate jt) { return new BadListener(jt); } @Bean Race race(JdbcTemplate jt) { return new Race(jt); } @Bean RaceAfter raceAfter(JdbcTemplate jt) { return new RaceAfter(jt); } @Bean BoomAfter boomAfter() { return new BoomAfter(); } }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    // 每种模式只启用需要的监听器:靠 Bean 名过滤不方便,所以用不同的上下文配置类
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(); c.register(Conf.class);
    Set<String> keep = switch (m) { case "phases" -> Set.of("listeners"); case "write" -> Set.of("wl"); case "bad" -> Set.of("bad"); case "race" -> Set.of("race"); case "raceAfter" -> Set.of("raceAfter"); default -> Set.of("boomAfter"); };
    c.addBeanFactoryPostProcessor(bf -> { for (String n : new String[]{"listeners", "wl", "bad", "race", "raceAfter", "boomAfter"}) if (!keep.contains(n)) ((org.springframework.beans.factory.support.BeanDefinitionRegistry) bf).removeBeanDefinition(n); }); try { c.refresh(); } catch (Exception e) { Throwable r = e; while (r.getCause() != null) r = r.getCause(); System.out.println("RES 启动失败:" + r.getClass().getSimpleName() + ": " + r.getMessage().replace("demo.Main$", "")); System.exit(0); }
    Svc s = c.getBean(Svc.class); JdbcTemplate jt = c.getBean(JdbcTemplate.class); jt.execute("create table if not exists orders(id int primary key) engine=innodb"); jt.execute("create table if not exists audit(id int auto_increment primary key, oid int, kind varchar(20)) engine=innodb"); jt.update("truncate orders"); jt.update("truncate audit");
    switch (m) {
      case "phases" -> { s.place(1, false); flush("事务正常提交"); try { s.place(2, true); } catch (Exception e) { ev("调用者收到 " + e.getClass().getSimpleName()); } flush("事务回滚"); s.placeNoTx(3); flush("没有事务时直接 publishEvent"); }
      case "write" -> { s.place(1, false); Thread.sleep(200); System.out.println("RES AFTER_COMMIT 监听器里的写入,事务提交之后 audit 表里有:" + jt.queryForList("select kind from audit order by id", String.class)); }
      case "bad" -> { System.out.println("RES 没有报错"); }
      case "race", "raceAfter" -> { int N = 100; for (int i = 1; i <= N; i++) s.place(i, false); Thread.sleep(800); Object r = m.equals("race") ? c.getBean(Race.class) : c.getBean(RaceAfter.class); int seen = m.equals("race") ? ((Race) r).seen() : ((RaceAfter) r).seen(), total = m.equals("race") ? ((Race) r).total() : ((RaceAfter) r).total();
        System.out.println("RES " + (m.equals("race") ? "@Async @EventListener(事件在事务里发布)" : "@Async @TransactionalEventListener(AFTER_COMMIT)") + ":" + N + " 次下单,监听器被调用 " + total + " 次,其中读得到刚下的那个订单的有 " + seen + " 次"); System.exit(0); }
      case "boom" -> { try { s.place(1, false); ev("place() 正常返回"); } catch (Exception e) { ev("调用者收到 " + e.getClass().getSimpleName() + ": " + e.getMessage()); } ev("表 orders 里有 " + jt.queryForObject("select count(*) from orders", Integer.class) + " 行"); Thread.sleep(100); flush("AFTER_COMMIT 监听器抛异常"); }
    }
    c.close(); System.exit(0);
  }
}
'''
b = sbuild('x38', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x38'); URL = jdbc(my)
def run(m): r = srun(b, 'demo.Main', args=[m], props={'url': URL}, timeout=180); return [l[4:] if l.startswith('RES ') else l[:230] for l in r['out'].splitlines() if l.startswith('RES ') or l.startswith('LOG ')] or [r['out'][-1500:]]
print('Spring Framework 7.0.9 + MySQL 26.7.0。事务提交之后再做事:@TransactionalEventListener')
print('== 一:各个 phase 什么时候收到事件,回滚和没有事务时呢')
[print('  ' + l) for l in run('phases')]
print('== 二:AFTER_COMMIT 监听器里的数据库写入。三个监听器各插一行 audit:没有 @Transactional 的、@Transactional(REQUIRES_NEW) 的、@Transactional(NOT_SUPPORTED) 的;另外试一个 @Transactional(REQUIRED) 的')
[print('  ' + l) for l in run('write')]
[print('  ' + l) for l in run('bad')]
print('== 三:异步监听器能不能读到刚下的订单。在事务里 publishEvent,监听器 @Async 在另一个线程里用自己的连接查这个订单。100 次下单')
[print('  ' + l) for l in run('race')]; [print('  ' + l) for l in run('raceAfter')]
print('== 四:AFTER_COMMIT 监听器抛异常')
[print('  ' + l) for l in run('boom')]
my.stop()
