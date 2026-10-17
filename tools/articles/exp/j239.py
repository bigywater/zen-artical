import sys, os, re, time, statistics as st; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j239'); R = {}
JU = mcp('org.junit.platform:junit-platform-console-standalone:1.11.3').split(':')[0]
def tcp(v): return mcp(f'org.testcontainers:junit-jupiter:{v}', f'org.testcontainers:postgresql:{v}', 'org.postgresql:postgresql:42.7.4', 'com.h2database:h2:2.3.232')
TCV = '1.20.4'; CP = JU + ':' + tcp(TCV)
d = jdir('j239a'); E = jenv('21'); J = JDKS['21'] + '/bin/'; SOCK = str(pathlib.Path.home() / '.docker/run/docker.sock'); API = ('-Dapi.version=1.44',)
def w(p, c): f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(c)
def sh(args, tmo=120, env=None): return subprocess.run(args, cwd=d, env=env or E, capture_output=True, text=True, timeout=tmo)
def dk(*a): r = sh(['docker', *a]); return (r.stdout + r.stderr).strip()
IMGS = ('postgres:16-alpine', 'testcontainers/ryuk')
def leftovers(): return [l for l in dk('ps', '-a', '--format', '{{.ID}} {{.Image}}').splitlines() if l.strip()]
def purge():
    for l in leftovers():
        if any(i in l for i in IMGS): dk('rm', '-f', l.split()[0])
purge()
PG = '''import org.junit.jupiter.api.*; import org.testcontainers.junit.jupiter.*; import org.testcontainers.containers.PostgreSQLContainer; import java.sql.*;
@Testcontainers%s public class %s { @Container %sPostgreSQLContainer<?> pg = new PostgreSQLContainer<>("postgres:16-alpine");
%s }'''
Q = '''@Test void %s() throws Exception { try (Connection c = DriverManager.getConnection(pg.getJdbcUrl(), pg.getUsername(), pg.getPassword()); ResultSet r = c.createStatement().executeQuery("select 1")) { r.next(); Assertions.assertEquals(1, r.getInt(1)); } }'''
w('PgIT.java', PG % ('', 'PgIT', 'static ', Q % 'selectOne'))
w('PgSkip.java', PG % ('(disabledWithoutDocker = true)', 'PgSkip', 'static ', Q % 'selectOne' + '\n  @Test void plain() { Assertions.assertTrue(true); }'))
w('Plain.java', 'import org.junit.jupiter.api.*; public class Plain { @Test void plain() { Assertions.assertTrue(true); } }')
w('PerMethod.java', PG % ('', 'PerMethod', '', '\n'.join(Q % f't{i}' for i in range(10))))
w('Shared.java', PG % ('', 'Shared', 'static ', '\n'.join(Q % f't{i}' for i in range(10))))
w('Life.java', r"""import org.testcontainers.containers.PostgreSQLContainer; import java.sql.*;
public class Life { static void say(String s) { System.out.println("RES " + s); }
  public static void main(String[] a) throws Exception {
    long t0 = System.nanoTime(); PostgreSQLContainer<?> pg = new PostgreSQLContainer<>("postgres:16-alpine"); pg.start(); long t1 = System.nanoTime();
    say("pg.start() 用时 " + (t1 - t0) / 1000000 + " ms(含连接 Docker、启动 Ryuk 容器、启动 postgres 并等到日志里出现 ready)");
    say("镜像 " + pg.getDockerImageName() + ",容器内 5432 映射到宿主机的 " + (pg.getMappedPort(5432) > 1024 ? "随机高位端口" : "?") + ",host " + pg.getHost() + ",默认库名 / 用户:" + pg.getDatabaseName() + " / " + pg.getUsername());
    try (Connection c = DriverManager.getConnection(pg.getJdbcUrl(), pg.getUsername(), pg.getPassword()); ResultSet r = c.createStatement().executeQuery("select version()")) { r.next(); say("select version() = " + r.getString(1).substring(0, 36)); }
    Process p = new ProcessBuilder("docker", "ps", "--format", "{{.Image}} | {{.Status}}").redirectErrorStream(true).start();
    for (String l : new String(p.getInputStream().readAllBytes()).split("\n")) say("测试运行期间 docker ps:" + l);
    if (a.length > 0) Thread.sleep(600000); System.exit(0); } }""")
