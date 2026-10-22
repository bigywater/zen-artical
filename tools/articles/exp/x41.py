import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x41'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.http.*; import org.springframework.web.ErrorResponse; import org.springframework.web.bind.annotation.*;
@SpringBootApplication @RestController
public class Main {
  public record User(String name, int age) { }
  public static class Form { private String name; private int age; private List<String> tags; public String getName() { return name; } public void setName(String n) { name = n; } public int getAge() { return age; } public void setAge(int a) { age = a; } public List<String> getTags() { return tags; } public void setTags(List<String> t) { tags = t; } public String toString() { return "Form(name=" + name + ",age=" + age + ",tags=" + tags + ")"; } }
  public static class FormPub { public String name; public int age; public String toString() { return "FormPub(name=" + name + ",age=" + age + ")"; } }
  @GetMapping("/p1") String p1(@RequestParam String q) { return "p1 q=" + q; }
  @GetMapping("/p2") String p2(@RequestParam(required = false) String q) { return "p2 q=" + q; }
  @GetMapping("/p3") String p3(@RequestParam(defaultValue = "dft") String q) { return "p3 q=" + q; }
  @GetMapping("/p4") String p4(@RequestParam Optional<Integer> n) { return "p4 n=" + n; }
  @GetMapping("/p5") String p5(@RequestParam int n) { return "p5 n=" + n; }
  @GetMapping("/p6") String p6(@RequestParam List<String> a) { return "p6 a=" + a; }
  @GetMapping("/p7") String p7(@RequestParam Map<String, String> all) { return "p7 all=" + new TreeMap<>(all); }
  @GetMapping("/p8") String p8(String implicit, int num) { return "p8 implicit=" + implicit + ",num=" + num; }
  @GetMapping("/p9") String p9(@RequestParam boolean flag) { return "p9 flag=" + flag; }
  @GetMapping("/h1") String h1(@RequestHeader("X-Id") String id, @CookieValue(value = "sid", defaultValue = "无") String sid) { return "h1 id=" + id + ",sid=" + sid; }
  @PostMapping("/b1") String b1(@RequestBody User u) { return "b1 " + u; }
  @PostMapping("/b2") String b2(@RequestBody(required = false) User u) { return "b2 " + u; }
  @PostMapping("/b3") String b3(@RequestBody String raw, @RequestParam(required = false) String q) { return "b3 raw=" + raw + ",q=" + q; }
  @PostMapping("/m1") String m1(Form f) { return "m1 " + f; }
  @PostMapping("/m3") String m3(FormPub f) { return "m3 " + f; }
  @PostMapping("/m2") String m2(@ModelAttribute Form f, @RequestParam String extra) { return "m2 " + f + ",extra=" + extra; }
  @GetMapping("/x1/{id}") String x1(@PathVariable int id) { return "x1 id=" + id; }
  @GetMapping("/x2") String x2(HttpServletRequest rq, java.util.Locale l, java.security.Principal p, java.io.InputStream in) { return "x2 method=" + rq.getMethod() + ",locale=" + l + ",principal=" + p; }
  @RestControllerAdvice public static class Adv extends org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler {
    @Override protected ResponseEntity<Object> handleExceptionInternal(Exception e, Object body, HttpHeaders h, HttpStatusCode st, org.springframework.web.context.request.WebRequest rq) { return ResponseEntity.status(st).body(e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()).split("\n")[0].replace("demo.Main$", "")); }
    @ExceptionHandler(IllegalStateException.class) public ResponseEntity<String> ise(IllegalStateException e) { return ResponseEntity.status(500).body("IllegalStateException: " + String.valueOf(e.getMessage()).split("\n")[0]); } }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x41', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
app = SApp(b, 'demo.Main').start()
def p(rows, sec):
    print(f'== {sec}'); 
    for m_, path, kw in rows:
        s_, d, h = app.get(path, method=m_, **kw); print(f'  {m_} {path}' + (f'  [{kw["body"][:40]}]' if kw.get('body') else '') + f' → {s_} {d.strip()[:200]}')
JSON = {'headers': {'Content-Type': 'application/json'}}; FORM = {'headers': {'Content-Type': 'application/x-www-form-urlencoded'}}
p([('GET', '/p1?q=hi', {}), ('GET', '/p1', {}), ('GET', '/p2', {}), ('GET', '/p3', {}), ('GET', '/p3?q=', {}), ('GET', '/p4?n=7', {}), ('GET', '/p4', {}), ('GET', '/p5?n=abc', {}), ('GET', '/p5', {}), ('GET', '/p9?flag=yes', {}), ('GET', '/p9?flag=on', {}), ('GET', '/p9?flag=maybe', {})], '一:@RequestParam:必需、可选、默认值、Optional、类型转换失败')
p([('GET', '/p6?a=1&a=2', {}), ('GET', '/p6?a=1,2', {}), ('GET', '/p7?x=1&y=2&x=3', {}), ('GET', '/p8?implicit=a&num=5', {}), ('GET', '/p8?implicit=a', {}), ('GET', '/x1/12', {}), ('GET', '/x1/abc', {})], '二:集合参数、Map、不带注解的简单类型参数、@PathVariable')
p([('GET', '/h1', {}), ('GET', '/h1', {'headers': {'X-Id': '7', 'Cookie': 'sid=abc'}}), ('GET', '/x2', {'headers': {'Accept-Language': 'zh-CN'}})], '三:请求头、Cookie 与 Servlet 相关的参数类型(没有登录时 Principal 是 null)')
p([('POST', '/b1', {'body': '{"name":"ann","age":30}', **JSON}), ('POST', '/b1', {'body': '{"name":"ann","age":"x"}', **JSON}), ('POST', '/b1', {'body': '{bad json', **JSON}), ('POST', '/b1', {'body': '', **JSON}), ('POST', '/b1', {'body': '{"name":"ann","age":30,"extra":1}', **JSON}), ('POST', '/b2', {'body': '', **JSON}), ('POST', '/b3?q=z', {'body': 'raw text', 'headers': {'Content-Type': 'text/plain'}})], '四:@RequestBody(JSON 转 record):正常、类型错、JSON 坏、空 body、多余字段、required = false、读原始字符串')
p([('POST', '/m1', {'body': 'name=ann&age=30&tags=a&tags=b', **FORM}), ('POST', '/m1?name=q&age=9', {'body': '', **FORM}), ('POST', '/m1', {'body': 'name=ann&age=x', **FORM}), ('POST', '/m1', {'body': 'name=ann&nope=1', **FORM}), ('POST', '/m3', {'body': 'name=ann&age=30', **FORM}), ('POST', '/m2?extra=e', {'body': 'name=bob&age=1', **FORM})], '五:不带注解的对象参数(隐式 @ModelAttribute):表单与查询参数绑定到对象;绑定失败')
app.stop()
