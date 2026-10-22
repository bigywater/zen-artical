import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x40'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*;
@SpringBootApplication @RestController
public class Main {
  @GetMapping("/users/me") String me() { return "me"; }
  @GetMapping("/users/{id}") String byId(@PathVariable String id) { return "byId(" + id + ")"; }
  @GetMapping("/users/{id:\\d+}/orders") String ordersNumeric(@PathVariable String id) { return "ordersNumeric(" + id + ")"; }
  @GetMapping("/users/{name}/orders") String ordersAny(@PathVariable String name) { return "ordersAny(" + name + ")"; }
  @GetMapping("/files/**") String files() { return "files/**"; }
  @GetMapping("/files/readme.txt") String readme() { return "files/readme.txt"; }
  @GetMapping("/doc/{name:.+}") String doc(@PathVariable String name) { return "doc(" + name + ")"; }
  @GetMapping("/hello") String hello() { return "hello"; }
  @GetMapping(value = "/neg", produces = "application/json") String negJson() { return "neg-json"; }
  @GetMapping(value = "/neg", produces = "text/plain") String negText() { return "neg-text"; }
  @GetMapping(value = "/cond", params = "debug=true") String condDebug() { return "cond(debug=true)"; }
  @GetMapping(value = "/cond") String cond() { return "cond()"; }
  @PostMapping(value = "/consume", consumes = "application/json") String consumeJson(@RequestBody String b) { return "consume-json"; }
  @GetMapping(value = "/hdr", headers = "X-Env=prod") String hdrProd() { return "hdr(prod)"; }
  @GetMapping(value = "/hdr") String hdr() { return "hdr()"; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
AMB = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*;
@SpringBootApplication @RestController
public class Main {
  @GetMapping("/x/{a}") String one(@PathVariable String a) { return "one"; }
  @GetMapping("/x/{b}") String two(@PathVariable String b) { return "two"; }
  public static void main(String[] a) { try { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); if (a.length > 0) { app.run(a); return; } app.run(a).close(); System.out.println("RES 启动成功"); } catch (Throwable t) { Throwable r = t; while (r.getCause() != null) r = r.getCause(); System.out.println("RES 启动失败 " + r.getClass().getSimpleName() + ": " + String.valueOf(r.getMessage()).replace("demo.Main#", "").replaceAll("\\s+", " ")); } System.exit(0); }
}
'''
BAD = AMB.replace('@GetMapping("/x/{a}") String one(@PathVariable String a) { return "one"; }\n  @GetMapping("/x/{b}") String two(@PathVariable String b) { return "two"; }','@GetMapping("/x/**/y") String bad() { return "bad"; }')
LOGE = '<configuration><appender name="O" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{0}: %msg%n</pattern></encoder></appender><root level="ERROR"><appender-ref ref="O"/></root></configuration>'
b = sbuild('x40', {'src/demo/Main.java': MAIN, 'logback.xml': LOGE}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
print('Spring Boot 4.0.8 / Spring MVC 7.0.9。请求怎么匹配到 Controller 方法(RequestMappingHandlerMapping + PathPattern)。每个 Controller 方法返回自己的名字,所以响应体就是“谁处理了这个请求”')
app = SApp(b, 'demo.Main', props={'server.error.include-message': 'always'}).start()
def probe(rows, hdr, **kw):
    out = []
    for lab, m_, path, kw_ in rows:
        try: s_, d, h = app.get(path, method=m_, **kw_)
        except Exception as e: s_, d = 'ERR', str(e)[:40]
        out.append((lab, f'{m_} {path}', s_, d.strip()[:60] if s_ == 200 else d.strip()[:50].replace('\n', ' ')))
    print('  ' + '  |  '.join(hdr)); [print('  ' + '  |  '.join(map(str, r))) for r in out]
print('== 一:同一个路径有多个模式时谁赢(最具体的)')
probe([('字面量 vs 变量', 'GET', '/users/me', {}), ('字面量 vs 变量', 'GET', '/users/42', {}), ('正则变量 vs 任意变量', 'GET', '/users/42/orders', {}), ('正则变量 vs 任意变量', 'GET', '/users/bob/orders', {}), ('/** vs 精确', 'GET', '/files/readme.txt', {}), ('/** vs 精确', 'GET', '/files/a/b/c.txt', {})], ['说明', '请求', '状态', '谁处理的'])
time.sleep(0.3); mm = re.search(r"(Ambiguous handler methods mapped for '/users/42/orders'[^\n]{0,300})", app.log()); print('  服务端日志里 /users/42/orders 的 500 原因:' + (mm.group(1).replace('demo.Main.', '').replace('java.lang.String ', '') if mm else '(没找到)'))
print('== 二:模式写法与默认行为')
probe([('末尾斜杠', 'GET', '/hello/', {}), ('后缀', 'GET', '/hello.json', {}), ('大小写', 'GET', '/Hello', {}), ('带点的路径变量(没写正则)', 'GET', '/users/a.b', {}), ('写了 {name:.+} 的带点变量', 'GET', '/doc/report.final.pdf', {}), ('路径变量里的 %2F', 'GET', '/users/a%2Fb', {})], ['说明', '请求', '状态', '响应(404 等是 Boot 的错误页 JSON)'])
print('== 三:除了路径,还能按 produces / consumes / params / headers 区分')
probe([('Accept: application/json', 'GET', '/neg', {'headers': {'Accept': 'application/json'}}), ('Accept: text/plain', 'GET', '/neg', {'headers': {'Accept': 'text/plain'}}), ('Accept: text/html', 'GET', '/neg', {'headers': {'Accept': 'text/html'}}), ('?debug=true', 'GET', '/cond?debug=true', {}), ('没有参数', 'GET', '/cond', {}), ('X-Env: prod', 'GET', '/hdr', {'headers': {'X-Env': 'prod'}}), ('没有头', 'GET', '/hdr', {}), ('Content-Type: application/json', 'POST', '/consume', {'body': '{}', 'headers': {'Content-Type': 'application/json'}}), ('Content-Type: text/plain', 'POST', '/consume', {'body': 'x', 'headers': {'Content-Type': 'text/plain'}})], ['说明', '请求', '状态', '谁处理的 / 错误'])
app.stop()
print('== 四:两个模式冲突或写法不被支持时')
bb = sbuild('x40e', {'src/demo/Main.java': AMB, 'logback.xml': LOGE}, CP); r = srun(bb, 'demo.Main', timeout=120); L = [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-600:]]
print('  两个方法映射到 GET /x/{a} 与 GET /x/{b}:' + L[0][:300])
ap2 = SApp(bb, 'demo.Main', args=['serve'], props={'server.error.include-message': 'always'}).start(); s_, d, h = ap2.get('/x/1'); time.sleep(0.3); lg = ap2.log(); ap2.stop(); m_ = re.search(r'(Ambiguous handler methods mapped for[^\n]{0,300})', lg)
print(f'  同一个应用启动后请求 GET /x/1 → {s_},消息:' + (m_.group(1).replace('demo.Main#', '').replace('\n', ' ') if m_ else lg[-300:]))
bb2 = sbuild('x40f', {'src/demo/Main.java': BAD, 'logback.xml': LOG}, CP); r = srun(bb2, 'demo.Main', timeout=120); L = [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-600:]]
print('  GET /x/**/y(PathPattern 不允许 ** 在中间):' + L[0][:300])
