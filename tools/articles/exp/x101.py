import sys, os, re, time, statistics, subprocess, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
import rl
tee('x101'); CP = scp('org.springframework.boot:spring-boot-starter-cache', 'org.springframework.boot:spring-boot-starter-data-redis')
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.cache.annotation.*; import org.springframework.cache.CacheManager; import org.springframework.cache.Cache; import org.springframework.data.redis.cache.*; import org.springframework.boot.cache.autoconfigure.RedisCacheManagerBuilderCustomizer; import org.springframework.context.annotation.Bean; import org.springframework.stereotype.Service; import java.time.Duration; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;\n'
FILES = {
 'src/demo/Svc.java': HDR + '''
@Service public class Svc {
  static final AtomicInteger CALLS = new AtomicInteger();
  @Cacheable(cacheNames = "users", key = "#id") public String byId(long id) { CALLS.incrementAndGet(); return "user-" + id; }
  @Cacheable(cacheNames = "users", key = "#id") public String nullable(long id) { CALLS.incrementAndGet(); return null; }
  @Cacheable(cacheNames = "users2", key = "#id", unless = "#result == null") public String nullableUnless(long id) { CALLS.incrementAndGet(); return null; }
  @Cacheable(cacheNames = "hot", key = "#k") public String slow(String k) throws Exception { CALLS.incrementAndGet(); Thread.sleep(300); return "v-" + k; }
  @Cacheable(cacheNames = "hotsync", key = "#k", sync = true) public String slowSync(String k) throws Exception { CALLS.incrementAndGet(); Thread.sleep(300); return "v-" + k; }
}
''',
 'src/demo/Cfg.java': HDR + '''
@org.springframework.context.annotation.Configuration @EnableCaching
public class Cfg {
  @Bean RedisCacheManagerBuilderCustomizer jitter(org.springframework.data.redis.connection.RedisConnectionFactory cf) { return b -> { if (System.getProperty("x101.lock") != null) b.cacheWriter(RedisCacheWriter.lockingRedisCacheWriter(cf)); b.withCacheConfiguration("jitter", RedisCacheConfiguration.defaultCacheConfig().entryTtl((k, v) -> Duration.ofSeconds(10 + ThreadLocalRandom.current().nextInt(10)))); }; }
}
''',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a); Svc s = c.getBean(Svc.class); CacheManager cm = c.getBean(CacheManager.class); String mode = System.getProperty("x101.mode");
    if (mode.equals("basic")) { s.byId(1); s.byId(1); s.byId(2); r("byId(1) 两次、byId(2) 一次:方法体真正执行了 " + Svc.CALLS.get() + " 次;CacheManager = " + cm.getClass().getSimpleName()); }
    else if (mode.equals("null")) {
      for (String w : new String[]{"nullable", "nullableUnless"}) { Svc.CALLS.set(0); Throwable e = null; try { if (w.equals("nullable")) { s.nullable(999); s.nullable(999); } else { s.nullableUnless(999); s.nullableUnless(999); } } catch (Throwable t) { e = t; }
        r(w + "(999) 调两次(方法体永远返回 null):方法体执行 " + Svc.CALLS.get() + " 次" + (e != null ? ";异常 " + e.getClass().getSimpleName() + ":" + String.valueOf(e.getMessage()).split("\\\\n")[0] : "")); }
    } else if (mode.equals("stampede")) {
      String which = System.getProperty("x101.which"); int th = 30; ExecutorService es = Executors.newFixedThreadPool(th); List<Future<?>> fs = new ArrayList<>(); CountDownLatch go = new CountDownLatch(1); long t0 = System.nanoTime();
      for (int i = 0; i < th; i++) fs.add(es.submit(() -> { go.await(); return which.equals("sync") ? s.slowSync("hot") : s.slow("hot"); })); go.countDown(); for (var f : fs) f.get(); es.shutdown();
      r(String.format("%s:%d 个线程同时请求同一个冷 key,方法体执行 %d 次,总用时 %.0f ms", (which.equals("sync") ? "sync = true" : "sync = false(默认)") + (System.getProperty("x101.lock") != null ? ",写入器换成 lockingRedisCacheWriter" : ""), th, Svc.CALLS.get(), (System.nanoTime() - t0) / 1e6));
    } else if (mode.equals("ttl")) {
      Cache fixed = cm.getCache("users"); Cache jit = cm.getCache("jitter"); for (int i = 0; i < 100; i++) { fixed.put("k" + i, "v"); jit.put("k" + i, "v"); } r("写入完成:users 100 个、jitter 100 个");
    }
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x101', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
node = rl.Node(7391, name='x101').start()
def run(mode, extra=None, which=None):
    pr = {'x101.lock': '1'} if (extra or {}).pop('lock', None) else {}
    pr.update({'spring.data.redis.host': '127.0.0.1', 'spring.data.redis.port': 7391, 'x101.mode': mode, 'spring.cache.type': 'redis'})
    if which: pr['x101.which'] = which
    pr.update(extra or {}); r = srun(b, 'demo.Main', props=pr, timeout=120); return res(r) or [r['out'][-1500:]]
