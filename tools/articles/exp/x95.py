import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x95'); CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.jdbc.core.*; import org.springframework.jdbc.core.simple.JdbcClient; import org.springframework.jdbc.core.namedparam.*; import org.springframework.jdbc.support.*; import java.sql.*; import java.util.*; import java.util.stream.*;\n'
FILES = {
 'src/demo/Person.java': HDR + 'public class Person { Long id; String firstName; String lastName; int age; String email; public Long getId() { return id; } public void setId(Long i) { id = i; } public String getFirstName() { return firstName; } public void setFirstName(String s) { firstName = s; } public String getLastName() { return lastName; } public void setLastName(String s) { lastName = s; } public int getAge() { return age; } public void setAge(int a) { age = a; } public String getEmail() { return email; } public void setEmail(String e) { email = e; } public String toString() { return "Person[" + id + "," + firstName + " " + lastName + "," + age + "," + email + "]"; } }\n',
 'src/demo/PersonRec.java': HDR + 'public record PersonRec(Long id, String firstName, String lastName, int age, String email) {}\n',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  interface Call { Object run() throws Exception; }
  static void t(String label, Call c) { String out; try { Object o = c.run(); out = o instanceof Collection<?> col ? col.size() + " 行 " + col : String.valueOf(o); } catch (Throwable e) { Throwable rc = e; while (rc.getCause() != null) rc = rc.getCause(); out = "抛 " + e.getClass().getSimpleName() + ":" + String.valueOf(e.getMessage()).split("\\\\n")[0]; } r(label + "  ⇒ " + (out.length() > 240 ? out.substring(0, 240) + "…" : out)); }
  static long status(JdbcTemplate j, String name) { return Long.parseLong(String.valueOf(j.queryForMap("show global status like '" + name + "'").get("Value"))); }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a); JdbcTemplate j = c.getBean(JdbcTemplate.class); NamedParameterJdbcTemplate np = c.getBean(NamedParameterJdbcTemplate.class); JdbcClient jc = c.getBean(JdbcClient.class);
    j.execute("drop table if exists person"); j.execute("create table person(id bigint auto_increment primary key, first_name varchar(30), last_name varchar(30), age int not null default 0, email varchar(50))");
    j.update("insert into person(first_name, last_name, age, email) values ('Ann','Lee',30,'ann@x'),('Bob','Lee',25,null),('Cid','Ray',41,'cid@x')");
    r("== 一:查询的几种写法与它们的异常");
    t("queryForObject(\\"select count(*) from person\\", Integer.class)", () -> j.queryForObject("select count(*) from person", Integer.class));
    t("queryForObject 没有匹配的行", () -> j.queryForObject("select first_name from person where id = ?", String.class, 999));
    t("queryForObject 有 2 行匹配", () -> j.queryForObject("select first_name from person where last_name = ?", String.class, "Lee"));
    t("queryForObject 返回 null 列(email 为 NULL)", () -> j.queryForObject("select email from person where id = 2", String.class));
    t("query(sql, RowMapper) 手写 lambda", () -> j.query("select * from person where last_name = ?", (rs, i) -> rs.getString("first_name") + "#" + i, "Lee"));
    t("BeanPropertyRowMapper<Person>(下划线列名 → 驼峰属性)", () -> j.query("select * from person order by id", new BeanPropertyRowMapper<>(Person.class)));
    t("DataClassRowMapper<PersonRec>(record)", () -> j.query("select * from person order by id", new DataClassRowMapper<>(PersonRec.class)));
    t("BeanPropertyRowMapper,但 select 里把 first_name 改名成 fname", () -> j.query("select id, first_name as fname, last_name, age, email from person where id = 1", new BeanPropertyRowMapper<>(Person.class)));
    t("JdbcClient:sql(...).param(...).query(Person.class).list()", () -> jc.sql("select * from person where last_name = ?").param("Lee").query(Person.class).list());
    t("JdbcClient:单值 .query(String.class).single() 没有匹配的行", () -> jc.sql("select first_name from person where id = ?").param(999).query(String.class).single());
    t("JdbcClient:.optional()", () -> jc.sql("select first_name from person where id = ?").param(999).query(String.class).optional());
    r("== 二:NamedParameterJdbcTemplate");
    t("命名参数:where last_name = :ln and age > :age", () -> np.query("select first_name from person where last_name = :ln and age > :age", Map.of("ln", "Lee", "age", 26), (rs, i) -> rs.getString(1)));
    t("IN 列表展开:id in (:ids),传入 List.of(1, 3)", () -> np.queryForList("select first_name from person where id in (:ids)", Map.of("ids", List.of(1, 3)), String.class));
    t("IN 列表是空集合", () -> np.queryForList("select first_name from person where id in (:ids)", Map.of("ids", List.of()), String.class));
    t("同一个命名参数用两次", () -> np.queryForList("select first_name from person where first_name = :n or last_name = :n", Map.of("n", "Ray"), String.class));
    t("少传了一个命名参数", () -> np.queryForList("select first_name from person where last_name = :ln and age > :age", Map.of("ln", "Lee"), String.class));
    t("BeanPropertySqlParameterSource(从对象取参数)", () -> { Person p = new Person(); p.setLastName("Ray"); p.setAge(40); return np.queryForList("select first_name from person where last_name = :lastName and age >= :age", new BeanPropertySqlParameterSource(p), String.class); });
    r("== 三:批量(5000 行 insert,各取 3 次中位数;MySQL 服务端 Com_insert 计数取差)");
    j.execute("drop table if exists t_batch"); j.execute("create table t_batch(id bigint auto_increment primary key, v varchar(20), n int)");
    List<Object[]> rows = IntStream.range(0, 5000).mapToObj(i -> new Object[]{"v" + i, i}).toList();
    String ins = "insert into t_batch(v, n) values (?, ?)";
    for (String mode : new String[]{"循环里一行一个 update", "batchUpdate(sql, List<Object[]>)", "NamedParameterJdbcTemplate.batchUpdate(sql, SqlParameterSource[])"}) {
      double[] ms = new double[3]; long com = 0;
      for (int k = 0; k < 3; k++) {
        j.execute("truncate table t_batch"); long before = status(j, "Com_insert"); long t0 = System.nanoTime();
        if (mode.startsWith("循环")) for (Object[] rw : rows) j.update(ins, rw);
        else if (mode.startsWith("batchUpdate")) j.batchUpdate(ins, rows);
        else np.batchUpdate("insert into t_batch(v, n) values (:v, :n)", rows.stream().map(rw -> new MapSqlParameterSource().addValue("v", rw[0]).addValue("n", rw[1])).toArray(SqlParameterSource[]::new));
        ms[k] = (System.nanoTime() - t0) / 1e6; com = status(j, "Com_insert") - before;
      }
      Arrays.sort(ms); r(String.format("  %s:中位 %.0f ms;服务端执行的 INSERT 语句数 Com_insert +%d;表里 %d 行", mode, ms[1], com, j.queryForObject("select count(*) from t_batch", Integer.class)));
    }
    r("== 四:update 的返回值与自增主键");
    t("第一次 update person set email = 'new@x' where id = 1(值确实变了)", () -> j.update("update person set email = 'new@x' where id = 1"));
    t("第二次执行同一条(值没有变)", () -> j.update("update person set email = 'new@x' where id = 1"));
    t("update 不存在的 id", () -> j.update("update person set email = 'y' where id = 999"));
    t("GeneratedKeyHolder 取自增主键", () -> { KeyHolder kh = new GeneratedKeyHolder(); j.update(con -> { PreparedStatement ps = con.prepareStatement("insert into person(first_name, last_name) values (?, ?)", Statement.RETURN_GENERATED_KEYS); ps.setString(1, "Dee"); ps.setString(2, "Ray"); return ps; }, kh); return "新行 id = " + kh.getKey(); });
    t("省了 RETURN_GENERATED_KEYS", () -> { KeyHolder kh = new GeneratedKeyHolder(); j.update(con -> { PreparedStatement ps = con.prepareStatement("insert into person(first_name, last_name) values (?, ?)"); ps.setString(1, "Eve"); ps.setString(2, "Poe"); return ps; }, kh); return "kh.getKeys() = " + kh.getKeys(); });
    t("上一条抛了异常,但那行 Eve 是不是已经插进去了(auto-commit)", () -> "person 里 first_name='Eve' 的行数 = " + j.queryForObject("select count(*) from person where first_name = 'Eve'", Integer.class));
    t("JdbcClient:.update(keyHolder)", () -> { KeyHolder kh = new GeneratedKeyHolder(); int n = jc.sql("insert into person(first_name, last_name) values (?, ?)").params("Fay", "Poe").update(kh); return "影响 " + n + " 行,新行 id = " + kh.getKey(); });
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x95', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x95'); URL = jdbc(my)
PR = {'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app'}
print('Spring Boot 4.0.8 / Spring Framework 7.0.9 JdbcTemplate / HikariCP / MySQL 26.7.0(自己起的实例);person 表 3 行(Ann Lee 30、Bob Lee 25 且 email 为 NULL、Cid Ray 41)')
r = srun(b, 'demo.Main', props=PR, timeout=300)
for l in res(r): print(l)
if not res(r): print(r['out'][-2500:])
my.stop()
