import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x45'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc', 'org.springframework.boot:spring-boot-starter-validation')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*; import java.util.stream.*;
import jakarta.validation.*; import jakarta.validation.constraints.*; import jakarta.validation.groups.Default;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty; import org.springframework.stereotype.Service;
import org.springframework.validation.*; import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.MethodArgumentNotValidException; import org.springframework.web.bind.annotation.*; import org.springframework.web.method.annotation.HandlerMethodValidationException;
@SpringBootApplication @RestController
public class Main {
  public interface Create {} public interface Update {}
  public record Address(@NotBlank(message = "city 不能为空") String city) {}
  public record User(@Null(groups = Create.class, message = "创建时 id 必须为空") @NotNull(groups = Update.class, message = "更新时 id 不能为空") Long id,
                     @NotBlank(message = "name 不能为空") String name, @Min(value = 18, message = "age 至少 18") int age, @Valid Address addr) {}
  public record Order1(@NotBlank(message = "no 不能为空") String no, Address addr) {}
  public record Order2(@NotBlank(message = "no 不能为空") String no, @Valid Address addr) {}
  @Service @Validated public static class Svc { public String run(@Min(value = 1, message = "n 至少 1") int n) { return "svc ok " + n; } }
  @Service public static class Plain { public String run(@Min(value = 1, message = "n 至少 1") int n) { return "plain ok " + n; } }
  final Svc svc; final Plain plain; Main(Svc s, Plain p) { svc = s; plain = p; }
  static String hit(String s) { System.out.println("RES EV     Controller 方法被调用:" + s); System.out.flush(); return s; }
  @PostMapping("/v/body") String body(@Valid @RequestBody User u) { return hit("body " + u); }
  @PostMapping("/v/body-nobind") String bodyNo(@RequestBody User u) { return hit("bodyNo(没有 @Valid) " + u); }
  @PostMapping("/v/body-binding") String bodyBinding(@Valid @RequestBody User u, BindingResult br) { return hit("BindingResult 错误数=" + br.getErrorCount() + " " + br.getFieldErrors().stream().map(f -> f.getField()).sorted().toList()); }
  @GetMapping("/v/param") String param(@RequestParam @Min(value = 1, message = "page 至少 1") int page, @RequestParam @NotBlank(message = "q 不能为空") String q) { return hit("param " + page + "," + q); }
  @GetMapping("/v/path/{id}") String path(@PathVariable @Min(value = 1, message = "id 至少 1") long id) { return hit("path " + id); }
  @PostMapping("/v/g-create") String gc(@Validated(Create.class) @RequestBody User u) { return hit("create " + u); }
  @PostMapping("/v/g-update") String gu(@Validated(Update.class) @RequestBody User u) { return hit("update " + u); }
  @PostMapping("/v/g-both") String gb(@Validated({Create.class, Default.class}) @RequestBody User u) { return hit("create+default " + u); }
  @PostMapping("/v/nested1") String n1(@Valid @RequestBody Order1 o) { return hit("nested1 " + o); }
  @PostMapping("/v/nested2") String n2(@Valid @RequestBody Order2 o) { return hit("nested2 " + o); }
  @GetMapping("/v/svc") String svc(@RequestParam int n) { return hit(svc.run(n)); }
  @GetMapping("/v/plain") String plain(@RequestParam int n) { return hit(plain.run(n)); }
  @RestController @Validated @RequestMapping("/vc") public static class Vc { @GetMapping("/param") String p(@RequestParam @Min(value = 1, message = "page 至少 1") int page) { return hit("类上有 @Validated page=" + page); } }
  @RestControllerAdvice @ConditionalOnProperty("app.advice") public static class Adv {
    @ExceptionHandler(Exception.class) org.springframework.http.ResponseEntity<String> any(Exception e) {
      String d;
      if (e instanceof MethodArgumentNotValidException m) d = m.getBindingResult().getFieldErrors().stream().map(f -> f.getField() + "=" + f.getDefaultMessage()).sorted().collect(Collectors.joining("; "));
      else if (e instanceof HandlerMethodValidationException h) d = h.getParameterValidationResults().stream().flatMap(r -> r.getResolvableErrors().stream().map(x -> x.getDefaultMessage())).sorted().collect(Collectors.joining("; "));
      else if (e instanceof ConstraintViolationException c) d = c.getConstraintViolations().stream().map(v -> v.getMessage()).sorted().collect(Collectors.joining("; "));
      else d = String.valueOf(e.getMessage());
      return org.springframework.http.ResponseEntity.status(e instanceof ConstraintViolationException ? 500 : 400).body("[" + e.getClass().getSimpleName() + "] " + d);
    } }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x45', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
J = {'headers': {'Content-Type': 'application/json'}}
def j(o): return {'body': json.dumps(o, ensure_ascii=False), **J}
OK = {'name': 'Tom', 'age': 20, 'addr': {'city': 'BJ'}}
BAD = {'name': ' ', 'age': 10, 'addr': {'city': ''}}
def run(props, reqs, title):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}')
    for m_, p_, kw in reqs:
        n0 = len(app.log().splitlines()); s, d, h = app.get(p_, method=m_, **kw); time.sleep(0.15); ev = [l[7:] for l in app.log().splitlines()[n0:] if l.startswith('RES EV ')]
        d = re.sub(r'"timestamp":"[^"]*",?', '', d.strip()); tag = {'/v/body': '带 @Valid', '/v/body-nobind': '没有 @Valid', '/v/body-binding': '带 BindingResult'}.get(p_, '')
        print(f'  {m_} {p_} {kw.get("body", "")[:60] if "body" in kw else ""}→ {s} {d[:150]}'); [print('     ' + l) for l in ev]
    app.stop()
