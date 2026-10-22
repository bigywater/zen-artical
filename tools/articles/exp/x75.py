import sys, os, re, time, json, shutil, subprocess, statistics, socket, threading, urllib.request; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x75')
CP_TC = scp('org.springframework.boot:spring-boot-starter-webmvc')
CP_BOTH = scp('org.springframework.boot:spring-boot-starter-webmvc', 'org.springframework.boot:spring-boot-starter-jetty')
def strip_tomcat(cp): return ':'.join(p for p in cp.strip().split(':') if not os.path.basename(p).startswith(('tomcat-embed', 'spring-boot-tomcat', 'spring-boot-starter-tomcat')))
CP_JT = strip_tomcat(CP_BOTH)
src60 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'x60.py')).read(); LOADGEN = re.search(r"LOADGEN = r'''(.*?)'''", src60, re.S).group(1)
LB = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*; import org.springframework.context.ApplicationContext; import jakarta.servlet.http.HttpServletRequest; import java.util.*;
@SpringBootApplication @RestController
public class Main {
  @GetMapping("/fast") String fast() { return "ok"; }
  @GetMapping("/slow50") String slow() throws Exception { Thread.sleep(50); return "ok"; }
  @GetMapping("/thread") String thread() { Thread t = Thread.currentThread(); return "name=[" + t.getName() + "] virtual=" + t.isVirtual(); }
  final ApplicationContext c; Main(ApplicationContext c) { this.c = c; }
  @GetMapping("/info") String info() throws Exception {
    List<String> f = new ArrayList<>(); for (String n : c.getBeanDefinitionNames()) if (n.contains("ServletWebServerFactory")) f.add(n);
    String v; try { v = "Tomcat " + Class.forName("org.apache.catalina.util.ServerInfo").getMethod("getServerNumber").invoke(null); } catch (Throwable e) { v = null; }
    if (v == null) try { v = "Jetty " + Class.forName("org.eclipse.jetty.util.Jetty").getField("VERSION").get(null); } catch (Throwable e) { v = "?"; }
    return "factory Bean=" + f + ";本次请求的处理线程=" + Thread.currentThread().getName() + ";classpath 上能加载到的容器类:" + v;
  }
  @GetMapping("/h") String h(@RequestHeader(value = "X-Big", required = false) String v) { return "len=" + (v == null ? 0 : v.length()); }
  @GetMapping("/echo/**") String echo(HttpServletRequest r) { return "uri=" + r.getRequestURI() + " servletPath=" + r.getServletPath() + " pathInfo=" + r.getPathInfo(); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x75', {'src/demo/Main.java': MAIN, 'src/demo/Load.java': LOADGEN, 'logback.xml': LB}, CP_TC)
if b['crc'] != 0: print(b['cout']); sys.exit()
VARIANTS = {'Tomcat': CP_TC, 'Jetty': CP_JT, 'Tomcat+Jetty 都在 classpath': CP_BOTH}
def bb(name): return dict(b, cp=VARIANTS[name])
def jars(cp): return [p for p in cp.strip().split(':') if p]
print('Spring Boot 4.0.8 / JDK 21;同一份应用代码(webmvc,一个 RestController),只换 classpath 上的内嵌容器')
print('== 一:classpath 上有什么')
for name in ('Tomcat', 'Jetty'):
    js = jars(VARIANTS[name]); size = sum(os.path.getsize(p) for p in js if os.path.exists(p)) / 1024 / 1024
    srv = sorted(os.path.basename(p).replace('.jar', '') for p in js if re.search(r'tomcat|jetty', os.path.basename(p)))
    print(f'  {name}:classpath 共 {len(js)} 个 jar,合计 {size:.1f} MB;名字里带 tomcat / jetty 的 {len(srv)} 个:')
    for s in srv: print('      ' + s)
for name in VARIANTS:
    app = SApp(bb(name), 'demo.Main').start(); st, body, _ = app.get('/info'); app.stop(); print(f'  {name} → {body}')
def maven_latest(artifact):
    req = urllib.request.Request(f'https://repo1.maven.org/maven2/org/springframework/boot/{artifact}/maven-metadata.xml'); op = urllib.request.build_opener(urllib.request.ProxyHandler({'https': 'http://127.0.0.1:1087'}))
    try: t = op.open(req, timeout=30).read().decode(); return re.search(r'<release>([^<]+)</release>', t).group(1)
    except Exception as e: return f'查询失败 {e!r}'
print(f'  Maven Central 上 spring-boot-starter-undertow 的最新版本:{maven_latest("spring-boot-starter-undertow")}(查询时 4.0.8 的这个 pom 返回 404);spring-boot-starter-jetty 最新:{maven_latest("spring-boot-starter-jetty")}')
print('== 二:启动时间、内存、第一次请求(各 7 次取中位数)')
def trial(name, props=None, jopts=()):
    app = SApp(bb(name), 'demo.Main', props=props or {}, jopts=list(jopts)); t0 = time.time(); app.start(timeout=60); up = (time.time() - t0) * 1000
    r0 = app.rss_mb(); t1 = time.time(); app.get('/fast'); first = (time.time() - t1) * 1000; t2 = time.time(); app.get('/fast'); second = (time.time() - t2) * 1000; r1 = app.rss_mb(); app.stop(); return up, first, second, r0, r1
for name in ('Tomcat', 'Jetty'):
    rs = [trial(name) for _ in range(7)]; m = lambda i: statistics.median(r[i] for r in rs)
    print(f'  {name}:端口可连接 中位 {m(0):.0f} ms(范围 {min(r[0] for r in rs):.0f}~{max(r[0] for r in rs):.0f});第 1 次请求 {m(1):.1f} ms,第 2 次 {m(2):.1f} ms;常驻内存 启动后 {m(3):.0f} MB,请求 2 次后 {m(4):.0f} MB')
print('== 三:吞吐(压测端 JDK HttpClient + 虚拟线程,预热 3 秒再测 6 秒,每个组合 2 轮;容器线程池都是默认值)')
def jproc(main, args, jopts=()): return subprocess.Popen(['java', *jopts, '-cp', str(b['out']) + ':' + b['cp'], main, *map(str, args)], env=jenv('21'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
def load(port, path, conc, warm=3, dur=6):
    p = jproc('demo.Load', [f'http://127.0.0.1:{port}{path}', conc, warm, dur]); out = p.communicate(timeout=120)[0]
    m = re.search(r'RES (\d+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) (\d+)', out); return None if not m else dict(rps=float(m.group(2)), p50=float(m.group(3)), p99=float(m.group(4)), errs=int(m.group(6)))
for lab, name, props in (('Tomcat 平台线程', 'Tomcat', {}), ('Jetty 平台线程', 'Jetty', {}), ('Tomcat + spring.threads.virtual.enabled=true', 'Tomcat', {'spring.threads.virtual.enabled': 'true'}), ('Jetty + spring.threads.virtual.enabled=true', 'Jetty', {'spring.threads.virtual.enabled': 'true'}), ('Jetty 平台线程 + server.jetty.threads.max=1000', 'Jetty', {'server.jetty.threads.max': '1000'}), ('Jetty + 虚拟线程 + server.jetty.threads.max=1000', 'Jetty', {'spring.threads.virtual.enabled': 'true', 'server.jetty.threads.max': '1000'}), ('Tomcat 平台线程 + server.tomcat.threads.max=1000', 'Tomcat', {'server.tomcat.threads.max': '1000'})):
    app = SApp(bb(name), 'demo.Main', props=props, jopts=['-Xmx1g', '-Xms256m']).start(); port = int(app.props['server.port'])
    print(f'  -- {lab}:处理线程 → {app.get("/thread")[1]}')
    load(port, '/fast', 32, 2, 2)
    for path, conc, what in (('/fast', 64, '/fast,并发 64'), ('/fast', 256, '/fast,并发 256'), ('/slow50', 400, '/slow50(sleep 50 ms),并发 400')):
        rs = [load(port, path, conc) for _ in range(2)]
        print('    ' + what + ':' + ('压测程序没有输出' if any(r is None for r in rs) else f'两轮吞吐 {rs[0]["rps"]:.0f} / {rs[1]["rps"]:.0f} 请求/秒;p50 {rs[0]["p50"]:.1f} / {rs[1]["p50"]:.1f} ms;p99 {rs[0]["p99"]:.1f} / {rs[1]["p99"]:.1f} ms;错误 {rs[0]["errs"]} / {rs[1]["errs"]}'))
    app.stop()
print('== 四:同样的请求,两个容器的不同反应')
def raw(port, target, hdrs=None, timeout=10):
    c = socket.create_connection(('127.0.0.1', port), timeout); h = ''.join(f'{k}: {v}\r\n' for k, v in (hdrs or {}).items())
    c.sendall(f'GET {target} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n{h}\r\n'.encode('latin1')); buf = b''
    try:
        while True:
            d = c.recv(65536)
            if not d: break
            buf += d
    except OSError: pass
    c.close(); head, _, body = buf.partition(b'\r\n\r\n'); st = head.split(b'\r\n')[0].decode('latin1') if head else '(没有响应)'
    return st.replace('HTTP/1.1 ', ''), body.decode('utf-8', 'replace').replace('\r\n', ' ').replace('\n', ' ')[:110]
apps = {n: SApp(bb(n), 'demo.Main').start() for n in ('Tomcat', 'Jetty')}
print('  -- 请求头 X-Big 的长度(默认的请求头上限):')
for n in (4000, 7000, 8000, 9000, 70000):
    print(f'    X-Big {n} 字节:' + ';'.join(f'{k} → {raw(int(a.props["server.port"]), "/h", {"X-Big": "a" * n})[0]}' for k, a in apps.items()))
print('  -- 路径写法(原样发送,不经过客户端规范化):')
for tgt in ('/echo/a/b', '/echo/a%2Fb', '/echo/a//b', '/echo/a/./b', '/echo/a/../b', '/echo/%2e%2e/b', '/echo/a;x=1/b', '/echo/a%00b', '/echo/a%5Cb', '/echo/a\\b'):
    print(f'    GET {tgt}')
    for k, a in apps.items():
        st, body = raw(int(a.props['server.port']), tgt); print(f'        {k}:{st}  {body}')
for a in apps.values(): a.stop()
apps = {n: SApp(bb(n), 'demo.Main', props={'server.max-http-request-header-size': '16KB'}).start() for n in ('Tomcat', 'Jetty')}
print('  -- 加上 server.max-http-request-header-size=16KB:')
for n in (9000, 15000, 20000):
    print(f'    X-Big {n} 字节:' + ';'.join(f'{k} → {raw(int(a.props["server.port"]), "/h", {"X-Big": "a" * n})[0]}' for k, a in apps.items()))
for a in apps.values(): a.stop()
print('  -- 连接空闲多久被服务端关掉(默认配置,发一个请求后什么都不发,最长等 120 秒):')
apps = {n: SApp(bb(n), 'demo.Main').start() for n in ('Tomcat', 'Jetty')}; R = {}
def idle(name, port):
    c = socket.create_connection(('127.0.0.1', port), 5); c.sendall(b'GET /fast HTTP/1.1\r\nHost: x\r\n\r\n'); c.recv(4096); t0 = time.time(); c.settimeout(125)
    try: d = c.recv(10); R[name] = f'{time.time() - t0:.1f} 秒后服务端关闭了连接' if d == b'' else f'收到了 {d!r}'
    except socket.timeout: R[name] = '125 秒内服务端没有关闭'
ths = [threading.Thread(target=idle, args=(n, int(a.props['server.port']))) for n, a in apps.items()]; [t.start() for t in ths]; [t.join() for t in ths]
for n in apps: print(f'    {n}:{R[n]}')
for a in apps.values(): a.stop()
