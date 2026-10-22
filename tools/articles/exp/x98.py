import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x98'); CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.annotation.*; import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.jdbc.datasource.*; import org.springframework.jdbc.datasource.lookup.AbstractRoutingDataSource; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.*; import org.springframework.transaction.support.TransactionSynchronizationManager; import com.zaxxer.hikari.HikariDataSource; import javax.sql.DataSource; import java.util.*;\n'
FILES = {
 'src/demo/Cfg.java': HDR + '''
@Configuration
public class Cfg {
  static DataSource hk(String url) { HikariDataSource d = new HikariDataSource(); d.setJdbcUrl(url); d.setUsername("app"); d.setPassword("app"); d.setMaximumPoolSize(4); return d; }
  @Bean @Primary DataSource routing() {
    String base = System.getProperty("x98.base");
    AbstractRoutingDataSource r = new AbstractRoutingDataSource() {
      protected Object determineCurrentLookupKey() { boolean ro = TransactionSynchronizationManager.isCurrentTransactionReadOnly(); Main.KEYS.add(ro ? "replica" : "primary"); return ro ? "replica" : "primary"; } };
    r.setTargetDataSources(Map.of("primary", hk(base.replace("/demo?", "/demo?")), "replica", hk(base.replace("/demo?", "/replica?")))); r.setDefaultTargetDataSource(hk(base)); r.afterPropertiesSet();
    return "true".equals(System.getProperty("x98.lazy")) ? new LazyConnectionDataSourceProxy(r) : r;
  }
}
''',
 'src/demo/Svc.java': HDR + '''
@Service public class Svc {
  final JdbcTemplate j; Svc(JdbcTemplate j) { this.j = j; }
  String db() { return j.queryForObject("select database()", String.class); }
  @Transactional(readOnly = true) public String readTx() { return db(); }
  @Transactional public String writeTx() { j.update("insert into log(msg) values ('writeTx')"); return db(); }
  public String noTx() { return db(); }
  @Transactional public String writeRequired(String msg) { j.update("insert into log(msg) values (?)", msg); return db(); }
  @Transactional(propagation = Propagation.REQUIRES_NEW) public String writeNew(String msg) { j.update("insert into log(msg) values (?)", msg); return db(); }
}
''',
 'src/demo/Outer.java': HDR + '''
@Service public class Outer {
  final Svc svc; Outer(Svc s) { svc = s; }
  @Transactional(readOnly = true) public String readThenWriteRequired() { String a = svc.readTx(); String b = svc.writeRequired("from-readonly-outer-REQUIRED"); return "外层 readOnly 事务里 → 先读在 " + a + ",再调 REQUIRED 的写方法,这次写在 " + b; }
  @Transactional(readOnly = true) public String readThenWriteNew() { String a = svc.readTx(); String b = svc.writeNew("from-readonly-outer-REQUIRES_NEW"); return "外层 readOnly 事务里 → 先读在 " + a + ",再调 REQUIRES_NEW 的写方法,这次写在 " + b; }
}
''',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static final List<String> KEYS = Collections.synchronizedList(new ArrayList<>());
  static void r(String s) { System.out.println("RES " + s); }
  static void t(String label, java.util.function.Supplier<String> c) { KEYS.clear(); String o; try { o = c.get(); } catch (Throwable e) { Throwable rc = e; while (rc.getCause() != null) rc = rc.getCause(); o = "抛 " + e.getClass().getSimpleName() + ":" + rc.getMessage(); } r(label + "  ⇒ " + o + ";determineCurrentLookupKey 被调用了 " + KEYS.size() + " 次,依次返回 " + KEYS); }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a); Svc s = c.getBean(Svc.class); Outer o = c.getBean(Outer.class); DataSource ds = c.getBean(DataSource.class);
    r("DataSource 的类型:" + ds.getClass().getName() + (ds.getClass().isAnonymousClass() ? "(AbstractRoutingDataSource 的匿名子类)" : ""));
    t("@Transactional(readOnly = true) 的 readTx()", s::readTx);
    t("@Transactional 的 writeTx()", s::writeTx);
    t("没有 @Transactional 的 noTx()", s::noTx);
    t("外层 readOnly 调 REQUIRED 的写方法", o::readThenWriteRequired);
    t("外层 readOnly 调 REQUIRES_NEW 的写方法", o::readThenWriteNew);
    var p = c.getBean(JdbcTemplate.class);
    r("  两个库里 log 表的内容(用 JDBC 直连两个库查):");
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x98', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x98'); URL = jdbc(my)
my.q('create database if not exists replica')
for db in ('demo', 'replica'): my.q(f'create table if not exists {db}.log(id bigint auto_increment primary key, msg varchar(60))')
print('Spring Boot 4.0.8 / Spring Framework 7.0.9 AbstractRoutingDataSource / MySQL 26.7.0(自己起的实例);用同一个实例里的两个库 demo(当主库 primary)与 replica(当从库)代替真正的主从,路由键 = 当前事务是否 readOnly')
def show_logs():
    for db in ('demo', 'replica'): print(f'    库 {db} 的 log 表:' + str(my.q(f'select msg from {db}.log order by id')))
for lazy in ('false', 'true'):
    for db in ('demo', 'replica'): my.q(f'truncate table {db}.log')
    print('== ' + ('一' if lazy == 'false' else '二') + ':' + ('直接用 AbstractRoutingDataSource 当 DataSource' if lazy == 'false' else '外面再包一层 LazyConnectionDataSourceProxy'))
    r = srun(b, 'demo.Main', props={'x98.base': URL, 'x98.lazy': lazy, 'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app'}, timeout=120)
    for l in res(r)[:-1]: print(l)
    if not res(r): print(r['out'][-2000:])
    show_logs()
my.stop()
