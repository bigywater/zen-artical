import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
import rl
tee('x100'); CP = scp('org.springframework.boot:spring-boot-starter-data-redis', 'org.apache.commons:commons-pool2', 'org.springframework.boot:spring-boot-starter-jackson'); CP_NOPOOL = ':'.join(p for p in CP.strip().split(':') if 'commons-pool2' not in p)
LOG = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.data.redis.core.*; import org.springframework.data.redis.connection.*; import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory; import org.springframework.data.redis.serializer.*; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*; import java.time.Duration;\n'
FILES = {
 'src/demo/User.java': HDR + 'public class User implements java.io.Serializable { public String name; public int age; public List<String> tags; public User() {} public User(String n, int a, List<String> t) { name = n; age = a; tags = t; } public String toString() { return "User[" + name + "," + age + "," + tags + "]"; } }\n',
 'src/demo/Main.java': HDR + '''
@SpringBootApplication
public class Main {
  @org.springframework.context.annotation.Bean static org.springframework.beans.factory.config.BeanPostProcessor noShare() { return new org.springframework.beans.factory.config.BeanPostProcessor() { public Object postProcessBeforeInitialization(Object bean, String n) { if (bean instanceof LettuceConnectionFactory f && System.getProperty("x100.noshare") != null) f.setShareNativeConnection(false); return bean; } }; }
  static void r(String s) { System.out.println("RES " + s); }
  static String info(StringRedisTemplate t, String sec, String key) { String i = t.execute((RedisCallback<String>) c -> { Properties p = c.serverCommands().info(sec); return p.getProperty(key); }); return i; }
  public static void main(String[] a) throws Exception {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a); String mode = System.getProperty("x100.mode");
    StringRedisTemplate st = c.getBean(StringRedisTemplate.class); LettuceConnectionFactory cf = (LettuceConnectionFactory) c.getBean(RedisConnectionFactory.class);
    if (mode.equals("ser")) {
      RedisTemplate<Object, Object> jdk = (RedisTemplate<Object, Object>) c.getBean("redisTemplate"); User u = new User("alice", 30, List.of("a", "b"));
      r("自动配置的 RedisTemplate 的 key / value 序列化器:" + jdk.getKeySerializer().getClass().getSimpleName() + " / " + jdk.getValueSerializer().getClass().getSimpleName() + ";StringRedisTemplate:" + st.getKeySerializer().getClass().getSimpleName() + " / " + st.getValueSerializer().getClass().getSimpleName());
      jdk.opsForValue().set("jdk:user", u); st.opsForValue().set("str:name", "alice");
      RedisTemplate<String, Object> js = new RedisTemplate<>(); js.setConnectionFactory(cf); js.setKeySerializer(new StringRedisSerializer()); js.setValueSerializer(GenericJacksonJsonRedisSerializer.builder().build()); js.afterPropertiesSet(); js.opsForValue().set("json:user", u);
      r("读回来:jdk → " + jdk.opsForValue().get("jdk:user") + ";json → " + js.opsForValue().get("json:user"));
    } else if (mode.equals("conn")) {
      r("Lettuce 默认的命令超时 = " + cf.getClientConfiguration().getCommandTimeout() + ",连接超时 = " + (cf.getClientConfiguration() instanceof org.springframework.data.redis.connection.lettuce.LettuceClientConfiguration l ? l.getClientOptions().map(o -> String.valueOf(o.getSocketOptions().getConnectTimeout())).orElse("?") : "?") + ";是否用连接池:" + (cf.getClientConfiguration() instanceof org.springframework.data.redis.connection.lettuce.LettucePoolingClientConfiguration));
      r("空闲时 connected_clients = " + info(st, "clients", "connected_clients"));
      int th = 64; ExecutorService es = Executors.newFixedThreadPool(th); AtomicLong done = new AtomicLong(); long end = System.currentTimeMillis() + 3000; AtomicInteger peak = new AtomicInteger();
      st.opsForValue().set("k", "v"); List<Future<?>> fs = new ArrayList<>();
      for (int i = 0; i < th; i++) fs.add(es.submit(() -> { while (System.currentTimeMillis() < end) { st.opsForValue().get("k"); done.incrementAndGet(); } }));
      Thread.sleep(1500); peak.set(Integer.parseInt(info(st, "clients", "connected_clients").trim())); for (var f : fs) f.get(); es.shutdown();
      r(String.format("%d 个线程并发 GET 3 秒:共 %d 次(%.0f 次/秒);压测中间 connected_clients = %d", th, done.get(), done.get() / 3.0, peak.get()));
    } else if (mode.equals("pipe")) {
      int n = 10000; st.getConnectionFactory().getConnection().serverCommands().flushDb(); double[] ms = new double[3];
      for (String way : new String[]{"循环里一个一个 set", "executePipelined", "multiSet(一条 MSET)"}) {
        for (int k = 0; k < 3; k++) { st.getConnectionFactory().getConnection().serverCommands().flushDb(); long t0 = System.nanoTime();
          if (way.startsWith("循环")) for (int i = 0; i < n; i++) st.opsForValue().set("k" + i, "v" + i);
          else if (way.startsWith("executePipelined")) st.executePipelined((RedisCallback<Object>) con -> { for (int i = 0; i < n; i++) con.stringCommands().set(("k" + i).getBytes(), ("v" + i).getBytes()); return null; });
          else { Map<String, String> m = new HashMap<>(); for (int i = 0; i < n; i++) m.put("k" + i, "v" + i); st.opsForValue().multiSet(m); }
          ms[k] = (System.nanoTime() - t0) / 1e6; }
        Arrays.sort(ms); r(String.format("  %s:%d 个 key,中位 %.0f ms(%.0f~%.0f);dbsize = %d", way, n, ms[1], ms[0], ms[2], st.getConnectionFactory().getConnection().serverCommands().dbSize()));
      }
    }
    else if (mode.equals("fail")) {
      System.out.println("RES READY"); long t00 = System.currentTimeMillis(); System.out.flush();
      while (System.currentTimeMillis() - t00 < 14000) { long t0 = System.nanoTime(); String res; try { st.opsForValue().get("k"); res = "成功"; } catch (Throwable e) { Throwable rc = e; while (rc.getCause() != null) rc = rc.getCause(); res = "失败 " + e.getClass().getSimpleName() + " / " + rc.getClass().getSimpleName(); }
        System.out.println(String.format("RES   t=%4.1fs GET %s,用时 %.0f ms", (System.currentTimeMillis() - t00) / 1000.0, res, (System.nanoTime() - t0) / 1e6)); System.out.flush(); Thread.sleep(500); }
    }
    System.exit(0);
  }
}
''',
 'logback.xml': LOG,
}
b = sbuild('x100', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
node = rl.Node(7390, name='x100').start(); cl = node.c()
def run(mode, extra=None):
    pr = {'spring.data.redis.host': '127.0.0.1', 'spring.data.redis.port': 7390, 'x100.mode': mode}; pr.update(extra or {})
    r = srun(b, 'demo.Main', props=pr, timeout=180); return res(r) or [r['out'][-1800:]]
print('Spring Boot 4.0.8 / Spring Data Redis 4.0.7 / Lettuce 6.8.2 / Redis ' + str(rl.info(cl, 'server').get('redis_version')) + '(自己起的实例,端口 7390)')
print('== 一:序列化器')
cl.do('FLUSHALL'); [print('  ' + l) for l in run('ser')]
for k in sorted(cl.do('KEYS', '*', raw=True)):
    kb = k if isinstance(k, bytes) else str(k).encode(); v = cl.do('GET', kb, raw=True)
    print(f'  redis 里的 key {kb!r}:value 共 {len(v)} 字节,前 60 字节 {v[:60]!r}')
print('== 二:Lettuce 的连接(监控用的 Python 连接在运行期间先断开,所以 connected_clients 里只有应用的连接)')
def conn_case(title, cp, extra=None, ns=False):
    cl.close(); lines = srun(dict(b, cp=cp), 'demo.Main', props=dict({'spring.data.redis.host': '127.0.0.1', 'spring.data.redis.port': 7390, 'x100.mode': 'conn'}, **({'x100.noshare': '1'} if ns else {}), **(extra or {})), timeout=180)
    print('  -- ' + title + ':'); [print('    ' + l) for l in (res(lines) or [lines['out'][-1500:]])]
conn_case('classpath 上没有 commons-pool2(默认)', CP_NOPOOL)
conn_case('classpath 上有 commons-pool2(Boot 因此自动启用连接池)', CP)
conn_case('有 commons-pool2,再把 spring.data.redis.lettuce.pool.enabled 显式设成 false', CP, {'spring.data.redis.lettuce.pool.enabled': 'false'})
conn_case('有 commons-pool2,并把 shareNativeConnection 关掉(每次操作都从池里借连接,max-active=8)', CP, {'spring.data.redis.lettuce.pool.max-active': 8}, True)
cl = node.c()
print('== 三:pipeline')
cl.do('FLUSHALL'); [print(l) for l in run('pipe')]
print('== 四:Redis 不可用时')
import subprocess, threading
t0 = time.time(); r = srun(b, 'demo.Main', props={'spring.data.redis.host': '127.0.0.1', 'spring.data.redis.port': 7391, 'x100.mode': 'ser'}, timeout=120)
ex = [x.strip() for x in r['out'].splitlines() if re.match(r'^(Exception in thread "main" |Caused by: )?[\w.$]+(Exception|Error):', x.strip())]
print('  端口上没有 Redis:第一条命令失败,最里面的异常:' + (ex[-1][:200] if ex else r['out'][-300:]))
print('  -- 运行中把 Redis 进程 kill -9(第 2.5 秒),第 7.5 秒再启动;spring.data.redis.timeout=2s;应用每 0.5 秒 GET 一次:')
cl.close(); node.do_kill = None
p = subprocess.Popen(['java', '-Dspring.data.redis.host=127.0.0.1', '-Dspring.data.redis.port=7390', '-Dspring.data.redis.timeout=2s', '-Dx100.mode=fail', '-cp', str(b['out']) + ':' + b['cp'], 'demo.Main'], env=jenv('21'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
out = []
def reader():
    for line in p.stdout: out.append(line.rstrip())
th = threading.Thread(target=reader); th.start()
while not any(x == 'RES READY' for x in out): time.sleep(0.05)
time.sleep(2.5); node.kill9(); time.sleep(5.0); node = rl.Node(7390, name='x100b').start(); th.join(); node.stop()
for x in out:
    if x.startswith('RES   t='): print('    ' + x[4:])
cl = None

