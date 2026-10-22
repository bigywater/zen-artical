import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x53'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '''<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG [%thread] traceId=[%X{traceId}] %logger{0}: %msg%n</pattern></encoder></appender>
<root level="OFF"/><logger name="demo" level="INFO"><appender-ref ref="C"/></logger><logger name="org.springframework.web.filter.CommonsRequestLoggingFilter" level="DEBUG"><appender-ref ref="C"/></logger></configuration>'''
MAIN = r'''
package demo;
import java.io.IOException; import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.AtomicInteger;
import jakarta.servlet.*; import jakarta.servlet.http.*;
import org.slf4j.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.autoconfigure.condition.*; import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.*; import org.springframework.core.task.TaskDecorator; import org.springframework.scheduling.annotation.*; import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.stereotype.Service; import org.springframework.web.bind.annotation.*; import org.springframework.web.filter.*; import org.springframework.web.servlet.*; import org.springframework.web.servlet.config.annotation.*;
@SpringBootApplication @EnableAsync @RestController
public class Main {
  static final Logger log = LoggerFactory.getLogger("demo.Main");
  static final AtomicInteger SEQ = new AtomicInteger();
  public static class MdcFilter extends OncePerRequestFilter {
    final boolean clean; MdcFilter(boolean clean) { this.clean = clean; }
    protected void doFilterInternal(HttpServletRequest rq, HttpServletResponse rs, FilterChain ch) throws ServletException, IOException {
      String id = rq.getHeader("X-Request-Id"); if (id == null && !clean) { ch.doFilter(rq, rs); return; } if (id == null) id = "gen-" + SEQ.incrementAndGet();
      MDC.put("traceId", id); rs.setHeader("X-Request-Id", id);
      try { ch.doFilter(rq, rs); } finally { if (clean) MDC.remove("traceId"); }
    } }
  @Bean @ConditionalOnProperty(name = "app.mdc", havingValue = "clean", matchIfMissing = true) FilterRegistrationBean<MdcFilter> f1() { var r = new FilterRegistrationBean<>(new MdcFilter(true)); r.setOrder(Integer.MIN_VALUE + 10); return r; }
  @Bean @ConditionalOnProperty(name = "app.mdc", havingValue = "leak") FilterRegistrationBean<MdcFilter> f2() { var r = new FilterRegistrationBean<>(new MdcFilter(false)); r.setOrder(Integer.MIN_VALUE + 10); return r; }
  @Bean @ConditionalOnProperty("app.reqlog") CommonsRequestLoggingFilter reqLog() { var f = new CommonsRequestLoggingFilter(); f.setIncludeQueryString(true); f.setIncludePayload(true); f.setMaxPayloadLength(30); f.setIncludeClientInfo(Boolean.getBoolean("app.client")); f.setIncludeHeaders(Boolean.getBoolean("app.headers")); if (Boolean.getBoolean("app.hideauth")) f.setHeaderPredicate(h -> !h.equalsIgnoreCase("authorization")); return f; }
  @Bean @ConditionalOnProperty("app.deco") TaskDecorator mdcDecorator() { return rn -> { Map<String, String> ctx = MDC.getCopyOfContextMap(); return () -> { if (ctx != null) MDC.setContextMap(ctx); try { rn.run(); } finally { MDC.clear(); } }; }; }
  @Service public static class Svc {
    final Logger l = LoggerFactory.getLogger("demo.Svc");
    public String work() { l.info("service 处理中"); return "done"; }
    @Async public CompletableFuture<String> plainAsync() { l.info("@Async 方法里"); return CompletableFuture.completedFuture("a"); }
  }
  final Svc svc; Main(Svc s) { svc = s; }
  @GetMapping("/work") String work() { log.info("controller 开始"); String r = svc.work(); log.info("controller 结束"); return r; }
  @GetMapping("/async-plain") String ap() throws Exception { log.info("controller 调用 @Async"); return svc.plainAsync().get(); }
  @GetMapping("/cf") String cf() throws Exception { log.info("controller 调用 CompletableFuture.supplyAsync"); return CompletableFuture.supplyAsync(() -> { log.info("supplyAsync 里(公共 ForkJoinPool)"); return "c"; }).get(); }
  @GetMapping("/new-thread") String nt() throws Exception { log.info("controller 开新线程"); var f = new CompletableFuture<String>(); new Thread(() -> { log.info("new Thread 里"); f.complete("n"); }, "raw-thread").start(); return f.get(); }
  @GetMapping("/callable") Callable<String> callable() { log.info("controller 返回 Callable"); return () -> { log.info("Callable 里"); return "call"; }; }
  @PostMapping("/post") String post(@RequestBody String b) { log.info("controller 收到 body 长度 " + b.length()); return "posted"; }
  @GetMapping("/plain") String plain() { log.info("controller 开始(没有带 X-Request-Id)"); return "plain"; }
  static class Ic implements HandlerInterceptor { static final Logger l = LoggerFactory.getLogger("demo.Ic");
    public void afterCompletion(HttpServletRequest q, HttpServletResponse s, Object h, Exception e) { if (q.getRequestURI().equals("/callable")) l.info("拦截器 afterCompletion [" + q.getDispatcherType() + "]"); }
    public boolean preHandle(HttpServletRequest q, HttpServletResponse s, Object h) { if (q.getRequestURI().equals("/callable")) l.info("拦截器 preHandle [" + q.getDispatcherType() + "]"); return true; } }
  @Bean WebMvcConfigurer cfg() { return new WebMvcConfigurer() { public void addInterceptors(InterceptorRegistry r) { r.addInterceptor(new Ic()); } }; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x53', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def loglines(app, n0): return [l[4:] for l in app.log().splitlines()[n0:] if l.startswith('LOG ') and 'Started Main' not in l]
def show(app, m, p, hd=None, body=None, label=None):
    n0 = len(app.log().splitlines()); s, d, h = app.get(p, method=m, headers=hd, body=body); time.sleep(0.25)
    print(f'  {label or ""}{m} {p}{"  [" + ", ".join(f"{k}: {v}" for k, v in (hd or {}).items() if k != "Content-Type") + "]" if hd else ""} → {s},响应头 X-Request-Id = {h.get("X-Request-Id")}')
    for l in loglines(app, n0): print('      ' + l)
def run(props, f, title):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}'); f(app); app.stop()
print('Spring Boot 4.0.8 / Spring MVC 7.0.9(Tomcat 11.0.24)。日志格式:[线程名] traceId=[MDC 里的 traceId] 日志器: 内容')
def one(app):
    show(app, 'GET', '/work', {'X-Request-Id': 'req-A'}); show(app, 'GET', '/work'); show(app, 'GET', '/work', {'X-Request-Id': 'req-B'})
run({}, one, '一:Filter 把请求头里的 X-Request-Id(没有就生成)放进 MDC;controller 与 service 的日志自动带上')
def two(app):
    for p in ['/async-plain', '/cf', '/new-thread', '/callable']: show(app, 'GET', p, {'X-Request-Id': 'req-T'})
run({}, two, '二:换了线程之后 MDC 还在吗(没有任何处理):@Async、CompletableFuture、new Thread、Callable 与它重新派发后的拦截器')
def three(app):
    for p in ['/async-plain', '/cf', '/new-thread', '/callable']: show(app, 'GET', p, {'X-Request-Id': 'req-T'})
run({'app.deco': 'true'}, three, '三:定义一个复制 MDC 的 TaskDecorator Bean(Boot 会把它用在自己的任务执行器上)')
def four(app):
    show(app, 'GET', '/plain', {'X-Request-Id': 'req-LEAK'}); show(app, 'GET', '/plain'); show(app, 'GET', '/plain')
run({'app.mdc': 'leak', 'server.tomcat.threads.max': '1', 'server.tomcat.threads.min-spare': '1'}, four, '四:Filter 里忘了在 finally 里清 MDC(Tomcat 只留 1 个线程,保证复用)')
def five(app):
    show(app, 'POST', '/post?x=1&y=2', {'X-Request-Id': 'req-R', 'Content-Type': 'application/json', 'Authorization': 'Bearer SECRET-TOKEN-123'}, body='{"name":"Tom","note":"' + 'z' * 60 + '"}')
run({'app.reqlog': 'true'}, five, '五:CommonsRequestLoggingFilter(includeQueryString、includePayload=true、maxPayloadLength=30)')
def six(app):
    show(app, 'POST', '/post?x=1', {'X-Request-Id': 'req-R', 'Content-Type': 'application/json', 'Authorization': 'Bearer SECRET-TOKEN-123', 'Cookie': 'sid=abc'}, body='{"a":1}')
run({'app.reqlog': 'true', 'app.headers': 'true', 'app.client': 'true'}, six, '六:加上 includeHeaders=true、includeClientInfo=true')
def seven(app):
    show(app, 'POST', '/post?x=1', {'X-Request-Id': 'req-R', 'Content-Type': 'application/json', 'Authorization': 'Bearer SECRET-TOKEN-123', 'Cookie': 'sid=abc'}, body='{"a":1}')
run({'app.reqlog': 'true', 'app.headers': 'true', 'app.hideauth': 'true'}, seven, '七:includeHeaders=true,headerPredicate 对 Authorization 返回 false')
