import sys, os, re, time, json, shutil, subprocess, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x83')
CP = scp('org.springframework.boot:spring-boot-starter-jdbc', 'org.springframework.boot:spring-boot-starter-data-redis', 'org.springframework.boot:spring-boot-starter-test', 'org.springframework.boot:spring-boot-testcontainers', 'org.testcontainers:testcontainers-mysql', 'org.testcontainers:testcontainers-junit-jupiter', 'com.mysql:mysql-connector-j', 'com.h2database:h2', 'org.junit.platform:junit-platform-console')
IMP = '''package demo;
import org.springframework.boot.test.context.SpringBootTest; import org.springframework.boot.test.context.TestConfiguration; import org.springframework.boot.testcontainers.service.connection.ServiceConnection; import org.springframework.context.annotation.*; import org.springframework.test.context.*; import org.springframework.beans.factory.annotation.Autowired; import org.springframework.jdbc.core.JdbcTemplate; import org.springframework.data.redis.core.StringRedisTemplate; import org.junit.jupiter.api.*; import org.testcontainers.junit.jupiter.*; import org.testcontainers.mysql.MySQLContainer; import org.testcontainers.containers.GenericContainer; import org.testcontainers.utility.DockerImageName; import java.sql.*; import java.util.*;
'''
FILES = {
 'src/demo/App.java': 'package demo;\nimport org.springframework.boot.autoconfigure.SpringBootApplication;\n@SpringBootApplication public class App {}\n',
 'src/demo/U.java': IMP + '''
public class U {
  static final long T0 = System.nanoTime();
  static long ms() { return (System.nanoTime() - T0) / 1_000_000; }
  static void r(String s) { System.out.println("RES " + s); }
  static String dockerPs() { try { Process p = new ProcessBuilder("docker", "ps", "--format", "{{.Image}} {{.Ports}}", "--filter", "label=org.testcontainers=true").redirectErrorStream(true).start(); String o = new String(p.getInputStream().readAllBytes()).trim().replace("\\n", " ; "); return o.isEmpty() ? "(没有)" : o; } catch (Exception e) { return e.toString(); } }
}
''',
 'logback.xml': '<configuration><root level="OFF"/></configuration>',
}
def cls(name, body): FILES[f'src/demo/{name}.java'] = IMP + body
cls('T1_MySql', '''@SpringBootTest @Testcontainers public class T1_MySql {
  static final long T = System.nanoTime();
  @Container @ServiceConnection static MySQLContainer mysql = new MySQLContainer(DockerImageName.parse("mysql:8.4"));
  @Autowired JdbcTemplate jdbc;
  @Test void t() throws Exception {
    U.r("[T1] 从测试类初始化到测试方法开始(含启动 MySQL 容器、等它就绪、建 Spring 上下文)用了 " + (System.nanoTime() - T) / 1_000_000 + " ms");
    U.r("[T1] 容器:" + mysql.getDockerImageName() + ",容器 id " + mysql.getContainerId().substring(0, 12) + ",JDBC URL " + mysql.getJdbcUrl().replaceAll("\\\\?.*", ""));
    U.r("[T1] docker ps(带 testcontainers 标签):" + U.dockerPs());
    U.r("[T1] select version() → " + jdbc.queryForObject("select version()", String.class));
    jdbc.execute("create table t(name varchar(20))"); jdbc.update("insert into t values ('abc')");
    U.r("[T1] MySQL:where name = 'ABC' 命中 " + jdbc.queryForObject("select count(*) from t where name = 'ABC'", Integer.class) + " 行(存的是 abc)");
    try (Connection c = DriverManager.getConnection("jdbc:h2:mem:t1"); Statement st = c.createStatement()) {
      st.execute("create table t(name varchar(20))"); st.execute("insert into t values ('abc')"); ResultSet rs = st.executeQuery("select count(*) from t where name = 'ABC'"); rs.next();
      U.r("[T1] H2 内存库:同样的 SQL 命中 " + rs.getInt(1) + " 行");
      st.execute("create table u(id int primary key, v int)"); st.execute("insert into u values (1, 1)");
      try { st.execute("insert into u values (1, 2) on duplicate key update v = 2"); U.r("[T1] H2:INSERT … ON DUPLICATE KEY UPDATE 成功"); } catch (SQLException e) { U.r("[T1] H2:INSERT … ON DUPLICATE KEY UPDATE 失败:" + e.getMessage().split("\\n")[0].substring(0, Math.min(90, e.getMessage().split("\\n")[0].length()))); }
    }
    jdbc.execute("create table u(id int primary key, v int)"); jdbc.update("insert into u values (1, 1)");
    jdbc.update("insert into u values (1, 2) on duplicate key update v = 2"); U.r("[T1] MySQL:INSERT … ON DUPLICATE KEY UPDATE 之后 v = " + jdbc.queryForObject("select v from u where id = 1", Integer.class));
  } }''')
cls('T2_Redis', '''@SpringBootTest @Testcontainers public class T2_Redis {
  @Container @ServiceConnection(name = "redis") static GenericContainer<?> redis = new GenericContainer<>(DockerImageName.parse("redis:7-alpine")).withExposedPorts(6379);
  @Autowired StringRedisTemplate rt;
  @Test void t() {
    U.r("[T2] 容器:" + redis.getDockerImageName() + ",容器 id " + redis.getContainerId().substring(0, 12) + ",映射端口 6379 → " + redis.getMappedPort(6379));
    rt.opsForValue().set("k", "v", java.time.Duration.ofSeconds(100)); U.r("[T2] set / get → " + rt.opsForValue().get("k") + ";ttl " + rt.getExpire("k") + " 秒");
  } }''')