def kinfo(cl, pat='*'):
    out = []
    for k in sorted(cl.do('KEYS', pat, raw=True)):
        kb = k if isinstance(k, bytes) else str(k).encode(); out.append((kb, cl.do('TTL', kb), len(cl.do('GET', kb, raw=True) or b'')))
    return out
cl = node.c(); print('Spring Boot 4.0.8 / Spring Framework 7.0.9 缓存抽象 / Spring Data Redis 4.0.7 RedisCacheManager / Redis 本机自己起的实例(端口 7391)')
print('== 一:key 的格式、过期时间与序列化')
cl.do('FLUSHALL'); cl.close(); [print('  ' + l) for l in run('basic')]; cl = node.c()
for kb, ttl, n in kinfo(cl): print(f'  redis 里的 key {kb!r}:TTL = {ttl}(-1 表示永不过期),value {n} 字节')
cl.do('FLUSHALL'); cl.close(); [print('  ' + l) for l in run('basic', {'spring.cache.redis.time-to-live': '60s'})]; cl = node.c()
print('  加 spring.cache.redis.time-to-live=60s 之后:' + str([(kb, ttl) for kb, ttl, n in kinfo(cl)]))
cl.do('FLUSHALL'); cl.close(); [print('  ' + l) for l in run('basic', {'spring.cache.redis.use-key-prefix': 'false'})]; cl = node.c()
print('  加 spring.cache.redis.use-key-prefix=false 之后 key:' + str([kb for kb, ttl, n in kinfo(cl)]))
print('== 二:缓存穿透:方法一直返回 null 的 key')
cl.do('FLUSHALL'); cl.close(); [print('  ' + l) for l in run('null', {'spring.cache.redis.time-to-live': '60s'})]; cl = node.c()
print('  redis 里留下的 key:' + str([(kb, ttl, n) for kb, ttl, n in kinfo(cl)]) + '(第一个是缓存了 null 的 users::999)')
cl.do('FLUSHALL'); cl.close(); [print('  cache-null-values=false:' + l) for l in run('null', {'spring.cache.redis.cache-null-values': 'false'})]; cl = node.c()
print('== 三:缓存击穿:一个冷 key 同时被很多线程请求')
cl.do('FLUSHALL'); cl.close(); [print('  ' + l) for l in run('stampede', which='nosync')]; cl = node.c()
cl.do('FLUSHALL'); cl.close(); [print('  ' + l) for l in run('stampede', which='sync')]; cl = node.c()
cl.do('FLUSHALL'); cl.close(); [print('  ' + l) for l in run('stampede', {'lock': 1}, which='sync')]; cl = node.c()
print('  -- 两个进程(模拟两个实例)同时请求同一个冷 key,sync = true + lockingRedisCacheWriter:')
cl.do('FLUSHALL'); cl.close(); outs = []
def go(i): outs.append(run('stampede', {'lock': 1}, which='sync'))
ts = [threading.Thread(target=go, args=(i,)) for i in range(2)]; [t.start() for t in ts]; [t.join() for t in ts]; cl = node.c()
for o in outs: print('    ' + o[0])
print('    两个进程的方法体执行次数相加 = ' + str(sum(int(re.search(r'方法体执行 (\d+) 次', o[0]).group(1)) for o in outs)))
print('== 四:缓存雪崩:TTL 集中在同一时刻')
cl.do('FLUSHALL'); cl.close(); [print('  ' + l) for l in run('ttl', {'spring.cache.redis.time-to-live': '20s'})]; cl = node.c()
fx = [t for kb, t, n in kinfo(cl, 'users::*')]; jt = [t for kb, t, n in kinfo(cl, 'jitter::*')]
print(f'  users(全局统一 TTL 20 秒):100 个 key 的剩余 TTL 取值 {sorted(set(fx))}')
print(f'  jitter(entryTtl 用 TtlFunction,10~19 秒随机):100 个 key 的剩余 TTL 最小 {min(jt)}、最大 {max(jt)},不同的取值有 {len(set(jt))} 个')
cl.close(); node.stop()
