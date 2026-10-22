import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x96'); CP = scp('org.springframework.boot:spring-boot-starter-data-jpa', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.data.jpa.repository.*; import org.springframework.data.domain.Persistable; import jakarta.persistence.Entity; import jakarta.persistence.Id; import jakarta.persistence.GeneratedValue; import jakarta.persistence.GenerationType; import jakarta.persistence.Transient; import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.transaction.support.TransactionTemplate; import java.util.*; import java.util.stream.*;\n'
FILES = {
 'src/demo/RowId.java': HDR + '@Entity public class RowId { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String v; int n; public RowId() {} public RowId(String v, int n) { this.v = v; this.n = n; } }\n',
 'src/demo/RowAssigned.java': HDR + '@Entity public class RowAssigned implements Persistable<Long> { @Id Long id; String v; int n; @Transient boolean fresh = true; public RowAssigned() {} public RowAssigned(Long id, String v, int n) { this.id = id; this.v = v; this.n = n; } public Long getId() { return id; } public boolean isNew() { return fresh; } }\n',
 'src/demo/RowAssignedPlain.java': HDR + '@Entity public class RowAssignedPlain { @Id Long id; String v; int n; public RowAssignedPlain() {} public RowAssignedPlain(Long id, String v, int n) { this.id = id; this.v = v; this.n = n; } }\n',
 'src/demo/RowIdRepo.java': HDR + 'public interface RowIdRepo extends JpaRepository<RowId, Long> {}\n',
 'src/demo/RowAssignedRepo.java': HDR + 'public interface RowAssignedRepo extends JpaRepository<RowAssigned, Long> {}\n',
 'src/demo/RowAssignedPlainRepo.java': HDR + 'public interface RowAssignedPlainRepo extends JpaRepository<RowAssignedPlain, Long> {}\n',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  static long status(JdbcTemplate j, String name) { return Long.parseLong(String.valueOf(j.queryForMap("show global status like '" + name + "'").get("Value"))); }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a); JdbcTemplate j = c.getBean(JdbcTemplate.class); TransactionTemplate tx = c.getBean(TransactionTemplate.class);
    RowIdRepo ri = c.getBean(RowIdRepo.class); RowAssignedRepo ra = c.getBean(RowAssignedRepo.class); RowAssignedPlainRepo rp = c.getBean(RowAssignedPlainRepo.class);
    int N = 10000; String ins = "insert into t_row(v, n) values (?, ?)";
    j.execute("drop table if exists t_row"); j.execute("create table t_row(id bigint auto_increment primary key, v varchar(20), n int)");
    List<Object[]> rows = IntStream.range(0, N).mapToObj(i -> new Object[]{"v" + i, i}).toList();
    record Sc(String name, Runnable prep, Runnable run, java.util.function.Supplier<Number> cnt) {}
    List<Sc> scs = List.of(
      new Sc("JdbcTemplate 循环里一行一个 update(同一个事务)", () -> j.execute("truncate table t_row"), () -> tx.executeWithoutResult(s -> { for (Object[] rw : rows) j.update(ins, rw); }), () -> j.queryForObject("select count(*) from t_row", Long.class)),
      new Sc("JdbcTemplate.batchUpdate(sql, List<Object[]>)(同一个事务)", () -> j.execute("truncate table t_row"), () -> tx.executeWithoutResult(s -> j.batchUpdate(ins, rows)), () -> j.queryForObject("select count(*) from t_row", Long.class)),
      new Sc("JPA saveAll,主键 IDENTITY(已设 hibernate.jdbc.batch_size=500)", () -> j.execute("truncate table row_id"), () -> tx.executeWithoutResult(s -> ri.saveAll(IntStream.range(0, N).mapToObj(i -> new RowId("v" + i, i)).toList())), () -> j.queryForObject("select count(*) from row_id", Long.class)),
      new Sc("JPA saveAll,手动指定主键 + Persistable.isNew()=true(batch_size=500)", () -> j.execute("truncate table row_assigned"), () -> tx.executeWithoutResult(s -> ra.saveAll(IntStream.range(0, N).mapToObj(i -> new RowAssigned((long) i + 1, "v" + i, i)).toList())), () -> j.queryForObject("select count(*) from row_assigned", Long.class)),
      new Sc("JPA saveAll,手动指定主键但不实现 Persistable(batch_size=500)", () -> j.execute("truncate table row_assigned_plain"), () -> tx.executeWithoutResult(s -> rp.saveAll(IntStream.range(0, N).mapToObj(i -> new RowAssignedPlain((long) i + 1, "v" + i, i)).toList())), () -> j.queryForObject("select count(*) from row_assigned_plain", Long.class)));
    for (Sc sc : scs) {
      double[] ms = new double[3]; long ci = 0, cs = 0;
      for (int k = 0; k < 3; k++) { sc.prep().run(); long bi = status(j, "Com_insert"), bs = status(j, "Com_select"); long t0 = System.nanoTime(); sc.run().run(); ms[k] = (System.nanoTime() - t0) / 1e6; ci = status(j, "Com_insert") - bi; cs = status(j, "Com_select") - bs; }
      Arrays.sort(ms); r(String.format("  %s:中位 %.0f ms(%.0f~%.0f);服务端 Com_insert +%d,Com_select +%d;表里 %d 行", sc.name(), ms[1], ms[0], ms[2], ci, cs, sc.cnt().get().longValue()));
    }
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x96', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x96'); URL = jdbc(my)
print('Spring Boot 4.0.8 / Hibernate 7 / MySQL 26.7.0(自己起的实例,mysql-connector-j);插入 10000 行,每种写法 3 次取中位数(括号里是最小~最大),服务端 Com_insert / Com_select 取差值')
for lab, url in (('默认连接参数', URL), ('连接参数加 rewriteBatchedStatements=true', URL + '&rewriteBatchedStatements=true')):
    print('== ' + {'默认连接参数': '一', '连接参数加 rewriteBatchedStatements=true': '二'}[lab] + ':' + lab)
    PR = {'spring.datasource.url': url, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app', 'spring.jpa.hibernate.ddl-auto': 'create', 'spring.jpa.properties.hibernate.jdbc.batch_size': '500', 'spring.jpa.properties.hibernate.order_inserts': 'true'}
    r = srun(b, 'demo.Main', props=PR, timeout=900)
    for l in res(r): print(l)
    if not res(r): print(r['out'][-2500:])
my.stop()
