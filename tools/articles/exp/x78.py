import sys, os, re, time, json, shutil, subprocess, statistics, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x78')
CP_ACT = scp('org.springframework.boot:spring-boot-starter-webmvc', 'org.springframework.boot:spring-boot-starter-actuator'); CP_NO = scp('org.springframework.boot:spring-boot-starter-webmvc')
src60 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'x60.py')).read(); LOADGEN = re.search(r"LOADGEN = r'''(.*?)'''", src60, re.S).group(1)
LB = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*;
@SpringBootApplication @RestController
public class Main {
  @GetMapping("/fast") String fast() { return "ok"; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x78', {'src/demo/Main.java': MAIN, 'src/demo/Load.java': LOADGEN, 'logback.xml': LB}, CP_ACT)
if b['crc'] != 0: print(b['cout']); sys.exit()
bn = dict(b, cp=CP_NO)
BASE = {'app.name': 'demo', 'app.password': 'p@ssw0rd', 'app.token': 'tok-123', 'app.url': 'http://example.com'}
def start(props=None, bb=b, base=True, **kw):
    pr = dict(BASE) if base else {}; pr.update(props or {}); pr.setdefault('server.port', free_port()); return SApp(bb, 'demo.Main', props=pr, port=pr['server.port'], **kw).start()
def get(app, path, port=None, method='GET'):
    st, body, h = app.get(path, port=port, method=method); return st, body, h
def short(s, n=150): s = ' '.join(s.split()); return s if len(s) <= n else s[:n] + '…'
print('Spring Boot 4.0.8 / JDK 21;应用 = webmvc + actuator,系统属性里放了 app.name=demo、app.password=p@ssw0rd、app.token=tok-123、app.url=http://example.com 用来看 /env 的脱敏')
print('== 一:什么都不配时,通过 HTTP 能访问哪些端点')
app = start(); st, body, _ = get(app, '/actuator'); j = json.loads(body)
print(f'  GET /actuator → {st};links = {sorted(k for k in j["_links"])}')
for p in ('/actuator/health', '/actuator/info', '/actuator/env', '/actuator/metrics', '/actuator/beans', '/actuator/heapdump'):
    st, body, _ = get(app, p); print(f'  GET {p} → {st}  {short(body, 70)}')
app.stop()
print('== 二:management.endpoints.web.exposure.include=* 之后')
app = start({'management.endpoints.web.exposure.include': '*'}); st, body, _ = get(app, '/actuator'); j = json.loads(body); ids = sorted(k for k in j['_links'] if k != 'self')
print(f'  GET /actuator → {st};共 {len(j["_links"])} 个链接(含 self);端点:{ids}')
for p in ('/actuator/env', '/actuator/beans', '/actuator/mappings', '/actuator/threaddump', '/actuator/configprops', '/actuator/loggers', '/actuator/conditions', '/actuator/heapdump'):
    t = time.time(); st, body, _ = get(app, p); print(f'  GET {p} → {st},{len(body) / 1024:.0f} KB,{(time.time() - t) * 1000:.0f} ms')
st, body, _ = get(app, '/actuator/shutdown', method='POST'); print(f'  POST /actuator/shutdown → {st}  {short(body, 70)}')
app.stop()
print('  -- 额外加 management.endpoint.heapdump.access=unrestricted:')
app = start({'management.endpoints.web.exposure.include': '*', 'management.endpoint.heapdump.access': 'unrestricted'}); st, body, _ = get(app, '/actuator'); j = json.loads(body)
print(f'  /actuator 里有 heapdump:{"heapdump" in j["_links"]}')
c = http.client.HTTPConnection('127.0.0.1', app.props['server.port'], timeout=120); t = time.time(); c.request('GET', '/actuator/heapdump'); r = c.getresponse(); n = len(r.read()); print(f'  GET /actuator/heapdump → {r.status},Content-Type {r.getheader("Content-Type")},{n / 1024 / 1024:.1f} MB,{(time.time() - t) * 1000:.0f} ms;请求里没有带任何认证信息')
app.stop()
print('  -- 暴露了但把访问权限关掉:management.endpoint.env.access=none、management.endpoint.shutdown.access=unrestricted')
app = start({'management.endpoints.web.exposure.include': '*', 'management.endpoint.env.access': 'none', 'management.endpoint.shutdown.access': 'unrestricted'}); st, body, _ = get(app, '/actuator'); j = json.loads(body)
print(f'  /actuator 里有 env:{"env" in j["_links"]};有 shutdown:{"shutdown" in j["_links"]}')
st, body, _ = get(app, '/actuator/env'); print(f'  GET /actuator/env → {st}')
st, body, _ = get(app, '/actuator/shutdown', method='POST'); print(f'  POST /actuator/shutdown → {st}  {short(body, 70)}'); time.sleep(3); print(f'  shutdown 之后 3 秒,java 进程 {"已退出,退出码 %s" % app.p.poll() if app.p.poll() is not None else "还在运行"}')
app.stop()
print('== 三:/actuator/env 里的敏感值')
def envrow(app):
    for k in ('app.name', 'app.password', 'app.token', 'app.url'):
        st, body, _ = get(app, f'/actuator/env/{k}'); jj = json.loads(body); p = jj.get('property', {}); print(f'    {k} → {st},值 {p.get("value")!r},来源 {p.get("source")}')
app = start({'management.endpoints.web.exposure.include': 'env'}); print('  默认(management.endpoint.env.show-values 不设):'); envrow(app)
app.stop()
app = start({'management.endpoints.web.exposure.include': 'env', 'management.endpoint.env.show-values': 'ALWAYS'}); print('  management.endpoint.env.show-values=ALWAYS:'); envrow(app)
app.stop()
app = start({'management.endpoints.web.exposure.include': 'env', 'management.endpoint.env.show-values': 'WHEN_AUTHORIZED'}); print('  management.endpoint.env.show-values=WHEN_AUTHORIZED(没有装 Spring Security):'); envrow(app); app.stop()
print('== 四:单独的管理端口与基础路径')
mp = free_port(); app = start({'management.server.port': mp, 'management.endpoints.web.exposure.include': 'health'})
t_main = time.time(); h1 = None; refused = 0
while time.time() - t_main < 10:
    try: h1 = get(app, "/actuator/health", port=mp); break
    except OSError: refused += 1; time.sleep(0.005)
t_first = (time.time() - t_main) * 1000; time.sleep(2); h2 = get(app, "/actuator/health", port=mp)
print(f'  management.server.port={mp}:业务端口 GET /actuator/health → {get(app, "/actuator/health")[0]};管理端口 GET /fast → {get(app, "/fast", port=mp)[0]};管理端口 GET /actuator/health:业务端口可连接之后又过了 {t_first:.0f} ms 才连得上管理端口(此前连接被拒绝 {refused} 次),第一次响应 → {h1[0]} {short(h1[1], 60)},2 秒后 → {h2[0]} {short(h2[1], 60)}')
app.stop()
app = start({'management.endpoints.web.base-path': '/ops', 'management.endpoints.web.exposure.include': 'health'}); print(f'  management.endpoints.web.base-path=/ops:/actuator/health → {get(app, "/actuator/health")[0]};/ops/health → {get(app, "/ops/health")[0]}'); app.stop()
print('== 五:装了 actuator 之后的开销')
def trial(bb, props=None):
    pr = {'server.port': free_port()}; pr.update(props or {}); a = SApp(bb, 'demo.Main', props=pr, port=pr['server.port']); t0 = time.time(); a.start(timeout=60); up = (time.time() - t0) * 1000; a.get('/fast'); r = a.rss_mb(); a.stop(); return up, r
for lab, bb, props in (('没有 actuator', bn, None), ('有 actuator(默认)', b, None)):
    rs = [trial(bb, props) for _ in range(7)]; print(f'  {lab}:启动到端口可连接 中位 {statistics.median(r[0] for r in rs):.0f} ms(范围 {min(r[0] for r in rs):.0f}~{max(r[0] for r in rs):.0f});启动后常驻内存中位 {statistics.median(r[1] for r in rs):.0f} MB')
