import sys, os, re, time, json, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from spl import *
tee('x52'); CP = scp('org.springframework.boot:spring-boot-starter-restclient')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*; import java.util.concurrent.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.restclient.RestTemplateBuilder; import org.springframework.boot.http.client.ClientHttpRequestFactoryBuilder;
import org.springframework.http.*; import org.springframework.web.client.*; import org.springframework.web.client.support.RestClientAdapter; import org.springframework.web.bind.annotation.*; import org.springframework.web.service.annotation.*; import org.springframework.web.service.invoker.HttpServiceProxyFactory;
@SpringBootApplication
public class Main implements ApplicationRunner {
  final RestClient.Builder rcb; final RestTemplateBuilder rtb; Main(RestClient.Builder b, RestTemplateBuilder t) { rcb = b; rtb = t; }
  static void r(String s) { System.out.println("RES " + s); System.out.flush(); }
  static String chain(Throwable e) { StringBuilder sb = new StringBuilder(); int n = 0; for (Throwable t = e; t != null && n < 4; t = t.getCause(), n++) sb.append(n == 0 ? "" : " ← ").append(t.getClass().getSimpleName()); return sb.toString(); }
  interface Api {
    @GetExchange("/echo") String echo(@RequestParam String x, @RequestHeader("X-Test") String h);
    @GetExchange("/s/{code}") String status(@PathVariable int code);
    @GetExchange("/s/{code}") ResponseEntity<Void> statusEntity(@PathVariable int code);
  }
  public void run(ApplicationArguments args) throws Exception {
    String base = System.getProperty("target"), sc = System.getProperty("scenario"), kind = System.getProperty("kind", "rc-boot");
    RestClient bootRc = rcb.baseUrl(base).build();
    switch (sc) {
      case "factory" -> {
        r("ClientHttpRequestFactoryBuilder.detect() 建出的工厂 = " + ClientHttpRequestFactoryBuilder.detect().build().getClass().getSimpleName());
        r("RestTemplateBuilder.build() 的工厂 = " + rtb.build().getRequestFactory().getClass().getSimpleName());
        r("new RestTemplate() 的工厂 = " + new RestTemplate().getRequestFactory().getClass().getSimpleName());
      }
      case "hdr" -> {
        for (String k : List.of("rc-boot", "rc-create", "rt-boot", "rt-new")) {
          String json = switch (k) { case "rc-boot" -> bootRc.get().uri("/headers").retrieve().body(String.class); case "rc-create" -> RestClient.create(base).get().uri("/headers").retrieve().body(String.class);
            case "rt-boot" -> rtb.build().getForObject(base + "/headers", String.class); default -> new RestTemplate().getForObject(base + "/headers", String.class); };
          r(k + " 服务端看到的请求头 = " + json);
        }
      }
      case "seq", "par" -> {
        int n = 20; long t0 = System.currentTimeMillis(); String path = sc.equals("seq") ? "/fast" : "/slow?ms=300";
        java.util.function.Supplier<String> call = switch (kind) {
          case "rc-boot" -> () -> bootRc.get().uri(path).retrieve().body(String.class);
          case "rc-create" -> { RestClient c = RestClient.create(base); yield () -> c.get().uri(path).retrieve().body(String.class); }
          case "rt-boot" -> { RestTemplate t = rtb.build(); yield () -> t.getForObject(base + path, String.class); }
          default -> { RestTemplate t = new RestTemplate(); yield () -> t.getForObject(base + path, String.class); }
        };
        if (sc.equals("seq")) { for (int i = 0; i < n; i++) call.get(); }
        else { var ex = Executors.newFixedThreadPool(n); var fs = new ArrayList<Future<String>>(); for (int i = 0; i < n; i++) fs.add(ex.submit(call::get)); for (var f : fs) f.get(); ex.shutdown(); }
        r(kind + " " + sc + " " + n + " 次完成,用时 " + (System.currentTimeMillis() - t0) + " ms");
      }
      case "timeout" -> {
        long t0 = System.currentTimeMillis();
        try { String s = bootRc.get().uri("/slow?ms=3000").retrieve().body(String.class); r("RestClient 读到 " + s + ",用时 " + (System.currentTimeMillis() - t0) + " ms"); }
        catch (Exception e) { r("RestClient 异常 " + chain(e) + ",用时 " + (System.currentTimeMillis() - t0) + " ms"); }
        t0 = System.currentTimeMillis();
        try { String s = rtb.build().getForObject(base + "/slow?ms=3000", String.class); r("RestTemplate(Boot 构建)读到 " + s + ",用时 " + (System.currentTimeMillis() - t0) + " ms"); }
        catch (Exception e) { r("RestTemplate(Boot 构建)异常 " + chain(e) + ",用时 " + (System.currentTimeMillis() - t0) + " ms"); }
        t0 = System.currentTimeMillis();
        try { String s = new RestTemplate().getForObject(base + "/slow?ms=3000", String.class); r("new RestTemplate() 读到 " + s + ",用时 " + (System.currentTimeMillis() - t0) + " ms"); }
        catch (Exception e) { r("new RestTemplate() 异常 " + chain(e) + ",用时 " + (System.currentTimeMillis() - t0) + " ms"); }
      }
      case "connect" -> {
        long t0 = System.currentTimeMillis();
        try { rcb.build().get().uri("http://10.255.255.1:81/x").retrieve().body(String.class); r("RestClient 连不可达地址:竟然成功"); }
        catch (Exception e) { r("RestClient 连 10.255.255.1:81 异常 " + chain(e) + ",用时 " + (System.currentTimeMillis() - t0) + " ms"); }
      }
      case "status" -> {
        for (int code : new int[]{200, 204, 404, 500}) {
          try { String s = bootRc.get().uri("/s/" + code).retrieve().body(String.class); r("retrieve().body(String) /s/" + code + " → 返回 " + (s == null ? "null" : "'" + s + "'")); }
          catch (RestClientResponseException e) { r("retrieve().body(String) /s/" + code + " → 抛 " + e.getClass().getSimpleName() + ",状态 " + e.getStatusCode().value() + ",body='" + e.getResponseBodyAsString() + "'"); }
        }
        var ent = bootRc.get().uri("/s/404").exchange((rq, rs) -> rs.getStatusCode().value() + " " + new String(rs.getBody().readAllBytes())); r("exchange() /s/404 → 不抛,拿到 '" + ent + "'");
        try { bootRc.get().uri("/s/404").retrieve().onStatus(HttpStatusCode::is4xxClientError, (rq, rs) -> { throw new IllegalStateException("自定义 4xx 处理:" + rs.getStatusCode()); }).body(String.class); }
        catch (Exception e) { r("onStatus 自定义 /s/404 → 抛 " + e.getClass().getSimpleName() + ": " + e.getMessage()); }
        var be = bootRc.get().uri("/s/500").retrieve().onStatus(s -> s.value() == 500, (rq, rs) -> {}).toBodilessEntity(); r("onStatus 吞掉 500 → toBodilessEntity 状态 " + be.getStatusCode().value());
        try { rtb.build().getForObject(base + "/s/404", String.class); } catch (Exception e) { r("RestTemplate /s/404 → 抛 " + e.getClass().getSimpleName()); }
      }
      case "iface" -> {
        Api api = HttpServiceProxyFactory.builderFor(RestClientAdapter.create(bootRc)).build().createClient(Api.class);
        r("api.echo(x=a b, h=H1) → " + api.echo("a b", "H1")); r("api.status(200) → " + api.status(200));
        r("api.statusEntity(404) 通过 ResponseEntity 接 → 仍然会抛?");
        try { r("返回 " + api.statusEntity(404).getStatusCode()); } catch (Exception e) { r("api.statusEntity(404) 抛 " + e.getClass().getSimpleName()); }
        try { api.status(500); } catch (Exception e) { r("api.status(500) 抛 " + e.getClass().getSimpleName() + " 状态 " + ((RestClientResponseException) e).getStatusCode().value()); }
      }
      case "redirect" -> {
        try { var e = bootRc.get().uri("/redirect").retrieve().toEntity(String.class); r("RestClient GET /redirect → 状态 " + e.getStatusCode().value() + " body='" + e.getBody() + "'"); } catch (Exception e) { r("RestClient GET /redirect → 抛 " + chain(e)); }
        try { String s = rtb.build().getForObject(base + "/redirect", String.class); r("RestTemplate(Boot 构建)GET /redirect → '" + s + "'"); } catch (Exception e) { r("RestTemplate(Boot 构建) /redirect → 抛 " + chain(e)); }
        try { String s = new RestTemplate().getForObject(base + "/redirect", String.class); r("new RestTemplate() GET /redirect → '" + s + "'"); } catch (Exception e) { r("new RestTemplate() /redirect → 抛 " + chain(e)); }
      }
    }
  }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE); app.run(a); }
}
'''
b = sbuild('x52', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
MAIN2 = r"""
package demo;
import java.util.*; import java.util.concurrent.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.http.client.ClientHttpRequestFactoryBuilder;
import org.springframework.http.client.HttpComponentsClientHttpRequestFactory; import org.springframework.web.client.*;
import org.apache.hc.client5.http.impl.classic.*; import org.apache.hc.client5.http.impl.io.*;
@SpringBootApplication
public class Main2 implements ApplicationRunner {
  final RestClient.Builder rcb; Main2(RestClient.Builder b) { rcb = b; }
  static void r(String s) { System.out.println("RES " + s); System.out.flush(); }
  static String chain(Throwable e) { StringBuilder sb = new StringBuilder(); int n = 0; for (Throwable t = e; t != null && n < 4; t = t.getCause(), n++) sb.append(n == 0 ? "" : " ← ").append(t.getClass().getSimpleName()); return sb.toString(); }
  static void burst(RestClient c, int n, String path, String label) throws Exception {
    long t0 = System.currentTimeMillis(); var ex = Executors.newFixedThreadPool(n); var fs = new ArrayList<Future<String>>(); for (int i = 0; i < n; i++) fs.add(ex.submit(() -> { try { return c.get().uri(path).retrieve().body(String.class); } catch (Exception e) { return "ERR " + chain(e); } }));
    int ok = 0; Map<String, Integer> errs = new TreeMap<>(); for (var f : fs) { String v = f.get(); if (v.startsWith("ERR")) errs.merge(v, 1, Integer::sum); else ok++; } ex.shutdown();
    r(label + ":" + n + " 个并发请求,成功 " + ok + ",失败 " + errs + ",总用时 " + (System.currentTimeMillis() - t0) + " ms");
  }
  public void run(ApplicationArguments args) throws Exception {
    String base = System.getProperty("target"), sc = System.getProperty("scenario");
    switch (sc) {
      case "detect" -> { r("detect() 建出的工厂 = " + ClientHttpRequestFactoryBuilder.detect().build().getClass().getSimpleName()); burst(rcb.baseUrl(base).build(), 30, "/slow?ms=300", "Boot 的 RestClient.Builder(默认)"); }
      case "custom" -> {
        var cm = PoolingHttpClientConnectionManagerBuilder.create().setMaxConnTotal(100).setMaxConnPerRoute(50).build();
        var f = new HttpComponentsClientHttpRequestFactory(HttpClients.custom().setConnectionManager(cm).build());
        burst(RestClient.builder().requestFactory(f).baseUrl(base).build(), 30, "/slow?ms=300", "自己配的连接池(总 100、每个路由 50)");
      }
      case "tiny" -> {
        var cm = PoolingHttpClientConnectionManagerBuilder.create().setMaxConnTotal(2).setMaxConnPerRoute(2).build();
        var f = new HttpComponentsClientHttpRequestFactory(HttpClients.custom().setConnectionManager(cm).build()); f.setConnectionRequestTimeout(java.time.Duration.ofMillis(200));
        burst(RestClient.builder().requestFactory(f).baseUrl(base).build(), 6, "/slow?ms=600", "连接池只有 2 个连接、等连接最多 200 ms");
      }
    }
  }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main2.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE); app.run(a); }
}
"""
CP2 = scp('org.springframework.boot:spring-boot-starter-restclient', 'org.apache.httpcomponents.client5:httpclient5')
b2 = sbuild('x52b', {'src/demo/Main2.java': MAIN2, 'logback.xml': LOG}, CP2)
if b2['crc'] != 0: print(b2['cout']); sys.exit()
class Srv(ThreadingHTTPServer):
    daemon_threads = True; request_queue_size = 256; conns = 0; reqs = 0
    def get_request(self): r = super().get_request(); self.conns += 1; return r
    def handle_error(self, request, client_address): pass
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def _send(self, code, body=b'', ctype='text/plain', extra=None):
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        self.server.reqs += 1; u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == '/fast': self._send(200, b'ok')
        elif u.path == '/slow': time.sleep(int(q['ms'][0]) / 1000); self._send(200, b'slow-done')
        elif u.path.startswith('/s/'):
            c = int(u.path[3:]); self._send(c, b'' if c == 204 else f'body-of-{c}'.encode())
        elif u.path == '/redirect': self._send(302, b'', extra={'Location': '/fast'})
        elif u.path == '/echo': self._send(200, f'x={q.get("x", [""])[0]},X-Test={self.headers.get("X-Test")}'.encode())
        elif u.path == '/headers': self._send(200, json.dumps({k: self.headers.get(k) for k in ['User-Agent', 'Accept', 'Connection', 'Upgrade', 'HTTP2-Settings', 'Accept-Encoding'] if self.headers.get(k)}, ensure_ascii=False).encode(), 'application/json')
        else: self._send(404, b'nf')
srv = Srv(('127.0.0.1', 0), H); PORT = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{PORT}'
def go(sc, kind=None, props=None, timeout=60, bb=None, main='demo.Main'):
    c0, q0 = srv.conns, srv.reqs; pr = {'target': BASE, 'scenario': sc, **({'kind': kind} if kind else {}), **(props or {})}
    r = srun(bb or b, main, props=pr, timeout=timeout); lines = res(r)
    return lines, srv.conns - c0, srv.reqs - q0, r
def p(lines): [print('  ' + l) for l in lines]
print('Spring Boot 4.0.8 / Spring Framework 7.0.9(spring-boot-starter-restclient,JDK 21);被调用的服务是本机的 Python http.server(HTTP/1.1,支持 keep-alive),它统计收到的 TCP 连接数')
print('== 一:Boot 给 RestClient / RestTemplate 选了哪种底层 HTTP 客户端')
l, c, q, r = go('factory'); p(l)
l, c, q, r = go('factory', props={'spring.http.clients.imperative.factory': 'simple'}); print('  spring.http.clients.imperative.factory=simple 时:'); p(l)
l, c, q, r = go('hdr', props={'spring.http.clients.imperative.factory': 'simple'}); print('  spring.http.clients.imperative.factory=simple 时 RestClient 的请求头:'); p(l[:1])
print('== 二:服务端看到的请求头(JDK 客户端和 HttpURLConnection 的差别)')
l, c, q, r = go('hdr'); p(l)
print('== 三:连接复用:20 次请求,服务端一共收到多少个 TCP 连接')
for kind, lab in [('rc-boot', 'Boot 的 RestClient.Builder'), ('rc-create', 'RestClient.create()'), ('rt-boot', 'RestTemplateBuilder'), ('rt-new', 'new RestTemplate()')]:
    l, c, q, r = go('seq', kind); print(f'  顺序 20 次 {lab}:服务端收到 {q} 个请求、{c} 个新连接'); 
    l, c, q, r = go('par', kind); print(f'  并发 20 个线程(每个请求在服务端睡 300 ms){lab}:服务端收到 {q} 个请求、{c} 个新连接;{l[-1] if l else r["out"][-200:]}')
print('== 四:读超时:服务端 3 秒才响应时,默认配置和设了 read-timeout 之后')
l, c, q, r = go('timeout'); print('  不配置任何超时:'); p(l)
l, c, q, r = go('timeout', props={'spring.http.client.read-timeout': '500ms'}); print('  spring.http.client.read-timeout=500ms(旧的属性名,没有 s):'); p(l)
l, c, q, r = go('timeout', props={'spring.http.clients.read-timeout': '500ms'}); print('  spring.http.clients.read-timeout=500ms:'); p(l)
print('== 五:连接超时:连接一个不可达的地址 10.255.255.1:81')
l, c, q, r = go('connect', props={'spring.http.clients.connect-timeout': '300ms'}); print('  spring.http.clients.connect-timeout=300ms:'); p(l)
l, c, q, r = go('connect', timeout=20); print('  不配置连接超时(最多等 20 秒):'); p(l if l else ['20 秒内没有返回,测试程序被强行终止(rc=%s)' % r['rc']])
print('== 六:状态码与异常:4xx / 5xx 默认怎么处理')
l, c, q, r = go('status'); p(l)
print('== 七:HTTP Interface(@HttpExchange):参数绑定与异常')
l, c, q, r = go('iface'); p(l)
print('== 八:重定向')
l, c, q, r = go('redirect'); print('  默认:'); p(l)
l, c, q, r = go('redirect', props={'spring.http.clients.redirects': 'dont-follow'}); print('  spring.http.clients.redirects=dont-follow:'); p(l)

print('== 九:换成 Apache HttpClient 5(类路径上有 httpclient5):连接池的上限')
for sc in ['detect', 'custom', 'tiny']:
    l, c, q, r = go(sc, bb=b2, main='demo.Main2'); p(l); print(f'      服务端收到 {q} 个请求、{c} 个新连接')