w('Cost.java', r"""import org.testcontainers.containers.PostgreSQLContainer; import java.sql.*; import java.util.*;
public class Cost { static void say(String s) { System.out.println("RES " + s); }
  static double med(List<Double> l) { List<Double> c = new ArrayList<>(l); Collections.sort(c); return c.get(c.size() / 2); }
  public static void main(String[] a) throws Exception {
    List<Double> st = new ArrayList<>(), q = new ArrayList<>(), sp = new ArrayList<>();
    for (int i = 0; i < 5; i++) { long t0 = System.nanoTime(); PostgreSQLContainer<?> pg = new PostgreSQLContainer<>("postgres:16-alpine"); pg.start(); long t1 = System.nanoTime();
      try (Connection c = DriverManager.getConnection(pg.getJdbcUrl(), pg.getUsername(), pg.getPassword()); ResultSet r = c.createStatement().executeQuery("select 1")) { r.next(); } long t2 = System.nanoTime(); pg.stop(); long t3 = System.nanoTime();
      st.add((t1 - t0) / 1e6); q.add((t2 - t1) / 1e6); sp.add((t3 - t2) / 1e6); say("第 " + (i + 1) + " 次:start " + Math.round((t1 - t0) / 1e6) + " ms(" + (i == 0 ? "含第一次连接 Docker 与启动 Ryuk" : "Ryuk 已在运行") + "),第一个连接加查询 " + Math.round((t2 - t1) / 1e6) + " ms,stop " + Math.round((t3 - t2) / 1e6) + " ms"); }
    List<Double> rest = st.subList(1, st.size()); say("start 的中位数 " + Math.round(med(st)) + " ms(后 4 次 " + Math.round(Collections.min(rest)) + "–" + Math.round(Collections.max(rest)) + " ms),stop 的中位数 " + Math.round(med(sp)) + " ms");
    PostgreSQLContainer<?> pg = new PostgreSQLContainer<>("postgres:16-alpine"); pg.start();
    try (Connection c = DriverManager.getConnection(pg.getJdbcUrl(), pg.getUsername(), pg.getPassword()); Statement s = c.createStatement()) { s.execute("CREATE DATABASE tpl"); }
    String u = pg.getJdbcUrl().replace("/test?", "/tpl?");
    try (Connection c = DriverManager.getConnection(u, pg.getUsername(), pg.getPassword()); Statement s = c.createStatement()) { s.execute("CREATE TABLE orders(id serial primary key, status text, total int); CREATE INDEX ON orders(status); INSERT INTO orders(status,total) SELECT 'NEW', g FROM generate_series(1,1000) g"); }
    List<Double> cl = new ArrayList<>(), dr = new ArrayList<>();
    try (Connection c = DriverManager.getConnection(pg.getJdbcUrl(), pg.getUsername(), pg.getPassword()); Statement s = c.createStatement()) { for (int i = 0; i < 20; i++) { long t0 = System.nanoTime(); s.execute("CREATE DATABASE c" + i + " TEMPLATE tpl"); long t1 = System.nanoTime(); s.execute("DROP DATABASE c" + i); long t2 = System.nanoTime(); cl.add((t1 - t0) / 1e6); dr.add((t2 - t1) / 1e6); } }
    say("同一个容器里(含 1000 行的 tpl 模板库)连续 20 次 CREATE DATABASE ... TEMPLATE tpl(通过 JDBC,不含进程启动)中位数 " + Math.round(med(cl)) + " ms(最小 " + Math.round(Collections.min(cl)) + "、最大 " + Math.round(Collections.max(cl)) + "),DROP DATABASE 中位数 " + Math.round(med(dr)) + " ms");
    pg.stop(); System.exit(0); } }""")
r = sh([J + 'javac', '-d', 'out', '-cp', CP, *[str(p) for p in d.glob('*.java')]])
if r.returncode: print(r.stderr[:2500]); sys.exit()
for v in ('1.21.3', '1.21.4'): (d / f'out{v}').mkdir(); assert sh([J + 'javac', '-d', f'out{v}', '-cp', JU + ':' + tcp(v), 'PgIT.java']).returncode == 0
def run(cls, cp=CP, outd='out', extra=(), env=None, tmo=280):
    t0 = time.perf_counter(); q = sh(['java', *extra, '-cp', f'{outd}:{cp}', 'org.junit.platform.console.ConsoleLauncher', 'execute', '--disable-banner', '--disable-ansi-colors', '--details=tree', '--select-class', cls], tmo, env)
    return tidy(q.stdout + q.stderr), time.perf_counter() - t0
