import sys, os, re, time, json, threading, socket, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x54'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.tomcat.autoconfigure.TomcatServerProperties;
import org.springframework.web.bind.annotation.*;
@SpringBootApplication @RestController
public class Main {
  final TomcatServerProperties sp; Main(TomcatServerProperties s) { sp = s; }
  @GetMapping("/slow") String slow(@RequestParam long ms) throws Exception { Thread.sleep(ms); return "slow-" + ms; }
  @GetMapping("/fast") String fast() { return "fast"; }
  @GetMapping("/conf") String conf() { var t = sp; return "threads.max=" + t.getThreads().getMax() + " threads.min-spare=" + t.getThreads().getMinSpare() + " max-connections=" + t.getMaxConnections() + " accept-count=" + t.getAcceptCount() + " connection-timeout=" + t.getConnectionTimeout(); }
  @GetMapping("/threads") String threads() { long n = Thread.getAllStackTraces().keySet().stream().filter(t -> t.getName().startsWith("http-nio") && t.getName().contains("-exec-")).count(); return "exec 线程数=" + n; }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x54', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def one(port, path, tmo=10):
    t0 = time.time(); c = http.client.HTTPConnection('127.0.0.1', port, timeout=tmo)
    ph = '连接阶段'
    try:
        c.connect(); tc = time.time() - t0; ph = '发请求阶段'; c.request('GET', path); ph = '等响应阶段'; r = c.getresponse(); d = r.read().decode(); return ('ok', round(tc * 1000), round((time.time() - t0) * 1000), r.status)
    except Exception as e: return (type(e).__name__ + '@' + ph, round((time.time() - t0) * 1000), round((time.time() - t0) * 1000), None)
    finally: c.close()
def burst(app, n, path, probe_after=0.3, tmo=10):
    port = int(app.props['server.port']); res = [None] * n; ths = []
    def w(i): res[i] = one(port, path, tmo)
    t0 = time.time()
    for i in range(n): th = threading.Thread(target=w, args=(i,)); th.start(); ths.append(th)
    time.sleep(probe_after); pr = one(port, '/fast', tmo); s, d, h = (app.get('/threads', timeout=tmo) if pr[0] == 'ok' else (0, '?', {}))
    for th in ths: th.join()
    return res, pr, d
def report(res, pr, d, n):
    ok = [r for r in res if r[0] == 'ok']; bad = [r for r in res if r[0] != 'ok']
    print(f'  {n} 个并发请求:成功 {len(ok)},失败 {len(bad)}' + (f'({sorted(set(r[0] for r in bad))})' if bad else ''))
    print('      成功请求的总耗时(ms,从小到大):' + str(sorted(r[2] for r in ok)))
    print('      成功请求建立 TCP 连接的耗时(ms,从小到大):' + str(sorted(r[1] for r in ok)))
    if bad: print('      失败请求的耗时(ms):' + str(sorted(r[2] for r in bad)))
    print(f'      压力期间另发一个 /fast:{pr[0]},总耗时 {pr[2]} ms,状态 {pr[3]};{d}')
def run(props, f, title):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}'); f(app); app.stop()
print('Spring Boot 4.0.8 / Tomcat 11.0.24(NIO),macOS 上本机回环;/slow 在服务端睡指定毫秒数。客户端用线程同时发请求,连接超时与读超时都是 10 秒')
def one_(app): s, d, h = app.get('/conf'); print('  ' + d)
run({}, one_, '一:Boot 默认的 Tomcat 线程池参数(从 TomcatServerProperties 读出)')
def two(app):
    res, pr, d = burst(app, 8, '/slow?ms=1000'); report(res, pr, d, 8)
run({'server.tomcat.threads.max': '2', 'server.tomcat.threads.min-spare': '2'}, two, '二:threads.max=2:8 个并发请求(每个处理 1000 ms)')
def three(app):
    from collections import Counter
    port = int(app.props['server.port'])
    for rnd in range(3):
        n = 12; res = [None] * n
        def w(i): res[i] = one(port, '/slow?ms=1000')
        ths = [threading.Thread(target=w, args=(i,)) for i in range(n)]; [t.start() for t in ths]; [t.join() for t in ths]
        c = Counter(('成功' if r[0] == 'ok' else '失败:' + r[0]) for r in res); mx = max([r[2] for r in res if r[0] == 'ok'] or [0])
        print(f'    第 {rnd + 1} 轮:12 个同时发起的请求 → {dict(c)};成功的里最慢的总耗时 {mx} ms;失败请求耗时最长 {max([r[2] for r in res if r[0] != "ok"] or [0])} ms'); time.sleep(1.5)
for mc, ac in [(4, 2), (4, 5), (4, 8), (4, 100), (100, 2)]:
    if (mc, ac) == (4, 2): print('== 三:连接数超过上限时的行为:threads.max=2,12 个请求同时发起(每个处理 1000 ms),max-connections 与 accept-count 的组合,每个组合连做 3 轮')
    print(f'  max-connections={mc}、accept-count={ac}:')
    app = SApp(b, 'demo.Main', {'server.tomcat.threads.max': '2', 'server.tomcat.threads.min-spare': '2', 'server.tomcat.max-connections': str(mc), 'server.tomcat.accept-count': str(ac)}).start(); three(app); app.stop()
def five(app):
    res, pr, d = burst(app, 8, '/slow?ms=1000', tmo=10); report(res, pr, d, 8)
run({'server.tomcat.threads.max': '2', 'server.tomcat.threads.min-spare': '2', 'server.tomcat.max-connections': '100', 'server.tomcat.accept-count': '100', 'server.tomcat.connection-timeout': '1500ms'}, five, '四:threads.max=2,connection-timeout=1500ms:排在队里等线程的请求会不会被这个超时踢掉')
