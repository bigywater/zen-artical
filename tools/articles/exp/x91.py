import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x91'); CP = scp('org.springframework.boot:spring-boot-starter-data-jpa', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.*; import org.springframework.data.jpa.repository.*; import org.springframework.data.repository.*; import org.springframework.data.domain.*; import jakarta.persistence.Entity; import jakarta.persistence.Id; import jakarta.persistence.GeneratedValue; import jakarta.persistence.GenerationType; import jakarta.persistence.OneToMany; import jakarta.persistence.ManyToOne; import jakarta.persistence.FetchType; import org.springframework.stereotype.Component; import org.springframework.transaction.support.TransactionTemplate; import org.springframework.data.jpa.repository.Query; import java.util.*;\n'
FILES = {
 'src/demo/Insp.java': HDR + '''
import org.hibernate.resource.jdbc.spi.StatementInspector; import org.springframework.boot.hibernate.autoconfigure.HibernatePropertiesCustomizer;
@Component public class Insp implements StatementInspector, HibernatePropertiesCustomizer {
  static volatile boolean on; static final List<String> SQLS = Collections.synchronizedList(new ArrayList<>()); static volatile int batch = 0;
  public String inspect(String sql) { if (on) SQLS.add(sql); return sql; }
  public void customize(Map<String, Object> p) { p.put("hibernate.session_factory.statement_inspector", this); if (System.getProperty("x91.batch") != null) p.put("hibernate.default_batch_fetch_size", System.getProperty("x91.batch")); }
}
''',
 'src/demo/Author.java': HDR + '@Entity public class Author { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String name; @OneToMany(mappedBy = "author") List<Book> books = new ArrayList<>(); @OneToMany(mappedBy = "author") List<Award> awards = new ArrayList<>(); public Author() {} public Author(String n) { name = n; } public Long getId() { return id; } public String getName() { return name; } public List<Book> getBooks() { return books; } public List<Award> getAwards() { return awards; } }\n',
 'src/demo/Book.java': HDR + '@Entity public class Book { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String title; @ManyToOne Author author; public Book() {} public Book(String t, Author a) { title = t; author = a; } public Author getAuthor() { return author; } }\n',
 'src/demo/Award.java': HDR + '@Entity public class Award { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String name; @ManyToOne(fetch = FetchType.LAZY) Author author; public Award() {} public Award(String n, Author a) { name = n; author = a; } }\n',
 'src/demo/Poet.java': HDR + '@Entity public class Poet { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String name; @OneToMany(mappedBy = "poet") Set<Poem> poems = new HashSet<>(); @OneToMany(mappedBy = "poet") Set<Prize> prizes = new HashSet<>(); public Poet() {} public Poet(String n) { name = n; } public Set<Poem> getPoems() { return poems; } }\n',
 'src/demo/Poem.java': HDR + '@Entity public class Poem { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String title; @ManyToOne(fetch = FetchType.LAZY) Poet poet; public Poem() {} public Poem(String t, Poet p) { title = t; poet = p; } }\n',
 'src/demo/Prize.java': HDR + '@Entity public class Prize { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String name; @ManyToOne(fetch = FetchType.LAZY) Poet poet; public Prize() {} public Prize(String n, Poet p) { name = n; poet = p; } }\n',
 'src/demo/AuthorDto.java': HDR + 'public record AuthorDto(String name, long books) {}\n',
 'src/demo/NameOnly.java': HDR + 'public interface NameOnly { String getName(); }\n',
 'src/demo/AuthorRepo.java': HDR + '''
public interface AuthorRepo extends JpaRepository<Author, Long> {
  @Query("select a from Author a join fetch a.books") List<Author> withBooks();
  @EntityGraph(attributePaths = "books") @Query("select a from Author a") List<Author> graphBooks();
  @EntityGraph(attributePaths = {"books"}) List<Author> findByNameStartingWith(String p);
  @Query("select a from Author a join fetch a.books join fetch a.awards") List<Author> withBoth();
  @Query("select new demo.AuthorDto(a.name, count(b)) from Author a join a.books b group by a.name") List<AuthorDto> dto();
  List<NameOnly> findAllProjectedBy();
}
''',
 'src/demo/BookRepo.java': HDR + 'public interface BookRepo extends JpaRepository<Book, Long> { @Query("select b from Book b join fetch b.author") List<Book> withAuthor(); }\n',
 'src/demo/PoetRepo.java': HDR + 'public interface PoetRepo extends JpaRepository<Poet, Long> { @Query("select p from Poet p join fetch p.poems join fetch p.prizes") List<Poet> withBoth(); }\n',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  static String sqlShort(String s) { String x = s.replaceAll("\\\\s+", " ").trim(); return x.replaceFirst("^select (distinct )?.*? from", x.startsWith("select distinct") ? "select distinct … from" : "select … from"); }
  interface Call { Object run(); }
  static TransactionTemplate tx;
  static void t(String label, Call c, boolean showSql) {
    Insp.SQLS.clear(); Object[] res = new Object[1]; try { tx.executeWithoutResult(s -> res[0] = c.run()); } catch (Throwable e) { Throwable rc = e; while (rc.getCause() != null) rc = rc.getCause(); res[0] = "抛 " + e.getClass().getSimpleName() + ":" + String.valueOf(rc.getMessage()).split("\\\\n")[0]; }
    Map<String, Integer> shapes = new LinkedHashMap<>(); for (String s : Insp.SQLS) shapes.merge(sqlShort(s), 1, Integer::sum);
    r(label + "  ⇒ " + res[0] + ";发出 " + Insp.SQLS.size() + " 条 SQL(" + shapes.size() + " 种)");
    if (showSql) shapes.forEach((k, v) -> r("    " + (v > 1 ? v + " × " : "") + (k.length() > 190 ? k.substring(0, 190) + "…" : k)));
  }
  static double med(Call c, int n) { double[] xs = new double[n]; for (int i = 0; i < n; i++) { long t0 = System.nanoTime(); tx.executeWithoutResult(s -> c.run()); xs[i] = (System.nanoTime() - t0) / 1e6; } Arrays.sort(xs); return xs[n / 2]; }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    ConfigurableApplicationContext c = app.run(a); AuthorRepo ar = c.getBean(AuthorRepo.class); BookRepo br = c.getBean(BookRepo.class); PoetRepo pr = c.getBean(PoetRepo.class); tx = c.getBean(TransactionTemplate.class);
    tx.executeWithoutResult(s -> { for (int i = 0; i < 200; i++) { Author au = ar.save(new Author("author" + i)); for (int j = 0; j < 10; j++) br.save(new Book("b" + i + "-" + j, au)); } });
    c.getBean(org.springframework.jdbc.core.JdbcTemplate.class).execute("insert into award(name, author_id) select concat('aw', a.id, x.n), a.id from author a join (select 1 n union select 2 union select 3) x");
    tx.executeWithoutResult(s -> { for (int i = 0; i < 20; i++) { Poet p = pr.save(new Poet("poet" + i)); } });
    c.getBean(org.springframework.jdbc.core.JdbcTemplate.class).execute("insert into poem(title, poet_id) select concat('m', p.id, x.n), p.id from poet p join (select 1 n union select 2 union select 3 union select 4 union select 5) x");
    c.getBean(org.springframework.jdbc.core.JdbcTemplate.class).execute("insert into prize(name, poet_id) select concat('z', p.id, x.n), p.id from poet p join (select 1 n union select 2 union select 3) x");
    Insp.on = true; boolean batched = System.getProperty("x91.batch") != null;
    if (batched) {
      r("== (default_batch_fetch_size=" + System.getProperty("x91.batch") + ")");
      t("findAll() 后遍历每个作者的 books.size()", () -> { int n = 0; for (Author au : ar.findAll()) n += au.getBooks().size(); return n + " 本书"; }, true);
      t("bookRepo.findAll() 后访问每本书的 author", () -> { Set<Long> ids = new HashSet<>(); for (Book bk : br.findAll()) ids.add(bk.getAuthor().getId()); return ids.size() + " 个作者"; }, true);
      System.exit(0);
    }
    r("== 一:N+1 是怎么出现的(200 个作者,每人 10 本书,3 个奖项)");
    t("authorRepo.findAll() 之后遍历每个作者的 books.size()", () -> { int n = 0; for (Author au : ar.findAll()) n += au.getBooks().size(); return n + " 本书"; }, true);
    t("bookRepo.findAll() 之后访问每本书的 author(@ManyToOne 默认 EAGER)", () -> { Set<Long> ids = new HashSet<>(); for (Book bk : br.findAll()) ids.add(bk.getAuthor().getId()); return ids.size() + " 个作者"; }, true);
    r("== 二:几种修法");
    t("@Query(\\"select a from Author a join fetch a.books\\")", () -> { int n = 0; List<Author> l = ar.withBooks(); for (Author au : l) n += au.getBooks().size(); return l.size() + " 个作者," + n + " 本书"; }, true);
    t("@EntityGraph(attributePaths = \\"books\\") + @Query(\\"select a from Author a\\")", () -> { int n = 0; List<Author> l = ar.graphBooks(); for (Author au : l) n += au.getBooks().size(); return l.size() + " 个作者," + n + " 本书"; }, true);
    t("@EntityGraph 加在派生查询 findByNameStartingWith(\\"author1\\")", () -> { int n = 0; List<Author> l = ar.findByNameStartingWith("author1"); for (Author au : l) n += au.getBooks().size(); return l.size() + " 个作者," + n + " 本书"; }, true);
    t("bookRepo.withAuthor()(join fetch 把 ManyToOne 一起取回)", () -> { Set<Long> ids = new HashSet<>(); for (Book bk : br.withAuthor()) ids.add(bk.getAuthor().getId()); return ids.size() + " 个作者"; }, true);
    t("DTO 投影 select new AuthorDto(name, count(b)) … group by", () -> ar.dto().size() + " 行 DTO", true);
    t("接口投影 findAllProjectedBy()(只有 getName)", () -> ar.findAllProjectedBy().size() + " 行", true);
    r("== 三:同时 fetch 两个集合");
    t("Author:join fetch a.books join fetch a.awards(两个 List)", () -> ar.withBoth().size() + " 个作者", false);
    t("Poet:join fetch p.poems join fetch p.prizes(两个 Set)", () -> { List<Poet> l = pr.withBoth(); return l.size() + " 个诗人"; }, true);
    var jt = c.getBean(org.springframework.jdbc.core.JdbcTemplate.class);
    r("  对应的 SQL 在数据库里实际返回的行数:Poet join poem join prize = " + jt.queryForObject("select count(*) from poet p join poem m on p.id=m.poet_id join prize z on p.id=z.poet_id", Integer.class) + " 行(20 个诗人 × 5 首 × 3 个奖);Author join book = " + jt.queryForObject("select count(*) from author a join book b on a.id=b.author_id", Integer.class) + " 行");
    r("== 四:耗时(200 个作者 × 10 本书,各取 5 次中位数,每次在新事务里)");
    for (var e : new LinkedHashMap<String, Call>() {{
      put("N+1(findAll 再遍历 books)", () -> { int n = 0; for (Author au : ar.findAll()) n += au.getBooks().size(); return n; });
      put("join fetch", () -> { int n = 0; for (Author au : ar.withBooks()) n += au.getBooks().size(); return n; });
      put("@EntityGraph", () -> { int n = 0; for (Author au : ar.graphBooks()) n += au.getBooks().size(); return n; });
    }}.entrySet()) { med(e.getValue(), 2); r(String.format("  %s:%.1f ms", e.getKey(), med(e.getValue(), 5))); }
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x91', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x91'); URL = jdbc(my)
PR = {'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app', 'spring.jpa.hibernate.ddl-auto': 'create'}
print('Spring Boot 4.0.8 / Hibernate 7 / MySQL 26.7.0(自己起的实例);Author 200 个、Book 2000 本、Award 600 个;Poet 20 个、Poem 100 首、Prize 60 个;SQL 来自 StatementInspector,select 的列清单省略成 …')
r = srun(b, 'demo.Main', props=PR, timeout=600)
for l in res(r): print(l)
if not res(r): print(r['out'][-2500:])
r = srun(b, 'demo.Main', props=dict(PR, **{'x91.batch': '50', 'spring.jpa.hibernate.ddl-auto': 'create'}), timeout=600)
print('== 五:default_batch_fetch_size = 50')
for l in res(r)[1:]: print(l)
if not res(r): print(r['out'][-2500:])
my.stop()
