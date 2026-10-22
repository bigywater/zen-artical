import sys, os, re, time, json, subprocess, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x60')
CP1 = scp('org.springframework.boot:spring-boot-starter-webmvc', 'org.springframework.boot:spring-boot-starter-restclient')
CP2 = scp('org.springframework.boot:spring-boot-starter-webflux', 'org.springframework.boot:spring-boot-starter-webclient')
LOG = '<configuration><root level="OFF"/></configuration>'
DOWN = r'''
package demo;
import com.sun.net.httpserver.*; import java.net.*; import java.util.concurrent.*;
public class Down { public static void main(String[] a) throws Exception {
  HttpServer s = HttpServer.create(new InetSocketAddress("127.0.0.1", Integer.parseInt(a[0])), 8192); s.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
  s.createContext("/slow", ex -> { try { String q = ex.getRequestURI().getQuery(); Thread.sleep(Long.parseLong(q.substring(q.indexOf('=') + 1))); byte[] b = "ok".getBytes(); ex.sendResponseHeaders(200, b.length); ex.getResponseBody().write(b); } catch (Exception e) { } finally { ex.close(); } });
  s.start(); System.out.println("RES down-up"); } }
'''
LOADGEN = r'''
package demo;
import java.net.*; import java.net.http.*; import java.time.Duration; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Load { public static void main(String[] a) throws Exception {
  String url = a[0]; int conc = Integer.parseInt(a[1]); long warm = Long.parseLong(a[2]) * 1000, dur = Long.parseLong(a[3]) * 1000, ramp = Math.min(warm - 500, 2500);
  HttpClient c = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(10)).executor(Executors.newVirtualThreadPerTaskExecutor()).build();
  long[] lat = new long[4_000_000]; AtomicInteger idx = new AtomicInteger(); AtomicInteger errs = new AtomicInteger(); ConcurrentHashMap<String, AtomicInteger> et = new ConcurrentHashMap<>(); long t0 = System.currentTimeMillis(), tMeasure = t0 + warm, tEnd = tMeasure + dur;
  CountDownLatch done = new CountDownLatch(conc); HttpRequest rq = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(20)).GET().build();
  for (int i = 0; i < conc; i++) { final int id = i; Thread.ofVirtual().start(() -> { try { Thread.sleep(ramp * id / conc);
      while (System.currentTimeMillis() < tEnd) { long s = System.nanoTime(); try { var r = c.send(rq, HttpResponse.BodyHandlers.discarding()); long e = System.nanoTime(); if (System.currentTimeMillis() >= tMeasure) { if (r.statusCode() == 200) { int k = idx.getAndIncrement(); if (k < lat.length) lat[k] = e - s; } else errs.incrementAndGet(); } } catch (Exception ex) { if (System.currentTimeMillis() >= tMeasure) { errs.incrementAndGet(); et.computeIfAbsent(ex.getClass().getSimpleName() + ":" + String.valueOf(ex.getMessage()).replaceAll("\\s+", " "), k -> new AtomicInteger()).incrementAndGet(); } try { Thread.sleep(20); } catch (InterruptedException ie) { } } }
    } catch (InterruptedException e) { } finally { done.countDown(); } }); }
  done.await(); int n = Math.min(idx.get(), lat.length); Arrays.sort(lat, 0, n);
  System.out.printf("RES %d %.1f %.1f %.1f %.1f %d%n", n, n * 1000.0 / dur, lat[n / 2] / 1e6, lat[(int) (n * 0.99)] / 1e6, lat[n - 1] / 1e6, errs.get()); et.forEach((k, v) -> System.out.println("ERR " + v + " x " + k)); System.exit(0); } }
'''
MAIN1 = r'''
package demo;
import java.lang.management.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*; import org.springframework.web.client.RestClient;
@SpringBootApplication @RestController
public class Main {
  final RestClient rc; Main(RestClient.Builder b) { rc = b.baseUrl(System.getProperty("down")).build(); }
  @GetMapping("/work") String work() { return rc.get().uri("/slow?ms=100").retrieve().body(String.class); }
  static final java.util.concurrent.ConcurrentHashMap<String, java.util.concurrent.atomic.AtomicInteger> ERR = new java.util.concurrent.ConcurrentHashMap<>();
  @ExceptionHandler(Exception.class) org.springframework.http.ResponseEntity<String> ex(Exception e) { Throwable r = e; while (r.getCause() != null && r.getCause() != r) r = r.getCause(); ERR.computeIfAbsent(e.getClass().getSimpleName() + " <- " + r.getClass().getSimpleName() + ": " + String.valueOf(r.getMessage()), k -> new java.util.concurrent.atomic.AtomicInteger()).incrementAndGet(); return org.springframework.http.ResponseEntity.status(500).body("err"); }
  @GetMapping("/stats") String stats() { System.gc(); var t = ManagementFactory.getThreadMXBean(); var m = ManagementFactory.getMemoryMXBean(); return "peakPlatformThreads=" + t.getPeakThreadCount() + " livePlatformThreads=" + t.getThreadCount() + " heapUsedMB=" + m.getHeapMemoryUsage().getUsed() / 1048576 + (ERR.isEmpty() ? "" : " 应用内的异常=" + ERR); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
MAIN2 = r'''
package demo;
import java.lang.management.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*; import org.springframework.web.reactive.function.client.WebClient; import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import reactor.core.publisher.Mono; import reactor.netty.http.client.HttpClient; import reactor.netty.resources.ConnectionProvider;
@SpringBootApplication @RestController
public class Main {
  final WebClient wc = WebClient.builder().baseUrl(System.getProperty("down")).clientConnector(new ReactorClientHttpConnector(HttpClient.create(ConnectionProvider.builder("big").maxConnections(20000).pendingAcquireMaxCount(20000).build()))).build();
  @GetMapping("/work") Mono<String> work() { return wc.get().uri("/slow?ms=100").retrieve().bodyToMono(String.class); }
  static final java.util.concurrent.ConcurrentHashMap<String, java.util.concurrent.atomic.AtomicInteger> ERR = new java.util.concurrent.ConcurrentHashMap<>();
  @ExceptionHandler(Exception.class) org.springframework.http.ResponseEntity<String> ex(Exception e) { Throwable r = e; while (r.getCause() != null && r.getCause() != r) r = r.getCause(); ERR.computeIfAbsent(e.getClass().getSimpleName() + " <- " + r.getClass().getSimpleName() + ": " + String.valueOf(r.getMessage()), k -> new java.util.concurrent.atomic.AtomicInteger()).incrementAndGet(); return org.springframework.http.ResponseEntity.status(500).body("err"); }
  @GetMapping("/stats") String stats() { System.gc(); var t = ManagementFactory.getThreadMXBean(); var m = ManagementFactory.getMemoryMXBean(); return "peakPlatformThreads=" + t.getPeakThreadCount() + " livePlatformThreads=" + t.getThreadCount() + " heapUsedMB=" + m.getHeapMemoryUsage().getUsed() / 1048576 + (ERR.isEmpty() ? "" : " 应用内的异常=" + ERR); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b1 = sbuild('x60a', {'src/demo/Main.java': MAIN1, 'src/demo/Down.java': DOWN, 'src/demo/Load.java': LOADGEN, 'logback.xml': LOG}, CP1)
b2 = sbuild('x60b', {'src/demo/Main.java': MAIN2, 'logback.xml': LOG}, CP2)
for bb in (b1, b2):
    if bb['crc'] != 0: print(bb['cout']); sys.exit()
def jproc(main, args, bb=b1, jopts=(), **kw): return subprocess.Popen(['java', *jopts, '-cp', str(bb['out']) + ':' + bb['cp'], main, *map(str, args)], env=jenv(bb['jdk']), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)
free = free_port(); down = jproc('demo.Down', [free], jopts=['-Dsun.net.httpserver.maxIdleConnections=1000000', '-Dsun.net.httpserver.idleInterval=3600']); down.stdout.readline()
DURL = f'http://127.0.0.1:{free}'
def rss(pid): return int(subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True).stdout.strip() or 0) / 1024
LAST_ERR = []
def load(port, conc, warm=3, dur=6):
    p = jproc('demo.Load', [f'http://127.0.0.1:{port}/work', conc, warm, dur]); out = p.communicate(timeout=120)[0]
    m = re.search(r'RES (\d+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) (\d+)', out); LAST_ERR[:] = re.findall(r'ERR .*', out)
    return None if not m else dict(n=int(m.group(1)), rps=float(m.group(2)), p50=float(m.group(3)), p99=float(m.group(4)), mx=float(m.group(5)), errs=int(m.group(6)))
print('Spring Boot 4.0.8 / JDK 21 / macOS 10 核;被测应用每个请求去调下游的 /slow?ms=100(下游是 JDK HttpServer + 虚拟线程,真实 HTTP 调用),应用 -Xmx1g;压测端是 JDK HttpClient + 虚拟线程,先预热 3 秒再测 6 秒,每个并发度一条独立 keep-alive 连接')
CONC = [int(x) for x in os.environ.get('CONC', '100,1000,3000').split(',')]
ONLY = os.environ.get('ONLY')
for name, bb, props, lab in [('mvc-platform', b1, {}, 'Spring MVC(Tomcat 默认 200 个平台线程)'), ('mvc-virtual', b1, {'spring.threads.virtual.enabled': 'true'}, 'Spring MVC + spring.threads.virtual.enabled=true'), ('webflux', b2, {}, 'Spring WebFlux(Reactor Netty,WebClient 连接池调大到 20000)')]:
    if ONLY and ONLY != name: continue
    app = SApp(bb, 'demo.Main', props={'down': DURL, **props}, jopts=['-Xmx1g', '-Xms256m']).start(); port = int(app.props['server.port'])
    s, d, h = app.get('/work'); print(f'== {lab}'); print(f'  启动后空闲 RSS {rss(app.p.pid):.0f} MB;单个请求 → {s} {d}')
    load(port, 50, 2, 2)
    for cc in CONC:
        rs = [load(port, cc) for _ in range(2)]; st = app.get('/stats')[1]
        if any(r is None for r in rs): print(f'  并发 {cc:>4}:压测程序没有输出'); continue
        [print('      ' + e[:230]) for e in LAST_ERR[:4]]
        print(f'  并发 {cc:>4}:两轮吞吐 {rs[0]["rps"]:>7.0f} / {rs[1]["rps"]:>7.0f} 请求/秒;p50 {rs[0]["p50"]:>6.1f} / {rs[1]["p50"]:>6.1f} ms;p99 {rs[0]["p99"]:>7.1f} / {rs[1]["p99"]:>7.1f} ms;错误 {rs[0]["errs"]} / {rs[1]["errs"]};RSS {rss(app.p.pid):>4.0f} MB;{st}')
    app.stop()
down.terminate()
