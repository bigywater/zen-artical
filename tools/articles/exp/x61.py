import sys, os, re, time, json, subprocess, threading, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x61'); CP = scp('org.springframework.boot:spring-boot-starter-data-r2dbc', 'org.postgresql:r2dbc-postgresql')
PGBIN = '/opt/homebrew/opt/postgresql@16/bin'
PGDIR = JT / 'pg61'; SOCK = '/tmp/pg61sock'
shutil.rmtree(PGDIR, ignore_errors=True); shutil.rmtree(SOCK, ignore_errors=True); os.makedirs(SOCK)
subprocess.run([f'{PGBIN}/initdb', '-D', str(PGDIR), '-U', 'app', '--auth=trust', '-E', 'UTF8'], capture_output=True, check=True)
PGPORT = free_port()
subprocess.run([f'{PGBIN}/pg_ctl', '-D', str(PGDIR), '-o', f'-p {PGPORT} -c max_connections=200 -c listen_addresses=127.0.0.1 -k {SOCK}', '-l', str(PGDIR / 'pg.log'), '-w', 'start'], capture_output=True, check=True)
def psql(sql, db='demo'): return subprocess.run([f'{PGBIN}/psql', '-h', '127.0.0.1', '-p', str(PGPORT), '-U', 'app', '-d', db, '-At', '-c', sql], capture_output=True, text=True).stdout.strip()
subprocess.run([f'{PGBIN}/createdb', '-h', '127.0.0.1', '-p', str(PGPORT), '-U', 'app', 'demo'], check=True)
psql('create table users(id serial primary key, name text not null)')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.time.Duration; import java.util.*; import java.util.concurrent.atomic.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.annotation.Id; import org.springframework.data.relational.core.mapping.Table; import org.springframework.data.repository.reactive.ReactiveCrudRepository; import org.springframework.data.r2dbc.repository.config.EnableR2dbcRepositories;
import org.springframework.r2dbc.core.DatabaseClient; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional; import org.springframework.transaction.reactive.TransactionalOperator;
import reactor.core.publisher.*;
@SpringBootApplication @EnableR2dbcRepositories
public class Main implements ApplicationRunner {
  final Svc svc; final DatabaseClient db; final UserRepo repo; Main(Svc s, DatabaseClient d, UserRepo r) { svc = s; db = d; repo = r; }
  static void r(String s) { System.out.println("RES " + s); System.out.flush(); }
  static String chain(Throwable e) { StringBuilder sb = new StringBuilder(); int n = 0; for (Throwable t = e; t != null && n < 3; t = t.getCause(), n++) sb.append(n == 0 ? "" : " ← ").append(t.getClass().getSimpleName()).append(n == 0 ? "" : ""); return sb.toString(); }
  void attempt(String label, Mono<Void> m, String prefix) { try { m.block(); r(label + " → 正常结束"); } catch (Exception e) { r(label + " → 抛 " + chain(e) + ": " + e.getMessage()); } r("    库里 name 以 '" + prefix + "' 开头的行数 = " + svc.count(prefix).block()); }
  public void run(ApplicationArguments args) throws Exception {
    String sc = System.getProperty("scenario");
    switch (sc) {
      case "lazy" -> {
        r("repo.save(...) 调用后不订阅:"); repo.save(new User(null, "lazy-no-sub")); Thread.sleep(300); r("    库里 'lazy-no-sub' 的行数 = " + svc.count("lazy-no-sub").block());
        r("repo.save(...).block():"); var u = repo.save(new User(null, "lazy-sub")).block(); r("    返回的实体 id = " + u.id() + ",库里 'lazy-sub' 的行数 = " + svc.count("lazy-sub").block());
        r("repo.findAll().count().block() = " + repo.findAll().count().block());
        r("db.sql(\"select name from users order by id\").map(...).all().collectList().block() = " + db.sql("select name from users order by id").map(row -> row.get(0, String.class)).all().collectList().block());
      }
      case "pid" -> { r("无事务:" + svc.pidsNoTx().block()); r("无事务(再来一次):" + svc.pidsNoTx().block()); r("@Transactional:" + svc.pidsTx().block()); r("@Transactional(再来一次):" + svc.pidsTx().block()); }
      case "tx" -> {
        attempt("没有事务:保存两行再抛错", svc.failNoTx(), "notx-");
        attempt("@Transactional:保存两行再抛错", svc.failTx(), "tx-");
        attempt("TransactionalOperator:保存两行再抛错", svc.failOperator(), "op-");
        attempt("@Transactional 里 subscribe() 一个没接到链上的 save,再抛错", svc.forgetChain(), "forgot");
        attempt("@Transactional 里把 save().block() 放到 boundedElastic 上,再抛错", svc.blockingInside(), "block-inside");
      }
      case "pool" -> {
        int n = Integer.getInteger("n", 30); long ms = Long.getLong("sleepMs", 300); long t0 = System.currentTimeMillis(); AtomicInteger ok = new AtomicInteger(); Map<String, Integer> errs = new TreeMap<>();
        Flux.range(1, n).flatMap(i -> db.sql("select pg_sleep(" + ms / 1000.0 + ")").then().doOnSuccess(x -> ok.incrementAndGet()).onErrorResume(e -> { synchronized (errs) { errs.merge(chain(e), 1, Integer::sum); } return Mono.empty(); }), n).blockLast();
        r(n + " 个并发的 pg_sleep(" + ms + " ms):成功 " + ok.get() + ",失败 " + errs + ",总用时 " + (System.currentTimeMillis() - t0) + " ms");
      }
    }
  }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE); app.run(a); }
}
'''
USER = r'''package demo;
import org.springframework.data.annotation.Id; import org.springframework.data.relational.core.mapping.Table;
@Table("users") public record User(@Id Integer id, String name) {}
'''
REPO = r'''package demo;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
public interface UserRepo extends ReactiveCrudRepository<User, Integer> {}
'''
SVC = r'''package demo;
import java.time.Duration; import java.util.*; import java.util.concurrent.atomic.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.annotation.Id; import org.springframework.data.relational.core.mapping.Table; import org.springframework.data.repository.reactive.ReactiveCrudRepository; import org.springframework.data.r2dbc.repository.config.EnableR2dbcRepositories;
import org.springframework.r2dbc.core.DatabaseClient; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional; import org.springframework.transaction.reactive.TransactionalOperator;
import reactor.core.publisher.*;
@Service public class Svc {
    final UserRepo repo; final DatabaseClient db; final TransactionalOperator tx; Svc(UserRepo r, DatabaseClient d, TransactionalOperator t) { repo = r; db = d; tx = t; }
    Mono<Integer> pid() { return db.sql("select pg_backend_pid()").map(r -> r.get(0, Integer.class)).one(); }
    public Mono<String> pidsNoTx() { return pid().zipWith(Mono.delay(Duration.ofMillis(5)).then(pid())).map(t -> "第一条语句 pid=" + t.getT1() + ",第二条语句 pid=" + t.getT2()); }
    @Transactional public Mono<String> pidsTx() { return pid().zipWith(Mono.delay(Duration.ofMillis(5)).then(pid())).map(t -> "第一条语句 pid=" + t.getT1() + ",第二条语句 pid=" + t.getT2()); }
    public Mono<Void> failNoTx() { return repo.save(new User(null, "notx-1")).then(repo.save(new User(null, "notx-2"))).then(Mono.error(new IllegalStateException("boom"))); }
    @Transactional public Mono<Void> failTx() { return repo.save(new User(null, "tx-1")).then(repo.save(new User(null, "tx-2"))).then(Mono.error(new IllegalStateException("boom"))); }
    public Mono<Void> failOperator() { return repo.save(new User(null, "op-1")).then(repo.save(new User(null, "op-2"))).then(Mono.<Void>error(new IllegalStateException("boom"))).as(tx::transactional); }
    @Transactional public Mono<Void> forgetChain() { repo.save(new User(null, "forgot-chain")).subscribe(); return Mono.error(new IllegalStateException("boom")); }
    @Transactional public Mono<Void> blockingInside() { return Mono.fromRunnable(() -> repo.save(new User(null, "block-inside")).block()).subscribeOn(reactor.core.scheduler.Schedulers.boundedElastic()).then(Mono.error(new IllegalStateException("boom"))); }
    public Mono<Long> count(String prefix) { return db.sql("select count(*) from users where name like :p").bind("p", prefix + "%").map(r -> r.get(0, Long.class)).one(); }
}
'''

b = sbuild('x61', {'src/demo/Main.java': MAIN, 'src/demo/User.java': USER, 'src/demo/UserRepo.java': REPO, 'src/demo/Svc.java': SVC, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); subprocess.run([f'{PGBIN}/pg_ctl', '-D', str(PGDIR), '-m', 'immediate', 'stop']); sys.exit()
BASE = {'spring.r2dbc.url': f'r2dbc:postgresql://127.0.0.1:{PGPORT}/demo', 'spring.r2dbc.username': 'app', 'spring.r2dbc.password': 'x'}
def go(sc, props=None, poll=False, timeout=90):
    mx = [0]; stop = threading.Event()
    def pol():
        while not stop.is_set():
            try: mx[0] = max(mx[0], int(psql("select count(*) from pg_stat_activity where datname='demo' and pid <> pg_backend_pid() and state is not null") or 0))
            except Exception: pass
            time.sleep(0.05)
    th = threading.Thread(target=pol, daemon=True)
    if poll: th.start()
    r = srun(b, 'demo.Main', props={**BASE, 'scenario': sc, **(props or {})}, timeout=timeout); stop.set()
    lines = res(r)
    if not lines: lines = ['(无输出)' + r['out'][-600:]]
    return lines, mx[0]
def p(lines): [print('  ' + l) for l in lines]
try:
    print('Spring Boot 4.0.8 / Spring Data R2DBC 4.0.7 / r2dbc-postgresql 1.1.2 / r2dbc-pool 1.0.2;数据库是本机自己起的 PostgreSQL 16(端口 %d),表 users(id serial, name text)' % PGPORT)
    print('== 一:惰性与基本用法:不订阅就没有查询')
    l, _ = go('lazy'); p(l)
    print('== 二:没有事务时,同一个方法里的两条语句是不是同一个连接(pg_backend_pid)')
    l, _ = go('pid'); p(l)
    print('== 三:事务的回滚:没有事务 / @Transactional / TransactionalOperator / 没接到链上的 subscribe()')
    l, _ = go('tx'); p(l)
    print('== 四:连接池:30 个并发的 pg_sleep(300 ms),服务端同时存在的连接数(每 50 ms 轮询 pg_stat_activity 取最大值)')
    for pr, lab in [({}, '默认的 R2DBC 连接池'), ({'spring.r2dbc.pool.max-size': '3', 'spring.r2dbc.pool.initial-size': '3'}, 'spring.r2dbc.pool.max-size=3'), ({'spring.r2dbc.pool.max-size': '30', 'spring.r2dbc.pool.initial-size': '1'}, 'spring.r2dbc.pool.max-size=30')]:
        l, mx = go('pool', pr, poll=True); print(f'  {lab}:'); p(l); print(f'      服务端同时存在的连接数最大值 = {mx}')
    l, mx = go('pool', {'spring.r2dbc.pool.max-size': '2', 'spring.r2dbc.pool.initial-size': '2', 'spring.r2dbc.pool.max-acquire-time': '200ms', 'n': '10', 'sleepMs': '600'}, poll=True); print('  max-size=2、max-acquire-time=200ms,10 个并发的 pg_sleep(600 ms):'); p(l); print(f'      服务端同时存在的连接数最大值 = {mx}')
finally:
    subprocess.run([f'{PGBIN}/pg_ctl', '-D', str(PGDIR), '-m', 'immediate', 'stop'], capture_output=True)
