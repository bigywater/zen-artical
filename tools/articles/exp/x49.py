import sys, os, re, time, json, threading, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x49'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.io.*; import java.util.*; import java.util.concurrent.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.*; import org.springframework.web.bind.annotation.*; import org.springframework.web.servlet.mvc.method.annotation.*;
@SpringBootApplication @RestController
public class Main {
  static synchronized void ev(String s) { System.out.println("RES EV @" + System.currentTimeMillis() + " " + s); System.out.flush(); }
  static String th() { return Thread.currentThread().getName(); }
  static void nap(long ms) { try { Thread.sleep(ms); } catch (InterruptedException e) { throw new RuntimeException(e); } }
  @GetMapping(value = "/sse", produces = MediaType.TEXT_EVENT_STREAM_VALUE) SseEmitter sse(@RequestHeader(value = "Last-Event-ID", required = false) String last) {
    ev("控制器方法在 " + th() + " 返回 SseEmitter;Last-Event-ID=" + last);
    SseEmitter em = new SseEmitter(60000L);
    new Thread(() -> { try {
      em.send(SseEmitter.event().id("1").name("greet").data("hello\nworld").reconnectTime(3000)); ev("已发送事件 1(线程 " + th() + ")"); nap(300);
      em.send(SseEmitter.event().comment("heartbeat")); ev("已发送注释"); nap(300);
      em.send(SseEmitter.event().id("2").data(Map.of("k", "v")));  ev("已发送事件 2(对象 → JSON)"); nap(300);
      em.complete(); ev("complete()");
    } catch (Exception e) { em.completeWithError(e); } }, "producer").start();
    return em;
  }
  @GetMapping("/stream-body") ResponseEntity<StreamingResponseBody> body() {
    ev("控制器方法在 " + th());
    return ResponseEntity.ok().contentType(MediaType.TEXT_PLAIN).body(out -> { ev("StreamingResponseBody 在 " + th() + " 开始写"); for (int i = 1; i <= 3; i++) { out.write(("chunk-" + i + "\n").getBytes()); out.flush(); ev("写出 chunk-" + i + " 并 flush"); nap(300); } });
  }
  @GetMapping("/stream-body-noflush") ResponseEntity<StreamingResponseBody> bodyNoFlush() {
    return ResponseEntity.ok().contentType(MediaType.TEXT_PLAIN).body(out -> { for (int i = 1; i <= 3; i++) { out.write(("chunk-" + i + "\n").getBytes()); ev("写出 chunk-" + i + "(没有 flush)"); nap(300); } });
  }
  @GetMapping("/raw") void raw(jakarta.servlet.http.HttpServletResponse r) throws IOException { r.setContentType("text/plain"); var o = r.getOutputStream(); for (int i = 1; i <= 3; i++) { o.write(("chunk-" + i + "\n").getBytes()); o.flush(); ev("raw 写出 chunk-" + i + " 并 flush"); nap(300); } }
  @GetMapping(value = "/direct", produces = "text/plain") StreamingResponseBody direct() { return out -> { for (int i = 1; i <= 3; i++) { out.write(("chunk-" + i + "\n").getBytes()); out.flush(); ev("direct 写出 chunk-" + i + " 并 flush"); nap(300); } }; }
  @GetMapping("/stream-body-big") ResponseEntity<StreamingResponseBody> big() { return ResponseEntity.ok().contentType(MediaType.TEXT_PLAIN).body(out -> { for (int i = 1; i <= 3; i++) { out.write(("chunk-" + i + "\n" + "x".repeat(20000) + "\n").getBytes()); out.flush(); ev("big 写出 chunk-" + i + "(20 KB)并 flush"); nap(300); } }); }
  @GetMapping("/plain-string") String plain() { nap(900); return "chunk-1\nchunk-2\nchunk-3\n"; }
  @GetMapping(value = "/sse-forever", produces = MediaType.TEXT_EVENT_STREAM_VALUE) SseEmitter forever() {
    SseEmitter em = new SseEmitter(60000L);
    em.onCompletion(() -> ev("onCompletion 回调(线程 " + th() + ")")); em.onError(e -> ev("onError 回调:" + e.getClass().getSimpleName() + "(线程 " + th() + ")")); em.onTimeout(() -> ev("onTimeout 回调"));
    new Thread(() -> { int i = 0; try { while (i < 40) { i++; em.send(SseEmitter.event().id("" + i).data("tick-" + i)); ev("发送 tick-" + i + " 成功"); nap(200); } ev("40 个都发完了,循环结束"); } catch (Exception e) { ev("发送 tick-" + i + " 失败:" + e.getClass().getSimpleName()); } }, "producer-forever").start();
    return em;
  }
  @GetMapping(value = "/sse-timeout", produces = MediaType.TEXT_EVENT_STREAM_VALUE) SseEmitter timeout() {
    SseEmitter em = new SseEmitter(1000L); em.onTimeout(() -> ev("onTimeout 回调(线程 " + th() + ")")); em.onCompletion(() -> ev("onCompletion 回调"));
    try { em.send(SseEmitter.event().data("only-one")); } catch (IOException e) { }
    return em;
  }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x49', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def parse_ev(app, n0, t0ms):
    out = []
    for l in app.log().splitlines()[n0:]:
        m = re.match(r'RES EV @(\d+) (.*)', l)
        if m: out.append((int(m.group(1)) - t0ms, m.group(2)))
    return out
def stream(app, path, headers=None, stop_after=None, maxsec=8, show_headers=('Content-Type', 'Transfer-Encoding', 'Cache-Control', 'Content-Encoding', 'Content-Length')):
    """流式读响应:每行带上到达时间(相对请求发出)。返回(到达的行, 服务端事件)"""
    n0 = len(app.log().splitlines()); t0 = time.time(); t0ms = int(t0 * 1000)
    c = http.client.HTTPConnection('127.0.0.1', int(app.props['server.port']), timeout=maxsec); c.request('GET', path, headers=headers or {}); r = c.getresponse(); th = (time.time() - t0) * 1000
    hd = {k: r.getheader(k) for k in show_headers if r.getheader(k)}; rows = [('响应头到达', round(th), f'{r.status} {hd}')]
    seen = 0
    try:
        while True:
            ln = r.fp.readline() if False else r.readline()
            if not ln: rows.append((round((time.time() - t0) * 1000), '(流结束)', '')); break
            ln = ln.decode('utf-8', 'replace').rstrip('\r\n'); rows.append((round((time.time() - t0) * 1000), ln, ''))
            if ln.startswith('data:') or ln.startswith('chunk'): seen += 1
            if stop_after and seen >= stop_after: rows.append((round((time.time() - t0) * 1000), f'(客户端读到第 {seen} 个数据后主动关闭连接)', '')); c.close(); break
    except Exception as e: rows.append((round((time.time() - t0) * 1000), f'(读取异常 {type(e).__name__})', ''))
    return rows, t0ms, n0
def pr(rows):
    for t, a, bb in rows:
        if len(a) > 60: a = a[:20] + f'…(共 {len(a)} 个字符)'
        print(f'    {t if isinstance(t, str) else str(t) + " ms":>8}  {a} {bb}'.rstrip())
def run(props, f, title):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}'); f(app); app.stop()
print('Spring Boot 4.0.8 / Spring MVC 7.0.9(Tomcat 11.0.24)。客户端是 Python http.client 逐行读,时间是相对请求发出的毫秒')
def one(app):
    rows, t0ms, n0 = stream(app, '/sse', headers={'Last-Event-ID': '41'}); time.sleep(0.2)
    print('  客户端看到的(行 = 一行文本,空行是事件分隔):'); pr(rows); print('  服务端事件:'); [print(f'    {t:>5} ms  {m}') for t, m in parse_ev(app, n0, t0ms)]
