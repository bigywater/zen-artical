import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x46'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc', 'tools.jackson.dataformat:jackson-dataformat-xml')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.*; import org.springframework.web.bind.annotation.*;
@SpringBootApplication @RestController
public class Main {
  public record User(String name, int age) {}
  @GetMapping("/n/user") User user() { return new User("Tom", 20); }
  @GetMapping("/n/str") String str() { return "plain-string"; }
  @GetMapping(value = "/n/json-only", produces = "application/json") User jsonOnly() { return new User("Tom", 20); }
  @GetMapping(value = "/n/two", produces = "application/json") String twoJson() { return "{\"from\":\"json-method\"}"; }
  @GetMapping(value = "/n/two", produces = "application/xml") String twoXml() { return "<from>xml-method</from>"; }
  @GetMapping("/n/entity") ResponseEntity<User> entity() { return ResponseEntity.ok().contentType(MediaType.APPLICATION_XML).body(new User("Tom", 20)); }
  @PostMapping(value = "/n/in", consumes = "application/json") String inJson(@RequestBody User u) { return "json-in " + u; }
  @PostMapping(value = "/n/any") String inAny(@RequestBody User u) { return "any-in " + u; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x46', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def show(app, m, p, hd=None, body=None):
    s, d, h = app.get(p, method=m, headers=hd, body=body); ct = h.get('Content-Type', '-'); d = re.sub(r'"timestamp":"[^"]*",?', '', d.strip())
    acc = (hd or {}).get('Accept'); ac = f' Accept: {acc}' if acc else ' (无 Accept)'; cti = (hd or {}).get('Content-Type')
    print(f'  {m} {p}{ac}{" Content-Type: " + cti if cti else ""} → {s} [{ct}] {d[:110]}')
def run(props, f, title):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}'); f(app); app.stop()
print('Spring Boot 4.0.8 / Spring MVC 7.0.9,classpath 里有 jackson-dataformat-xml(tools.jackson.dataformat),所以同时有 JSON 和 XML 转换器')
def one(app):
    for acc in [None, '*/*', 'application/json', 'application/xml', 'application/json;q=0.5, application/xml;q=0.9', 'text/html', 'text/plain', 'application/xml, application/json']:
        show(app, 'GET', '/n/user', {'Accept': acc} if acc else None)
run({}, one, '一:返回对象(User record)时 Accept 如何决定 Content-Type')
def two(app):
    for acc in [None, 'application/json', 'text/plain', 'application/xml', 'text/html']:
        show(app, 'GET', '/n/str', {'Accept': acc} if acc else None)
run({}, two, '二:返回 String 时(StringHttpMessageConverter 排在最前面)')
def three(app):
    show(app, 'GET', '/n/json-only', {'Accept': 'application/xml'}); show(app, 'GET', '/n/json-only', {'Accept': 'application/json'}); show(app, 'GET', '/n/json-only')
    for acc in ['application/json', 'application/xml', 'text/plain', None]: show(app, 'GET', '/n/two', {'Accept': acc} if acc else None)
    show(app, 'GET', '/n/entity', {'Accept': 'application/json'}); show(app, 'GET', '/n/entity', {'Accept': 'application/xml'})
run({}, three, '三:produces 限定、同路径按 produces 分流、ResponseEntity 自己指定 Content-Type')
def four(app):
    show(app, 'GET', '/n/user.json'); show(app, 'GET', '/n/user.xml'); show(app, 'GET', '/n/user?format=xml'); show(app, 'GET', '/n/user?format=json', {'Accept': 'application/xml'})
run({}, four, '四:不加任何配置时,路径后缀和 ?format= 能不能决定格式')
def five(app):
    show(app, 'GET', '/n/user?format=xml'); show(app, 'GET', '/n/user?format=json', {'Accept': 'application/xml'}); show(app, 'GET', '/n/user?format=csv')
run({'spring.mvc.contentnegotiation.favor-parameter': 'true', 'spring.mvc.contentnegotiation.parameter-name': 'format'}, five, '五:spring.mvc.contentnegotiation.favor-parameter=true,parameter-name=format')
def six(app):
    J = {'Content-Type': 'application/json'}; X = {'Content-Type': 'application/xml'}
    show(app, 'POST', '/n/in', J, '{"name":"Tom","age":20}'); show(app, 'POST', '/n/in', X, '<User><name>Tom</name><age>20</age></User>'); show(app, 'POST', '/n/in', {'Content-Type': 'text/plain'}, 'x'); show(app, 'POST', '/n/in', None, '{"name":"Tom","age":20}')
    show(app, 'POST', '/n/any', X, '<User><name>Tom</name><age>20</age></User>'); show(app, 'POST', '/n/any', {'Content-Type': 'text/plain'}, 'x')
run({}, six, '六:请求体方向:Content-Type 与 consumes(415)')
