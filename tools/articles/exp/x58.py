import sys, os, re, time, json, threading, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x58'); CP = scp('org.springframework.boot:spring-boot-starter-webflux')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.time.Duration;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.*; import reactor.core.publisher.Mono; import reactor.core.scheduler.Schedulers;
@SpringBootApplication @RestController
public class Main {
  static String tn() { return Thread.currentThread().getName(); }
  @GetMapping("/thread") Mono<String> thread() { return Mono.fromSupplier(Main::tn); }
  @GetMapping("/fast") Mono<String> fast() { return Mono.just("fast"); }
  @GetMapping("/block") Mono<String> block(@RequestParam long ms) { return Mono.fromCallable(() -> { Thread.sleep(ms); return "blocked-" + ms + "@" + tn(); }); }
  @GetMapping("/offload") Mono<String> offload(@RequestParam long ms) { return Mono.fromCallable(() -> { Thread.sleep(ms); return "offload-" + ms + "@" + tn(); }).subscribeOn(Schedulers.boundedElastic()); }
  @GetMapping("/direct-block") String direct(@RequestParam long ms) throws Exception { Thread.sleep(ms); return "direct-" + ms + "@" + tn(); }
  @GetMapping("/delay") Mono<String> delay(@RequestParam long ms) { return Mono.just("delayed").delayElement(Duration.ofMillis(ms)); }
  @ExceptionHandler(Exception.class) org.springframework.http.ResponseEntity<String> ex(Exception e) { return org.springframework.http.ResponseEntity.status(500).body("[" + e.getClass().getSimpleName() + "] " + e.getMessage()); }
  @GetMapping("/call-block") Mono<String> callBlock() { return Mono.fromSupplier(() -> Mono.just("x").delayElement(Duration.ofMillis(10)).block()); }
  @GetMapping("/call-block-offload") Mono<String> callBlockOff() { return Mono.fromSupplier(() -> Mono.just("x").delayElement(Duration.ofMillis(10)).block()).subscribeOn(Schedulers.boundedElastic()); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x58', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def one(port, path, tmo=15):
    t0 = time.time(); c = http.client.HTTPConnection('127.0.0.1', port, timeout=tmo)
    try:
        c.request('GET', path, headers={'Connection': 'close'}); r = c.getresponse(); d = r.read().decode(); return r.status, d, round((time.time() - t0) * 1000)
    except Exception as e: return 0, type(e).__name__, round((time.time() - t0) * 1000)
    finally: c.close()
def run(props, f, title, head=True):
    app = SApp(b, 'demo.Main', props=props).start(); print(f'== {title}' if head else f'  -- {title}'); f(app); app.stop()
def conc(port, path, n):
    res = [None] * n
    def w(i): res[i] = one(port, path)
    ths = [threading.Thread(target=w, args=(i,)) for i in range(n)]; [t.start() for t in ths]; return ths, res
def probes(port, dur=1.6, gap=0.04):
    out = []; t_end = time.time() + dur
    while time.time() < t_end: out.append(one(port, '/fast')[2]); time.sleep(gap)
    return out
print('Spring Boot 4.0.8 / Spring WebFlux 7.0.9 / Reactor Netty 1.3.7(Netty 4.2.17);每个请求新建连接(Connection: close),让 Netty 把连接轮流分给各个 event loop 线程')
def one_(app):
    port = int(app.props['server.port']); names = {}
    for i in range(100): s, d, ms = one(port, '/thread'); names[d] = names.get(d, 0) + 1
    print(f'  100 个请求(每个新连接)分布在 {len(names)} 个线程上:{dict(sorted(names.items()))}')
run({}, one_, '一:默认配置下处理请求的线程(CPU 逻辑核心数 10)')
def two(app):
    port = int(app.props['server.port']); names = {}
    for i in range(40): s, d, ms = one(port, '/thread'); names[d] = names.get(d, 0) + 1
    print(f'  reactor.netty.ioWorkerCount=2:40 个请求分布在 {len(names)} 个线程上:{dict(sorted(names.items()))}')
run({'reactor.netty.ioWorkerCount': '2'}, two, '二:把 event loop 线程数设成 2(-Dreactor.netty.ioWorkerCount=2)')
print('== 三:阻塞调用放在哪里:ioWorkerCount=2,4 个并发请求(每个处理 500 ms),期间持续用新连接探测 /fast')
for path, lab in [('/block?ms=500', '在 Mono.fromCallable 里 Thread.sleep(500)(没有切线程)'), ('/direct-block?ms=500', '控制器方法直接返回 String,里面 Thread.sleep(500)'), ('/offload?ms=500', 'Thread.sleep(500) 放到 subscribeOn(boundedElastic)'), ('/delay?ms=500', 'Mono.delayElement(500 ms)(非阻塞等待)')]:
    def f(app, path=path):
        port = int(app.props['server.port']); ths, res = conc(port, path, 4); time.sleep(0.1); pr = probes(port); [t.join() for t in ths]
        lat = sorted(r[2] for r in res); slow = [p for p in pr if p > 100]
        print(f'  4 个并发请求的耗时(ms):{lat};响应里的线程:{sorted(set(re.sub(chr(64)+".*", "", r[1]) + chr(64) + r[1].split(chr(64))[-1] if chr(64) in r[1] else r[1] for r in res))}')
        print(f'  期间每 40 ms 发一个 /fast(新连接)共 {len(pr)} 个:最慢 {max(pr)} ms,超过 100 ms 的有 {len(slow)} 个;耗时序列 {pr[:25]}')
    run({'reactor.netty.ioWorkerCount': '2'}, f, lab, False)
def four(app):
    port = int(app.props['server.port'])
    for p in ['/call-block', '/call-block-offload']:
        s, d, ms = one(port, p); print(f'  GET {p} → {s} {re.sub(chr(34)+"timestamp"+chr(34)+":"+chr(34)+"[^"+chr(34)+"]*"+chr(34)+",?", "", d)[:200]}')
run({'reactor.netty.ioWorkerCount': '2'}, four, '四:在 event loop 线程上调用 block()')
def five(app):
    from collections import Counter
    port = int(app.props['server.port'])
    for n in [50, 100, 200]:
        t0 = time.time(); ths, res = conc(port, '/delay?ms=500', n); [t.join() for t in ths]; el = (time.time() - t0) * 1000
        c = Counter((r[0] if r[0] else r[1]) for r in res); ok = [r[2] for r in res if r[0] == 200]
        print(f'  {n} 个并发的 /delay?ms=500:全部完成用了 {round(el)} ms;结果统计 {dict(c)};成功的里最慢 {max(ok) if ok else None} ms')
        time.sleep(0.5)
run({'reactor.netty.ioWorkerCount': '2'}, five, '五:非阻塞等待的好处:N 个并发请求各等 500 ms,只有 2 个 event loop 线程')
