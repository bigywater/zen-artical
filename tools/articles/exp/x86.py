import sys, os, re, time, json, shutil, subprocess, statistics, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x86')
CP = scp('org.springframework.boot:spring-boot-starter-actuator', 'org.springframework.boot:spring-boot-starter-webmvc', 'org.springframework.boot:spring-boot-starter-aspectj', 'io.micrometer:micrometer-tracing-bridge-brave', 'org.springframework.boot:spring-boot-micrometer-tracing-brave')
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*; import org.springframework.context.annotation.Bean; import org.springframework.stereotype.Service; import io.micrometer.observation.*; import io.micrometer.observation.annotation.Observed; import io.micrometer.observation.aop.ObservedAspect; import io.micrometer.tracing.Tracer; import brave.handler.*; import brave.propagation.TraceContext; import java.util.*; import java.util.concurrent.*; import org.slf4j.*;
@SpringBootApplication @RestController
public class Main {
  static final Logger LOG = LoggerFactory.getLogger(Main.class); static final List<String> SPANS = new CopyOnWriteArrayList<>();
  final ObservationRegistry reg; final Tracer tracer; final Svc svc;
  Main(ObservationRegistry r, Tracer t, Svc s) { reg = r; tracer = t; svc = s; }
  @GetMapping("/work") String work() { LOG.info("处理 /work"); svc.call(); return "traceId=" + tracer.currentSpan().context().traceId(); }
  @GetMapping("/plain") String plain() { return "ok"; }
  @GetMapping("/manual") String manual(@RequestParam String type) { Observation.createNotStarted("order.process", reg).lowCardinalityKeyValue("type", type).highCardinalityKeyValue("orderId", UUID.randomUUID().toString().substring(0, 8)).observe(() -> { try { Thread.sleep(20); } catch (Exception e) {} }); return "ok"; }
  @GetMapping("/spans") String spans(@RequestParam(required = false) String prefix) { StringBuilder b = new StringBuilder(); for (String s : SPANS) if (prefix == null || s.startsWith(prefix)) b.append(s).append('\n'); return b.toString(); }
  @GetMapping("/clear") String clear() { SPANS.clear(); return "ok"; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
@org.springframework.context.annotation.Configuration class Beans {
  @Bean ObservedAspect observedAspect(ObservationRegistry r) { return new ObservedAspect(r); }
  @Bean SpanHandler capture() { return new SpanHandler() { public boolean end(TraceContext c, MutableSpan s, Cause cause) {
      TreeMap<String, String> tags = new TreeMap<>(); s.forEachTag((m, k, v) -> m.put(k, v), tags);
      Main.SPANS.add((s.name() + "|trace=" + c.traceIdString().substring(0, 8) + "|parent=" + (c.parentIdString() == null ? "-" : "有") + "|" + tags)); return true; } }; }
}
@Service class Svc { @Observed(name = "svc.call", contextualName = "svc-call", lowCardinalityKeyValues = {"layer", "service"}) public void call() { try { Thread.sleep(10); } catch (Exception e) {} } }
'''
b = sbuild('x86', {'src/demo/Main.java': MAIN}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def start(props=None):
    pr = {'management.endpoints.web.exposure.include': 'metrics', 'management.tracing.sampling.probability': '1.0', 'spring.application.name': 'demo', 'server.port': free_port()}; pr.update(props or {})
    a = SApp(b, 'demo.Main', props=pr, port=pr['server.port'], name='stdout'); a.start(); time.sleep(0.3); return a
def g(a, p): return a.get(p)[1]
def metric(a, name, tags=()):
    q = '/actuator/metrics/' + name + ('?' + '&'.join('tag=' + urllib.parse.quote(t, safe=':') for t in tags) if tags else ''); st, body, _ = a.get(q); return json.loads(body) if st == 200 else None
def tagvals(m): return {t['tag']: t['values'] for t in m['availableTags']} if m else None
def cnt(m): return next((x['value'] for x in m['measurements'] if x['statistic'] == 'COUNT'), None) if m else None
print('Spring Boot 4.0.8 / JDK 21;actuator + webmvc + aspectj + micrometer-tracing-bridge-brave;自己写了一个 SpanHandler 把结束的 span 收集起来;management.tracing.sampling.probability=1.0(除非另有说明)')
print('== 一:一个 HTTP 请求,同时得到指标和链路')
a = start(); r = g(a, '/work'); time.sleep(0.2)
print(f'  GET /work → {r}')
log = [l for l in a.log().splitlines() if '处理 /work' in l]; print('  日志行(Boot 默认格式里多了关联 id):' + (re.sub(r'^\S+\s+', '', log[0])[:200] if log else '(没有)'))
sp = g(a, '/spans').strip().splitlines(); print(f'  收集到的 span {len(sp)} 个:')
for s in sp: print('    ' + re.sub(r'\|trace=\w+', '|trace=…', s)[:230])
m = metric(a, 'http.server.requests', ['uri:/work']); print(f'  指标 http.server.requests?tag=uri:/work:COUNT {cnt(m):.0f},标签 {tagvals(m)}')
a.stop()
print('== 二:手动 Observation:低基数标签进指标,高基数标签只进 span')
a = start(); [g(a, f'/manual?type={t}') for t in ('a', 'a', 'b')]; time.sleep(0.2)
m = metric(a, 'order.process'); print(f'  指标 order.process:COUNT {cnt(m):.0f},标签 {tagvals(m)}')
sp = [s for s in g(a, '/spans?prefix=order').strip().splitlines()]; print(f'  span 个数 {len(sp)},每个 span 的标签:')
for s in sp: print('    ' + re.sub(r'\|trace=\w+', '|trace=…', s)[:200])
a.stop()
print('== 三:@Observed 注解(加 ObservedAspect Bean)')
a = start(); g(a, '/work'); g(a, '/work'); time.sleep(0.2)
m = metric(a, 'svc.call'); print(f'  指标 svc.call:COUNT {cnt(m):.0f},标签 {tagvals(m)}')
sp = [s for s in g(a, '/spans?prefix=svc').strip().splitlines()]; print(f'  span svc-call 个数 {len(sp)},第 1 个:' + re.sub(r'\|trace=\w+', '|trace=…', sp[0])[:220])
allsp = g(a, '/spans').strip().splitlines(); names = collections_names = sorted({s.split('|')[0] for s in allsp}); print(f'  全部 span 名字:{names}')
a.stop()
print('== 四:采样与开关(发 100 个 /plain 请求之后)')
def start_nop(props=None):
    pr = {'management.endpoints.web.exposure.include': 'metrics', 'spring.application.name': 'demo', 'server.port': free_port()}; pr.update(props or {})
    a = SApp(b, 'demo.Main', props=pr, port=pr['server.port'], name='stdout'); a.start(); time.sleep(0.3); return a
for lab, mk in (('management.tracing.sampling.probability 不设(默认)', lambda: start_nop()), ('probability=1.0', lambda: start()), ('probability=0.0', lambda: start({'management.tracing.sampling.probability': '0.0'})), ('probability=1.0 且 management.observations.enable.svc.call=false', lambda: start({'management.observations.enable.svc.call': 'false'}))):
    a = mk()
    for _ in range(100): g(a, '/plain')
    if 'svc.call' in lab: [g(a, '/work') for _ in range(5)]
    time.sleep(0.3); sp = g(a, '/spans').strip().splitlines(); m = metric(a, 'http.server.requests', ['uri:/plain']); svc = metric(a, 'svc.call')
    print(f'  {lab}:/plain 的 span {sum(1 for s in sp if "plain" in s.split("|")[0])} 个;http.server.requests?uri=/plain 的 COUNT {cnt(m):.0f}' + (f';5 次 /work 之后 svc.call 指标 {("COUNT %d" % cnt(svc)) if svc else "没有这个指标"},svc-call 的 span {sum(1 for s in sp if s.startswith("svc"))} 个,http get /work 的 span {sum(1 for s in sp if s.startswith("http get /work"))} 个' if 'svc.call' in lab else ''))
    a.stop()