def keep(o, n=60): return [re.sub(r'\s+', ' ', l.strip())[:170] for l in o.splitlines() if re.search(r'IllegalState|✔|✘|↷|tests (successful|failed|skipped|found)|Disabled|disabled|containers (found|skipped|successful|failed)', l)][:n]
def curl(path, code=False): r = sh(['curl', '-s', '--unix-socket', SOCK, *(['-o', '/dev/null', '-w', '%{http_code}'] if code else []), 'http://localhost' + path]); return r.stdout
print('== 一:Testcontainers 与 Docker 引擎的 API 版本:本机 Docker Desktop 的服务端是 29.8.x,Testcontainers 能不能连上')
v = curl('/version'); print('  docker 服务端(GET /version):' + ' / '.join(f'{k} {x}' for k, x in re.findall(r'"(Version|ApiVersion|MinAPIVersion)":"([^"]*)"', v)[:3]))
print(f'  GET /v1.32/info 返回 HTTP {curl("/v1.32/info", True)}(1.20.4 的 docker-java 默认请求这个版本),GET /v1.44/info 返回 HTTP {curl("/v1.44/info", True)}')
for lab, cp, od, ex, en in (('Testcontainers 1.20.4,没有任何设置', CP, 'out', (), E), ('1.20.4 + 环境变量 DOCKER_API_VERSION=1.44', CP, 'out', (), jenv('21', DOCKER_API_VERSION='1.44')), ('1.20.4 + -Dapi.version=1.44', CP, 'out', API, E), ('Testcontainers 1.21.3,没有任何设置', JU + ':' + tcp('1.21.3'), 'out1.21.3', (), E), ('Testcontainers 1.21.4,没有任何设置', JU + ':' + tcp('1.21.4'), 'out1.21.4', (), E)):
    o, t = run('PgIT', cp, od, ex, en); k = keep(o); print(f'  {lab}:PgIT 用时 {t:.1f} s;' + (' / '.join(x for x in k if 'PgIT' in x or 'tests successful' in x))[:200])
