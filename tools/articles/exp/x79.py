import sys, os, re, time, json, shutil, subprocess, statistics, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x79')
CP = scp('org.springframework.boot:spring-boot-starter-webmvc', 'org.springframework.boot:spring-boot-starter-actuator')
LB = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*; import org.springframework.boot.health.contributor.*; import org.springframework.boot.availability.*; import org.springframework.context.ApplicationContext; import org.springframework.stereotype.Component; import java.util.concurrent.atomic.*;
@SpringBootApplication @RestController
public class Main {
  static volatile String STATUS = "UP"; static volatile long DELAY_MY = 0, DELAY_OTHER = 0; static final AtomicInteger CALLS = new AtomicInteger();
  @Component("myCheck") static class MyCheck implements HealthIndicator {
    public Health health() { CALLS.incrementAndGet(); try { Thread.sleep(DELAY_MY); } catch (Exception e) {} return Health.status(new Status(STATUS)).withDetail("note", "自定义检查").build(); } }
  @Component("other") static class Other implements HealthIndicator {
    public Health health() { try { Thread.sleep(DELAY_OTHER); } catch (Exception e) {} return Health.up().build(); } }
  final ApplicationContext ctx; Main(ApplicationContext c) { ctx = c; }
  @GetMapping("/set") String set(@RequestParam String s) { STATUS = s; return "myCheck=" + s; }
  @GetMapping("/delay") String delay(@RequestParam long my, @RequestParam long other) { DELAY_MY = my; DELAY_OTHER = other; return "ok"; }
  @GetMapping("/calls") String calls() { return String.valueOf(CALLS.get()); }
  @GetMapping("/reset") String reset() { CALLS.set(0); return "ok"; }
  @GetMapping("/ready") String ready(@RequestParam String s) { AvailabilityChangeEvent.publish(ctx, ReadinessState.valueOf(s)); return "readiness→" + s; }
  @GetMapping("/live") String live(@RequestParam String s) { AvailabilityChangeEvent.publish(ctx, LivenessState.valueOf(s)); return "liveness→" + s; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x79', {'src/demo/Main.java': MAIN, 'logback.xml': LB}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
BASE = {'management.endpoints.web.exposure.include': 'health', 'management.endpoint.health.show-details': 'always'}
def start(props=None, env=None):
    pr = dict(BASE); pr.update(props or {}); pr['server.port'] = free_port(); a = SApp(b, 'demo.Main', props=pr, port=pr['server.port'], env=env or {}).start(); time.sleep(0.3); return a
def g(app, path, timeout=20):
    t = time.time(); st, body, _ = app.get(path, timeout=timeout); return st, body, (time.time() - t) * 1000
def brief(body):
    try:
        j = json.loads(body); comp = j.get('components')
        return f'status={j.get("status")}' + (f',components={sorted(comp)}' if comp else '') + (f',groups={j["groups"]}' if 'groups' in j else '')
    except Exception: return body[:80]
def show(app, path):
    st, body, ms = g(app, path); print(f'    GET {path} → {st} {brief(body)}')
print('Spring Boot 4.0.8 / JDK 21;webmvc + actuator;自定义健康指示器 myCheck(状态可通过 /set 改)和 other;management.endpoint.health.show-details=always')
print('== 一:/actuator/health 里有什么,liveness / readiness 默认要不要打开')
app = start()
for p in ('/actuator/health', '/actuator/health/liveness', '/actuator/health/readiness', '/actuator/health/myCheck', '/actuator/health/nope'): show(app, p)
st, body, _ = g(app, '/actuator/health'); print('  /actuator/health 完整内容(去掉空白):' + ' '.join(body.split())[:520])
app.stop()
print('  -- 设置 management.endpoint.health.probes.enabled=false:')
app = start({'management.endpoint.health.probes.enabled': 'false'})
for p in ('/actuator/health', '/actuator/health/liveness'): show(app, p)
app.stop()
print('  -- 设置环境变量 KUBERNETES_SERVICE_HOST=1.2.3.4(模拟「在 K8s 里」):')
app = start(env={'KUBERNETES_SERVICE_HOST': '1.2.3.4'})
for p in ('/actuator/health', '/actuator/health/liveness', '/actuator/health/readiness'): show(app, p)
app.stop()
print('== 二:状态怎么聚合,HTTP 状态码是什么')
app = start()
for s in ('UP', 'DOWN', 'OUT_OF_SERVICE', 'UNKNOWN', 'MY_CUSTOM'):
    app.get(f'/set?s={s}'); st, body, _ = g(app, '/actuator/health'); print(f'  myCheck={s:<14} → /actuator/health 返回 HTTP {st},{brief(body).split(",components")[0]}')
app.stop()
print('  -- 自定义映射 management.endpoint.health.status.http-mapping.DOWN=500、http-mapping.MY_CUSTOM=202,order=DOWN,MY_CUSTOM,UP:')
app = start({'management.endpoint.health.status.http-mapping.DOWN': '500', 'management.endpoint.health.status.http-mapping.MY_CUSTOM': '202', 'management.endpoint.health.status.order': 'DOWN,MY_CUSTOM,UP'})
for s in ('DOWN', 'MY_CUSTOM', 'UP'):
    app.get(f'/set?s={s}'); st, body, _ = g(app, '/actuator/health'); print(f'  myCheck={s:<10} → HTTP {st},{brief(body).split(",components")[0]}')
app.stop()
print('== 三:业务检查失败,liveness / readiness 会不会跟着变')
app = start(); app.get('/set?s=DOWN')
print('  myCheck=DOWN,默认配置:')
for p in ('/actuator/health', '/actuator/health/liveness', '/actuator/health/readiness'): show(app, p)
app.stop()
app = start({'management.endpoint.health.group.readiness.include': 'readinessState,myCheck'}); app.get('/set?s=DOWN')
print('  myCheck=DOWN,management.endpoint.health.group.readiness.include=readinessState,myCheck:')
for p in ('/actuator/health/liveness', '/actuator/health/readiness'): show(app, p)
app.get('/set?s=UP'); print('    myCheck 改回 UP 之后:'); show(app, '/actuator/health/readiness')
app.stop()
app = start({'management.endpoint.health.group.custom.include': 'myCheck,other', 'management.endpoint.health.group.custom.show-details': 'never'}); print('  自定义分组 management.endpoint.health.group.custom.include=myCheck,other(show-details=never):')
for p in ('/actuator/health', '/actuator/health/custom'): show(app, p)
app.stop()
print('== 四:应用自己发布 AvailabilityChangeEvent')
app = start()
for q in ('/ready?s=REFUSING_TRAFFIC', '/live?s=BROKEN'):
    print(f'  {q} → {g(app, q)[1]}')
    for p in ('/actuator/health/liveness', '/actuator/health/readiness', '/actuator/health'):
        st, body, _ = g(app, p); print(f'    GET {p} → {st} {" ".join(body.split())[:170]}')
app.stop()
print('== 五:每次探针请求都会真的跑一遍检查')
app = start(); app.get('/reset')
for _ in range(5): g(app, '/actuator/health')
print(f'  默认:连续请求 /actuator/health 5 次,myCheck 被执行了 {g(app, "/calls")[1]} 次'); app.stop()
app = start({'management.endpoint.health.cache.time-to-live': '10s'}); app.get('/reset')
for _ in range(5): g(app, '/actuator/health')
print(f'  management.endpoint.health.cache.time-to-live=10s:连续请求 5 次,myCheck 被执行了 {g(app, "/calls")[1]} 次'); app.stop()
app = start(); app.get('/delay?my=1000&other=1000')
st, body, ms = g(app, '/actuator/health'); print(f'  myCheck 和 other 各慢 1000 ms:GET /actuator/health 用时 {ms:.0f} ms')
st, body, ms = g(app, '/actuator/health/liveness'); print(f'  同时 GET /actuator/health/liveness 用时 {ms:.0f} ms')
app.get('/delay?my=0&other=0'); app.stop()
