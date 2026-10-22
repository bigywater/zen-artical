import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x90'); CP = scp('org.springframework.boot:spring-boot-starter-data-jpa', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.*; import org.springframework.data.jpa.repository.*; import org.springframework.data.jpa.domain.Specification; import org.springframework.data.repository.*; import org.springframework.data.domain.*; import jakarta.persistence.Entity; import jakarta.persistence.Id; import jakarta.persistence.GeneratedValue; import jakarta.persistence.GenerationType; import jakarta.persistence.OneToMany; import jakarta.persistence.ManyToOne; import jakarta.persistence.FetchType; import jakarta.persistence.criteria.*; import org.springframework.stereotype.Component; import java.util.*;\n'
FILES = {
 'src/demo/Insp.java': HDR + '''
import org.hibernate.resource.jdbc.spi.StatementInspector; import org.springframework.boot.hibernate.autoconfigure.HibernatePropertiesCustomizer;
@Component public class Insp implements StatementInspector, HibernatePropertiesCustomizer {
  static volatile boolean on; static final List<String> SQLS = Collections.synchronizedList(new ArrayList<>());
  public String inspect(String sql) { if (on) SQLS.add(sql); return sql; }
  public void customize(Map<String, Object> p) { p.put("hibernate.session_factory.statement_inspector", this); }
}
''',
 'src/demo/Phone.java': HDR + '@Entity public class Phone { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String number; @ManyToOne(fetch = FetchType.LAZY) Person owner; public Phone() {} public Phone(String n, Person o) { number = n; owner = o; } }\n',
 'src/demo/Person.java': HDR + '@Entity public class Person { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String name; int age; String city; @OneToMany(mappedBy = "owner") List<Phone> phones = new ArrayList<>(); public Person() {} public Person(String n, int a, String c) { name = n; age = a; city = c; } public Long getId() { return id; } public String toString() { return name; } }\n',
 'src/demo/PersonRepo.java': HDR + 'public interface PersonRepo extends JpaRepository<Person, Long>, JpaSpecificationExecutor<Person> {}\n',
 'src/demo/PhoneRepo.java': HDR + 'public interface PhoneRepo extends JpaRepository<Phone, Long> {}\n',
 'src/demo/Specs.java': HDR + '''
public class Specs {
  static Specification<Person> nameLike(String n) { return n == null ? Specification.unrestricted() : (r, q, cb) -> cb.like(cb.lower(r.get("name")), "%" + n.toLowerCase() + "%"); }
  static Specification<Person> minAge(Integer a) { return a == null ? Specification.unrestricted() : (r, q, cb) -> cb.greaterThanOrEqualTo(r.get("age"), a); }
  static Specification<Person> city(String c) { return c == null ? Specification.unrestricted() : (r, q, cb) -> cb.equal(r.get("city"), c); }
  static Specification<Person> phoneLike(String p) { return (r, q, cb) -> { Join<Person, Phone> j = r.join("phones"); return cb.like(j.get("number"), p + "%"); }; }
  static Specification<Person> phoneLikeDistinct(String p) { return (r, q, cb) -> { q.distinct(true); Join<Person, Phone> j = r.join("phones"); return cb.like(j.get("number"), p + "%"); }; }
  static Specification<Person> rawContains(String s) { return (r, q, cb) -> cb.like(r.get("name"), "%" + s + "%"); }
  static Specification<Person> safeContains(String s) { return (r, q, cb) -> cb.like(r.get("name"), "%" + s.replace("\\\\", "\\\\\\\\").replace("%", "\\\\%").replace("_", "\\\\_") + "%", '\\\\'); }
}
''',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  interface Call { Object run(); }
  static String sqlShort(String s) { String x = s.replaceAll("\\\\s+", " ").trim(); return (x.startsWith("select count") || x.contains("count(")) ? x : x.replaceFirst("^select (distinct )?.*? from", x.startsWith("select distinct") ? "select distinct … from" : "select … from"); }
  static void t(String label, Call c) {
    Insp.SQLS.clear(); Object res; try { res = c.run(); } catch (Throwable e) { res = "抛 " + e.getClass().getSimpleName() + ":" + String.valueOf(e.getMessage()).split("\\\\n")[0]; }
    String out = res instanceof Page<?> p ? "Page(内容 " + p.getContent().size() + " 行,总数 " + p.getTotalElements() + ")" : res instanceof Collection<?> col ? col.size() + " 行 " + col : String.valueOf(res);
    r(label + "  ⇒ " + (out.length() > 150 ? out.substring(0, 150) + "…" : out));
    for (String s : Insp.SQLS) r("    " + sqlShort(s));
  }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    ConfigurableApplicationContext c = app.run(a); PersonRepo repo = c.getBean(PersonRepo.class); PhoneRepo pr = c.getBean(PhoneRepo.class);
    List<Person> ps = repo.saveAll(List.of(new Person("Ann Lee", 30, "Rome"), new Person("Bob Lee", 25, "Rome"), new Person("Cid Ray", 41, "Oslo"), new Person("Dee Ray", 19, "Oslo"), new Person("50%off", 50, "Oslo"), new Person("500off", 51, "Oslo"), new Person("Eve Poe", 22, "Rome"), new Person("x' or '1'='1", 33, "Rome")));
    pr.saveAll(List.of(new Phone("555-1", ps.get(0)), new Phone("555-2", ps.get(0)), new Phone("555-3", ps.get(0)), new Phone("666-1", ps.get(1)), new Phone("555-9", ps.get(2))));
    Insp.on = true;
    r("== 一:Specification 组合出的 SQL");
    t("name like 'lee'", () -> repo.findAll(Specs.nameLike("lee")));
    t("minAge 30 and city Rome(Specification.where(…).and(…))", () -> repo.findAll(Specification.where(Specs.minAge(30)).and(Specs.city("Rome"))));
    t("city Rome or city Oslo", () -> repo.findAll(Specification.where(Specs.city("Rome")).or(Specs.city("Oslo"))));
    t("not(city Rome)", () -> repo.findAll(Specification.not(Specs.city("Rome"))));
    t("Specification.where(null)", () -> repo.findAll(Specification.where((Specification<Person>) null)));
    t("spec.and(null)", () -> repo.findAll(Specification.where(Specs.city("Rome")).and((Specification<Person>) null)));
    t("Specification.unrestricted()", () -> repo.findAll(Specification.unrestricted()));
    t("所有条件都不成立(三个辅助方法都返回 Specification.unrestricted())", () -> repo.findAll(Specification.where(Specs.nameLike(null)).and(Specs.minAge(null)).and(Specs.city(null))));
    r("  -- 动态查询:三个可选条件 name / minAge / city,8 种组合");
    for (int m = 0; m < 8; m++) {
      String n = (m & 1) != 0 ? "e" : null; Integer ag = (m & 2) != 0 ? 25 : null; String ci = (m & 4) != 0 ? "Rome" : null;
      Insp.SQLS.clear(); List<Person> res = repo.findAll(Specification.where(Specs.nameLike(n)).and(Specs.minAge(ag)).and(Specs.city(ci)));
      String sql = Insp.SQLS.isEmpty() ? "" : sqlShort(Insp.SQLS.get(0)); String wh = sql.contains(" where ") ? sql.substring(sql.indexOf(" where ")) : "(没有 where)";
      r(String.format("  name=%s minAge=%s city=%s → %d 行;SQL 条数 %d,%s", n, ag, ci, res.size(), Insp.SQLS.size(), wh));
    }
    r("== 二:Specification + Pageable");
    t("findAll(minAge 20, PageRequest.of(0, 3, Sort.by(\\"age\\")))", () -> repo.findAll(Specs.minAge(20), PageRequest.of(0, 3, Sort.by("age"))));
    t("findAll(city Oslo, PageRequest.of(1, 2))", () -> repo.findAll(Specs.city("Oslo"), PageRequest.of(1, 2)));
    t("count(city Oslo)", () -> repo.count(Specs.city("Oslo")));
    t("exists(city Mars)", () -> repo.exists(Specs.city("Mars")));
    t("findOne(name like 'cid')", () -> repo.findOne(Specs.nameLike("cid")));
    r("== 三:join 一对多带来的重复行");
    t("phone like '555' 不 distinct", () -> repo.findAll(Specs.phoneLike("555")));
    t("phone like '555' + query.distinct(true)", () -> repo.findAll(Specs.phoneLikeDistinct("555")));
    t("Page:phone like '555' 不 distinct,每页 2", () -> repo.findAll(Specs.phoneLike("555"), PageRequest.of(0, 2)));
    t("Page:phone like '555' + distinct,每页 2", () -> repo.findAll(Specs.phoneLikeDistinct("555"), PageRequest.of(0, 2)));
    r("== 四:用户输入");
    t("rawContains(\\"50%\\")(自己拼 %)", () -> repo.findAll(Specs.rawContains("50%")));
    t("safeContains(\\"50%\\")(转义 % 和 _ 并声明 escape)", () -> repo.findAll(Specs.safeContains("50%")));
    t("rawContains(\\"x' or '1'='1\\")(想注入)", () -> repo.findAll(Specs.rawContains("x' or '1'='1")));
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x90', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x90'); URL = jdbc(my)
PR = {'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app', 'spring.jpa.hibernate.ddl-auto': 'create'}
print('Spring Boot 4.0.8 / Hibernate 7 / MySQL 26.7.0(自己起的实例);Person 8 行,Phone 5 行(Ann 有 3 个 555 开头的号码);SQL 来自 StatementInspector')
r = srun(b, 'demo.Main', props=PR, timeout=300)
for l in res(r): print(l)
if not res(r): print(r['out'][-2500:])
my.stop()
