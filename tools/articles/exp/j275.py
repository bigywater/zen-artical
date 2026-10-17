import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *; from jpal import *
tee('j275'); R = {}
FILES = {'logging.properties': JPA_LOGGING, 'P.java': '''
import jakarta.persistence.*;
@Entity public class P { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String name; int age; P() {} P(String n, int a) { name = n; age = a; } public String getName() { return name; } }
''', 'Main.java': r'''
import jakarta.persistence.*; import org.hibernate.*; import java.util.*;
public class Main {
  static EntityManagerFactory emf;
  static long stmts() { return emf.unwrap(SessionFactory.class).getStatistics().getPrepareStatementCount(); }
  static void say(String s) { System.out.println("RES " + s); }
  static void sec(String s) { System.out.println("SEC " + s); }
  static void tx(java.util.function.Consumer<EntityManager> w) { EntityManager em = emf.createEntityManager(); em.getTransaction().begin(); w.accept(em); em.getTransaction().commit(); em.close(); }
  public static void main(String[] a) throws Exception {
    emf = Persistence.createEntityManagerFactory("demo");
    tx(em -> { em.persist(new P("alice", 30)); em.persist(new P("bob", 40)); });
    sec("== 一:脏检查:改了托管实体的字段、没有调用任何 save / update,提交时就会发出 UPDATE");
    EntityManager em = emf.createEntityManager(); em.getTransaction().begin(); long s0 = stmts(); P p = em.find(P.class, 1L); say("find 之后:SQL 语句数 +" + (stmts() - s0) + ",em.contains(p) = " + em.contains(p) + ",age = " + p.age);
    p.age = 31; say("p.age = 31(没有调用任何持久化方法);在 commit 之前 SQL 语句数 +" + (stmts() - s0)); long s1 = stmts(); em.getTransaction().commit(); say("commit 之后新增 SQL 语句 " + (stmts() - s1) + " 条(更新语句,见上面的 Hibernate: update …)"); em.close();
    em = emf.createEntityManager(); em.getTransaction().begin(); p = em.find(P.class, 1L); s1 = stmts(); p.age = p.age; em.getTransaction().commit(); say("把 age 赋成相同的值再 commit:新增 UPDATE " + (stmts() - s1) + " 条(只比较值,不看是否调用过 setter)"); em.close();
    em = emf.createEntityManager(); em.getTransaction().begin(); p = em.find(P.class, 1L); s1 = stmts(); int old = p.age; p.age = 99; p.age = old; em.getTransaction().commit(); say("改成 99 又改回原值再 commit:新增 UPDATE " + (stmts() - s1) + " 条(与加载时的快照比较,中间状态不重要)"); em.close();
    em = emf.createEntityManager(); em.getTransaction().begin(); p = em.find(P.class, 2L); say("批量更新绕过持久化上下文:内存里 bob 的 age = " + p.age); int n = em.createQuery("update P set age = 70 where id = 2").executeUpdate(); say("JPQL update 影响 " + n + " 行;内存里的 p.age 仍是 " + p.age + ",数据库里已经是 70"); em.refresh(p); say("em.refresh(p) 之后 p.age = " + p.age); em.getTransaction().rollback(); em.close();
    sec("== 二:一级缓存与身份映射:同一个 EntityManager 里同一个主键永远是同一个对象");
    em = emf.createEntityManager(); s0 = stmts(); P x1 = em.find(P.class, 1L); P x2 = em.find(P.class, 1L); say("同一个 EntityManager 里 find 两次:x1 == x2 为 " + (x1 == x2) + ",SQL 语句数 +" + (stmts() - s0)); P viaQuery = em.createQuery("select p from P p where p.id = 1", P.class).getSingleResult(); say("再用 JPQL 查同一行:返回的对象 == x1 为 " + (viaQuery == x1) + ",SQL 语句数 +" + (stmts() - s0) + "(查询仍然发出了 SQL,但返回的是已托管的那个对象)");
    EntityManager em2 = emf.createEntityManager(); P y = em2.find(P.class, 1L); say("另一个 EntityManager 里 find 同一行:y == x1 为 " + (y == x1) + ",y.equals(x1) 为 " + y.equals(x1) + "(没有重写 equals,所以是不同对象)"); long b0 = stmts(); P ref = em.getReference(P.class, 2L); say("getReference(2):新增 SQL 语句 " + (stmts() - b0) + " 条(没有查询),对象类 = " + ref.getClass().getSimpleName().replaceAll("\\$.*", "") + "(Hibernate 生成的代理子类),Hibernate.isInitialized = " + Hibernate.isInitialized(ref)); say("直接读代理对象的字段 ref.name = " + ref.name + "(代理自己的字段是 null,没有触发加载),Hibernate.isInitialized = " + Hibernate.isInitialized(ref)); b0 = stmts(); String nm = ref.getName(); say("调用 ref.getName() = " + nm + ":新增 SQL 语句 " + (stmts() - b0) + " 条,Hibernate.isInitialized = " + Hibernate.isInitialized(ref)); em2.close(); em.close();
    sec("== 三:托管、游离与 merge");
    em = emf.createEntityManager(); em.getTransaction().begin(); P d = em.find(P.class, 1L); em.detach(d); d.age = 500; s1 = stmts(); em.getTransaction().commit(); say("detach 之后改 age = 500,commit:新增 UPDATE " + (stmts() - s1) + " 条,contains = " + em.contains(d)); em.close();
    em = emf.createEntityManager(); em.getTransaction().begin(); P merged = em.merge(d); say("把游离对象 d 交给 merge:返回对象 merged 与 d 是否同一个 = " + (merged == d) + ",merged 是否托管 = " + em.contains(merged) + ",d 是否托管 = " + em.contains(d) + ",merged.age = " + merged.age); s1 = stmts(); em.getTransaction().commit(); say("commit:新增 UPDATE " + (stmts() - s1) + " 条;之后再改 d.age = 1(d 仍然游离)不会有任何效果"); em.close();
    P fresh = new P("carol", 20); em = emf.createEntityManager(); em.getTransaction().begin(); say("新建的 P:persist 前 id = " + fresh.id + ",contains = " + em.contains(fresh)); em.persist(fresh); say("persist 之后 id = " + fresh.id + "(IDENTITY 策略要立刻 INSERT 才能得到 id),contains = " + em.contains(fresh) + ",SQL 语句数是否已增加:是"); em.getTransaction().rollback(); em.close();
    sec("== 四:flush 的时机:AUTO 模式下查询之前会先把挂起的修改发出去");
    for (FlushModeType fm : new FlushModeType[]{FlushModeType.AUTO, FlushModeType.COMMIT}) { em = emf.createEntityManager(); em.setFlushMode(fm); em.getTransaction().begin(); P q = em.find(P.class, 2L); q.age = 71; s0 = stmts(); long c = em.createQuery("select count(p) from P p where p.age = 71", Long.class).getSingleResult(); say("FlushMode = " + fm + ":改了 bob 的 age = 71 之后立刻 JPQL 查询 count(age = 71) = " + c + ",查询时新增 SQL 语句 " + (stmts() - s0) + " 条(" + (fm == FlushModeType.AUTO ? "先 UPDATE 再 SELECT" : "只有 SELECT") + ")"); em.getTransaction().rollback(); em.close(); }
    sec("== 五:代价:托管实体越多,每次 flush 的脏检查越慢");
    tx(m -> m.createNativeQuery("insert into P(name, age) select 'n' || g, g % 100 from generate_series(1, 50000) g").executeUpdate());
    for (int pass = 0; pass < 2; pass++) for (int N : new int[]{1000, 10000, 50000}) { em = emf.createEntityManager(); em.getTransaction().begin(); List<P> all = em.createQuery("select p from P p order by p.id", P.class).setMaxResults(N).getResultList(); double[] t = new double[31]; for (int i = 0; i < 31; i++) { long t0 = System.nanoTime(); em.flush(); t[i] = (System.nanoTime() - t0) / 1e6; } Arrays.sort(t); double noChange = t[15]; all.get(0).age += 1; long t0 = System.nanoTime(); em.flush(); double oneChange = (System.nanoTime() - t0) / 1e6; em.clear(); t0 = System.nanoTime(); em.flush(); double cleared = (System.nanoTime() - t0) / 1e6; if (pass == 1) say(N + " 个托管实体:没有任何修改时 flush 约 " + String.format("%.2f", noChange) + " ms(31 次中位数,第二轮,JIT 已预热);改其中 1 个后 flush " + String.format("%.2f", oneChange) + " ms;em.clear() 之后 flush " + String.format("%.3f", cleared) + " ms"); em.getTransaction().rollback(); em.close(); }
    for (int pass = 0; pass < 2; pass++) { em = emf.createEntityManager(); em.getTransaction().begin(); List<P> all = em.createQuery("select p from P p order by p.id", P.class).setMaxResults(50000).setHint("org.hibernate.readOnly", true).getResultList(); double[] t = new double[31]; for (int i = 0; i < 31; i++) { long t0 = System.nanoTime(); em.flush(); t[i] = (System.nanoTime() - t0) / 1e6; } Arrays.sort(t); if (pass == 1) say("50000 个以只读方式加载的实体(hint org.hibernate.readOnly = true):flush 约 " + String.format("%.2f", t[15]) + " ms(31 次中位数)"); all.get(0).age += 1; if (pass == 1) { long s2 = stmts(); em.flush(); say("只读加载的实体被修改后 flush:新增 SQL 语句 " + (stmts() - s2) + " 条(只读实体的修改不会被写回)"); } em.getTransaction().rollback(); em.close(); }
    emf.close();
  }
}
'''}
pg = PGI(9501).start()
try:
    rc, o = jpa('j275a', FILES, ['P'], props={'hibernate.show_sql': 'true'})
finally: pg.stop()
if rc != 0: print(o[:3000]); sys.exit()
for l in o.splitlines():
    if l.startswith('SEC '): print(l[4:])
    elif l.startswith('RES '): print('  ' + l[4:])
    elif l.startswith('Hibernate: ') and not re.search(r'set client_min_messages|drop table|create table|alter table|generate_series', l): print('      SQL> ' + l[11:])
