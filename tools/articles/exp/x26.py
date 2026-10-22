import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x26'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
import org.springframework.cache.*; import org.springframework.cache.annotation.*; import org.springframework.cache.concurrent.ConcurrentMapCacheManager; import org.springframework.context.annotation.*;
public class Main {
  static final AtomicInteger loads = new AtomicInteger();
  public static class Repo {
    @Cacheable("a") public String noArg() { loads.incrementAndGet(); return "v"; }
    @Cacheable("a") public String one(int id) { loads.incrementAndGet(); return "v" + id; }
    @Cacheable("a") public String two(int x, String y) { loads.incrementAndGet(); return x + y; }
    @Cacheable(value = "b", key = "#x + ':' + #y") public String spel(int x, String y) { loads.incrementAndGet(); return x + y; }
    @Cacheable(value = "c", key = "#root.methodName + #id") public String named(int id) { loads.incrementAndGet(); return "n" + id; }
    @Cacheable(value = "d") public String nullable(int id) { loads.incrementAndGet(); return id == 0 ? null : "x"; }
    @Cacheable(value = "e", unless = "#result == null") public String unlessNull(int id) { loads.incrementAndGet(); return id == 0 ? null : "x"; }
    @Cacheable(value = "f", condition = "#id > 10") public String cond(int id) { loads.incrementAndGet(); return "c" + id; }
    @Cacheable(value = "g") public String slow(int id) throws Exception { loads.incrementAndGet(); Thread.sleep(200); return "s" + id; }
    @Cacheable(value = "h", sync = true) public String slowSync(int id) throws Exception { loads.incrementAndGet(); Thread.sleep(200); return "s" + id; }
    @CachePut(value = "a", key = "#id") public String put(int id) { loads.incrementAndGet(); return "put" + id; }
    @CacheEvict(value = "a", key = "#id") public void evict(int id) { }
    @CacheEvict(value = "a", allEntries = true) public void evictAll() { }
    @CacheEvict(value = "a", key = "#id") public void evictFails(int id) { throw new IllegalStateException("失败"); }
    @CacheEvict(value = "a", key = "#id", beforeInvocation = true) public void evictFailsBefore(int id) { throw new IllegalStateException("失败"); }
    @Cacheable("m") public List<String> list(int id) { loads.incrementAndGet(); return new ArrayList<>(List.of("a", "b")); }
    @Cacheable("a") public String inner(int id) { loads.incrementAndGet(); return "i" + id; }
    public String callInner(int id) { return inner(id); }
  }
  @Configuration @EnableCaching static class Conf { @Bean CacheManager cacheManager() { return new ConcurrentMapCacheManager(); } @Bean Repo repo() { return new Repo(); } }
  static String keys(CacheManager m, String c) { Object n = m.getCache(c).getNativeCache(); return new ArrayList<>(((Map<?, ?>) n).keySet()).toString().replace("org.springframework.cache.interceptor.", ""); }
  static String l(java.util.concurrent.Callable<Object> c) { loads.set(0); try { c.call(); c.call(); } catch (Exception e) { return "✗ " + e.getClass().getSimpleName(); } return "同一个调用连续 2 次,目标方法执行 " + loads.get() + " 次"; }
  public static void main(String[] args) throws Exception {
    AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Repo r = c.getBean(Repo.class); CacheManager cm = c.getBean(CacheManager.class); String m = args[0];
    switch (m) {
      case "keys" -> {
        r.noArg(); System.out.println("RES 无参数:缓存里的键 " + keys(cm, "a")); cm.getCache("a").clear();
        r.one(7); System.out.println("RES 一个参数 one(7):键 " + keys(cm, "a") + "(键的类型 " + ((Map<?, ?>) cm.getCache("a").getNativeCache()).keySet().iterator().next().getClass().getSimpleName() + ")"); cm.getCache("a").clear();
        r.two(1, "x"); System.out.println("RES 两个参数 two(1, \"x\"):键 " + keys(cm, "a")); r.two(1, "x"); cm.getCache("a").clear();
        r.noArg(); r.one(7); System.out.println("RES 同一个缓存 \"a\" 里同时放无参方法和 one(7) 的结果 → 键 " + keys(cm, "a")); cm.getCache("a").clear();
        r.spel(2, "y"); System.out.println("RES key=\"#x + ':' + #y\" 的 spel(2, \"y\"):键 " + keys(cm, "b")); r.named(3); System.out.println("RES key=\"#root.methodName + #id\" 的 named(3):键 " + keys(cm, "c"));
        loads.set(0); r.one(1); int afterOne = loads.get(); loads.set(0); String v = r.inner(1); System.out.println("RES 键冲突:one(1) 先调用(目标方法执行 " + afterOne + " 次),缓存 \"a\" 里键 1 对应 v1;再调另一个方法 inner(1)(同一个缓存 \"a\"、同样的单个参数 1):inner 的目标方法执行 " + loads.get() + " 次,返回的是 " + v + "(拿到了 one(1) 的缓存值)"); }
      case "null" -> { System.out.println("RES 返回 null 的方法,没有 unless:" + l(() -> r.nullable(0)) + ";缓存里键 " + keys(cm, "d") + ";有 unless=\"#result == null\":" + l(() -> r.unlessNull(0)) + "(null 不缓存)"); System.out.println("RES condition=\"#id > 10\":id=5 → " + l(() -> r.cond(5)) + ";id=50 → " + l(() -> r.cond(50))); }
      case "sync" -> { for (String k : new String[]{"slow", "slowSync"}) { loads.set(0); int N = 8; ExecutorService ex = Executors.newFixedThreadPool(N); CountDownLatch go = new CountDownLatch(1); List<Future<String>> fs = new ArrayList<>();
          for (int i = 0; i < N; i++) fs.add(ex.submit(() -> { go.await(); return k.equals("slow") ? r.slow(1) : r.slowSync(1); })); long t0 = System.nanoTime(); go.countDown(); for (Future<String> f : fs) f.get(); long ms = (System.nanoTime() - t0) / 1_000_000; ex.shutdown();
          System.out.println("RES " + (k.equals("slow") ? "没有 sync" : "sync = true") + ":8 个线程同时取同一个 key(加载要 200 ms),目标方法执行了 " + loads.get() + " 次,全部返回花了 " + ms + " ms"); } }
      case "put" -> { r.one(5); r.put(5); System.out.println("RES one(5) 缓存后 @CachePut put(5):缓存值 " + cm.getCache("a").get(5).get() + "(@CachePut 总会执行方法并覆盖缓存)"); r.evict(5); System.out.println("RES @CacheEvict 之后 键 " + keys(cm, "a"));
        r.one(6); r.one(7); r.evictAll(); System.out.println("RES allEntries 之后 键 " + keys(cm, "a"));
        r.one(8); try { r.evictFails(8); } catch (Exception e) { } System.out.println("RES 方法抛异常时 @CacheEvict(默认 beforeInvocation=false):evictFails(8) 之后键 " + keys(cm, "a") + "(缓存没清掉)"); try { r.evictFailsBefore(8); } catch (Exception e) { } System.out.println("RES beforeInvocation = true:evictFailsBefore(8) 之后键 " + keys(cm, "a")); }
      case "mut" -> { List<String> a = r.list(1); a.add("被调用者改过"); List<String> b = r.list(1); System.out.println("RES 缓存了一个可变 List:第一次拿到后往里 add 一个元素,第二次拿到 " + b + "(同一个对象:" + (a == b) + ";目标方法执行 " + loads.get() + " 次)"); }
      case "self" -> { loads.set(0); r.callInner(9); r.callInner(9); int viaSelf = loads.get(); loads.set(0); r.inner(9); r.inner(9); System.out.println("RES 通过 callInner(同一个类里调 inner)连调 2 次:目标方法执行 " + viaSelf + " 次(缓存没生效);直接调 inner 连调 2 次:目标方法执行 " + loads.get() + " 次(第 1 次未命中,第 2 次命中)"); }
    }
  }
}
'''
b = sbuild('x26', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): r = srun(b, 'demo.Main', args=[m]); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-900:]]
print('Spring Framework 7.0.9(@EnableCaching + ConcurrentMapCacheManager)。缓存抽象')
print('== 一:默认的键怎么生成')
[print('  ' + l) for l in run('keys')]
print('== 二:null 与条件')
[print('  ' + l) for l in run('null')]
print('== 三:并发取同一个键:sync = true')
[print('  ' + l) for l in run('sync')]
print('== 四:@CachePut 与 @CacheEvict')
[print('  ' + l) for l in run('put')]
print('== 五:缓存的是引用')
[print('  ' + l) for l in run('mut')]
print('== 六:自调用')
[print('  ' + l) for l in run('self')]