purge()
print('== 二:一个真实的 Testcontainers 容器(1.20.4 + -Dapi.version=1.44,postgres:16-alpine 已在本地):启动、端口、测试运行期间的 docker ps')
q = sh(['java', *API, '-cp', f'out:{CP}', 'Life'], 200); lines = [l[4:] for l in (q.stdout + q.stderr).splitlines() if l.startswith('RES ')]
for l in lines: print('  ' + l)
purge()
print('== 三:JVM 结束之后容器去哪了:Ryuk 清理、JVM 退出钩子,以及 kill -9')
def gone_after(env=None, kill=False, wait=45):
    p = subprocess.Popen(['java', *API, '-cp', f'out:{CP}', 'Life', *(['hang'] if kill else [])], cwd=d, env=env or E, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if kill:
        for l in p.stdout:
            if 'docker ps' in l and 'postgres' in l: break
        time.sleep(0.5); os.kill(p.pid, 9)
    p.wait(timeout=120); n0 = len(leftovers()); tex = time.time(); g = None
    while time.time() - tex < wait:
        if not leftovers(): g = time.time() - tex; break
        time.sleep(0.25)
    return n0, g
for lab, env, kill in (('Ryuk 开启(默认),JVM 正常退出(没有调用 stop)', None, False), ('Ryuk 开启(默认),JVM 被 kill -9', None, True), ('TESTCONTAINERS_RYUK_DISABLED=true,JVM 正常退出', jenv('21', TESTCONTAINERS_RYUK_DISABLED='true'), False), ('TESTCONTAINERS_RYUK_DISABLED=true,JVM 被 kill -9', jenv('21', TESTCONTAINERS_RYUK_DISABLED='true'), True)):
    n0, g = gone_after(env, kill)
    print(f'  {lab}:JVM 结束时 docker ps -a 里有 {n0} 个容器;' + (f'{g:.1f} 秒后全部消失' if g is not None else f'45 秒后还剩 {len(leftovers())} 个:' + ' ;; '.join(dk("ps", "-a", "--format", "{{.Image}} | {{.Status}}").splitlines())))
    purge()
print('== 四:一个容器要花多少时间:每个测试类 / 每个测试方法一个容器,与同一个容器里克隆库')
q = sh(['java', *API, '-cp', f'out:{CP}', 'Cost'], 280); [print('  ' + l[4:]) for l in (q.stdout + q.stderr).splitlines() if l.startswith('RES ')]; purge()
for cls, lab in (('PerMethod', '10 个测试方法,@Container 是非静态字段(每个测试方法一个容器)'), ('Shared', '同样 10 个测试方法,@Container 是 static(整个类一个容器)')):
    ts = int(time.time()); o, t = run(cls, CP, 'out', API); te = int(time.time()) + 1
    ev = dk('events', '--since', str(ts - 1), '--until', str(te), '--filter', 'type=container', '--filter', 'event=create', '--format', '{{.Actor.Attributes.image}}'); from collections import Counter; cnt = Counter(l.strip() for l in ev.splitlines() if l.strip()); n = cnt.get('postgres:16-alpine', 0)
    print(f'  {cls}:{lab}:总用时 {t:.1f} s,创建的容器(按镜像):{dict(cnt)};' + ' / '.join(x for x in keep(o) if 'tests successful' in x or 'tests failed' in x)); purge()
print('== 五:没有 Docker 时的表现(把 user.home 指向一个空目录,让 Testcontainers 看不到 ~/.docker/run/docker.sock;Docker Desktop 本身仍在运行)')
(d / 'nohome').mkdir(exist_ok=True)
for cls in ('PgIT', 'PgSkip', 'Plain'):
    if cls == 'PgSkip': print('  --- 同一个类加 @Testcontainers(disabledWithoutDocker = true),并多一个根本不需要容器的 plain() 测试;对照一个没有容器的 Plain 类')
    o, t = run(cls, CP, 'out', (*API, f'-Duser.home={d / "nohome"}')); print(f'  [{cls}] 用时 {t:.1f} s'); [print('      ' + x) for x in keep(o)]
purge()
MAIN = r"""
import java.sql.*; import java.util.*;
public class Main {
  static String one(Connection c, String sql) { try (Statement s = c.createStatement()) { boolean rs = s.execute(sql); if (rs) { ResultSet r = s.getResultSet(); StringBuilder b = new StringBuilder(); int n = 0; while (r.next() && n++ < 3) { if (b.length() > 0) b.append(","); b.append(r.getObject(1)); } return "成功 " + b; } return "成功(更新 " + s.getUpdateCount() + ")"; } catch (SQLException e) { return "失败 [" + e.getSQLState() + "] " + e.getMessage().split("\n")[0].replaceAll("; SQL statement:.*", "").replaceAll(" \\[\\d+-\\d+\\]", ""); } }
  public static void main(String[] a) throws Exception {
    String[][] cases = {
      {"ON CONFLICT DO UPDATE", "INSERT INTO t(id, name) VALUES (1, 'x') ON CONFLICT (id) DO UPDATE SET name = 'y'"},
      {"RETURNING", "INSERT INTO t(id, name) VALUES (9, 'r') RETURNING id"},
      {"jsonb 运算符", "SELECT '{\"a\":1}'::jsonb ->> 'a'"},
      {"generate_series", "SELECT * FROM generate_series(1, 3)"},
      {"数组包含 @>", "SELECT ARRAY[1,2,3] @> ARRAY[2]"},
      {"text 列 = 整数", "SELECT id FROM t WHERE name = 1"},
      {"FOR UPDATE SKIP LOCKED", "SELECT id FROM t ORDER BY id FOR UPDATE SKIP LOCKED"},
      {"DISTINCT ON", "SELECT DISTINCT ON (name) id FROM t ORDER BY name, id"},
      {"to_char(date)", "SELECT to_char(DATE '2026-03-08', 'YYYY-MM-DD')"},
      {"字符串比较 'a' < 'B'", "SELECT 'a' < 'B'"},
      {"除零", "SELECT 1 / 0"},
      {"整数溢出 2147483647 + 1", "SELECT CAST(2147483647 AS INTEGER) + 1"},
    };
    String[][] dbs = {{"H2 2.3 默认模式", "jdbc:h2:mem:a;DB_CLOSE_DELAY=-1"}, {"H2 2.3 MODE=PostgreSQL", "jdbc:h2:mem:b;MODE=PostgreSQL;DB_CLOSE_DELAY=-1"}, {"PostgreSQL 16 真实", "jdbc:postgresql://127.0.0.1:" + a[0] + "/lab?user=lab"}};
    Map<String, List<String>> res = new LinkedHashMap<>();
    for (String[] db : dbs) { try (Connection c = DriverManager.getConnection(db[1])) {
        for (String[] cs : cases) { try (Statement s = c.createStatement()) { s.execute("DROP TABLE IF EXISTS t"); s.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name VARCHAR(20))"); s.execute("INSERT INTO t VALUES (1,'a'),(2,'a'),(3,'b'),(4,'1')"); }
          res.computeIfAbsent(cs[0], k -> new ArrayList<>()).add(one(c, cs[1])); }
        try (Statement s = c.createStatement()) { s.execute("DROP TABLE IF EXISTS t"); }
    } }
    System.out.println("RES1 " + "=== 逐条 SQL 在三种数据库上的结果");
    for (var e : res.entrySet()) { System.out.println("RES1 [" + e.getKey() + "]"); for (int i = 0; i < 3; i++) System.out.println("RES1     " + dbs[i][0] + ":" + e.getValue().get(i)); }
    // 事务性 DDL
    for (String[] db : dbs) { try (Connection c = DriverManager.getConnection(db[1].replace(":mem:", ":mem:q"))) { c.setAutoCommit(false); Statement s = c.createStatement();
        s.execute("CREATE TABLE ddl_t(id INT)"); c.rollback(); String r;
        try { s.executeQuery("SELECT count(*) FROM ddl_t").next(); r = "回滚之后表还在(DDL 没有被回滚)"; } catch (SQLException e) { r = "回滚之后表不存在(DDL 被回滚)"; }
        System.out.println("RES2 " + db[0] + ":CREATE TABLE 之后 ROLLBACK → " + r); try { c.setAutoCommit(true); s.execute("DROP TABLE IF EXISTS ddl_t"); } catch (Exception e) { } } }
    System.exit(0);
  }
}
"""
pg = PGI(9501).start()
try:
    CPB = mcp('org.postgresql:postgresql:42.7.4', 'com.h2database:h2:2.3.232')
    r = jrun('j239b', {'Main.java': MAIN}, cp=CPB, args=('9501',), timeout=120)
    if r['crc'] != 0: print(r['cout'][:2500]); sys.exit()
    sec1 = [l[5:] for l in r['out'].splitlines() if l.startswith('RES1 ')]; sec2 = [l[5:] for l in r['out'].splitlines() if l.startswith('RES2 ')]
    print('== 六:同样的 12 条 SQL 在 H2 2.3(默认 / PostgreSQL 模式)与真实 PostgreSQL 16.15 上的结果(H2 是进程内的替身)')
    [print('  ' + l) for l in sec1[1:]]
    print('== 七:DDL 在事务里回滚(autocommit=false,CREATE TABLE 后 ROLLBACK)')
    [print('  ' + l) for l in sec2]
    print('== 八:不用容器的隔离:本机真实 PostgreSQL 上 CREATE DATABASE ... TEMPLATE 的成本')
    import statistics as st
    def sql(q, db='lab'): return subprocess.run([f'{PGBIN}/psql', '-h', '127.0.0.1', '-p', '9501', '-U', 'lab', '-d', db, '-qAt', '-c', q], capture_output=True, text=True)
    sql("CREATE DATABASE tpl"); sql("CREATE TABLE orders(id serial primary key, status text, total int); CREATE INDEX ON orders(status); INSERT INTO orders(status,total) SELECT 'NEW', g FROM generate_series(1,1000) g", 'tpl')
    sql("ALTER DATABASE tpl IS_TEMPLATE true")
    cl = []; dr = []
    for i in range(20):
        t0 = time.perf_counter(); r1 = sql(f"CREATE DATABASE t{i} TEMPLATE tpl"); cl.append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter(); r2 = sql(f"DROP DATABASE t{i}"); dr.append((time.perf_counter() - t0) * 1000)
        assert r1.returncode == 0 and r2.returncode == 0, (r1.stderr, r2.stderr)
    cnt = sql("SELECT count(*) FROM orders", 'tpl').stdout.strip()
    print(f'  模板库里有 orders 表,{cnt} 行;连续 20 次 CREATE DATABASE ... TEMPLATE tpl 的中位数 {st.median(cl):.0f} ms(最小 {min(cl):.0f},最大 {max(cl):.0f});DROP DATABASE 中位数 {st.median(dr):.0f} ms(含 psql 进程启动)')
    t0 = time.perf_counter(); sql("SELECT 1"); base = (time.perf_counter() - t0) * 1000
    print(f'  对照:一次 psql -c "SELECT 1"(只有进程启动与连接)约 {base:.0f} ms')
    sql("CREATE DATABASE shared TEMPLATE tpl")
    q = "SELECT count(*) FROM orders WHERE status = 'A-left'"
    sql("INSERT INTO orders(status) VALUES ('A-left')", 'shared'); seen = sql(q, 'shared').stdout.strip()
    sql("CREATE DATABASE cla TEMPLATE tpl"); sql("CREATE DATABASE clb TEMPLATE tpl"); sql("INSERT INTO orders(status) VALUES ('A-left')", 'cla')
    print(f'  共享一个库:测试类 A 插入 1 行后没清理,测试类 B 执行 {q} 看到 {seen} 行;各自一个克隆库:A 在 cla 里插入同样的行,B 在 clb 里看到 {sql(q, "clb").stdout.strip()} 行(A 自己看到 {sql(q, "cla").stdout.strip()} 行)')
finally:
    pg.stop()