for n in ('P1', 'P2'):
    cls(n + '_Own', f'''@SpringBootTest @Testcontainers public class {n}_Own {{
  @Container @ServiceConnection static MySQLContainer mysql = new MySQLContainer(DockerImageName.parse("mysql:8.4"));
  @Autowired JdbcTemplate jdbc;
  @Test void t() {{ U.r("[{n}] 自己的容器 id " + mysql.getContainerId().substring(0, 12) + ";select 1 → " + jdbc.queryForObject("select 1", Integer.class)); }} }}''')
cls('Cfg', '''@TestConfiguration(proxyBeanMethods = false) public class Cfg { @Bean @ServiceConnection MySQLContainer mysql() { return new MySQLContainer(DockerImageName.parse("mysql:8.4")); } }''')
for n in ('Q1', 'Q2'):
    cls(n + '_Shared', f'''@SpringBootTest @Import(Cfg.class) public class {n}_Shared {{
  @Autowired JdbcTemplate jdbc; @Autowired MySQLContainer mysql;
  @Test void t() {{ U.r("[{n}] 共用的容器 id " + mysql.getContainerId().substring(0, 12) + ";select 1 → " + jdbc.queryForObject("select 1", Integer.class)); }} }}''')
b = sbuild('x83', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
ENVV = {'TESTCONTAINERS_RYUK_DISABLED': 'true', 'DOCKER_HOST': 'unix:///Users/w/.docker/run/docker.sock'}
def leftovers(): return subprocess.run(['docker', 'ps', '-a', '--filter', 'label=org.testcontainers=true', '--format', '{{.ID}} {{.Image}} {{.Status}}'], capture_output=True, text=True).stdout.strip()
def cleanup():
    ids = subprocess.run(['docker', 'ps', '-aq', '--filter', 'label=org.testcontainers=true'], capture_output=True, text=True).stdout.split()
    if ids: subprocess.run(['docker', 'rm', '-f', *ids], capture_output=True)
def junit(classes):
    t = time.time(); r = subprocess.run(['java', '-Dspring.docker.compose.enabled=false', '-cp', str(b['out']) + ':' + b['cp'], 'org.junit.platform.console.ConsoleLauncher', 'execute', '--disable-banner', '--disable-ansi-colors', '--details=summary', *sum((['--select-class', 'demo.' + c] for c in classes), [])], cwd=b['dir'], env=jenv('21', **ENVV), capture_output=True, text=True, timeout=600)
    o = tidy(r.stdout + r.stderr); return o, r.returncode, (time.time() - t) * 1000
def show(o, rc, ms):
    for l in [l[4:] for l in o.splitlines() if l.startswith('RES ')]: print('  ' + l)
    m = re.search(r'\[\s*(\d+) tests successful', o); f = re.search(r'\[\s*(\d+) tests failed', o)
    print(f'  退出码 {rc};成功 {m.group(1) if m else "?"},失败 {f.group(1) if f else "?"};整条命令 {ms:.0f} ms' + ('' if rc == 0 else '\n  ' + '\n  '.join(l.strip()[:300] for l in o.splitlines() if 'Exception' in l or 'Caused' in l)[:1200]))
cleanup()
print('Spring Boot 4.0.8 / JDK 21 / Testcontainers 2.0.5 / Docker 引擎 29.8.2(Docker Desktop);镜像 mysql:8.4 与 redis:7-alpine 预先 docker load 好了;为了不额外拉 Ryuk 镜像,设了 TESTCONTAINERS_RYUK_DISABLED=true,结束后我自己清理容器')
print('== 一:@ServiceConnection 加 MySQL 容器,跑真实 SQL')
o, rc, ms = junit(['T1_MySql']); show(o, rc, ms); print(f'  测试结束后带 testcontainers 标签的容器:{leftovers() or "(没有)"}'); cleanup()
print('== 二:Redis 容器')
o, rc, ms = junit(['T2_Redis']); show(o, rc, ms); print(f'  测试结束后带 testcontainers 标签的容器:{leftovers() or "(没有)"}'); cleanup()
print('== 三:两个测试类:各自一个 @Container,还是共用一个容器')
def rep(classes, label):
    msl = []
    for i in range(3):
        o, rc, ms = junit(classes); cleanup(); msl.append(ms)
        if i == 0: print(f'  {label}:'); show(o, rc, ms)
    print(f'  {label}:3 次整条命令中位 {statistics.median(msl):.0f} ms(范围 {min(msl):.0f}~{max(msl):.0f})'); return statistics.median(msl)
m1 = rep(['P1_Own', 'P2_Own'], '各自 @Container(static 字段)')
m2 = rep(['Q1_Shared', 'Q2_Shared'], '共用 @TestConfiguration 里的 @Bean @ServiceConnection 容器(两个类 @Import 同一个配置,共用 Spring 上下文缓存)')
print(f'  对比:各自容器 {m1:.0f} ms,共用容器 {m2:.0f} ms')
