import sys, os, re, time, json, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x48'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*; import java.util.concurrent.*;
import jakarta.servlet.http.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.annotation.Bean;
import org.springframework.web.bind.annotation.*; import org.springframework.web.context.request.async.*; import org.springframework.web.servlet.*; import org.springframework.web.servlet.config.annotation.*;
@SpringBootApplication @RestController
public class Main {
  static synchronized void ev(String s) { System.out.println("RES EV " + s); System.out.flush(); }
  static String th() { return Thread.currentThread().getName(); }
  static final ScheduledExecutorService TIMER = Executors.newScheduledThreadPool(1, r -> { Thread t = new Thread(r, "my-timer"); t.setDaemon(true); return t; });
  static final Map<String, DeferredResult<String>> PENDING = new ConcurrentHashMap<>();
  @GetMapping("/sync") String sync() throws Exception { ev("  /sync 方法在 " + th()); Thread.sleep(300); return "sync-done"; }
  @GetMapping("/callable") Callable<String> callable() { ev("  /callable 控制器方法在 " + th() + ",返回 Callable"); return () -> { ev("  /callable 的 Callable 在 " + th() + " 执行"); Thread.sleep(300); return "callable-done"; }; }
  @GetMapping("/deferred") DeferredResult<String> deferred(@RequestParam(defaultValue = "d1") String id) { ev("  /deferred 控制器方法在 " + th() + ",返回 DeferredResult(id=" + id + ")"); var d = new DeferredResult<String>(); PENDING.put(id, d); return d; }
  @GetMapping("/complete") String complete(@RequestParam(defaultValue = "d1") String id, @RequestParam(defaultValue = "ok") String v) { var d = PENDING.remove(id); ev("  /complete 在 " + th() + " 完成 DeferredResult(" + id + ") → " + (d == null ? "找不到" : String.valueOf(d.setResult("deferred-" + v)))); return "completed"; }
  @GetMapping("/deferred-timeout") DeferredResult<String> dto(@RequestParam(defaultValue = "500") long ms) { var d = new DeferredResult<String>(ms, "timeout-fallback"); d.onTimeout(() -> ev("  onTimeout 回调在 " + th())); d.onCompletion(() -> ev("  onCompletion 回调在 " + th())); return d; }
  @GetMapping("/dt") DeferredResult<String> dt(@RequestParam long ms) { return new DeferredResult<String>(ms, "fallback"); }
  @GetMapping("/deferred-timeout-default") DeferredResult<String> dto2() { var d = new DeferredResult<String>(400L); d.onTimeout(() -> ev("  onTimeout 回调在 " + th())); return d; }
  @GetMapping("/callable-timeout") Callable<String> cto() { return () -> { try { Thread.sleep(3000); } catch (InterruptedException e) { ev("  慢 Callable 的 sleep 被中断了(InterruptedException),线程 " + th()); throw e; } ev("  慢 Callable 做完了,线程 " + th()); return "too-late"; }; }
  @GetMapping("/callable-ex") Callable<String> cex() { return () -> { throw new IllegalStateException("callable 里抛的"); }; }
  @GetMapping("/deferred-ex") DeferredResult<String> dex() { var d = new DeferredResult<String>(); TIMER.schedule(() -> d.setErrorResult(new IllegalArgumentException("setErrorResult 设的")), 100, TimeUnit.MILLISECONDS); return d; }
  @GetMapping("/from-timer") DeferredResult<String> fromTimer() { var d = new DeferredResult<String>(); ev("  /from-timer 控制器方法在 " + th()); TIMER.schedule(() -> { ev("  my-timer 线程里 setResult"); d.setResult("from-timer-done"); }, 200, TimeUnit.MILLISECONDS); return d; }
  @GetMapping("/inflight") String inflight() { return "inflight"; }
  @GetMapping("/block-sleep") Callable<String> blockSleep(@RequestParam long ms) { return () -> { ev("BS " + th()); Thread.sleep(ms); return "slept-" + ms; }; }
  @ExceptionHandler(Exception.class) org.springframework.http.ResponseEntity<String> ex(Exception e) { ev("  @ExceptionHandler 收到 " + e.getClass().getSimpleName() + " 在 " + th()); return org.springframework.http.ResponseEntity.status(500).body("[" + e.getClass().getSimpleName() + "] " + e.getMessage()); }
  static class Ic implements AsyncHandlerInterceptor {
    public boolean preHandle(HttpServletRequest q, HttpServletResponse s, Object h) { if (q.getRequestURI().equals("/probe")) return true; ev("  拦截器 preHandle [" + q.getDispatcherType() + "] " + q.getRequestURI() + " 在 " + th()); return true; }
    public void postHandle(HttpServletRequest q, HttpServletResponse s, Object h, ModelAndView m) { ev("  拦截器 postHandle [" + q.getDispatcherType() + "]"); }
    public void afterCompletion(HttpServletRequest q, HttpServletResponse s, Object h, Exception e) { ev("  拦截器 afterCompletion [" + q.getDispatcherType() + "]"); }
    public void afterConcurrentHandlingStarted(HttpServletRequest q, HttpServletResponse s, Object h) { ev("  拦截器 afterConcurrentHandlingStarted(原线程释放前)"); } }
  @Bean WebMvcConfigurer cfg() { return new WebMvcConfigurer() { public void addInterceptors(InterceptorRegistry r) { r.addInterceptor(new Ic()).addPathPatterns("/sync", "/callable", "/deferred", "/from-timer", "/callable-ex", "/deferred-ex"); } }; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x48', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def evs(app, n0): return [l[7:] for l in app.log().splitlines()[n0:] if l.startswith('RES EV ')]
def show(app, p, lab=None):
    n0 = len(app.log().splitlines()); t0 = time.time(); s, d, h = app.get(p, timeout=20); dt = (time.time() - t0) * 1000; time.sleep(0.15)
    print(f'  GET {p} → {s} {re.sub(chr(34)+"timestamp"+chr(34)+":"+chr(34)+"[^"+chr(34)+"]*"+chr(34)+",?", "", d.strip())[:100]} ({dt:.0f} ms)'); [print('   ' + l) for l in evs(app, n0)]
def run(props, f, title):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}'); f(app); app.stop()
print('Spring Boot 4.0.8 / Spring MVC 7.0.9(Tomcat 11.0.24)。AsyncHandlerInterceptor 打印 DispatcherType;每个请求用线程名区分')
def one(app):
    show(app, '/sync'); show(app, '/callable')
run({}, one, '一:同步 vs Callable:哪个线程做事,拦截器被调用几次,dispatcher 类型')
def two(app):
    n0 = len(app.log().splitlines()); res = {}
    t = threading.Thread(target=lambda: res.update(r=app.get('/deferred?id=d1', timeout=20))); t0 = time.time(); t.start(); time.sleep(0.5)
    print('  请求 /deferred 发出 0.5 秒后,客户端还在等响应:', t.is_alive()); app.get('/complete?id=d1&v=ok'); t.join(); print(f'  /deferred 最终 → {res["r"][0]} {res["r"][1]} (总耗时 {(time.time() - t0) * 1000:.0f} ms)'); time.sleep(0.15)
    [print('   ' + l) for l in evs(app, n0)]
    show(app, '/from-timer')
run({}, two, '二:DeferredResult:由另一个请求 / 另一个线程完成')
def three(app):
    show(app, '/deferred-timeout?ms=500'); show(app, '/deferred-timeout-default'); show(app, '/callable-timeout'); time.sleep(3.2); print('  (等 3.2 秒再看慢 Callable 的下场)'); [print('   ' + l) for l in evs(app, 0) if '慢 Callable' in l]
run({'spring.mvc.async.request-timeout': '1000'}, three, '三:全局超时 spring.mvc.async.request-timeout=1000ms;DeferredResult 自己指定的超时 500ms / 400ms;慢 Callable(3000ms)')
def three2(app):
    for ms in [100, 300, 700]:
        out = []
        for ph in [0, 0.13, 0.31, 0.47, 0.66, 0.85]:
            time.sleep(ph); t0 = time.time(); s, d, h = app.get(f'/dt?ms={ms}', timeout=20); out.append(round((time.time() - t0) * 1000))
        print(f'  DeferredResult 超时 {ms} ms,6 次(每次开始前错开一点时间)实际等了(ms):{out}')
run({'spring.mvc.async.request-timeout': '30000'}, three2, '三补:DeferredResult 的超时到底有多准(全局超时设成 30 秒,排除干扰)')
def four(app):
    show(app, '/callable-ex'); show(app, '/deferred-ex')
run({}, four, '四:异步里的异常:Callable 抛出 / DeferredResult.setErrorResult')
def five(app):
    # 并发:Tomcat 只留 2 个线程,10 个慢请求 —— 同步 vs Callable
    import concurrent.futures as cf
    def burst(path, n):
        t0 = time.time()
        with cf.ThreadPoolExecutor(n) as ex: futs = [ex.submit(app.get, path, timeout=60) for _ in range(n)]; rs = [f.result() for f in futs]
        return time.time() - t0, [r[0] for r in rs]
    def probe_during(path, n):
        res = {}
        th_ = threading.Thread(target=lambda: res.update(b=burst(path, n))); th_.start(); time.sleep(0.4)
        t0 = time.time(); s, d, h = app.get('/inflight', timeout=60); pt = (time.time() - t0) * 1000; th_.join(); return pt, res['b']
    pt, (tt, st) = probe_during('/sync', 10); print(f'  10 个并发 /sync(每个 300ms):总耗时 {tt:.2f} s,状态码都是 200:{set(st) == {200}};期间另一个 /inflight 等了 {pt:.0f} ms')
    pt, (tt, st) = probe_during('/block-sleep?ms=300', 10); names = {l.split()[-1] for l in app.log().splitlines() if l.startswith('RES EV BS ')}; print(f'  Callable 实际执行在 {len(names)} 个不同的线程上:{sorted(names)}'); print(f'  10 个并发 /block-sleep(Callable,每个 300ms):总耗时 {tt:.2f} s,状态码都是 200:{set(st) == {200}};期间另一个 /inflight 等了 {pt:.0f} ms')
run({'server.tomcat.threads.max': '2', 'server.tomcat.threads.min-spare': '2', 'server.tomcat.accept-count': '100'}, five, '五:Tomcat 只有 2 个线程时,10 个并发慢请求:同步 vs Callable')
