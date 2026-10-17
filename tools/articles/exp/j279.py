import sys, os, re, time, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *; from jpal import *
tee('j279'); R = {}
GEN = mcp('org.hibernate.orm:hibernate-jpamodelgen:6.6.4.Final')
ENTITY = 'import jakarta.persistence.*;\n@Entity public class Person { @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id; String name; int age; String city; boolean active; Person() {} Person(String n, int a, String c, boolean act) { name = n; age = a; city = c; active = act; } }'
FILES = {'logging.properties': JPA_LOGGING, 'Person.java': ENTITY, 'Insp.java': 'public class Insp implements org.hibernate.resource.jdbc.spi.StatementInspector { public String inspect(String sql) { Main.SQLS.add(sql); return sql; } }',
 'Main.java': r'''
import jakarta.persistence.*; import jakarta.persistence.criteria.*; import org.hibernate.*; import org.hibernate.stat.*; import java.util.*;
public class Main {
  static final Set<String> SQLS = Collections.synchronizedSet(new LinkedHashSet<>()); static EntityManagerFactory emf; static void say(String s) { System.out.println("RES " + s); } static void sec(String s) { System.out.println("SEC " + s); }
  static Statistics st() { return emf.unwrap(SessionFactory.class).getStatistics(); }
  static String err(Throwable t) { String m = String.valueOf(t.getMessage()).replaceAll("\\s+", " "); return t.getClass().getSimpleName() + ":" + m.substring(0, Math.min(140, m.length())); }
  static List<Person> dyn(EntityManager em, String name, Integer minAge, String city, Boolean active) { CriteriaBuilder cb = em.getCriteriaBuilder(); CriteriaQuery<Person> q = cb.createQuery(Person.class); Root<Person> r = q.from(Person.class); List<Predicate> ps = new ArrayList<>();
    if (name != null) ps.add(cb.like(r.get(Person_.name), name + "%")); if (minAge != null) ps.add(cb.ge(r.get(Person_.age), minAge)); if (city != null) ps.add(cb.equal(r.get(Person_.city), city)); if (active != null) ps.add(cb.equal(r.get(Person_.active), active)); q.select(r).where(ps.toArray(new Predicate[0])); return em.createQuery(q).getResultList(); }
  public static void main(String[] a) throws Exception {
    emf = Persistence.createEntityManagerFactory("demo"); EntityManager em = emf.createEntityManager(); em.getTransaction().begin(); String[] cities = {"Beijing", "Shanghai", "Shenzhen", "Hangzhou"}; for (int i = 1; i <= 2000; i++) em.persist(new Person("name" + i, 18 + i % 50, cities[i % 4], i % 3 != 0)); em.getTransaction().commit(); em.close();
    em = emf.createEntityManager(); CriteriaBuilder cb = em.getCriteriaBuilder();
    sec("== 一:同一个查询的 JPQL 与 Criteria 写法发出的 SQL,以及字面量会不会被内联");
    say("JPQL:select p from Person p where p.age >= :min and p.city = :city order by p.name"); em.createQuery("select p from Person p where p.age >= :min and p.city = :city order by p.name", Person.class).setParameter("min", 30).setParameter("city", "Beijing").setMaxResults(1).getResultList();
    say("Criteria:cb.ge(age, 30)、cb.equal(city, \"Beijing\"),orderBy name:"); { CriteriaQuery<Person> q = cb.createQuery(Person.class); Root<Person> r = q.from(Person.class); q.select(r).where(cb.ge(r.get("age"), 30), cb.equal(r.get("city"), "Beijing")).orderBy(cb.asc(r.get("name"))); em.createQuery(q).setMaxResults(1).getResultList(); }
    say("Criteria:cb.equal(city, cb.literal(\"Beijing\"))(显式字面量):"); { CriteriaQuery<Person> q = cb.createQuery(Person.class); Root<Person> r = q.from(Person.class); q.select(r).where(cb.equal(r.get("city"), cb.literal("Beijing"))); em.createQuery(q).setMaxResults(1).getResultList(); }
    say("cb.literal 带单引号的用户输入 x' or '1'='1:"); { CriteriaQuery<Person> q = cb.createQuery(Person.class); Root<Person> r = q.from(Person.class); q.select(r).where(cb.equal(r.get("city"), cb.literal("x' or '1'='1"))); say("    返回 " + em.createQuery(q).getResultList().size() + " 行(单引号被转义成 '',没有变成 SQL 注入)"); }
    say("JPQL 里直接写字面量 p.city = 'Beijing':"); em.createQuery("select p from Person p where p.city = 'Beijing'", Person.class).setMaxResults(1).getResultList();
    sec("== 二:写错属性名:字符串形式在运行时才报错,静态元模型在编译时就报错(编译错误见下面 Python 部分的输出)");
    try { CriteriaQuery<Person> q = cb.createQuery(Person.class); Root<Person> r = q.from(Person.class); q.select(r).where(cb.equal(r.get("agee"), 1)); say("r.get(\"agee\") 在构建查询时:没有报错"); em.createQuery(q).getResultList(); } catch (Throwable t) { say("r.get(\"agee\"):" + err(t)); }
    try { CriteriaQuery<Person> q = cb.createQuery(Person.class); Root<Person> r = q.from(Person.class); q.select(r).where(cb.equal(r.get("age"), "not-a-number")); em.createQuery(q).getResultList(); say("age 与字符串比较:没有报错"); } catch (Throwable t) { say("cb.equal(r.get(\"age\"), \"not-a-number\"):" + err(t)); }
    try { CriteriaQuery<Person> q = cb.createQuery(Person.class); Root<Person> r = q.from(Person.class); q.select(r).where(cb.equal(r.get(Person_.age), 30)); say("r.get(Person_.age)(静态元模型)的属性类型是 " + Person_.age.getJavaType().getSimpleName() + ",正常执行返回 " + em.createQuery(q).getResultList().size() + " 行"); } catch (Throwable t) { say("元模型:" + err(t)); }
    sec("== 三:查询构建与执行的开销(每种做法重复 5000 次 select … where id = ? 的单行查询,取第二轮,按 µs / 次;数据库往返也包含在内)");
    for (int pass = 0; pass < 2; pass++) { String[] names = {"JPQL 字符串 + setParameter", "每次重新构建 CriteriaQuery", "CriteriaQuery 构建一次、复用(ParameterExpression)", "命名查询(@NamedQuery 等价:createNamedQuery)"};
      EntityManagerFactory f = emf; f.getCache(); EntityManager e = f.createEntityManager(); st().clear();
      CriteriaBuilder b = e.getCriteriaBuilder(); CriteriaQuery<Person> once = b.createQuery(Person.class); Root<Person> ro = once.from(Person.class); ParameterExpression<Long> pid = b.parameter(Long.class); once.select(ro).where(b.equal(ro.get("id"), pid));
      f.addNamedQuery("byId", e.createQuery("select p from Person p where p.id = :id", Person.class));
      for (int m = 0; m < 4; m++) { int N = 5000; long t0 = System.nanoTime(); long hit0 = st().getQueryPlanCacheHitCount(), miss0 = st().getQueryPlanCacheMissCount(); for (int i = 0; i < N; i++) { long id = 1 + (i % 2000); e.clear();
          switch (m) { case 0 -> e.createQuery("select p from Person p where p.id = :id", Person.class).setParameter("id", id).getSingleResult(); case 1 -> { CriteriaBuilder cb2 = e.getCriteriaBuilder(); CriteriaQuery<Person> q = cb2.createQuery(Person.class); Root<Person> r = q.from(Person.class); q.select(r).where(cb2.equal(r.get("id"), id)); e.createQuery(q).getSingleResult(); } case 2 -> e.createQuery(once).setParameter(pid, id).getSingleResult(); default -> e.createNamedQuery("byId", Person.class).setParameter("id", id).getSingleResult(); } }
        double us = (System.nanoTime() - t0) / 1e3 / N; if (pass == 1) say(String.format("%-44s 每次 %.1f µs;查询计划缓存 命中 %d / 未命中 %d", names[m], us, st().getQueryPlanCacheHitCount() - hit0, st().getQueryPlanCacheMissCount() - miss0)); }
      e.close(); }
    sec("== 四:动态条件:Criteria 按条件拼接,不同的条件组合产生不同的 SQL 文本;对照 JPQL 的“可选参数”写法只有一条 SQL");
    em.close(); em = emf.createEntityManager();
    Object[][] combos = {{null, null, null, null}, {"name1", null, null, null}, {null, 30, null, null}, {"name1", 30, null, null}, {null, null, "Beijing", null}, {"name1", 30, "Beijing", null}, {"name1", 30, "Beijing", true}, {null, null, null, true}};
    SQLS.clear(); for (int rep = 0; rep < 3; rep++) for (Object[] c : combos) dyn(em, (String) c[0], (Integer) c[1], (String) c[2], (Boolean) c[3]);
    say("8 种条件组合各执行 3 次(共 24 次)Criteria 动态查询:发给数据库的不同 SQL 文本共 " + SQLS.size() + " 种"); int k = 0; for (String q : SQLS) { if (k++ < 3) say("    例 " + k + ":" + q.replace("p1_0.id,p1_0.active,p1_0.age,p1_0.city,p1_0.name from Person p1_0", "…from Person p1_0")); }
    SQLS.clear(); String opt = "select p from Person p where (:name is null or p.name like :name) and (:minAge is null or p.age >= :minAge) and (:city is null or p.city = :city) and (:active is null or p.active = :active)";
    for (int rep = 0; rep < 3; rep++) for (Object[] c : combos) em.createQuery(opt, Person.class).setParameter("name", c[0] == null ? null : c[0] + "%").setParameter("minAge", c[1]).setParameter("city", c[2]).setParameter("active", c[3]).getResultList();
    say("同样 8 种组合 × 3 次,用一条“可选参数”JPQL(:p is null or …):发给数据库的不同 SQL 文本共 " + SQLS.size() + " 种(都是同一条带 ? 的 SQL,数据库的预编译语句可以复用;代价是执行计划是通用的,(? is null or col = ?) 往往用不上索引)");
    sec("== 五:CriteriaUpdate 与 CriteriaDelete");
    em.getTransaction().begin(); CriteriaBuilder cb3 = em.getCriteriaBuilder(); CriteriaUpdate<Person> up = cb3.createCriteriaUpdate(Person.class); Root<Person> ur = up.from(Person.class); up.set(ur.get(Person_.active), false).where(cb3.equal(ur.get(Person_.city), "Beijing")); int n1 = em.createQuery(up).executeUpdate(); say("CriteriaUpdate:把 city = Beijing 的 active 设为 false,影响 " + n1 + " 行");
    CriteriaDelete<Person> del = cb3.createCriteriaDelete(Person.class); Root<Person> dr = del.from(Person.class); del.where(cb3.lt(dr.get(Person_.age), 20)); int n2 = em.createQuery(del).executeUpdate(); say("CriteriaDelete:删除 age < 20 的行,影响 " + n2 + " 行"); em.getTransaction().rollback(); em.close();
    emf.close();
  }
}
'''}
pg = PGI(9501).start()
try:
    rc, o = jpa('j279a', FILES, ['Person'], props={'hibernate.show_sql': 'true', 'hibernate.generate_statistics': 'true', 'hibernate.session_factory.statement_inspector': 'Insp'}, extra_cp=GEN, timeout=900)
