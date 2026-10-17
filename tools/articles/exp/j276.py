import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *; from jpal import *
tee('j276'); R = {}
CB = lambda cls: f'''
  @PrePersist void prePersist() {{ Log.cb("{cls}", "@PrePersist", this); }} @PostPersist void postPersist() {{ Log.cb("{cls}", "@PostPersist", this); }}
  @PreUpdate void preUpdate() {{ Log.cb("{cls}", "@PreUpdate", this); }} @PostUpdate void postUpdate() {{ Log.cb("{cls}", "@PostUpdate", this); }}
  @PreRemove void preRemove() {{ Log.cb("{cls}", "@PreRemove", this); }} @PostRemove void postRemove() {{ Log.cb("{cls}", "@PostRemove", this); }}
  @PostLoad void postLoad() {{ Log.cb("{cls}", "@PostLoad", this); }}'''
FILES = {'logging.properties': JPA_LOGGING,
 'Log.java': 'public class Log { static void cb(String c, String ev, Object o) { System.out.println("RES     回调 " + c + " " + ev); } static void say(String s) { System.out.println("RES " + s); } static void sec(String s) { System.out.println("SEC " + s); } }',
 'A.java': 'import jakarta.persistence.*;\n@Entity public class A { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String name; int touched; ' + CB('A(IDENTITY)') + '\n A() {} A(String n) { name = n; } }',
 'B.java': 'import jakarta.persistence.*;\n@Entity @SequenceGenerator(name = "bseq", sequenceName = "b_seq", allocationSize = 1) public class B { @Id @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "bseq") Long id; String name; int touched; ' + CB('B(SEQUENCE)') + '\n B() {} B(String n) { name = n; } }',
 'C.java': 'import jakarta.persistence.*; import java.time.*;\n@Entity public class C { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String name; String note; Instant modified; @PreUpdate void pre() { modified = Instant.parse("2026-01-01T00:00:00Z"); } @PostUpdate void post() { note = "set-in-PostUpdate"; Log.cb("C", "@PostUpdate 里改了 note = " + note, this); } @PrePersist void pp() { if (name == null) throw new IllegalStateException("name 不能为空(@PrePersist 校验)"); } C() {} C(String n) { name = n; } }',
 'D.java': 'import jakarta.persistence.*;\n@Entity public class D { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String name; @PreUpdate void pre() { EntityManager em = Main.currentEm; try { Main.dCalls++; Long n = em.createQuery("select count(d) from D d", Long.class).getSingleResult(); if (Main.dCalls <= 2) Log.cb("D", "@PreUpdate 里执行 JPQL 成功,count = " + n + "(第 " + Main.dCalls + " 次进入回调)", this); } catch (Throwable t) { Log.cb("D", "@PreUpdate 里执行 JPQL 失败:" + t.getClass().getSimpleName() + ":" + String.valueOf(t.getMessage()).replaceAll("\\\\s+", " ").substring(0, Math.min(90, String.valueOf(t.getMessage()).length())), this); } } D() {} D(String n) { name = n; } }',
 'Main.java': r'''
import jakarta.persistence.*; import org.hibernate.*; import java.util.*;
public class Main {
  static EntityManagerFactory emf; static EntityManager currentEm; static EntityManager em; static int dCalls;
  static String t(Throwable e) { return e.getClass().getSimpleName() + ":" + String.valueOf(e.getMessage()).replaceAll("\\s+", " ").substring(0, Math.min(110, String.valueOf(e.getMessage()).length())); }
  static void tryIt(String label, Runnable r) { try { r.run(); } catch (Throwable e) { Log.say("  " + label + " → " + t(e)); return; } Log.say("  " + label + " → 没有异常"); }
  public static void main(String[] a) {
    emf = Persistence.createEntityManagerFactory("demo"); em = emf.createEntityManager(); em.getTransaction().begin(); em.persist(new A("seed")); em.persist(new B("seed")); em.persist(new C("seed")); em.persist(new D("seed")); em.getTransaction().commit(); em.close();
    Log.sec("== 一:状态转换:new / managed / detached / removed");
    em = emf.createEntityManager(); em.getTransaction().begin(); A n = new A("n1"); Log.say("new A:contains = " + em.contains(n) + ",id = " + n.id); em.persist(n); Log.say("persist 之后:contains = " + em.contains(n) + ",id = " + n.id); long b = Main.stmts(); em.persist(n); Log.say("对托管对象再次 persist:新增 SQL " + (Main.stmts() - b) + " 条(无操作)");
    A loaded = em.find(A.class, 1L); em.detach(loaded); Log.say("find 后 detach:contains = " + em.contains(loaded)); tryIt("对游离对象 persist", () -> em.persist(loaded)); tryIt("对游离对象 remove", () -> em.remove(loaded));
    A m = em.find(A.class, 1L); em.remove(m); Log.say("remove(托管对象) 之后:contains = " + em.contains(m) + "(removed 状态,contains 返回 false),SQL 还没发"); b = Main.stmts(); em.persist(m); Log.say("对 removed 对象再次 persist:contains = " + em.contains(m) + "(回到 managed,新增 SQL " + (Main.stmts() - b) + " 条,不会 DELETE 也不会 INSERT)"); em.remove(m); tryIt("对 removed 对象 merge", () -> em.merge(m));
    A fresh = new A("never-persisted"); tryIt("对 new 对象 remove", () -> em.remove(fresh)); tryIt("persist(null)", () -> em.persist(null));
    em.getTransaction().rollback(); em.close();
    Log.sec("== 二:回调的顺序与 SQL 的时机:IDENTITY 与 SEQUENCE 两种主键策略(show_sql 的 Hibernate: … 行是实际发出的 SQL)");
    em = emf.createEntityManager(); em.getTransaction().begin(); Log.say("persist(new A) —— IDENTITY:"); em.persist(new A("a1")); Log.say("persist(new B) —— SEQUENCE:"); em.persist(new B("b1")); Log.say("flush():"); em.flush();
    Log.say("find(A, 1) / 修改 touched / flush:"); A a1 = em.find(A.class, 1L); a1.touched = 5; em.flush(); Log.say("remove(A 1) / flush:"); em.remove(a1); em.flush(); Log.say("commit:"); em.getTransaction().commit(); em.close();
    Log.sec("== 三:回调里改字段:@PreUpdate 里的修改写进同一条 UPDATE;@PostUpdate 里的修改让实体再次变脏,在下一次 flush(这里是 commit)又发一条 UPDATE");
    em = emf.createEntityManager(); em.getTransaction().begin(); C c = em.find(C.class, 1L); c.name = "renamed"; em.flush(); Log.say("flush 之后内存里:modified = " + c.modified + ",note = " + c.note + "(此时库里的 note 还是旧值,因为 @PostUpdate 在 UPDATE 之后才改它)"); long u1 = Main.stmts(); em.getTransaction().commit(); Log.say("commit 时又发出 " + (Main.stmts() - u1) + " 条 UPDATE(实体因为 @PostUpdate 里的修改又变脏了),@PostUpdate 又被调用一次"); em.close();
    em = emf.createEntityManager(); C c2 = em.find(C.class, 1L); Log.say("重新加载:modified = " + c2.modified + ",note = " + c2.note + "(两个回调里的修改最终都保存了,但 @PostUpdate 的那个靠的是第二条 UPDATE)"); em.close();
    Log.sec("== 四:回调里的限制与异常");
    em = emf.createEntityManager(); em.getTransaction().begin(); em.persist(new A("keep-me")); try { em.persist(new C((String) null)); Log.say("@PrePersist 里抛 IllegalStateException:persist 没有抛出"); } catch (Throwable e) { Log.say("@PrePersist 里抛 IllegalStateException:persist 抛出 " + t(e) + ";事务 isActive = " + em.getTransaction().isActive() + ",getRollbackOnly = " + em.getTransaction().getRollbackOnly()); } try { em.getTransaction().commit(); Log.say("之后 commit():没有抛异常"); } catch (Throwable e) { Log.say("之后 commit():" + t(e)); } em.close(); em = emf.createEntityManager(); Log.say("同一个事务里更早 persist 的 A(\"keep-me\")最终是否保存 = " + (em.createQuery("select count(a) from A a where a.name = 'keep-me'", Long.class).getSingleResult() > 0) + "(事务被标记为只能回滚,commit 没有提交它)"); em.close();
    em = emf.createEntityManager(); currentEm = em; em.getTransaction().begin(); D d = em.find(D.class, 1L); d.name = "changed"; long u0 = Main.stmts(); try { em.flush(); Log.say("@PreUpdate 里使用 EntityManager 执行 JPQL 查询之后 flush 完成:@PreUpdate 被进入了 " + dCalls + " 次(查询触发了自动 flush,flush 又触发 @PreUpdate),这次 flush 一共发出 " + (Main.stmts() - u0) + " 条 SQL"); } catch (Throwable e) { Log.say("flush 抛出 " + t(e)); } try { em.getTransaction().rollback(); } catch (Throwable e) { } em.close();
    em = emf.createEntityManager(); tryIt("没有事务时 persist(IDENTITY 主键的 A)", () -> em.persist(new A("no-tx"))); tryIt("没有事务时 flush()", () -> em.flush()); em.close();
    em = emf.createEntityManager(); tryIt("没有事务时 persist(SEQUENCE 主键的 B)", () -> em.persist(new B("no-tx"))); tryIt("之后 flush()", () -> em.flush()); em.close();
    emf.close();
  }
  static long stmts() { return emf.unwrap(SessionFactory.class).getStatistics().getPrepareStatementCount(); }
}
'''}
pg = PGI(9501).start()
try:
    rc, o = jpa('j276a', FILES, ['A', 'B', 'C', 'D'], props={'hibernate.show_sql': 'true'})
finally: pg.stop()
if rc != 0: print(o[:3000]); sys.exit()
seen_main = False; sqlD = 0
for l in o.splitlines():
    if l.startswith('SEC '): print(l[4:]); seen_main = True
    elif not seen_main: continue
    elif l.startswith('RES '): print('  ' + l[4:])
    elif l.startswith('Hibernate: ') and not re.search(r'set client_min_messages|drop table|create table|alter table|create sequence|drop sequence', l): sqlD += (1 if (l[11:].startswith('update D set') or l[11:].startswith('select count(d1_0.id)')) else 0); print('      SQL> ' + l[11:]) if not (l[11:].startswith('update D set') or l[11:].startswith('select count(d1_0.id)')) or sqlD < 2 else None
