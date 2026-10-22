import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x88'); CP = scp('org.springframework.boot:spring-boot-starter-data-jpa', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.*; import org.springframework.data.jpa.repository.*; import org.springframework.data.repository.*; import org.springframework.data.domain.*; import jakarta.persistence.*; import org.springframework.stereotype.Component; import org.springframework.transaction.annotation.Transactional; import java.util.*; import java.time.*;\n'
INSP = HDR + '''
import org.hibernate.resource.jdbc.spi.StatementInspector; import org.springframework.boot.hibernate.autoconfigure.HibernatePropertiesCustomizer;
@Component public class Insp implements StatementInspector, HibernatePropertiesCustomizer {
  static volatile boolean on; static final List<String> SQLS = new ArrayList<>();
  public String inspect(String sql) { if (on) SQLS.add(sql); return sql; }
  public void customize(Map<String, Object> p) { p.put("hibernate.session_factory.statement_inspector", this); }
}
'''
GOOD = {
 'src/demo/Insp.java': INSP,
 'src/demo/Address.java': HDR + '@Embeddable public class Address { String zipCode; String street; public Address() {} public Address(String z, String s) { zipCode = z; street = s; } }\n',
 'src/demo/Person.java': HDR + '@Entity public class Person { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String firstName; String lastName; int age; String city; boolean active; LocalDate joined; @Embedded Address address; public Person() {} public Person(String f, String l, int a, String c, boolean act, String zip) { firstName = f; lastName = l; age = a; city = c; active = act; joined = LocalDate.of(2024, 1, 1).plusDays(a); address = new Address(zip, "x"); } public String toString() { return firstName + " " + lastName; } }\n',
 'src/demo/PersonRepo.java': HDR + '''
public interface PersonRepo extends JpaRepository<Person, Long> {
  List<Person> findByLastName(String l);
  List<Person> findByFirstNameAndLastName(String f, String l);
  List<Person> findByFirstNameOrLastName(String f, String l);
  List<Person> findByAgeGreaterThanEqual(int a);
  List<Person> findByAgeBetween(int a, int b);
  List<Person> findByAgeIn(Collection<Integer> ages);
  List<Person> findByCityIsNull();
  List<Person> findByFirstNameLike(String p);
  List<Person> findByFirstNameStartingWith(String p);
  List<Person> findByFirstNameContaining(String p);
  List<Person> findByLastNameIgnoreCase(String l);
  List<Person> findByActiveTrue();
  List<Person> findByCityNot(String c);
  List<Person> findByCityOrderByAgeDesc(String c);
  List<Person> findTop3ByOrderByAgeDesc();
  Person findFirstByOrderByAgeAsc();
  long countByCity(String c);
  boolean existsByLastName(String l);
  List<String> findDistinctLastNameByCity(String c);
  List<Person> findByAddressZipCode(String z);
  List<Person> findByAddress_ZipCode(String z);
  @Transactional long deleteByCity(String c);
  Optional<Person> findOptionalByFirstName(String f);
}
''',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  interface Call { Object run(); }
  static PersonRepo repo;
  static void t(String label, Call c) {
    Insp.SQLS.clear(); Object res; try { res = c.run(); } catch (Throwable e) { res = "抛 " + e.getClass().getSimpleName() + ":" + String.valueOf(e.getMessage()).split("\\\\n")[0]; }
    String out = res instanceof Collection<?> col ? col.size() + " 行 " + col : String.valueOf(res);
    r(label + "  ⇒ 返回 " + (out.length() > 260 ? out.substring(0, 260) + "…" : out));
    for (String s : Insp.SQLS) r("    " + s.replaceAll("select .*? from", "select … from").replaceAll("\\\\s+", " ").trim());
  }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    ConfigurableApplicationContext c = app.run(a); repo = c.getBean(PersonRepo.class);
    repo.saveAll(List.of(new Person("Ann", "Lee", 30, "Rome", true, "10001"), new Person("Bob", "Lee", 25, "Rome", false, "10001"), new Person("Cid", "Ray", 41, "Oslo", true, "20002"), new Person("Dee", "Ray", 19, null, true, "20002"), new Person("50%off", "Sale", 50, "Oslo", true, "30003"), new Person("500off", "Sale", 51, "Oslo", true, "30003"), new Person("Eve", "Poe", 22, "Rome", true, "10001"), new Person("Fay", "lee", 60, "Oslo", false, "30003")));
    Insp.on = true;
    r("== 一:方法名 → SQL(select 的列清单省略成 …;? 是绑定参数)");
    t("findByLastName(\\"Lee\\")", () -> repo.findByLastName("Lee"));
    t("findByFirstNameAndLastName(\\"Ann\\",\\"Lee\\")", () -> repo.findByFirstNameAndLastName("Ann", "Lee"));
    t("findByFirstNameOrLastName(\\"Ann\\",\\"Ray\\")", () -> repo.findByFirstNameOrLastName("Ann", "Ray"));
    t("findByAgeGreaterThanEqual(40)", () -> repo.findByAgeGreaterThanEqual(40));
    t("findByAgeBetween(20,30)", () -> repo.findByAgeBetween(20, 30));
    t("findByAgeIn([19,22,25])", () -> repo.findByAgeIn(List.of(19, 22, 25)));
    t("findByCityIsNull()", () -> repo.findByCityIsNull());
    t("findByActiveTrue()", () -> repo.findByActiveTrue());
    t("findByCityNot(\\"Rome\\")", () -> repo.findByCityNot("Rome"));
    t("findByCityOrderByAgeDesc(\\"Oslo\\")", () -> repo.findByCityOrderByAgeDesc("Oslo"));
    t("findTop3ByOrderByAgeDesc()", () -> repo.findTop3ByOrderByAgeDesc());
    t("findFirstByOrderByAgeAsc()", () -> repo.findFirstByOrderByAgeAsc());
    t("countByCity(\\"Oslo\\")", () -> repo.countByCity("Oslo"));
    t("existsByLastName(\\"Lee\\")", () -> repo.existsByLastName("Lee"));
    t("findDistinctLastNameByCity(\\"Oslo\\")", () -> repo.findDistinctLastNameByCity("Oslo"));
    t("findOptionalByFirstName(\\"Ann\\")", () -> repo.findOptionalByFirstName("Ann"));
    r("== 二:Like / StartingWith / Containing / IgnoreCase 对特殊字符和大小写");
    t("findByFirstNameLike(\\"50%\\")(自己写通配符)", () -> repo.findByFirstNameLike("50%"));
    t("findByFirstNameStartingWith(\\"50%\\")", () -> repo.findByFirstNameStartingWith("50%"));
    t("findByFirstNameContaining(\\"0%o\\")", () -> repo.findByFirstNameContaining("0%o"));
    t("findByLastNameIgnoreCase(\\"LEE\\")", () -> repo.findByLastNameIgnoreCase("LEE"));
    t("findByLastName(\\"LEE\\")(MySQL 默认排序规则)", () -> repo.findByLastName("LEE"));
    r("== 三:嵌套属性怎么解析");
    t("findByAddressZipCode(\\"10001\\")", () -> repo.findByAddressZipCode("10001"));
    t("findByAddress_ZipCode(\\"10001\\")", () -> repo.findByAddress_ZipCode("10001"));
    r("== 四:deleteBy 与结果");
    t("deleteByCity(\\"Rome\\")(@Transactional)", () -> repo.deleteByCity("Rome"));
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
BAD = dict(GOOD)
BAD['src/demo/PersonRepo.java'] = HDR + 'public interface PersonRepo extends JpaRepository<Person, Long> { List<Person> findByLastNme(String l); List<Person> findByNickname(String n); }\n'
BAD['src/demo/Main.java'] = HDR + '@SpringBootApplication public class Main { public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE); app.run(a); System.out.println("RES 启动成功"); System.exit(0); } }\n'
BAD['logback.xml'] = '<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>%msg%n</pattern></encoder></appender><logger name="org.springframework.boot.diagnostics.LoggingFailureAnalysisReporter" level="ERROR"/><root level="OFF"><appender-ref ref="C"/></root></configuration>'
b = sbuild('x88', GOOD, CP); bb = sbuild('x88bad', BAD, CP)
for x in (b, bb):
    if x['crc'] != 0: print(x['cout']); sys.exit()
my = mysql('x88'); URL = jdbc(my)
PR = {'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app', 'spring.jpa.hibernate.ddl-auto': 'create'}
print('Spring Boot 4.0.8 / Hibernate 7 / MySQL 26.7.0(自己起的实例);实体 Person(id、firstName、lastName、age、city、active、joined、嵌入的 Address.zipCode),8 行数据;SQL 来自 Hibernate 的 StatementInspector')
r = srun(b, 'demo.Main', props=PR, timeout=120)
for l in res(r): print(l)
if not res(r): print(r['out'][-2500:])
print('== 五:方法名写错的时候(接口里有两个写错的方法:findByLastNme、findByNickname)')
r2 = srun(bb, 'demo.Main', props=PR, timeout=120); o = r2['out']
ex = [x.strip() for x in o.splitlines() if re.match(r'^(Exception in thread "main" |Caused by: )?[\w.$]+(Exception|Error):', x.strip())]
print(f'  退出码 {r2["rc"]};有 APPLICATION FAILED TO START 报告:{"APPLICATION FAILED TO START" in o};输出共 {len([l for l in o.splitlines() if l.strip()])} 行,其中堆栈帧 {sum(1 for l in o.splitlines() if l.strip().startswith("at "))} 行')
print('  异常链(外 → 里):')
for x in ex[:5]: print('    ' + x.replace('Exception in thread "main" ', '')[:300])
print(f'  nickname 也是错的,但报错里提到了它吗:{"nickname" in o}')
my.stop()