print('Spring Boot 4.0.8 / Spring Framework 7.0.9 / spring-boot-starter-validation(Hibernate Validator 由 Boot BOM 决定)')
R1 = [('POST', '/v/body', j(OK)), ('POST', '/v/body', j(BAD)), ('POST', '/v/body-nobind', j(BAD)), ('POST', '/v/body-binding', j(BAD))]
run({'app.advice': 'true'}, R1, '一:@RequestBody 上的 @Valid(Advice 打印异常类型与消息;含 @Valid 嵌套的 addr.city)')
R2 = [('GET', '/v/param?page=0&q=%20', {}), ('GET', '/v/path/0', {}), ('GET', '/vc/param?page=0', {}), ('GET', '/v/svc?n=0', {}), ('GET', '/v/plain?n=0', {})]
run({'app.advice': 'true'}, R2, '二:直接标在方法参数上的约束:控制器参数 / 类上有 @Validated / Service 上有或没有 @Validated')
R3 = [('POST', '/v/g-create', j({'id': 5, 'name': '', 'age': 1})), ('POST', '/v/g-create', j({'name': '', 'age': 1})), ('POST', '/v/g-update', j({'name': '', 'age': 1})), ('POST', '/v/g-both', j({'id': 5, 'name': '', 'age': 1}))]
run({'app.advice': 'true'}, R3, '三:分组:@Validated(Create.class) 时默认组的约束还会不会检查')
R4 = [('POST', '/v/nested1', j({'no': 'a', 'addr': {'city': ''}})), ('POST', '/v/nested2', j({'no': 'a', 'addr': {'city': ''}}))]
run({'app.advice': 'true'}, R4, '四:嵌套对象:字段上没有 @Valid 和有 @Valid')
R5 = [('POST', '/v/body', j(BAD)), ('GET', '/v/param?page=0&q=%20', {}), ('GET', '/vc/param?page=0', {}), ('GET', '/v/svc?n=0', {})]
run({}, R5, '五:不写任何处理器,Boot 默认给的响应')
run({'spring.mvc.problemdetails.enabled': 'true'}, [R5[0], R5[1]], '六:spring.mvc.problemdetails.enabled=true')
