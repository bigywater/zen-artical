import sys, os, re, time, json, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from spl import *
tee('x59'); CP = scp('org.springframework.boot:spring-boot-starter-webclient', 'org.springframework.boot:spring-boot-starter-reactor-netty')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.time.Duration; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.client.reactive.ReactorClientHttpConnector; import org.springframework.web.reactive.function.client.*;
import reactor.core.publisher.*; import reactor.netty.http.client.HttpClient; import reactor.netty.resources.ConnectionProvider; import reactor.util.retry.Retry;
@SpringBootApplication
public class Main implements ApplicationRunner {
  final WebClient.Builder wcb; Main(WebClient.Builder b) { wcb = b; }
  static void r(String s) { System.out.println("RES " + s); System.out.flush(); }
  static String chain(Throwable e) { StringBuilder sb = new StringBuilder(); int n = 0; for (Throwable t = e; t != null && n < 4; t = t.getCause(), n++) sb.append(n == 0 ? "" : " ← ").append(t.getClass().getSimpleName()); return sb.toString(); }
  static long now() { return System.currentTimeMillis(); }
  public void run(ApplicationArguments args) throws Exception {
    String base = System.getProperty("target"), sc = System.getProperty("scenario");
    WebClient wc = wcb.baseUrl(base).build();
    switch (sc) {
      case "poolconf" -> { r("HttpResources.get()(WebClient 默认用的共享资源)的 maxConnections() = " + reactor.netty.http.HttpResources.get().maxConnections()); r("ConnectionProvider.builder(\"t\").build().maxConnections() = " + ConnectionProvider.builder("t").build().maxConnections()); }
      case "pool" -> {
        int n = Integer.getInteger("n", 600); int max = Integer.getInteger("max", -1); long acq = Long.getLong("acquireMs", -1);
        WebClient c = wc;
        if (max > 0) { var pb = ConnectionProvider.builder("test").maxConnections(max).pendingAcquireMaxCount(1000); if (acq > 0) pb.pendingAcquireTimeout(Duration.ofMillis(acq)); c = WebClient.builder().baseUrl(base).clientConnector(new ReactorClientHttpConnector(HttpClient.create(pb.build()))).build(); }
        final WebClient cc = c; long t0 = now(); AtomicInteger ok = new AtomicInteger(); Map<String, Integer> errs = new TreeMap<>();
        Flux.range(1, n).delayElements(Duration.ofMillis(Long.getLong("rampMs", 0))).flatMap(i -> cc.get().uri("/slow?ms=" + Long.getLong("slowMs", 300)).retrieve().bodyToMono(String.class).doOnNext(x -> ok.incrementAndGet()).onErrorResume(e -> { synchronized (errs) { errs.merge(chain(e), 1, Integer::sum); } return Mono.empty(); }), n).blockLast();
        r(n + " 个并发请求(服务端各睡 " + Long.getLong("slowMs", 300) + " ms,每 " + Long.getLong("rampMs", 0) + " ms 发起一个):成功 " + ok.get() + ",失败 " + errs + ",总用时 " + (now() - t0) + " ms");
      }
      case "timeout" -> {
        long t0 = now(); try { String s = wc.get().uri("/slow?ms=2000").retrieve().bodyToMono(String.class).block(); r("WebClient 读到 " + s + ",用时 " + (now() - t0) + " ms"); } catch (Exception e) { r("WebClient 异常 " + chain(e) + ",用时 " + (now() - t0) + " ms"); }
        t0 = now(); try { String s = wc.get().uri("/slow?ms=2000").retrieve().bodyToMono(String.class).timeout(Duration.ofMillis(500)).block(); r("Mono.timeout(500ms) 读到 " + s); } catch (Exception e) { r("Mono.timeout(500ms) 异常 " + chain(e) + ",用时 " + (now() - t0) + " ms"); }
        t0 = now(); try { String s = WebClient.builder().baseUrl(base).clientConnector(new ReactorClientHttpConnector(HttpClient.create().responseTimeout(Duration.ofMillis(500)))).build().get().uri("/slow?ms=2000").retrieve().bodyToMono(String.class).block(); r("HttpClient.responseTimeout(500ms) 读到 " + s); } catch (Exception e) { r("HttpClient.responseTimeout(500ms) 异常 " + chain(e) + ",用时 " + (now() - t0) + " ms"); }
      }
      case "connect" -> { long t0 = now(); try { wc.get().uri("http://10.255.255.1:81/x").retrieve().bodyToMono(String.class).block(); } catch (Exception e) { r("连 10.255.255.1:81:异常 " + chain(e) + ",用时 " + (now() - t0) + " ms"); } }
      case "retry" -> {
        long t0 = now();
        try { String s = wc.get().uri("/flaky?key=a").retrieve().bodyToMono(String.class).retryWhen(Retry.backoff(3, Duration.ofMillis(100))).block(); r("Retry.backoff(3, 100ms) 对 /flaky(前 2 次返回 503)→ '" + s + "',用时 " + (now() - t0) + " ms"); } catch (Exception e) { r("Retry.backoff 异常 " + chain(e)); }
        t0 = now(); try { wc.get().uri("/s/404").retrieve().bodyToMono(String.class).retryWhen(Retry.backoff(3, Duration.ofMillis(50))).block(); } catch (Exception e) { r("对 404 也 retry(没有 filter):异常 " + chain(e) + ",message=" + e.getMessage() + ",用时 " + (now() - t0) + " ms"); }
        t0 = now(); try { wc.get().uri("/s/404").retrieve().bodyToMono(String.class).retryWhen(Retry.backoff(3, Duration.ofMillis(50)).filter(e -> e instanceof WebClientResponseException w && w.getStatusCode().is5xxServerError())).block(); } catch (Exception e) { r("retry 加 filter(只重试 5xx),对 404:异常 " + chain(e) + ",用时 " + (now() - t0) + " ms"); }
        t0 = now(); try { wc.get().uri("/s/503").retrieve().bodyToMono(String.class).retryWhen(Retry.backoff(2, Duration.ofMillis(50)).onRetryExhaustedThrow((spec, sig) -> sig.failure())).block(); } catch (Exception e) { r("onRetryExhaustedThrow 还原原异常:" + chain(e)); }
        t0 = now(); try { String s = wc.get().uri("/flaky?key=b").retrieve().bodyToMono(String.class).retryWhen(Retry.fixedDelay(3, Duration.ofMillis(200))).block(); r("Retry.fixedDelay(3, 200ms) → '" + s + "',用时 " + (now() - t0) + " ms"); } catch (Exception e) { r("异常 " + chain(e)); }
      }
      case "post-retry" -> {
        long t0 = now(); try { wc.post().uri("/post-slow").bodyValue("order-1").retrieve().bodyToMono(String.class).timeout(Duration.ofMillis(300)).retry(2).block(); } catch (Exception e) { r("POST /post-slow(服务端先写入再睡 1 秒),timeout(300ms).retry(2):最终 " + chain(e) + ",用时 " + (now() - t0) + " ms"); }
      }
      case "status" -> {
        for (int c : new int[]{200, 404, 500}) { try { String s = wc.get().uri("/s/" + c).retrieve().bodyToMono(String.class).block(); r("retrieve() /s/" + c + " → '" + s + "'"); } catch (WebClientResponseException e) { r("retrieve() /s/" + c + " → 抛 " + e.getClass().getSimpleName() + ",body='" + e.getResponseBodyAsString() + "'"); } }
        var s = wc.get().uri("/s/404").exchangeToMono(rs -> rs.bodyToMono(String.class).map(b -> rs.statusCode().value() + " " + b)).block(); r("exchangeToMono /s/404 → 不抛,'" + s + "'");
        try { wc.get().uri("/s/404").retrieve().onStatus(st -> st.value() == 404, rs -> Mono.error(new IllegalStateException("自定义 404"))).bodyToMono(String.class).block(); } catch (Exception e) { r("onStatus 自定义 → " + chain(e)); }
        String empty = wc.get().uri("/s/204").retrieve().bodyToMono(String.class).defaultIfEmpty("(空)").block(); r("204 → bodyToMono 为空,defaultIfEmpty 得到 " + empty);
      }
    }
  }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE); app.run(a); }
}
'''
b = sbuild('x59', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
class Srv(ThreadingHTTPServer):
    daemon_threads = True; request_queue_size = 1024; conns = 0
    def get_request(self): r = super().get_request(); self.conns += 1; return r
    def handle_error(self, request, client_address): pass
CALLS = {}; FLAKY = {}
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def _send(self, code, body=b'', ctype='text/plain'):
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    def _hit(self, k): CALLS[k] = CALLS.get(k, 0) + 1
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); self._hit(u.path)
        if u.path == '/slow': time.sleep(int(q['ms'][0]) / 1000); self._send(200, b'slow-done')
        elif u.path == '/flaky':
            k = q['key'][0]; FLAKY[k] = FLAKY.get(k, 0) + 1; self._hit('/flaky?' + k)
            self._send(503 if FLAKY[k] <= 2 else 200, b'flaky-fail' if FLAKY[k] <= 2 else b'flaky-ok')
        elif u.path.startswith('/s/'): c = int(u.path[3:]); self._send(c, b'' if c == 204 else f'body-of-{c}'.encode())
        else: self._send(404, b'nf')
    def do_POST(self):
        u = urlparse(self.path); n = int(self.headers.get('Content-Length', 0)); self.rfile.read(n); self._hit(u.path)
        if u.path == '/post-slow': time.sleep(1.0); self._send(200, b'posted')
        else: self._send(404)
srv = Srv(('127.0.0.1', 0), H); PORT = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start(); BASE = f'http://127.0.0.1:{PORT}'
def go(sc, props=None, timeout=90):
    c0 = srv.conns; CALLS.clear(); FLAKY.clear(); pr = {'target': BASE, 'scenario': sc, **(props or {})}
    r = srun(b, 'demo.Main', props=pr, timeout=timeout); lines = res(r)
    if not lines: lines = ['(无输出)' + r['out'][-300:]]
    return lines, srv.conns - c0, dict(CALLS), r
def p(lines): [print('  ' + l) for l in lines]
print('Spring Boot 4.0.8 / Spring WebFlux 7.0.9 / Reactor Netty 1.3.7(spring-boot-starter-webclient,非 Web 模式);被调用的服务是本机 Python http.server(HTTP/1.1,keep-alive),统计连接数与每个路径被调用的次数')
print('== 一:连接池:并发请求数与服务端收到的连接数')
l, c, calls, r = go('poolconf'); p(l)
for n, mx, acq, lab in [(700, -1, -1, '默认连接池'), (20, 5, -1, '自己建连接池 maxConnections=5(等待连接的超时用默认值)'), (20, 5, 200, '自己建连接池 maxConnections=5,pendingAcquireTimeout=200ms')]:
    pr = {'n': n}
    if n == 700: pr.update({'rampMs': 2, 'slowMs': 1500})
    if mx > 0: pr['max'] = mx
    if acq > 0: pr['acquireMs'] = acq
    l, c, calls, r = go('pool', pr); print(f'  {lab}:'); p(l); print(f'      服务端收到 {calls.get("/slow", 0)} 个请求、{c} 个连接')
print('== 二:超时:服务端 2 秒才响应')
l, c, calls, r = go('timeout'); print('  不配置任何超时:'); p(l)
l, c, calls, r = go('timeout', {'spring.http.clients.read-timeout': '500ms'}); print('  spring.http.clients.read-timeout=500ms:'); p(l[:1])
l, c, calls, r = go('connect', {'spring.http.clients.connect-timeout': '300ms'}, timeout=30); print('  spring.http.clients.connect-timeout=300ms:'); p(l)
print('== 三:重试')
l, c, calls, r = go('retry'); p(l); print(f'      服务端统计各路径被调用次数:{ {k: v for k, v in calls.items()} }')
print('== 四:非幂等请求加了重试:服务端已经写入、客户端却超时')
l, c, calls, r = go('post-retry'); p(l); print(f'      服务端 /post-slow 被调用(并执行写入){calls.get("/post-slow", 0)} 次')
print('== 五:状态码、onStatus 与空响应体')
l, c, calls, r = go('status'); p(l)