run({}, one, '一:SseEmitter:线格式、响应头、什么时候到达、哪个线程在发')
def two(app):
    for p, lab in [('/raw', '对照:Controller 里直接写 HttpServletResponse 并 flush'), ('/direct', '直接返回 StreamingResponseBody(不包 ResponseEntity),每块 flush'), ('/stream-body-big', 'ResponseEntity<StreamingResponseBody>,每块 20 KB 并 flush'), ('/stream-body', 'ResponseEntity<StreamingResponseBody>,每块 flush'), ('/stream-body-noflush', 'StreamingResponseBody,不 flush'), ('/plain-string', '对照:普通 String 返回(处理 900ms 后一次性返回)')]:
        rows, t0ms, n0 = stream(app, p); time.sleep(0.2); print(f'  {lab}:'); pr(rows)
        if p != '/plain-string' and True: [print(f'    (服务端) {t:>5} ms  {m}') for t, m in parse_ev(app, n0, t0ms)]
run({}, two, '二:StreamingResponseBody 与普通返回:第一块什么时候到客户端')
def three(app):
    rows, t0ms, n0 = stream(app, '/sse-forever', stop_after=2); time.sleep(1.5)
    print('  客户端:'); pr(rows); print('  服务端(客户端关闭连接后继续观察):'); [print(f'    {t:>5} ms  {m}') for t, m in parse_ev(app, n0, t0ms)]
run({}, three, '三:客户端中途断开连接,服务端什么时候发现')
def four(app):
    rows, t0ms, n0 = stream(app, '/sse-timeout'); time.sleep(0.2)
    print('  客户端:'); pr(rows); print('  服务端:'); [print(f'    {t:>5} ms  {m}') for t, m in parse_ev(app, n0, t0ms)]
run({}, four, '四:SseEmitter(1000L) 的超时:流什么时候结束,回调是什么')
def five(app):
    for ae, lab in [(None, '不带 Accept-Encoding'), ('gzip', 'Accept-Encoding: gzip')]:
        n0 = len(app.log().splitlines()); t0 = time.time(); c = http.client.HTTPConnection('127.0.0.1', int(app.props['server.port']), timeout=10)
        c.request('GET', '/sse', headers={'Accept-Encoding': ae} if ae else {}); r = c.getresponse(); rows = [f'响应头到达 {round((time.time() - t0) * 1000)} ms,Content-Encoding={r.getheader("Content-Encoding")}']
        while True:
            d = r.read1(65536)
            if not d: rows.append(f'{round((time.time() - t0) * 1000)} ms 流结束'); break
            rows.append(f'{round((time.time() - t0) * 1000)} ms 收到 {len(d)} 字节')
        c.close(); print(f'  {lab}:'); [print('      ' + x) for x in rows]
run({'server.compression.enabled': 'true', 'server.compression.mime-types': 'text/event-stream', 'server.compression.min-response-size': '1'}, five, '五:server.compression.enabled=true、mime-types 加上 text/event-stream:客户端按到达的数据块读')
