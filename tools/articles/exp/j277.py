import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *; from jpal import *
tee('j277'); R = {}
FILES = {'logging.properties': JPA_LOGGING,
 'P.java': 'import jakarta.persistence.*;\n@Entity @Table(uniqueConstraints = @UniqueConstraint(columnNames = "code")) public class P { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String code; String name; int age; byte[] pad; P() {} P(String c, String n, int a) { code = c; name = n; age = a; } public String getName() { return name; } }',
 'Main.java': r'''
import jakarta.persistence.*; import org.hibernate.*; import java.util.*; import java.sql.*;
public class Main {
  static EntityManagerFactory emf; static void say(String s) { System.out.println("RES " + s); } static void sec(String s) { System.out.println("SEC " + s); }
  static long stmts() { return emf.unwrap(SessionFactory.class).getStatistics().getPrepareStatementCount(); }
  static void jdbc(String sql) throws Exception { try (Connection c = DriverManager.getConnection("jdbc:postgresql://127.0.0.1:9501/lab", "lab", ""); Statement s = c.createStatement()) { s.execute(sql); } }
  static long used() { System.gc(); try { Thread.sleep(150); } catch (InterruptedException e) { } System.gc(); Runtime r = Runtime.getRuntime(); return (r.totalMemory() - r.freeMemory()) >> 20; }
  public static void main(String[] a) throws Exception {
    emf = Persistence.createEntityManagerFactory("demo"); EntityManager em = emf.createEntityManager(); em.getTransaction().begin(); em.persist(new P("c1", "alice", 30)); em.persist(new P("c2", "bob", 40)); em.getTransaction().commit(); em.close();
    sec("== 一:哪些操作会用到一级缓存、哪些一定访问数据库(同一个 EntityManager 里,每条语句的新增 SQL 数)");
    em = emf.createEntityManager(); long s0 = stmts(); long b = s0;
    P p = em.find(P.class, 1L); say("find(1) 第一次:+" + (stmts() - b)); b = stmts(); em.find(P.class, 1L); say("find(1) 第二次:+" + (stmts() - b) + "(命中一级缓存)"); b = stmts(); em.find(P.class, 1L); em.find(P.class, 1L); say("再 find 两次:+" + (stmts() - b));
    b = stmts(); em.createQuery("select p from P p where p.id = 1", P.class).getSingleResult(); say("JPQL 按主键查同一行:+" + (stmts() - b) + "(JPQL 总是访问数据库)"); b = stmts(); em.createQuery("select p from P p where p.code = 'c1'", P.class).getSingleResult(); say("JPQL 按唯一字段 code 查同一行:+" + (stmts() - b)); b = stmts(); em.getReference(P.class, 1L); say("getReference(1)(已经在缓存里):+" + (stmts() - b));
    b = stmts(); em.find(P.class, 999L); em.find(P.class, 999L); em.find(P.class, 999L); say("find 一个不存在的主键(999)三次:+" + (stmts() - b) + "(不存在的行没有“负缓存”,每次都查)"); b = stmts(); em.createQuery("select count(p) from P p", Long.class).getSingleResult(); say("count 聚合查询:+" + (stmts() - b));
    P q = em.createQuery("select p from P p where p.id = 2", P.class).getSingleResult(); b = stmts(); P q2 = em.find(P.class, 2L); say("先用 JPQL 把 bob 查出来,再 find(2):+" + (stmts() - b) + ",q == q2 为 " + (q == q2) + "(JPQL 的结果也会放进一级缓存)"); em.close();
    sec("== 二:陈旧数据:另一个事务(这里直接用 JDBC)改了行,当前 EntityManager 看到的是什么");
    em = emf.createEntityManager(); em.getTransaction().begin(); P x = em.find(P.class, 1L); say("加载 alice:age = " + x.age + ",name = " + x.name); jdbc("update p set age = 99, name = 'ALICE-DB' where id = 1"); say("(另一个连接已经提交:age = 99,name = ALICE-DB)");
    P y = em.find(P.class, 1L); say("find(1):age = " + y.age + ",name = " + y.name + "(缓存里的旧值)"); P z = em.createQuery("select p from P p where p.id = 1", P.class).getSingleResult(); say("JPQL 重新查询(SQL 确实发给了数据库):返回对象 == 缓存里的对象为 " + (z == x) + ",z.age = " + z.age + ",z.name = " + z.name + "(数据库里已经是 99,但返回的还是缓存里的旧实体)");
    Object[] row = em.createQuery("select p.age, p.name from P p where p.id = 1", Object[].class).getSingleResult(); say("只查字段(投影)select p.age, p.name:" + row[0] + ", " + row[1] + "(投影直接读数据库,看到新值)");
    em.refresh(x); say("em.refresh(x) 之后:age = " + x.age + ",name = " + x.name); jdbc("update p set age = 100 where id = 1"); em.clear(); P w = em.find(P.class, 1L); say("em.clear() 后再 find:age = " + w.age + "(重新从数据库加载)"); em.getTransaction().commit(); em.close();
    sec("== 三:陈旧的缓存 + 修改 = 丢失更新(没有 @Version 时)");
    jdbc("update p set age = 10, name = 'alice' where id = 1"); em = emf.createEntityManager(); em.getTransaction().begin(); P m = em.find(P.class, 1L); say("EntityManager 1 加载 alice:age = " + m.age); jdbc("update p set age = 77 where id = 1"); say("(另一个连接把 age 改成 77 并提交)"); m.name = "alice-renamed"; em.getTransaction().commit(); em.close();
    em = emf.createEntityManager(); P after = em.find(P.class, 1L); say("EntityManager 1 只改了 name,提交之后库里:age = " + after.age + ",name = " + after.name + "(UPDATE 带上了所有列,把另一个事务写的 age = 77 覆盖回了 10)"); em.close();
    sec("== 四:缓存里的实体不会自己释放:加载 100,000 行,堆内存与耗时");
    jdbc("insert into p(code, name, age, pad) select 'k' || g, 'n' || g, g % 100, decode(repeat('ab', 200), 'hex') from generate_series(1, 100000) g");
    long base = used(); say("加载前堆内存 " + base + " MiB");
    for (int mode = 0; mode < 3; mode++) { String lab = mode == 0 ? "托管实体不清理(一个 EntityManager 全部留着)" : mode == 1 ? "每 1000 个 em.clear()" : "StatelessSession(没有一级缓存)"; long t0 = System.nanoTime(); long peak = 0; int n = 0;
      if (mode < 2) { em = emf.createEntityManager(); em.getTransaction().begin(); try (var rs = em.createQuery("select p from P p", P.class).setHint("org.hibernate.fetchSize", 1000).getResultStream()) { var it = rs.iterator(); while (it.hasNext()) { P e = it.next(); n++; if (mode == 1 && n % 1000 == 0) em.clear(); if (n == 100000) peak = used(); } } if (mode == 0) { long after2 = used(); say(lab + ":读完 " + n + " 行,堆内存 " + after2 + " MiB(+" + (after2 - base) + " MiB),耗时 " + (System.nanoTime() - t0) / 1_000_000 + " ms,em.contains 随机一个 = " + em.contains(em.find(P.class, 5L))); } else { long after2 = used(); say(lab + ":读完 " + n + " 行,堆内存 " + after2 + " MiB(+" + (after2 - base) + " MiB),耗时 " + (System.nanoTime() - t0) / 1_000_000 + " ms"); } em.getTransaction().rollback(); em.close(); }
      else { try (StatelessSession ss = emf.unwrap(SessionFactory.class).openStatelessSession()) { ss.getTransaction().begin(); try (var sc = ss.createQuery("select p from P p", P.class).setFetchSize(1000).scroll(ScrollMode.FORWARD_ONLY)) { while (sc.next()) { n++; } } long after2 = used(); say(lab + ":读完 " + n + " 行,堆内存 " + after2 + " MiB(+" + (after2 - base) + " MiB),耗时 " + (System.nanoTime() - t0) / 1_000_000 + " ms"); ss.getTransaction().rollback(); } } }
    emf.close();
  }
}
'''}
pg = PGI(9501).start()
try:
    rc, o = jpa('j277a', FILES, ['P'], props={'hibernate.show_sql': 'false'}, jopts=('-Xmx1g',), timeout=600)
finally: pg.stop()
if rc != 0: print(o[:3000]); sys.exit()
for l in o.splitlines():
    if l.startswith('SEC '): print(l[4:])
    elif l.startswith('RES '): print('  ' + l[4:])
