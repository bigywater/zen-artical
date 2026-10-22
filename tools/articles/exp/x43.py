import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x43'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.io.IOException; import java.net.URI; import java.util.*;
import jakarta.servlet.*; import jakarta.servlet.http.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty; import org.springframework.context.annotation.Bean;
import org.springframework.core.annotation.Order; import org.springframework.http.*; import org.springframework.web.ErrorResponse; import org.springframework.web.bind.annotation.*; import org.springframework.web.server.ResponseStatusException;
@SpringBootApplication @RestController
public class Main {
  public static class BizException extends RuntimeException { final int code; BizException(int code, String m) { super(m); this.code = code; } }
  @ResponseStatus(value = HttpStatus.CONFLICT, reason = "冲突了") public static class ConflictEx extends RuntimeException { }
  @GetMapping("/e/illegal") String illegal() { throw new IllegalStateException("非法状态"); }
  @GetMapping("/e/rse") String rse() { throw new ResponseStatusException(HttpStatus.I_AM_A_TEAPOT, "我是茶壶"); }
  @GetMapping("/e/annotated") String annotated() { throw new ConflictEx(); }
  @GetMapping("/e/biz") String biz() { throw new BizException(1001, "业务异常:余额不足"); }
  @GetMapping("/e/arg") String arg() { throw new IllegalArgumentException("参数不合法"); }
  @GetMapping("/e/local") String local() { throw new IllegalArgumentException("本地处理器应该处理我"); }
  @GetMapping("/e/param") String param(@RequestParam String q) { return q; }
  @GetMapping("/e/inhandler") String inhandler() { throw new UnsupportedOperationException("触发处理器内部异常"); }
  @ExceptionHandler(IllegalArgumentException.class) ResponseEntity<String> localArg(IllegalArgumentException e) { return ResponseEntity.status(422).body("[控制器内的 @ExceptionHandler] " + e.getMessage()); }
  @Bean Filter boomFilter() { return new jakarta.servlet.http.HttpFilter() { protected void doFilter(HttpServletRequest rq, HttpServletResponse rs, FilterChain ch) throws IOException, ServletException { if (rq.getHeader("X-Boom") != null && rq.getDispatcherType() == DispatcherType.REQUEST) throw new IllegalStateException("Filter 里抛的异常"); ch.doFilter(rq, rs); } }; }
  @RestControllerAdvice @ConditionalOnProperty("app.advice") @Order(2) public static class Adv extends org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler {
    @ExceptionHandler(BizException.class) ProblemDetail biz(BizException e) { ProblemDetail p = ProblemDetail.forStatusAndDetail(HttpStatus.UNPROCESSABLE_ENTITY, e.getMessage()); p.setTitle("业务错误"); p.setType(URI.create("https://example.com/errors/biz")); p.setProperty("code", e.code); return p; }
    @ExceptionHandler(IllegalStateException.class) ResponseEntity<String> ise(IllegalStateException e) { return ResponseEntity.status(500).body("[Advice 里 IllegalStateException] " + e.getMessage()); }
    @ExceptionHandler(IllegalArgumentException.class) ResponseEntity<String> iae(IllegalArgumentException e) { return ResponseEntity.status(400).body("[Advice 里 IllegalArgumentException] " + e.getMessage()); }
    @ExceptionHandler(RuntimeException.class) ResponseEntity<String> rt(RuntimeException e) { if (e instanceof UnsupportedOperationException) throw new IllegalStateException("处理器自己又抛了"); return ResponseEntity.status(500).body("[Advice 里 RuntimeException 兜底] " + e.getClass().getSimpleName() + ": " + e.getMessage()); } }
  @RestControllerAdvice @ConditionalOnProperty("app.advice") @Order(1) public static class Adv2 { @ExceptionHandler(IllegalStateException.class) ResponseEntity<String> ise(IllegalStateException e) { return ResponseEntity.status(500).body("[Order(1) 的另一个 Advice 抢先处理了 IllegalStateException] " + e.getMessage()); } }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x43', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
paths = [('/e/illegal', {}), ('/e/rse', {}), ('/e/annotated', {}), ('/e/biz', {}), ('/e/arg', {}), ('/e/param', {}), ('/nope', {}), ('/e/illegal', {'headers': {'X-Boom': '1'}})]
def table(props, title):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}')
    for p_, kw in paths:
        s, d, h = app.get(p_, **kw); ct = h.get('Content-Type', '-').split(';')[0]
        txt = d.strip().replace('\n', ' ')
        try: j = json.loads(txt); txt = json.dumps({k: v for k, v in j.items() if k not in ('timestamp', 'instance')}, ensure_ascii=False)
        except Exception: pass
        print(f'  GET {p_}' + ('  [头 X-Boom]' if kw else '') + f' → {s} [{ct}] {txt[:210]}')
    app.stop()
print('Spring Boot 4.0.8 / Spring MVC 7.0.9。Controller 里的几种异常:IllegalStateException(/e/illegal)、ResponseStatusException 418(/e/rse)、带 @ResponseStatus 的异常(/e/annotated)、自定义业务异常 BizException(/e/biz)、IllegalArgumentException(/e/arg,控制器内部有一个 @ExceptionHandler 管它,另一个 /e/local 与它相同)、缺少必需参数(/e/param)、不存在的路径(/nope)、Filter 里抛异常(/e/illegal 加请求头 X-Boom)')
table({}, '一:什么都不配(Boot 默认的 /error 页)')
table({'spring.mvc.problemdetails.enabled': 'true'}, '二:spring.mvc.problemdetails.enabled=true(标准 MVC 异常输出 RFC 9457 的 problem+json)')
table({'app.advice': 'true'}, '三:加上两个 @RestControllerAdvice(Adv 的 @Order(2) 继承了 ResponseEntityExceptionHandler,Adv2 的 @Order(1) 只管 IllegalStateException)')
app = SApp(b, 'demo.Main', props={'app.advice': 'true'}).start()
print('== 四:处理器自己抛异常;控制器内处理器与 Advice 谁优先')
s, d, h = app.get('/e/inhandler'); print(f'  GET /e/inhandler(UnsupportedOperationException → Advice 兜底处理器里又抛了 IllegalStateException)→ {s} {d.strip()[:200]}')
s, d, h = app.get('/e/local'); print(f'  GET /e/local(控制器内有 IllegalArgumentException 处理器,Advice 里也有)→ {s} {d.strip()}')
app.stop()
