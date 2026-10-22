import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x97'); CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{30} - %msg%n</pattern></encoder></appender><logger name="com.zaxxer.hikari" level="INFO"/><root level="WARN"><appender-ref ref="C"/></root></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.jdbc.core.JdbcTemplate; import com.zaxxer.hikari.*; import javax.sql.DataSource; import java.sql.*; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;\n'
FILES = {
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a); DataSource d = c.getBean(DataSource.class); JdbcTemplate j = c.getBean(JdbcTemplate.class); String mode = System.getProperty("x97.mode");
    HikariDataSource h = (HikariDataSource) d; if (mode.equals("defaults")) r("(Boot 创建的 HikariDataSource 是惰性的:第一次取连接时才真正建池;下面先 select 1 触发它)"); j.queryForObject("select 1", Integer.class);
    if (mode.equals("defaults")) {
      r("DataSource 的类型:" + d.getClass().getName());
      r("poolName=" + h.getPoolName() + ",maximumPoolSize=" + h.getMaximumPoolSize() + ",minimumIdle=" + h.getMinimumIdle() + ",connectionTimeout=" + h.getConnectionTimeout() + " ms,idleTimeout=" + h.getIdleTimeout() + " ms,maxLifetime=" + h.getMaxLifetime() + " ms");
      r("keepaliveTime=" + h.getKeepaliveTime() + ",validationTimeout=" + h.getValidationTimeout() + " ms,leakDetectionThreshold=" + h.getLeakDetectionThreshold() + ",autoCommit=" + h.isAutoCommit() + ",connectionTestQuery=" + h.getConnectionTestQuery() + ",initializationFailTimeout=" + h.getInitializationFailTimeout());
      Thread.sleep(1500); var mx = h.getHikariPoolMXBean();
      r("启动后 1.5 秒:total=" + mx.getTotalConnections() + ",active=" + mx.getActiveConnections() + ",idle=" + mx.getIdleConnections() + ",waiting=" + mx.getThreadsAwaitingConnection());
      r("MySQL 服务端 show processlist 里属于本程序的连接数:" + j.queryForObject("select count(*) from information_schema.processlist where user = 'app'", Integer.class));
    } else if (mode.equals("exhaust")) {
      var mx = h.getHikariPoolMXBean(); CountDownLatch got = new CountDownLatch(2); ExecutorService es = Executors.newCachedThreadPool(); List<Connection> held = new ArrayList<>();
      for (int i = 0; i < 2; i++) es.submit(() -> { try { Connection cn = d.getConnection(); synchronized (held) { held.add(cn); } got.countDown(); Thread.sleep(2500); cn.close(); } catch (Exception e) {} });
      got.await(); r("池大小 2,两个连接都被占住:total=" + mx.getTotalConnections() + ",active=" + mx.getActiveConnections() + ",idle=" + mx.getIdleConnections());
      long t0 = System.nanoTime(); try { j.queryForObject("select 1", Integer.class); r("第 3 个请求拿到连接"); } catch (Throwable e) { Throwable rc = e; while (rc.getCause() != null) rc = rc.getCause(); r(String.format("第 3 个请求等了 %.0f ms 之后失败:%s / 最里面:%s", (System.nanoTime() - t0) / 1e6, e.getClass().getSimpleName(), rc.getClass().getSimpleName() + ": " + rc.getMessage())); }
      Thread.sleep(1700);
      t0 = System.nanoTime(); Integer v = null; try { v = j.queryForObject("select 1", Integer.class); } catch (Throwable e) { }
      r(String.format("两个连接放回之后再请求:%s,用时 %.0f ms", v, (System.nanoTime() - t0) / 1e6));
      es.shutdown();
    } else if (mode.equals("wait")) {
      CountDownLatch got = new CountDownLatch(2); ExecutorService es = Executors.newCachedThreadPool();
      for (int i = 0; i < 2; i++) es.submit(() -> { try { Connection cn = d.getConnection(); got.countDown(); Thread.sleep(600); cn.close(); } catch (Exception e) {} });
      got.await(); long t0 = System.nanoTime(); Integer v = null; String err = ""; try { v = j.queryForObject("select 1", Integer.class); } catch (Throwable e) { err = e.getClass().getSimpleName(); }
      r(String.format("池大小 2、connection-timeout=%d ms,两个连接各被占 600 ms:第 3 个请求 结果=%s%s,等了 %.0f ms", h.getConnectionTimeout(), v, err.isEmpty() ? "" : " 异常=" + err, (System.nanoTime() - t0) / 1e6)); es.shutdown();
    } else if (mode.equals("leak")) {
      Connection cn = d.getConnection(); Thread.sleep(2600); r("故意不关连接,持有了 2600 ms(leak-detection-threshold=2000 ms)"); cn.close(); Thread.sleep(300);
    } else if (mode.equals("size")) {
      int size = h.getMaximumPoolSize(); int clients = 32; AtomicLong done = new AtomicLong(); long end = System.currentTimeMillis() + 4000; ExecutorService es = Executors.newFixedThreadPool(clients); List<Future<?>> fs = new ArrayList<>();
      for (int i = 0; i < clients; i++) fs.add(es.submit(() -> { while (System.currentTimeMillis() < end) { j.queryForObject("select sleep(0.02)", Integer.class); done.incrementAndGet(); } }));
      for (var f : fs) f.get(); es.shutdown(); r(String.format("  maximum-pool-size=%d:%d 个客户端线程各自循环执行 select sleep(0.02)(约 20 ms),4 秒内完成 %d 次,即 %.0f 次/秒", size, clients, done.get(), done.get() / 4.0));
    }
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x97', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x97'); URL = jdbc(my)
BASE = {'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app'}
def run(mode, extra=None):
    r = srun(b, 'demo.Main', props=dict(BASE, **{'x97.mode': mode}, **(extra or {})), timeout=120); return [l for l in res(r)] or [r['out'][-1500:]], r['out']
