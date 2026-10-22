import sys, os, re, time, json, shutil, subprocess, statistics, collections, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x80')
CP = scp('org.springframework.boot:spring-boot-starter-webmvc', 'org.springframework.boot:spring-boot-starter-actuator', 'io.micrometer:micrometer-registry-prometheus')
LB = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*; import io.micrometer.core.instrument.*; import io.micrometer.core.instrument.config.MeterFilter; import java.util.concurrent.atomic.*; import java.time.Duration; import jakarta.annotation.PostConstruct;
@SpringBootApplication @RestController
public class Main {
  final MeterRegistry reg; final AtomicInteger queue = new AtomicInteger(7); static double W0, W1;
  @GetMapping("/weak") String weak() { return "注册后立刻读 = " + W0 + ";紧接着两次 System.gc() 之后读 = " + W1; }
  Main(MeterRegistry r) { reg = r; }
  @PostConstruct void init() {
    reg.config().meterFilter(MeterFilter.maximumAllowableTags("capped.ids", "id", 100, MeterFilter.deny()));
    Gauge.builder("queue.size", queue, AtomicInteger::get).register(reg);       // 强引用:queue 是字段
    reg.gauge("weak.demo", Tags.empty(), new AtomicInteger(42));                // 弱引用:没有任何别处持有这个对象
    W0 = reg.get("weak.demo").gauge().value(); System.gc(); System.gc(); W1 = reg.get("weak.demo").gauge().value();
  }
  @GetMapping("/fast") String fast() { return "ok"; }
  @GetMapping("/user/{id}") String user(@PathVariable String id) { return "u" + id; }
  @GetMapping("/boom") String boom() { throw new IllegalStateException("boom"); }
  @GetMapping("/order") String order(@RequestParam String type) { Counter.builder("orders.created").tag("type", type).description("created orders").register(reg).increment(); return "ok"; }
  @GetMapping("/work") String work(@RequestParam long ms) throws Exception { Timer t = Timer.builder("work.duration").publishPercentileHistogram(false).register(reg); t.record(() -> { try { Thread.sleep(ms); } catch (Exception e) {} }); return "ok"; }
  @GetMapping("/size") String size(@RequestParam long bytes) { DistributionSummary.builder("payload.size").baseUnit("bytes").register(reg).record(bytes); return "ok"; }
  @GetMapping("/queue") String q(@RequestParam int n) { queue.set(n); return "ok"; }
  @GetMapping("/gc") String gc() { System.gc(); System.gc(); return "ok"; }
  static long used() { System.gc(); System.gc(); Runtime r = Runtime.getRuntime(); return r.totalMemory() - r.freeMemory(); }
  @GetMapping("/many") String many(@RequestParam String name, @RequestParam int n) {
    long before = used(); int m0 = reg.getMeters().size(); long t = System.nanoTime();
    for (int i = 0; i < n; i++) Counter.builder(name).tag("id", "u" + i).register(reg).increment();
    long ms = (System.nanoTime() - t) / 1_000_000; long after = used();
    return "创建 " + n + " 个同名不同 id 标签的 Counter(" + name + "):Meter 总数 " + m0 + " → " + reg.getMeters().size() + ",用时 " + ms + " ms,GC 之后堆占用 " + (before / 1048576) + " MB → " + (after / 1048576) + " MB";
  }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x80', {'src/demo/Main.java': MAIN, 'logback.xml': LB}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
pr = {'management.endpoints.web.exposure.include': 'health,metrics,prometheus', 'server.port': free_port()}
app = SApp(b, 'demo.Main', props=pr, port=pr['server.port'], jopts=['-Xmx1g']).start(); time.sleep(0.5)
def g(path): return app.get(path, timeout=120)
def js(path): st, body, _ = g(path); return st, (json.loads(body) if st == 200 and body.startswith('{') else body)
def names(): return js('/actuator/metrics')[1]['names']
def metric(name, tags=()):
    q = '/actuator/metrics/' + name + ('?' + '&'.join('tag=' + urllib.parse.quote(t, safe=':') for t in tags) if tags else ''); return js(q)
def group(ns):
    c = collections.Counter(n.split('.')[0] for n in ns); return ', '.join(f'{k}×{v}' for k, v in sorted(c.items()))
n0 = names()
for p in ('/fast', '/user/1'): g(p)
n1 = names()
for i in range(30): g(f'/user/{i}')
for i in range(30): g(f'/nope/{i}')
for _ in range(5): g('/boom')
for t in ('a', 'a', 'b'): g(f'/order?type={t}')
for ms in (10, 30, 20): g(f'/work?ms={ms}')
for by in (100, 300, 200): g(f'/size?bytes={by}')
weak = g('/weak')[1]; q1 = metric('queue.size')[1]['measurements'][0]['value']
g('/queue?n=3'); q2 = metric('queue.size')[1]['measurements'][0]['value']
t = time.time(); st, prom0, _ = g('/actuator/prometheus'); prom0_ms = (time.time() - t) * 1000
manyres = [g('/many?name=many.ids&n=100000')[1], g('/many?name=capped.ids&n=100000')[1]]
t = time.time(); st, prom1, _ = g('/actuator/prometheus'); prom1_ms = (time.time() - t) * 1000
print('Spring Boot 4.0.8 / JDK 21 / -Xmx1g;webmvc + actuator + micrometer-registry-prometheus(Boot 管理版本);暴露 health、metrics、prometheus')
print('== 一:自带了哪些指标')
print(f'  刚启动、还没有任何请求:/actuator/metrics 共 {len(n0)} 个指标名;按第一段分组:{group(n0)}')
print(f'  发过 2 个请求之后:{len(n1)} 个;多出来的:{sorted(set(n1) - set(n0))}')
for pre in ('jvm.memory', 'jvm.gc', 'jvm.threads', 'process', 'system', 'tomcat', 'executor', 'disk', 'logback', 'application', 'http'):
    xs = [n for n in n1 if n.startswith(pre)]; print(f'  {pre}*:{len(xs)} 个,例如 {xs[:4]}')
print('== 二:http.server.requests 的标签(发了 31 个 /user/{id}、30 个不存在的 /nope/{i}、5 个抛异常的 /boom 之后)')
r = metric('http.server.requests')[1]; print(f'  总次数(COUNT)= {next(m["value"] for m in r["measurements"] if m["statistic"] == "COUNT"):.0f};统计量 {[m["statistic"] for m in r["measurements"]]};baseUnit={r.get("baseUnit")}')
for t in r['availableTags']: print(f'  标签 {t["tag"]}:{len(t["values"])} 个取值 {t["values"] if len(t["values"]) <= 12 else t["values"][:12]}')
for q in (['uri:/user/{id}'], ['status:404'], ['outcome:SERVER_ERROR'], ['uri:/**'], ['uri:/nope/1']):
    rr = metric('http.server.requests', q)[1]; print(f'  tag={q[0]} → COUNT {next(m["value"] for m in rr["measurements"] if m["statistic"] == "COUNT"):.0f}' if isinstance(rr, dict) else f'  tag={q[0]} → {rr}')
rr = metric('http.server.requests', ['status:500'])[1]; print('  tag=status:500 的 exception 标签取值:' + str([t['values'] for t in rr['availableTags'] if t['tag'] == 'exception']))
print('== 三:自定义指标')
for nm in ('orders.created', 'work.duration', 'payload.size'):
    rr = metric(nm)[1]; print(f'  {nm}:baseUnit={rr.get("baseUnit")},{[(m["statistic"], round(m["value"], 3)) for m in rr["measurements"]]},标签 {[(t["tag"], t["values"]) for t in rr["availableTags"]]}')
print(f'  orders.created?tag=type:a → COUNT {metric("orders.created", ["type:a"])[1]["measurements"][0]["value"]:.0f}')
print(f'  Gauge queue.size(Gauge.builder 引用字段 queue):{q1:.0f};g(/queue?n=3) 之后 → {q2:.0f}')
print(f'  Gauge weak.demo(reg.gauge("weak.demo", Tags.empty(), new AtomicInteger(42)),没有任何地方持有这个对象):{weak};后来通过 /actuator/metrics/weak.demo 读 = {metric("weak.demo")[1]["measurements"][0]["value"]}')
print('== 四:标签的基数')
for l in manyres: print('  ' + l)
print('== 五:Prometheus 抓取')
lines0 = prom0.splitlines(); lines1 = prom1.splitlines()
print(f'  抓取前(Meter 数较少):/actuator/prometheus 共 {len(lines0)} 行,{len(prom0) / 1024:.0f} KB,用时 {prom0_ms:.0f} ms')
print(f'  创建了 100000 个 many.ids 之后:{len(lines1)} 行,{len(prom1) / 1024:.0f} KB,用时 {prom1_ms:.0f} ms')
for pat in (r'^# TYPE jvm_memory_used_bytes', r'^jvm_memory_used_bytes\{area="heap"', r'^# TYPE http_server_requests_seconds', r'^http_server_requests_seconds_count\{[^}]*uri="/user/\{id\}"', r'^(# TYPE )?orders_', r'^# TYPE work_duration', r'^work_duration_seconds_(count|sum|max)', r'^payload_size_bytes_(count|sum|max)', r'^queue_size'):
    ls = [l for l in lines0 if re.search(pat, l)]; print('  ' + (' | '.join(l[:150] for l in ls[:4]) if ls else f'(没有匹配 {pat})'))
app.stop()
