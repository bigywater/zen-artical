import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x94'); CP = scp('org.springframework.boot:spring-boot-starter-data-jpa', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty; import org.springframework.context.annotation.*; import org.springframework.data.annotation.*; import org.springframework.data.domain.AuditorAware; import org.springframework.data.jpa.repository.*; import org.springframework.data.jpa.repository.config.EnableJpaAuditing; import org.springframework.data.jpa.domain.support.AuditingEntityListener; import jakarta.persistence.Entity; import jakarta.persistence.Id; import jakarta.persistence.GeneratedValue; import jakarta.persistence.GenerationType; import jakarta.persistence.EntityListeners; import jakarta.persistence.Column; import org.springframework.stereotype.Component; import org.springframework.transaction.support.TransactionTemplate; import java.time.*; import java.util.*; import java.util.concurrent.*;\n'
FILES = {
 'src/demo/Insp.java': HDR + '''
import org.hibernate.resource.jdbc.spi.StatementInspector; import org.springframework.boot.hibernate.autoconfigure.HibernatePropertiesCustomizer;
@Component public class Insp implements StatementInspector, HibernatePropertiesCustomizer {
  static volatile boolean on; static final List<String> SQLS = Collections.synchronizedList(new ArrayList<>());
  public String inspect(String sql) { if (on) SQLS.add(sql); return sql; }
  public void customize(Map<String, Object> p) { p.put("hibernate.session_factory.statement_inspector", this); }
}
''',
 'src/demo/Cur.java': HDR + 'public class Cur { static final ThreadLocal<String> USER = new ThreadLocal<>(); }\n',
 'src/demo/Cfg.java': HDR + '''
@Configuration @ConditionalOnProperty(name = "x94.audit", havingValue = "true", matchIfMissing = true) @EnableJpaAuditing(auditorAwareRef = "auditor")
class Cfg { @Bean AuditorAware<String> auditor() { return () -> Optional.ofNullable(Cur.USER.get()); } }
''',
 'src/demo/Doc.java': HDR + '''
@Entity @EntityListeners(AuditingEntityListener.class)
public class Doc {
  @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String title;
  @CreatedDate @Column(updatable = false) LocalDateTime createdDate; @LastModifiedDate LocalDateTime lastModifiedDate; @CreatedBy @Column(updatable = false) String createdBy; @LastModifiedBy String lastModifiedBy;
  public Doc() {} public Doc(String t) { title = t; } public Long getId() { return id; } public void setTitle(String t) { title = t; }
  public String toString() { return "Doc[" + title + " 创建 " + (createdDate == null ? null : createdDate.toLocalTime()) + " by " + createdBy + ",修改 " + (lastModifiedDate == null ? null : lastModifiedDate.toLocalTime()) + " by " + lastModifiedBy + "]"; }
}
''',
 'src/demo/DocNoListener.java': HDR + '''
@Entity
public class DocNoListener { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String title; @CreatedDate LocalDateTime createdDate; @CreatedBy String createdBy; public DocNoListener() {} public DocNoListener(String t) { title = t; } public String toString() { return "DocNoListener[createdDate=" + createdDate + ",createdBy=" + createdBy + "]"; } }
''',
 'src/demo/DocRepo.java': HDR + '''
public interface DocRepo extends JpaRepository<Doc, Long> {
  @Modifying @org.springframework.data.jpa.repository.Query("update Doc d set d.title = ?2 where d.id = ?1") int bulkTitle(Long id, String t);
}
''',
 'src/demo/NoListenerRepo.java': HDR + 'public interface NoListenerRepo extends JpaRepository<DocNoListener, Long> {}\n',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  static String ex(Throwable e) { Throwable rc = e; while (rc.getCause() != null) rc = rc.getCause(); return e.getClass().getSimpleName() + ":" + String.valueOf(rc.getMessage()).split("\\\\n")[0]; }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a); DocRepo repo = c.getBean(DocRepo.class); NoListenerRepo nl = c.getBean(NoListenerRepo.class); TransactionTemplate tx = c.getBean(TransactionTemplate.class);
    boolean audit = !"false".equals(System.getProperty("x94.audit"));
    if (!audit) {
      r("== 五:没有 @EnableJpaAuditing");
      Cur.USER.set("alice"); Doc d = repo.save(new Doc("t0")); r("  save 之后:" + d + "(实体上有 @EntityListeners 与注解,但没开 @EnableJpaAuditing)");
      System.exit(0);
    }
    r("== 一:创建与修改");
    Cur.USER.set("alice"); Insp.on = true; Insp.SQLS.clear();
    Doc d = repo.save(new Doc("t1")); Long id = d.getId(); r("save(new Doc) 之后:" + d);
    for (String s : Insp.SQLS) r("    SQL:" + s.replaceAll("\\\\s+", " "));
    Thread.sleep(1100); Cur.USER.set("bob"); Insp.SQLS.clear();
    tx.executeWithoutResult(s -> { Doc x = repo.findById(id).get(); x.setTitle("t1-改"); });
    for (String s : Insp.SQLS) if (s.startsWith("update")) r("    SQL:" + s.replaceAll("\\\\s+", " "));
    Doc d2 = repo.findById(id).get(); r("bob 修改之后:" + d2);
    r("== 二:哪些情况不会更新 lastModifiedDate");
    Thread.sleep(1100); Cur.USER.set("carol");
    tx.executeWithoutResult(s -> { Doc x = repo.findById(id).get(); x.setTitle("t1-改"); }); r("把标题改成同样的值(脏检查没发现变化):" + repo.findById(id).get());
    Insp.SQLS.clear(); tx.executeWithoutResult(s -> { Doc x = repo.findById(id).get(); }); r("只读取不修改,发出的 update 条数:" + Insp.SQLS.stream().filter(s -> s.startsWith("update")).count());
    tx.executeWithoutResult(s -> repo.bulkTitle(id, "批量改")); r("@Modifying 批量 update 改了标题(carol 操作):" + repo.findById(id).get() + "——lastModified 仍是旧的,lastModifiedBy 仍是 bob");
    tx.executeWithoutResult(s -> { Doc x = repo.findById(id).get(); x.setTitle("再改一次"); }); r("实体方式再改一次(carol 操作):" + repo.findById(id).get());
    r("== 三:AuditorAware 返回空、实体没有 @EntityListeners");
    Cur.USER.remove(); Doc nobody = repo.save(new Doc("无登录用户")); r("没有当前用户(AuditorAware 返回 Optional.empty())时 save:" + nobody);
    Cur.USER.set("alice"); DocNoListener n = nl.save(new DocNoListener("x")); r("注解齐全但实体没有 @EntityListeners(AuditingEntityListener.class):" + n);
    r("== 四:换一个线程");
    Cur.USER.set("alice"); ExecutorService es = Executors.newSingleThreadExecutor(); Doc other = es.submit(() -> repo.save(new Doc("在另一个线程里保存"))).get(); es.shutdown(); r("alice 的线程里调用,但 save 在线程池的线程里执行:" + other + "(AuditorAware 读的是 ThreadLocal)");
    es = Executors.newSingleThreadExecutor(); String who = "carol"; Doc other2 = es.submit(() -> { Cur.USER.set(who); try { return repo.save(new Doc("线程里先设置用户")); } finally { Cur.USER.remove(); } }).get(); es.shutdown(); r("在任务里自己把用户设置到那个线程:" + other2);
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x94', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x94'); URL = jdbc(my)
PR = {'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app', 'spring.jpa.hibernate.ddl-auto': 'create'}
print('Spring Boot 4.0.8 / Hibernate 7 / MySQL 26.7.0(自己起的实例);Doc 实体带 @CreatedDate、@LastModifiedDate、@CreatedBy、@LastModifiedBy;AuditorAware<String> 从一个 ThreadLocal 里取当前用户(代替 Spring Security)')
r = srun(b, 'demo.Main', props=PR, timeout=300)
for l in res(r): print(l)
if not res(r): print(r['out'][-2500:])
r2 = srun(b, 'demo.Main', props=dict(PR, **{'x94.audit': 'false'}), timeout=300)
for l in res(r2): print(l)
if not res(r2): print(r2['out'][-2500:])
my.stop()
