import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x93'); CP = scp('org.springframework.boot:spring-boot-starter-data-jpa', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.data.jpa.repository.*; import jakarta.persistence.Entity; import jakarta.persistence.Id; import jakarta.persistence.Version; import jakarta.persistence.EntityManager; import jakarta.persistence.PersistenceContext; import org.springframework.stereotype.Component; import org.springframework.transaction.support.TransactionTemplate; import org.springframework.transaction.TransactionDefinition; import org.springframework.transaction.PlatformTransactionManager; import org.springframework.transaction.support.DefaultTransactionDefinition; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;\n'
FILES = {
 'src/demo/Insp.java': HDR + '''
import org.hibernate.resource.jdbc.spi.StatementInspector; import org.springframework.boot.hibernate.autoconfigure.HibernatePropertiesCustomizer;
@Component public class Insp implements StatementInspector, HibernatePropertiesCustomizer {
  static volatile boolean on; static final List<String> SQLS = Collections.synchronizedList(new ArrayList<>());
  public String inspect(String sql) { if (on) SQLS.add(sql); return sql; }
  public void customize(Map<String, Object> p) { p.put("hibernate.session_factory.statement_inspector", this); }
}
''',
 'src/demo/AccNoV.java': HDR + '@Entity public class AccNoV { @Id Long id; long balance; public AccNoV() {} public AccNoV(Long i, long b) { id = i; balance = b; } public long getBalance() { return balance; } public void setBalance(long b) { balance = b; } }\n',
 'src/demo/AccV.java': HDR + '@Entity public class AccV { @Id Long id; long balance; @Version Long version; public AccV() {} public AccV(Long i, long b) { id = i; balance = b; } public long getBalance() { return balance; } public void setBalance(long b) { balance = b; } public Long getVersion() { return version; } public void setVersion(Long v) { version = v; } public Long getId() { return id; } }\n',
 'src/demo/AccVRepo.java': HDR + '''
public interface AccVRepo extends JpaRepository<AccV, Long> {
  @Modifying @org.springframework.data.jpa.repository.Query("update AccV a set a.balance = a.balance + ?2 where a.id = ?1") int bulk(Long id, long d);
  @Modifying @org.springframework.data.jpa.repository.Query("update versioned AccV a set a.balance = a.balance + ?2 where a.id = ?1") int bulkVersioned(Long id, long d);
}
''',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  static PlatformTransactionManager ptm; static TransactionTemplate tx, txNew; static AccVRepo repo; static EntityManager emf;
  static String ex(Throwable e) { Throwable rc = e; while (rc.getCause() != null) rc = rc.getCause(); return e.getClass().getSimpleName() + ":" + String.valueOf(rc.getMessage()).split("\\\\n")[0]; }
  static long bal(Class<?> c, long id) { return tx.execute(s -> ((Number) emf.createQuery("select a.balance from " + c.getSimpleName() + " a where a.id = :i").setParameter("i", id).getSingleResult()).longValue()); }
  static long ver() { return tx.execute(s -> emf.find(AccV.class, 1L).getVersion()); }
  static void reset(long id) { tx.executeWithoutResult(s -> { emf.createQuery("delete from AccV").executeUpdate(); emf.createQuery("delete from AccNoV").executeUpdate(); emf.persist(new AccV(id, 100)); emf.persist(new AccNoV(id, 100)); }); }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a); repo = c.getBean(AccVRepo.class); ptm = c.getBean(PlatformTransactionManager.class); tx = new TransactionTemplate(ptm); txNew = new TransactionTemplate(ptm); txNew.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    emf = c.getBean(jakarta.persistence.EntityManagerFactory.class).createEntityManager() == null ? null : org.springframework.orm.jpa.SharedEntityManagerCreator.createSharedEntityManager(c.getBean(jakarta.persistence.EntityManagerFactory.class));
    r("== 一:@Version 做了什么");
    reset(1); Insp.on = true; Insp.SQLS.clear();
    r("初始 version = " + ver());
    for (int i = 0; i < 3; i++) { tx.executeWithoutResult(s -> { AccV x = emf.find(AccV.class, 1L); x.setBalance(x.getBalance() + 10); }); }
    for (String s : Insp.SQLS) if (s.startsWith("update")) r("  SQL:" + s);
    r("3 次修改之后 version = " + ver() + ",balance = " + bal(AccV.class, 1));
    Insp.on = false;
    r("  -- 两个事务同时改同一行(A 先读,B 完整地改完提交,A 再改并提交)");
    try {
      tx.executeWithoutResult(sA -> { AccV x = emf.find(AccV.class, 1L); long v0 = x.getVersion(); txNew.executeWithoutResult(sB -> { AccV y = emf.find(AccV.class, 1L); y.setBalance(y.getBalance() + 1000); }); x.setBalance(x.getBalance() + 1); r("  A 读到的 version = " + v0 + ",B 提交后 A 准备提交"); });
      r("  A 提交成功(不应该)");
    } catch (Throwable e) { r("  A 提交失败:" + ex(e)); }
    r("  最终 balance = " + bal(AccV.class, 1) + "(B 的 +1000 保住了,A 的 +1 没有写进去),version = " + ver());
    r("== 二:8 个线程各给同一行加 25 次 1(应得 +200),三种做法");
    for (String mode : new String[]{"没有 @Version", "@Version,失败就放弃", "@Version,失败重试(最多 20 次,随机退避)"}) {
      reset(1); AtomicInteger fails = new AtomicInteger(), attempts = new AtomicInteger(), gaveUp = new AtomicInteger(); long t0 = System.nanoTime(); ExecutorService es = Executors.newFixedThreadPool(8); List<Future<?>> fs = new ArrayList<>();
      for (int th = 0; th < 8; th++) fs.add(es.submit(() -> { for (int i = 0; i < 25; i++) {
        int max = mode.contains("重试") ? 20 : 1; boolean ok = false;
        for (int at = 1; at <= max && !ok; at++) { attempts.incrementAndGet(); try {
          if (mode.startsWith("没有")) tx.executeWithoutResult(s -> { AccNoV x = emf.find(AccNoV.class, 1L); x.setBalance(x.getBalance() + 1); });
          else tx.executeWithoutResult(s -> { AccV x = emf.find(AccV.class, 1L); x.setBalance(x.getBalance() + 1); });
          ok = true; } catch (Throwable e) { fails.incrementAndGet(); if (at < max) try { Thread.sleep(ThreadLocalRandom.current().nextInt(1, 6) * at); } catch (Exception z) {} } }
        if (!ok) gaveUp.incrementAndGet(); } })); for (var f : fs) f.get(); es.shutdown(); long ms = (System.nanoTime() - t0) / 1_000_000;
      long fin = mode.startsWith("没有") ? bal(AccNoV.class, 1) : bal(AccV.class, 1);
      r(String.format("  %s:最终 balance = %d(应为 300),比应得的少 %d;乐观锁冲突 %d 次;放弃 %d 次;总尝试 %d 次;用时 %d ms", mode, fin, 300 - fin, fails.get(), gaveUp.get(), attempts.get(), ms));
    }
    r("== 三:批量 JPQL 更新绕过 @Version");
    for (String how : new String[]{"update(不带 versioned)", "update versioned"}) {
      reset(1);
      try {
        tx.executeWithoutResult(sA -> { AccV x = emf.find(AccV.class, 1L); txNew.executeWithoutResult(sB -> { if (how.startsWith("update(")) repo.bulk(1L, 50); else repo.bulkVersioned(1L, 50); }); x.setBalance(x.getBalance() + 10); });
        r("  B 用 " + how + " 加 50,A(已读到旧值 100)加 10 并提交:成功;最终 balance = " + bal(AccV.class, 1) + "(两笔都应该保住,应为 160),version = " + ver());
      } catch (Throwable e) { r("  B 用 " + how + " 加 50,A 提交:失败 " + ex(e) + ";最终 balance = " + bal(AccV.class, 1) + ",version = " + ver()); }
    }
    r("== 四:表单场景:带着旧 version 回来保存");
    reset(1); AccV stale = tx.execute(s -> { AccV x = emf.find(AccV.class, 1L); return new AccV(x.getId(), x.getBalance()) {{ setVersion(x.getVersion()); }}; });
    tx.executeWithoutResult(s -> { AccV y = emf.find(AccV.class, 1L); y.setBalance(500); });
    AccV copy = new AccV(1L, 200); copy.setVersion(stale.getVersion());
    try { repo.save(copy); r("  save(带旧 version=" + stale.getVersion() + " 的游离对象):成功(不应该)"); } catch (Throwable e) { r("  save(带旧 version=" + stale.getVersion() + " 的游离对象,而库里已经是 version=" + ver() + "):失败 " + ex(e)); }
    AccV nov = new AccV(1L, 200);
    try { repo.save(nov); r("  save(没带 version 的游离对象,version=null):成功;最终 balance = " + bal(AccV.class, 1) + ",version = " + ver()); } catch (Throwable e) { r("  save(没带 version 的游离对象):失败 " + ex(e)); }
    tx.executeWithoutResult(sx -> { AccV fresh = emf.find(AccV.class, 1L); fresh.setBalance(200); });
    r("  重新 find 一个最新的实体、再把表单里的字段拷进去(丢掉了页面上带回来的旧 version):提交成功,最终 balance = " + bal(AccV.class, 1) + ",version = " + ver() + "——别人改的 500 被静默覆盖了");
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x93', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x93'); URL = jdbc(my)
PR = {'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app', 'spring.jpa.hibernate.ddl-auto': 'create', 'spring.datasource.hikari.maximum-pool-size': '16'}
print('Spring Boot 4.0.8 / Hibernate 7 / MySQL 26.7.0(自己起的实例,默认隔离级别 REPEATABLE-READ);Account 一行,初始余额 100,AccV 带 @Version,AccNoV 不带')
r = srun(b, 'demo.Main', props=PR, timeout=300)
for l in res(r): print(l)
if not res(r): print(r['out'][-2500:])
my.stop()
