import sys, os, re, time, statistics, threading, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x92'); CP = scp('org.springframework.boot:spring-boot-starter-data-jpa', 'org.springframework.boot:spring-boot-starter-webmvc', 'com.mysql:mysql-connector-j')
LOG = '<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{40} - %msg%n</pattern></encoder></appender><root level="WARN"><appender-ref ref="C"/></root></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.data.jpa.repository.*; import jakarta.persistence.Entity; import jakarta.persistence.Id; import jakarta.persistence.OneToMany; import jakarta.persistence.ManyToOne; import org.springframework.web.bind.annotation.*; import com.zaxxer.hikari.HikariDataSource; import javax.sql.DataSource; import java.util.*;\n'
FILES = {
 'src/demo/Author.java': HDR + '@Entity public class Author { @Id Long id; String name; @OneToMany(mappedBy = "author") List<Book> books = new ArrayList<>(); public Long getId() { return id; } public List<Book> getBooks() { return books; } }\n',
 'src/demo/Book.java': HDR + '@Entity public class Book { @Id Long id; String title; @ManyToOne Author author; }\n',
 'src/demo/AuthorRepo.java': HDR + 'public interface AuthorRepo extends JpaRepository<Author, Long> {}\n',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication @RestController
public class Main {
  final AuthorRepo repo; final HikariDataSource ds; Main(AuthorRepo r, DataSource d) { repo = r; ds = (HikariDataSource) d; }
  int active() { return ds.getHikariPoolMXBean().getActiveConnections(); }
  @GetMapping("/probe") String probe(@RequestParam long ms) throws Exception { int before = active(); repo.findById(1L); int afterDb = active(); Thread.sleep(ms); return "查库之前活动连接=" + before + ",repo.findById 返回之后=" + afterDb + ",再睡 " + ms + " ms 之后=" + active(); }
  @GetMapping("/lazy") String lazy() { Author a = repo.findById(1L).get(); return "books.size()=" + a.getBooks().size(); }
  @GetMapping("/work") String work(@RequestParam long ms) throws Exception { repo.findById(1L); Thread.sleep(ms); return "ok"; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x92', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x92'); URL = jdbc(my)
BASE = {'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app', 'spring.jpa.hibernate.ddl-auto': 'create', 'spring.datasource.hikari.maximum-pool-size': '2', 'spring.datasource.hikari.minimum-idle': '2', 'spring.datasource.hikari.connection-timeout': '1000'}
def start(extra=None, ddl='update'):
    pr = dict(BASE); pr['spring.jpa.hibernate.ddl-auto'] = ddl; pr.update(extra or {}); pr['server.port'] = free_port(); a = SApp(b, 'demo.Main', props=pr, port=pr['server.port'], name='stdout'); a.start(timeout=90); return a
# 先建表并放一行数据
a = start(ddl='create'); a.stop()
my.q("insert into demo.author(id, name) values (1, 'a1')"); my.q("insert into demo.book(id, title, author_id) values (1, 't1', 1), (2, 't2', 1), (3, 't3', 1)")
print('Spring Boot 4.0.8 / Hibernate 7 / HikariCP / MySQL 26.7.0(自己起的实例);Hikari maximum-pool-size=2、connection-timeout=1000 ms,Tomcat 线程池是默认值;一个 Author 带 3 本 Book')
def g(a, p, t=20):
    try: s, body, _ = a.get(p, timeout=t); return s, body
    except Exception as e: return None, repr(e)[:100]
print('== 一:默认(open-in-view 没写)的启动警告,以及连接被占多久')
a = start(); warn = [l for l in a.log().splitlines() if 'open-in-view' in l]
print('  启动日志里的 open-in-view 警告:' + (warn[0][:260] if warn else '(没有)'))
print('  GET /probe?ms=600 → ' + g(a, '/probe?ms=600')[1]); a.stop()
a = start({'spring.jpa.open-in-view': 'true'}); warn = [l for l in a.log().splitlines() if 'open-in-view' in l]; print(f'  显式写 spring.jpa.open-in-view=true:启动日志里的警告条数 {len(warn)}')
print('  GET /probe?ms=600 → ' + g(a, '/probe?ms=600')[1]); a.stop()
a = start({'spring.jpa.open-in-view': 'false'}); warn = [l for l in a.log().splitlines() if 'open-in-view' in l]; print(f'  spring.jpa.open-in-view=false:启动日志里的警告条数 {len(warn)}')
print('  GET /probe?ms=600 → ' + g(a, '/probe?ms=600')[1]); a.stop()
print('== 二:懒加载在控制器里(没有 @Transactional)能不能用')
for lab, pr in (('open-in-view=true', {'spring.jpa.open-in-view': 'true'}), ('open-in-view=false', {'spring.jpa.open-in-view': 'false'})):
    a = start(pr); s, body = g(a, '/lazy'); print(f'  {lab}:GET /lazy → HTTP {s} {body[:180]}'); 
    lg = [l for l in a.log().splitlines() if 'LazyInitializationException' in l]; print(f'    日志里的异常行:' + (lg[0][:230] if lg else '(没有)')); a.stop()
print('== 三:池只有 2 个连接,10 个并发请求,每个请求 查库 1 次 + 睡 300 ms(模拟调用外部服务或渲染),持续 8 秒')
def load(a, conc=10, dur=8, ms=300):
    ok = [0]; errs = {}; lat = []; stop = time.time() + dur; lock = threading.Lock()
    def w():
        while time.time() < stop:
            t = time.time(); s, body = g(a, f'/work?ms={ms}', 10); d = (time.time() - t) * 1000
            with lock:
                if s == 200: ok[0] += 1; lat.append(d)
                else: errs[str(s)] = errs.get(str(s), 0) + 1
    ts = [threading.Thread(target=w) for _ in range(conc)]; [t.start() for t in ts]; [t.join() for t in ts]
    lat.sort(); return ok[0], errs, (lat[len(lat) // 2] if lat else 0), (lat[int(len(lat) * .99)] if lat else 0)
for lab, pr in (('open-in-view=true', {'spring.jpa.open-in-view': 'true'}), ('open-in-view=false', {'spring.jpa.open-in-view': 'false'})):
    a = start(pr); g(a, '/work?ms=10'); ok, errs, p50, p99 = load(a)
    lg = [l for l in a.log().splitlines() if 'not available' in l or 'request timed out' in l]
    print(f'  {lab}:成功 {ok} 个({ok / 8:.1f} 个/秒),失败 {sum(errs.values())} 个 {errs or ""};成功请求的延迟 p50 {p50:.0f} ms、p99 {p99:.0f} ms')
    if lg: print('    服务端日志里的一行:' + lg[0][:230])
    a.stop()
my.stop()