print('Spring Boot 4.0.8 / HikariCP(Boot 默认连接池)/ MySQL 26.7.0(自己起的实例)')
print('== 一:Boot 里 HikariCP 的默认值')
l, o = run('defaults'); [print('  ' + x) for x in l]
print('== 二:池耗尽的症状(maximum-pool-size=2,connection-timeout=1000 ms,两个连接被占住 2500 ms)')
l, o = run('exhaust', {'spring.datasource.hikari.maximum-pool-size': '2', 'spring.datasource.hikari.minimum-idle': '2', 'spring.datasource.hikari.connection-timeout': '1000'}); [print('  ' + x) for x in l]
l, o = run('wait', {'spring.datasource.hikari.maximum-pool-size': '2', 'spring.datasource.hikari.minimum-idle': '2', 'spring.datasource.hikari.connection-timeout': '3000'}); [print('  ' + x) for x in l]
print('== 三:连接泄漏检测')
l, o = run('leak', {'spring.datasource.hikari.leak-detection-threshold': '500'}); [print('  leak-detection-threshold=500:' + x) for x in [y for y in o.splitlines() if 'leakDetectionThreshold' in y][:1]]
l, o = run('leak', {'spring.datasource.hikari.leak-detection-threshold': '2000'}); [print('  ' + x) for x in l]
lg = [x for x in o.splitlines() if 'leak' in x.lower()]; print('  日志里和泄漏有关的行:' + str(len(lg))); [print('    ' + x[:230]) for x in lg[:2]]
st = [x for x in o.splitlines() if x.strip().startswith('at demo.Main')]; print('  堆栈里指向我这段代码的帧:' + (st[0].strip() if st else '(没有)'))
print('== 四:池大小就是数据库并发度(32 个并发客户端,每次查询约 20 ms)')
for sz in (2, 4, 10, 32):
    l, o = run('size', {'spring.datasource.hikari.maximum-pool-size': str(sz), 'spring.datasource.hikari.minimum-idle': str(sz)}); [print(x) for x in l]
my.stop()
