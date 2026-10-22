import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x42'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.math.BigDecimal; import java.time.*; import java.util.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.http.*; import org.springframework.web.bind.annotation.*;
@SpringBootApplication @RestController
public class Main {
  public enum Color { RED, GREEN }
  public record Sample(LocalDate day, LocalDateTime dt, Instant at, ZonedDateTime zdt, Date legacy, Long big, BigDecimal dec, double d, Color color, String nul, Optional<String> opt, List<String> emptyList) { }
  public record In(LocalDate day, LocalDateTime dt, Instant at, Date legacy, Long big, Color color) { }
  @GetMapping("/sample") Sample sample() { return new Sample(LocalDate.of(2026, 10, 19), LocalDateTime.of(2026, 10, 19, 14, 30, 5), Instant.parse("2026-10-19T06:30:05Z"), ZonedDateTime.of(2026, 10, 19, 14, 30, 5, 0, ZoneId.of("Asia/Shanghai")), new Date(1792391405000L), 9007199254740993L, new BigDecimal("12345678901234567890.12"), 0.1 + 0.2, Color.GREEN, null, Optional.empty(), List.of()); }
  @PostMapping("/in") String in(@RequestBody In i) { return "收到 " + i; }
  @GetMapping("/text") String text() { return "中文 ok"; }
  @GetMapping(value = "/xml-only", produces = "application/xml") String xml() { return "<a/>"; }
  @RestControllerAdvice public static class Adv extends org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler {
    @Override protected ResponseEntity<Object> handleExceptionInternal(Exception e, Object body, HttpHeaders h, HttpStatusCode st, org.springframework.web.context.request.WebRequest rq) { return ResponseEntity.status(st).body(e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()).split("\n")[0].replace("demo.Main$", "")); } }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x42', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def start(props=None): return SApp(b, 'demo.Main', props=props or {}).start()
JSON = {'Content-Type': 'application/json'}
print('Spring Boot 4.0.8 / Spring MVC 7.0.9。HttpMessageConverter 与 Jackson(Boot 4 默认的 JSON 转换器是 JacksonJsonHttpMessageConverter,即 Jackson 3)')
app = start()
print('== 一:序列化:GET /sample 的响应(同一个 record 里各种类型)')
s, d, h = app.get('/sample'); j = json.loads(d, parse_float=lambda x: 'F:' + x, parse_int=lambda x: 'I:' + x)
for k_, v in j.items(): print(f'  {k_:<10} → ' + ('(JSON 数字) ' + v[2:] if isinstance(v, str) and v[:2] in ('F:', 'I:') else json.dumps(v, ensure_ascii=False)))
print(f'  响应头 Content-Type: {h.get("Content-Type")}')
print('  说明:Java 里 big=9007199254740993L,在 JSON 里写成了数字,JavaScript 的 JSON.parse 会把它读成 9007199254740992(超过 2^53 的整数丢精度)。下面用 Python 的 float 模拟:float(9007199254740993) = ' + str(int(float(9007199254740993))))
print('== 二:反序列化 POST /in:各种日期等写法')
cases = [('正常', '{"day":"2026-10-19","dt":"2026-10-19T14:30:05","at":"2026-10-19T06:30:05Z","legacy":"2026-10-19T06:30:05.000+00:00","big":1,"color":"RED"}'), ('day 写成 2026/10/19', '{"day":"2026/10/19"}'), ('day 写成时间戳数字', '{"day":1792391405000}'), ('dt 带时区后缀 Z', '{"dt":"2026-10-19T14:30:05Z"}'), ('at 写成秒级数字', '{"at":1792391405}'), ('at 写成毫秒级数字', '{"at":1792391405000}'), ('legacy 写成毫秒数字', '{"legacy":1792391405000}'), ('color 写小写 red', '{"color":"red"}'), ('color 写不存在的 BLUE', '{"color":"BLUE"}'), ('未知字段 extra', '{"extra":1}'), ('big 写成字符串 "123"', '{"big":"123"}'), ('big 写成小数 1.5', '{"big":1.5}')]
for lab, body in cases:
    s, d, h = app.get('/in', method='POST', body=body, headers=JSON); print(f'  {lab} → {s} {d.strip()[:170]}')
print('== 三:String 返回值与协商')
s, d, h = app.get('/text'); print(f'  GET /text → {s} {d.strip()} Content-Type: {h.get("Content-Type")}')
s, d, h = app.get('/sample', headers={'Accept': 'application/xml'}); print(f'  GET /sample Accept: application/xml → {s}')
s, d, h = app.get('/xml-only'); print(f'  GET /xml-only(produces application/xml,返回 String)→ {s} {d.strip()[:30]} Content-Type: {h.get("Content-Type")}')
app.stop()
print('== 四:用配置改默认行为')
for props in ({'spring.jackson.default-property-inclusion': 'non_null'}, {'spring.jackson.datatype.datetime.write-dates-as-timestamps': 'true'}):
    ap = start(props); s, d, h = ap.get('/sample'); j = json.loads(d); ap.stop()
    k_ = list(props)[0]; print(f'  {k_}={props[k_]}:字段 {list(j.keys())};day={json.dumps(j.get("day"))},at={json.dumps(j.get("at"))},legacy={json.dumps(j.get("legacy"))}')
LOGE = '<configuration><appender name="O" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>LOG %level %logger{0}: %msg%n</pattern></encoder></appender><root level="ERROR"><appender-ref ref="O"/></root></configuration>'
be = sbuild('x42e', {'src/demo/Main.java': MAIN, 'logback.xml': LOGE}, CP); r = srun(be, 'demo.Main', props={'spring.jackson.serialization.write-dates-as-timestamps': 'true', 'server.port': 0}, timeout=40)
m_ = re.search(r'(Failed to bind properties under [^\n]+)\n\s*\n\s*Reason: ([^\n]+)', r['out']); print('  spring.jackson.serialization.write-dates-as-timestamps=true(Jackson 2 时代的写法)→ 启动失败:' + (m_.group(1).replace('tools.jackson.databind.', '') + ';' + m_.group(2).replace('tools.jackson.databind.', '')[:260] if m_ else r['out'][-300:]))
