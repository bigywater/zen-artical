import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *; from jpal import *
tee('j281'); R = {}
FILES = {'logging.properties': 'handlers=java.util.logging.ConsoleHandler\n.level=WARNING\njava.util.logging.ConsoleHandler.level=WARNING\n',
 'Author.java': '''import jakarta.persistence.*; import org.hibernate.annotations.*; import java.util.*;
@Entity @NamedEntityGraph(name = "author.books", attributeNodes = @NamedAttributeNode("books"))
public class Author { @Id Long id; String name;
  @OneToMany(mappedBy = "author") List<Book> books = new ArrayList<>();
  @OneToMany @JoinColumn(name = "author_id", insertable = false, updatable = false) @BatchSize(size = 25) List<Book> booksBatch = new ArrayList<>();
  @OneToMany @JoinColumn(name = "author_id", insertable = false, updatable = false) @Fetch(FetchMode.SUBSELECT) List<Book> booksSub = new ArrayList<>();
  @OneToMany(mappedBy = "author") Set<Book> bookSet = new LinkedHashSet<>();
  @OneToMany(mappedBy = "author") List<Award> awards = new ArrayList<>();
  @OneToMany(mappedBy = "author") Set<Award> awardSet = new LinkedHashSet<>();
  Author() {} Author(Long i, String n) { id = i; name = n; } }''',
 'Book.java': 'import jakarta.persistence.*;\n@Entity public class Book { @Id Long id; String title; @ManyToOne(fetch = FetchType.LAZY) Author author; Book() {} Book(Long i, String t, Author a) { id = i; title = t; author = a; } }',
 'Award.java': 'import jakarta.persistence.*;\n@Entity public class Award { @Id Long id; String name; @ManyToOne(fetch = FetchType.LAZY) Author author; Award() {} Award(Long i, String n, Author a) { id = i; name = n; author = a; } }',
 'Review.java': 'import jakarta.persistence.*;\n@Entity public class Review { @Id Long id; String text; @ManyToOne Author author; Review() {} Review(Long i, String t, Author a) { id = i; text = t; author = a; } }',
 'AuthorDto.java': 'public record AuthorDto(Long id, String name, Long bookCount) {}',
 'Main.java': r'''
import jakarta.persistence.*; import org.hibernate.*; import org.hibernate.stat.*; import java.util.*;
public class Main {
  static EntityManagerFactory emf; static void say(String s) { System.out.println("RES " + s); } static void sec(String s) { System.out.println("SEC " + s); }
  static Statistics st() { return emf.unwrap(SessionFactory.class).getStatistics(); } static long stmts() { return st().getPrepareStatementCount(); }
  static String t(Throwable e) { Throwable c = e; StringBuilder b = new StringBuilder(e.getClass().getSimpleName()); while (c.getCause() != null && c.getCause() != c) { c = c.getCause(); b.append(" ← ").append(c.getClass().getSimpleName()); } String m = String.valueOf(c.getMessage()).replaceAll("\\s+", " "); return b + ":" + m.substring(0, Math.min(150, m.length())); }
  interface Work { long run(EntityManager em); }
  static void measure(String label, Work w) { double[] ms = new double[7]; long stm = 0, extra = 0; for (int i = 0; i < 7; i++) { EntityManager em = emf.createEntityManager(); em.getTransaction().begin(); long s0 = stmts(); long t0 = System.nanoTime(); extra = w.run(em); ms[i] = (System.nanoTime() - t0) / 1e6; stm = stmts() - s0; em.getTransaction().rollback(); em.close(); } Arrays.sort(ms); say(String.format("%-52s SQL 语句 %5d 条;耗时 %.1f ms(7 次中位数);结果统计 %d", label, stm, ms[3], extra)); }
  public static void main(String[] a) throws Exception {
    emf = Persistence.createEntityManagerFactory("demo"); int NA = 1000, NB = 5, NW = 4; EntityManager em = emf.createEntityManager(); em.getTransaction().begin(); long bid = 1, wid = 1, rid = 1;
    for (long i = 1; i <= NA; i++) { Author au = new Author(i, "author" + i); em.persist(au); for (int k = 0; k < NB; k++) em.persist(new Book(bid++, "b" + i + "-" + k, au)); for (int k = 0; k < NW; k++) em.persist(new Award(wid++, "w" + k, au)); em.persist(new Review(rid++, "r" + i, au)); } em.getTransaction().commit(); em.close();
    sec("== 一:经典 N+1:查出 " + NA + " 个作者,再逐个访问 books.size()(每个作者 " + NB + " 本书)");
    measure("1 条查询 select a from Author a(不访问 books)", e -> e.createQuery("select a from Author a", Author.class).getResultList().size());
    measure("查询作者 + 逐个访问 a.books.size()(N+1)", e -> { long n = 0; for (Author au : e.createQuery("select a from Author a", Author.class).getResultList()) n += au.books.size(); return n; });
    sec("== 二:@ManyToOne 默认是 EAGER:select r from Review r 也会 N+1(" + NA + " 个评论,各指向一个不同的作者)");
    measure("em.find(Review, 1)(find 会 join 出作者)", e -> { Review r = e.find(Review.class, 1L); return r.author.id; });
    measure("JPQL select r from Review r(默认 EAGER 的作者)", e -> e.createQuery("select r from Review r", Review.class).getResultList().size());
    measure("JPQL select r from Review r join fetch r.author", e -> e.createQuery("select r from Review r join fetch r.author", Review.class).getResultList().size());
    sec("== 三:几种修复方式(同样的工作:读出 " + NA + " 个作者并统计所有书的数量)");
    measure("基线:N+1(plain lazy)", e -> { long n = 0; for (Author au : e.createQuery("select a from Author a", Author.class).getResultList()) n += au.books.size(); return n; });
    measure("join fetch(select distinct a … join fetch a.books)", e -> { long n = 0; for (Author au : e.createQuery("select distinct a from Author a join fetch a.books", Author.class).getResultList()) n += au.books.size(); return n; });
    measure("@BatchSize(size = 25)", e -> { long n = 0; for (Author au : e.createQuery("select a from Author a", Author.class).getResultList()) n += au.booksBatch.size(); return n; });
    measure("@Fetch(FetchMode.SUBSELECT)", e -> { long n = 0; for (Author au : e.createQuery("select a from Author a", Author.class).getResultList()) n += au.booksSub.size(); return n; });
    measure("EntityGraph(命名图 author.books,fetchgraph 提示)", e -> { long n = 0; for (Author au : e.createQuery("select a from Author a", Author.class).setHint("jakarta.persistence.fetchgraph", e.getEntityGraph("author.books")).getResultList()) n += au.books.size(); return n; });
    measure("DTO 投影(select new AuthorDto(a.id, a.name, count(b)) … group by)", e -> { long n = 0; for (AuthorDto d : e.createQuery("select new AuthorDto(a.id, a.name, count(b)) from Author a left join a.books b group by a.id, a.name", AuthorDto.class).getResultList()) n += d.bookCount(); return n; });
    sec("== 四:同时抓取两个集合:MultipleBagFetchException 与笛卡尔积");
    try { EntityManager e = emf.createEntityManager(); e.createQuery("select a from Author a join fetch a.books join fetch a.awards", Author.class).getResultList(); say("两个 List 同时 join fetch:没有报错"); e.close(); } catch (Throwable ex) { say("两个 List 同时 join fetch:" + t(ex)); }
    for (String q : new String[]{"select distinct a from Author a join fetch a.bookSet", "select distinct a from Author a join fetch a.bookSet join fetch a.awardSet"}) { EntityManager e = emf.createEntityManager(); long s0 = stmts(); long t0 = System.nanoTime(); List<Author> l = e.createQuery(q, Author.class).getResultList(); double ms = (System.nanoTime() - t0) / 1e6; long rows = e.createNativeQuery(q.contains("awardSet") ? "select count(*) from author a join book b on b.author_id = a.id join award w on w.author_id = a.id" : "select count(*) from author a join book b on b.author_id = a.id", Long.class).getSingleResult().equals(0L) ? 0 : (Long) e.createNativeQuery(q.contains("awardSet") ? "select count(*) from author a join book b on b.author_id = a.id join award w on w.author_id = a.id" : "select count(*) from author a join book b on b.author_id = a.id").getSingleResult(); say((q.contains("awardSet") ? "Set 同时 join fetch books 与 awards" : "Set join fetch books") + ":返回 " + l.size() + " 个作者,SQL " + (stmts() - s0 - 2) + " 条,数据库返回的行数 " + rows + ",耗时 " + String.format("%.1f", ms) + " ms"); e.close(); }
    sec("== 五:分页 + 集合 join fetch:setMaxResults 被“在内存里分页”(警告 HHH90003004)");
    for (String q : new String[]{"select a from Author a order by a.id", "select a from Author a join fetch a.bookSet order by a.id"}) { EntityManager e = emf.createEntityManager(); long s0 = stmts(); long t0 = System.nanoTime(); List<Author> l = e.createQuery(q, Author.class).setMaxResults(10).getResultList(); double ms = (System.nanoTime() - t0) / 1e6; say((q.contains("fetch") ? "带集合 join fetch 的" : "不带 fetch 的") + "分页查询 setMaxResults(10):返回 " + l.size() + " 个作者,SQL " + (stmts() - s0) + " 条,耗时 " + String.format("%.1f", ms) + " ms,一级缓存里有 " + e.unwrap(Session.class).getStatistics().getEntityCount() + " 个实体"); e.close(); }
    emf.close();
  }
}
'''}
pg = PGI(9501).start()
try:
    rc, o = jpa('j281a', FILES, ['Author', 'Book', 'Award', 'Review'], props={'hibernate.show_sql': 'false'}, timeout=900)
finally: pg.stop()
if rc != 0: print(o[:3500]); sys.exit()
for l in o.splitlines():
    if l.startswith('SEC '): print(l[4:])
    elif l.startswith('RES '): print('  ' + l[4:])
    elif 'HHH90003004' in l or 'applying in memory' in l: print('  [日志警告] ' + l.strip()[:200])
