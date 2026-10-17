import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *; from jpal import *
tee('j278'); R = {}
FILES = {'logging.properties': JPA_LOGGING,
 'Acc.java': 'import jakarta.persistence.*;\n@Entity public class Acc { @Id Long id; String owner; long balance; @Version long version; Acc() {} Acc(Long i, String o, long b) { id = i; owner = o; balance = b; } }',
 'Cnt.java': 'import jakarta.persistence.*;\n@Entity public class Cnt { @Id Long id; long n; @Version long version; Cnt() {} Cnt(Long i) { id = i; } }',
 'Raw.java': 'import jakarta.persistence.*;\n@Entity public class Raw { @Id Long id; long n; Raw() {} Raw(Long i) { id = i; } }',
 'Main.java': r'''
import jakarta.persistence.*; import org.hibernate.*; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static EntityManagerFactory emf; static void say(String s) { System.out.println("RES " + s); } static void sec(String s) { System.out.println("SEC " + s); }
  static String t(Throwable e) { Throwable c = e; StringBuilder b = new StringBuilder(e.getClass().getSimpleName()); while (c.getCause() != null && c.getCause() != c) { c = c.getCause(); b.append(" ← ").append(c.getClass().getSimpleName()); } String m = String.valueOf(c.getMessage()).replaceAll("\\s+", " "); return b + ":" + m.substring(0, Math.min(150, m.length())); }
  static void resetAcc() { EntityManager em = emf.createEntityManager(); em.getTransaction().begin(); em.createNativeQuery("delete from acc").executeUpdate(); em.persist(new Acc(1L, "alice", 100)); em.persist(new Acc(2L, "bob", 200)); em.getTransaction().commit(); em.close(); }
  public static void main(String[] a) throws Exception {
    emf = Persistence.createEntityManagerFactory("demo"); resetAcc();
    sec("== 一:@Version:乐观锁在 UPDATE 的 where 里带上版本号");
    EntityManager e1 = emf.createEntityManager(), e2 = emf.createEntityManager(); e1.getTransaction().begin(); e2.getTransaction().begin(); Acc a1 = e1.find(Acc.class, 1L), a2 = e2.find(Acc.class, 1L); say("两个 EntityManager 都加载 alice:version = " + a1.version + " / " + a2.version + ",balance = " + a1.balance);
    a1.balance += 50; e1.getTransaction().commit(); say("EM1 加 50 并提交成功:version 现在是 " + a1.version + "(每次成功更新 +1)"); a2.balance += 30;
    try { e2.getTransaction().commit(); say("EM2 加 30 并提交成功(不应该)"); } catch (Throwable ex) { say("EM2 加 30 并提交:" + t(ex)); } e1.close(); e2.close();
    e1 = emf.createEntityManager(); Acc fin = e1.find(Acc.class, 1L); say("最终库里:balance = " + fin.balance + ",version = " + fin.version + "(EM2 的修改被拒绝,没有覆盖 EM1 的)"); e1.getTransaction().begin(); fin.balance = fin.balance; e1.getTransaction().commit(); Acc fin2 = emf.createEntityManager().find(Acc.class, 1L); say("没有真正修改任何字段再提交:version 仍是 " + fin2.version + "(没有变化就不发 UPDATE,版本不增加)"); e1.close();
    sec("== 二:LockModeType.OPTIMISTIC 与 OPTIMISTIC_FORCE_INCREMENT:只读的实体也能被保护");
    resetAcc(); e1 = emf.createEntityManager(); e2 = emf.createEntityManager(); e1.getTransaction().begin(); e2.getTransaction().begin(); Acc r1 = e1.find(Acc.class, 1L, LockModeType.OPTIMISTIC); Acc w2 = e2.find(Acc.class, 1L); w2.balance += 1; e2.getTransaction().commit(); e2.close(); say("EM1 以 OPTIMISTIC 读了 alice(没有修改),EM2 随后修改并提交了 alice");
    try { e1.getTransaction().commit(); say("EM1 提交成功(没有发现读到的行已经被改)"); } catch (Throwable ex) { say("EM1 提交:" + t(ex)); } e1.close();
    resetAcc(); e1 = emf.createEntityManager(); e2 = emf.createEntityManager(); e1.getTransaction().begin(); e2.getTransaction().begin(); Acc n1 = e1.find(Acc.class, 1L); Acc n2 = e2.find(Acc.class, 1L); n2.balance += 1; e2.getTransaction().commit(); e2.close(); say("对照:EM1 用默认锁模式读 alice(没有修改),EM2 修改并提交");
    try { e1.getTransaction().commit(); say("EM1 提交成功(没有任何检查:读到的数据已经过期但不知道)"); } catch (Throwable ex) { say("EM1 提交:" + t(ex)); } e1.close();
    resetAcc(); e1 = emf.createEntityManager(); e1.getTransaction().begin(); Acc f1 = e1.find(Acc.class, 2L, LockModeType.OPTIMISTIC_FORCE_INCREMENT); long vb = f1.version; e1.getTransaction().commit(); Acc f2 = emf.createEntityManager().find(Acc.class, 2L); say("OPTIMISTIC_FORCE_INCREMENT 读 bob 但不修改:提交后 version " + vb + " → " + f2.version + "(提交时强制把版本号 +1,用来保护聚合根)"); e1.close();
    sec("== 三:PESSIMISTIC_WRITE:SELECT … FOR UPDATE 的 SQL、阻塞、NOWAIT 与 SKIP LOCKED");
    resetAcc(); e1 = emf.createEntityManager(); e1.getTransaction().begin(); Acc l1 = e1.find(Acc.class, 1L, LockModeType.PESSIMISTIC_WRITE); say("EM1 以 PESSIMISTIC_WRITE 读 alice(持有行锁)");
    CountDownLatch go = new CountDownLatch(1); AtomicLong waited = new AtomicLong(); Thread th = new Thread(() -> { EntityManager e = emf.createEntityManager(); e.getTransaction().begin(); long t0 = System.nanoTime(); Acc x = e.find(Acc.class, 1L, LockModeType.PESSIMISTIC_WRITE); waited.set((System.nanoTime() - t0) / 1_000_000); e.getTransaction().commit(); e.close(); go.countDown(); }); th.start(); Thread.sleep(800); say("线程 2 的 PESSIMISTIC_WRITE 已经等了约 800 ms,线程状态 " + th.getState() + ",仍未拿到"); e1.getTransaction().commit(); e1.close(); go.await(); say("EM1 提交释放锁之后,线程 2 拿到了锁:从申请到拿到共等了 " + waited.get() + " ms");
    e1 = emf.createEntityManager(); e1.getTransaction().begin(); e1.find(Acc.class, 1L, LockModeType.PESSIMISTIC_WRITE); say("EM1 再次持有 alice 的行锁:");
    for (String[] cfg : new String[][]{{"0", "NOWAIT(jakarta.persistence.lock.timeout = 0)"}, {"-2", "SKIP LOCKED(timeout = -2)"}}) { EntityManager e = emf.createEntityManager(); e.getTransaction().begin(); long t0 = System.nanoTime(); try { Map<String, Object> hints = Map.of("jakarta.persistence.lock.timeout", Integer.parseInt(cfg[0])); Acc x = e.find(Acc.class, 1L, LockModeType.PESSIMISTIC_WRITE, hints); say("线程 2 用 " + cfg[1] + ":find 返回 " + (x == null ? "null" : "实体") + ",用时 " + (System.nanoTime() - t0) / 1_000_000 + " ms"); } catch (Throwable ex) { say("线程 2 用 " + cfg[1] + ":" + t(ex) + ",用时 " + (System.nanoTime() - t0) / 1_000_000 + " ms"); } try { e.getTransaction().rollback(); } catch (Throwable ex) { } e.close(); }
    EntityManager e3 = emf.createEntityManager(); e3.getTransaction().begin(); List<Acc> got = e3.createQuery("select a from Acc a order by a.id", Acc.class).setLockMode(LockModeType.PESSIMISTIC_WRITE).setHint("jakarta.persistence.lock.timeout", -2).getResultList(); say("SKIP LOCKED 的查询(select a from Acc a order by id,锁 alice 的事务还没提交):返回 " + got.size() + " 行(跳过了被锁的 alice,返回 " + (got.isEmpty() ? "-" : got.get(0).owner) + ")"); e3.getTransaction().rollback(); e3.close();
    AtomicLong wt = new AtomicLong(-1); Thread tt = new Thread(() -> { EntityManager e = emf.createEntityManager(); e.getTransaction().begin(); long t0 = System.nanoTime(); try { e.find(Acc.class, 1L, LockModeType.PESSIMISTIC_WRITE, Map.of("jakarta.persistence.lock.timeout", 1000)); } catch (Throwable ex) { say("timeout = 1000 ms 的线程抛出:" + t(ex)); } wt.set((System.nanoTime() - t0) / 1_000_000); try { e.getTransaction().rollback(); } catch (Throwable ex) { } e.close(); }); tt.start(); Thread.sleep(2500);
    say("线程 2 用 jakarta.persistence.lock.timeout = 1000 ms:2.5 秒之后线程状态 " + tt.getState() + "(没有在 1 秒时超时,PostgreSQL 方言不支持大于 0 的锁超时,超时设置被忽略);等待结束的耗时 " + (wt.get() < 0 ? "尚未结束" : wt.get() + " ms")); e1.getTransaction().rollback(); e1.close(); tt.join(); say("EM1 回滚之后线程 2 拿到了锁,整个等待 " + wt.get() + " ms");
    sec("== 四:死锁:两个事务以相反的顺序加行锁");
    resetAcc(); CountDownLatch bothLocked = new CountDownLatch(2); AtomicReference<String> r1x = new AtomicReference<>(), r2x = new AtomicReference<>(); long dt0 = System.nanoTime();
    Thread d1 = new Thread(() -> { EntityManager e = emf.createEntityManager(); e.getTransaction().begin(); e.find(Acc.class, 1L, LockModeType.PESSIMISTIC_WRITE); bothLocked.countDown(); try { bothLocked.await(); e.find(Acc.class, 2L, LockModeType.PESSIMISTIC_WRITE); e.getTransaction().commit(); r1x.set("提交成功"); } catch (Throwable ex) { r1x.set(t(ex)); try { e.getTransaction().rollback(); } catch (Throwable z) { } } e.close(); });
    Thread d2 = new Thread(() -> { EntityManager e = emf.createEntityManager(); e.getTransaction().begin(); e.find(Acc.class, 2L, LockModeType.PESSIMISTIC_WRITE); bothLocked.countDown(); try { bothLocked.await(); e.find(Acc.class, 1L, LockModeType.PESSIMISTIC_WRITE); e.getTransaction().commit(); r2x.set("提交成功"); } catch (Throwable ex) { r2x.set(t(ex)); try { e.getTransaction().rollback(); } catch (Throwable z) { } } e.close(); });
    d1.start(); d2.start(); d1.join(); d2.join(); say("线程 1(先锁 alice 再锁 bob):" + r1x.get()); say("线程 2(先锁 bob 再锁 alice):" + r2x.get()); say("从两个事务各自锁好第一行到有一方失败共用了约 " + (System.nanoTime() - dt0) / 1_000_000 + " ms(PostgreSQL 的 deadlock_timeout 默认 1 秒)");
    sec("== 五:计数器基准:8 个线程各自对同一行做 200 次 +1,三种做法");
    em0(); int T = 8, N = 200; for (String mode : new String[]{"无锁(没有 @Version)", "乐观锁(@Version)+ 冲突后重试", "悲观锁(PESSIMISTIC_WRITE)"}) {
      EntityManager s = emf.createEntityManager(); s.getTransaction().begin(); s.createNativeQuery("delete from cnt").executeUpdate(); s.createNativeQuery("delete from raw").executeUpdate(); s.persist(new Cnt(1L)); s.persist(new Raw(1L)); s.getTransaction().commit(); s.close();
      AtomicInteger retries = new AtomicInteger(), failed = new AtomicInteger(); long t0 = System.nanoTime(); List<Thread> ts = new ArrayList<>();
      for (int i = 0; i < T; i++) { Thread th2 = new Thread(() -> { for (int k = 0; k < N; k++) { boolean done = false; while (!done) { EntityManager e = emf.createEntityManager(); try { e.getTransaction().begin();
              if (mode.startsWith("无锁")) { Raw r = e.find(Raw.class, 1L); r.n++; } else if (mode.startsWith("乐观")) { Cnt c = e.find(Cnt.class, 1L); c.n++; } else { Cnt c = e.find(Cnt.class, 1L, LockModeType.PESSIMISTIC_WRITE); c.n++; }
              e.getTransaction().commit(); done = true; } catch (Throwable ex) { retries.incrementAndGet(); try { if (e.getTransaction().isActive()) e.getTransaction().rollback(); } catch (Throwable z) { } if (!mode.startsWith("乐观")) { failed.incrementAndGet(); done = true; } } finally { e.close(); } } } }); ts.add(th2); th2.start(); }
      for (Thread th2 : ts) th2.join(); double sec = (System.nanoTime() - t0) / 1e9; EntityManager v = emf.createEntityManager(); long finalN = mode.startsWith("无锁") ? v.find(Raw.class, 1L).n : v.find(Cnt.class, 1L).n; v.close();
      say(String.format("%-28s 期望 %d,最终计数 %d(%s),重试 / 异常 %d 次,耗时 %.2f s,约 %.0f 次提交/秒", mode, T * N, finalN, finalN == T * N ? "正确" : "丢失了 " + (T * N - finalN) + " 次", retries.get(), sec, T * N / sec)); }
    emf.close();
  }
  static void em0() { }
}
'''}
pg = PGI(9501).start()
try:
    rc, o = jpa('j278a', FILES, ['Acc', 'Cnt', 'Raw'], props={'hibernate.show_sql': 'true'}, timeout=600)
finally: pg.stop()
if rc != 0: print(o[:3000]); sys.exit()
sec = 0
for l in o.splitlines():
    if l.startswith('SEC '): print(l[4:]); sec = int(re.search(r'== (.):', l).group(1) in '一二三四五' and '一二三四五'.index(re.search(r'== (.):', l).group(1)) + 1)
    elif l.startswith('RES '): print('  ' + l[4:])
    elif l.startswith('Hibernate: ') and sec in (1, 3) and not re.search(r'set client_min_messages|drop table|create table|alter table|delete from|insert into', l): print('      SQL> ' + l[11:])
