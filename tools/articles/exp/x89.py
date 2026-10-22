import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x89'); CP = scp('org.springframework.boot:spring-boot-starter-data-jpa', 'com.mysql:mysql-connector-j')
LOG = '<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %logger{30} %level %msg%n</pattern></encoder></appender><logger name="org.hibernate" level="WARN"/><root level="OFF"><appender-ref ref="C"/></root></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.*; import org.springframework.data.jpa.repository.*; import org.springframework.data.repository.*; import org.springframework.data.repository.query.Param; import org.springframework.data.domain.*; import jakarta.persistence.Entity; import jakarta.persistence.Id; import jakarta.persistence.Table; import jakarta.persistence.ManyToOne; import jakarta.persistence.OneToMany; import org.springframework.stereotype.Component; import org.springframework.jdbc.core.JdbcTemplate; import java.util.*; import java.time.*;\n'
FILES = {
 'src/demo/Insp.java': HDR + '''
import org.hibernate.resource.jdbc.spi.StatementInspector; import org.springframework.boot.hibernate.autoconfigure.HibernatePropertiesCustomizer;
@Component public class Insp implements StatementInspector, HibernatePropertiesCustomizer {
  static volatile boolean on; static final List<String> SQLS = Collections.synchronizedList(new ArrayList<>());
  public String inspect(String sql) { if (on) SQLS.add(sql); return sql; }
  public void customize(Map<String, Object> p) { p.put("hibernate.session_factory.statement_inspector", this); }
}
''',
 'src/demo/Customer.java': HDR + '@Entity public class Customer { @Id Long id; String name; @OneToMany(mappedBy = "customer") List<Ord> orders = new ArrayList<>(); public Long getId() { return id; } public List<Ord> getOrders() { return orders; } }\n',
 'src/demo/Ord.java': HDR + '@Entity @Table(name = "ord") public class Ord { @Id Long id; String status; int amount; int bucket; LocalDateTime createdAt; @ManyToOne(fetch = jakarta.persistence.FetchType.LAZY) Customer customer; public Long getId() { return id; } public int getBucket() { return bucket; } }\n',
 'src/demo/OrdRepo.java': HDR + '''
public interface OrdRepo extends JpaRepository<Ord, Long> {
  Page<Ord> findByStatus(String s, Pageable p);
  Slice<Ord> findSliceByStatus(String s, Pageable p);
  List<Ord> findListByStatus(String s, Pageable p);
  Slice<Ord> findSliceBy(Pageable p);
  @Query("select o from Ord o where o.status = ?1") Page<Ord> q1(String s, Pageable p);
  @Query(value = "select * from ord where status = ?1", nativeQuery = true) Page<Ord> nat(String s, Pageable p);
  @Query(value = "select o from Ord o where o.status = ?1", countQuery = "select count(o) from Ord o where o.status = ?1") Page<Ord> q2(String s, Pageable p);
  @Query("select o from Ord o where o.id > :after order by o.id") List<Ord> keyset(@Param("after") long after, Pageable p);
  Page<Ord> findByIdLessThanEqual(long id, Pageable p);
}
''',
 'src/demo/CustRepo.java': HDR + '''
public interface CustRepo extends JpaRepository<Customer, Long> {
  @Query("select c from Customer c join fetch c.orders") Page<Customer> fetchAll(Pageable p);
  @Query(value = "select c from Customer c join fetch c.orders", countQuery = "select count(c) from Customer c") Page<Customer> fetchAll2(Pageable p);
}
''',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  interface Call { Object run(); }
  static String sqlShort(String s) { String x = s.replaceAll("\\\\s+", " ").trim(); return x.startsWith("select count") ? x : x.replaceAll("select .*? from", "select … from"); }
  static void t(String label, Call c) {
    Insp.SQLS.clear(); Object res; long t0 = System.nanoTime(); try { res = c.run(); } catch (Throwable e) { res = "抛 " + e.getClass().getSimpleName() + ":" + String.valueOf(e.getMessage()).split("\\\\n")[0]; }
    double ms = (System.nanoTime() - t0) / 1e6; String out = res instanceof Page<?> p ? "Page(第 " + p.getNumber() + " 页,内容 " + p.getContent().size() + " 行,总数 " + p.getTotalElements() + ",总页数 " + p.getTotalPages() + ")" : res instanceof Slice<?> s ? "Slice(内容 " + s.getContent().size() + " 行,hasNext=" + s.hasNext() + ")" : res instanceof Collection<?> col ? col.size() + " 行" : String.valueOf(res);
    r(label + "  ⇒ " + (out.length() > 220 ? out.substring(0, 220) + "…" : out) + String.format(",用时 %.0f ms,发出 %d 条 SQL", ms, Insp.SQLS.size()));
    for (String s : Insp.SQLS) r("    " + sqlShort(s));
  }
  static double med(Call c, int n) { double[] xs = new double[n]; for (int i = 0; i < n; i++) { long t0 = System.nanoTime(); c.run(); xs[i] = (System.nanoTime() - t0) / 1e6; } Arrays.sort(xs); return xs[n / 2]; }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    ConfigurableApplicationContext c = app.run(a); OrdRepo repo = c.getBean(OrdRepo.class); CustRepo cr = c.getBean(CustRepo.class); JdbcTemplate jdbc = c.getBean(JdbcTemplate.class);
    jdbc.execute("set session cte_max_recursion_depth = 600000");
    jdbc.execute("insert into customer(id, name) with recursive s(n) as (select 1 union all select n + 1 from s where n < 50) select n, concat('c', n) from s");
    jdbc.execute("insert into ord(id, status, amount, bucket, created_at, customer_id) with recursive s(n) as (select 1 union all select n + 1 from s where n < 500000) select n, elt(1 + n % 4, 'NEW', 'PAID', 'SHIPPED', 'DONE'), n % 1000, n % 10, date_add('2024-01-01', interval n second), case when n <= 20000 then 1 + n % 50 else null end from s");
    jdbc.execute("create index ix_ord_status on ord(status)"); jdbc.execute("analyze table ord");
    r("数据:ord 表 " + jdbc.queryForObject("select count(*) from ord", Integer.class) + " 行,status 有 4 个取值各约 125000 行,索引 ix_ord_status(status);前 20000 行属于 50 个 customer(每人 400 行)");
    Insp.on = true;
    r("== 一:Page、Slice、List 各发几条 SQL");
    t("findByStatus(\\"NEW\\", PageRequest.of(0, 20))(Page)", () -> repo.findByStatus("NEW", PageRequest.of(0, 20)));
    t("findSliceByStatus(\\"NEW\\", PageRequest.of(0, 20))(Slice)", () -> repo.findSliceByStatus("NEW", PageRequest.of(0, 20)));
    t("findListByStatus(\\"NEW\\", PageRequest.of(0, 20))(List)", () -> repo.findListByStatus("NEW", PageRequest.of(0, 20)));
    t("@Query(\\"select o from Ord o where o.status = ?1\\") Page,不写 countQuery", () -> repo.q1("NEW", PageRequest.of(0, 20)));
    t("@Query(…, countQuery = …) Page", () -> repo.q2("NEW", PageRequest.of(0, 20)));
    r("== 二:什么时候 Page 可以不发 count 查询");
    t("findByIdLessThanEqual(5, 第 0 页,每页 20)(总共只有 5 行)", () -> repo.findByIdLessThanEqual(5, PageRequest.of(0, 20)));
    t("findByIdLessThanEqual(30, 第 0 页,每页 20)(总共 30 行,第一页满了)", () -> repo.findByIdLessThanEqual(30, PageRequest.of(0, 20)));
    t("findByIdLessThanEqual(30, 第 1 页,每页 20)(最后一页只有 10 行)", () -> repo.findByIdLessThanEqual(30, PageRequest.of(1, 20)));
    t("findByIdLessThanEqual(30, 第 5 页,每页 20)(超出末页)", () -> repo.findByIdLessThanEqual(30, PageRequest.of(5, 20)));
    r("== 三:排序的几个坑");
    t("Sort.by(\\"amount\\")", () -> repo.findByStatus("NEW", PageRequest.of(0, 3, Sort.by("amount"))));
    t("Sort.by(\\"nope\\")(不存在的属性)", () -> repo.findByStatus("NEW", PageRequest.of(0, 3, Sort.by("nope"))));
    t("Sort.by(\\"amount; drop table ord\\")(想注入)", () -> repo.findByStatus("NEW", PageRequest.of(0, 3, Sort.by("amount; drop table ord"))));
    t("原生查询 Sort.by(\\"createdAt\\")(Java 属性名)", () -> repo.nat("NEW", PageRequest.of(0, 3, Sort.by("createdAt"))));
    t("原生查询 Sort.by(\\"created_at\\")(列名)", () -> repo.nat("NEW", PageRequest.of(0, 3, Sort.by("created_at"))));
    t("原生查询 Page 不排序", () -> repo.nat("NEW", PageRequest.of(0, 3)));
    for (String col : new String[]{"bucket", "bucket,id"}) {
      Sort so = col.contains(",") ? Sort.by("bucket", "id") : Sort.by("bucket"); Set<Long> seen = new HashSet<>(); int total = 0;
      for (int pg = 0; pg < 50; pg++) for (Ord o : repo.findByIdLessThanEqual(1000, PageRequest.of(pg, 20, so)).getContent()) { seen.add(o.getId()); total++; }
      r("  分页遍历前 1000 行(每页 20,50 页)按 " + so + ":共读到 " + total + " 行,其中不同的行 " + seen.size() + " 个");
    }
    r("== 四:深分页的代价(500000 行,按 id 排序,每页 20 行,各取 5 次中位数)");
    for (int pg : new int[]{0, 1000, 12500, 24999}) {
      final int p = pg; double s = med(() -> repo.findSliceBy(PageRequest.of(p, 20, Sort.by("id"))), 5); double pgm = med(() -> repo.findAll(PageRequest.of(p, 20, Sort.by("id"))), 5);
      r(String.format("  第 %d 页(offset %d):Slice %.1f ms;Page(多一条 count(*))%.1f ms", pg, pg * 20, s, pgm));
    }
    for (long after : new long[]{0, 20000, 250000, 499980}) { final long af = after; double ms = med(() -> repo.keyset(af, PageRequest.of(0, 20)), 5); r(String.format("  keyset:where id > %d order by id limit 20:%.1f ms", after, ms)); }
    r("== 五:join fetch 加分页");
    t("@Query(\\"select c from Customer c join fetch c.orders\\") Page,每页 5 个 customer", () -> cr.fetchAll(PageRequest.of(0, 5)));
    t("同上,但 countQuery 指向 select count(c) from Customer c", () -> cr.fetchAll2(PageRequest.of(0, 5)));
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x89', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x89'); URL = jdbc(my)
PR = {'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app', 'spring.jpa.hibernate.ddl-auto': 'create'}
print('Spring Boot 4.0.8 / Hibernate 7 / MySQL 26.7.0(自己起的实例);ord 表 500000 行;SQL 来自 Hibernate 的 StatementInspector')
r = srun(b, 'demo.Main', props=PR, jopts=['-Xmx2g'], timeout=900)
for l in res(r): print(l)
lg = [l for l in r['out'].splitlines() if l.startswith('LOG ')]
print(f'  Hibernate 日志(WARN 及以上)共 {len(lg)} 条:'); [print('    ' + l[:260]) for l in lg[:4]]
if not res(r): print(r['out'][-2500:])
my.stop()