finally: pg.stop()
if rc != 0: print(o[:3000]); sys.exit()
sec = 0; sqlshown = 0
for l in o.splitlines():
    if l.startswith('SEC '): print(l[4:]); sec = '一二三四五'.index(re.search(r'== (.):', l).group(1)) + 1
    elif l.startswith('RES '): print('  ' + l[4:])
    elif l.startswith('Hibernate: ') and sec == 1 and 'Person' in l and 'insert' not in l: print('      SQL> ' + l[11:])
# 静态元模型的编译期错误
d = JT / 'j279a'; (d / 'Bad.java').write_text('import jakarta.persistence.criteria.*; public class Bad { static void f(CriteriaBuilder cb, Root<Person> r) { Predicate p = cb.equal(r.get(Person_.agee), 1); Predicate q = cb.equal(r.get(Person_.age), "x"); } }')
cp = JPA_CP + ':' + GEN
r = subprocess.run(['javac', '-d', str(d / 'out2'), '-cp', str(d / 'out') + ':' + cp, str(d / 'Bad.java')], cwd=d, env=jenv('21'), capture_output=True, text=True)
print('== 六:静态元模型在编译期的反馈:把 r.get("agee") 换成 r.get(Person_.agee),另一行是 cb.equal(r.get(Person_.age), "x")')
print('  javac 退出码 ' + str(r.returncode) + ':')
lines = tidy(r.stderr).splitlines(); i = 0
while i < len(lines):
    if 'error:' in lines[i]:
        for l in lines[i:i + 4]:
            if l.strip(): print('      ' + l.replace(str(d), '<jtmp>')[:200])
        i += 4
    else: i += 1
