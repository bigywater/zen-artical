import sys, os, re, time, json, shutil, subprocess, statistics, signal, socket, threading, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x76'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LB = '<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>%msg%n</pattern></encoder></appender><logger name="org.springframework.boot" level="INFO"/><root level="OFF"><appender-ref ref="C"/></root></configuration>'
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*; import org.springframework.context.event.*; import org.springframework.context.*; import org.springframework.boot.availability.*;
@SpringBootApplication @RestController
public class Main {
  final ApplicationAvailability av; Main(ApplicationAvailability av) { this.av = av; }
  @GetMapping("/fast") String fast() { return "ok"; }
  @GetMapping("/slow") String slow(@RequestParam int ms) throws Exception { Thread.sleep(ms); return "done after " + ms + " ms"; }
  @GetMapping("/state") String state() { return "readiness=" + av.getReadinessState(); }
  @EventListener void closed(ContextClosedEvent e) { System.out.println("RES ContextClosedEvent 到达,readiness=" + av.getReadinessState() + " t=" + System.currentTimeMillis()); }
  @EventListener void avail(AvailabilityChangeEvent<?> e) { System.out.println("RES AvailabilityChangeEvent " + e.getState() + " t=" + System.currentTimeMillis()); }
  @jakarta.annotation.PreDestroy void bye() { System.out.println("RES @PreDestroy 执行 t=" + System.currentTimeMillis()); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x76', {'src/demo/Main.java': MAIN, 'logback.xml': LB}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def start(props):
    pr = {'server.port': free_port()}; pr.update(props); return SApp(b, 'demo.Main', props=pr, port=pr['server.port'], name='x76').start()
def call(port, path, timeout=20, conn=None):
    t = time.time()
    try:
        c = conn or http.client.HTTPConnection('127.0.0.1', port, timeout=timeout); c.request('GET', path); r = c.getresponse(); body = r.read().decode()
        return f'{r.status} {body}', time.time() - t
    except Exception as e: return f'{type(e).__name__}: {str(e)[:60]}', time.time() - t
    finally:
        if conn is None:
            try: c.close()
            except Exception: pass
def fmt_log(app):
    keep = [l for l in app.log().splitlines() if re.search(r'raceful|Commencing|shutdown', l, re.I)]
    return keep
def scenario(title, props, sigterm_at=0.5, slow_ms=3000, probe_at=0.3):
    app = start(props); port = int(app.props['server.port']); R = {}
    ka = http.client.HTTPConnection('127.0.0.1', port, timeout=20); R['ka0'] = call(port, '/fast', conn=ka)[0]
    th = threading.Thread(target=lambda: R.__setitem__('slow', call(port, f'/slow?ms={slow_ms}'))); t0 = time.time(); th.start()
    time.sleep(sigterm_at); ts = time.time(); app.p.send_signal(signal.SIGTERM)
    time.sleep(probe_at); R['new'] = call(port, '/fast', timeout=5)[0]; R['ka1'] = call(port, '/fast', conn=ka)[0]
    th.join(); t_slow = time.time() - t0
    try: app.p.wait(30); exit_s = time.time() - ts; rc = app.p.returncode
    except subprocess.TimeoutExpired: exit_s = None; rc = None; app.stop()
    print(f'  {title}')
    print(f'    正在处理的 /slow?ms={slow_ms}(SIGTERM 前 {sigterm_at} 秒发出):{R["slow"][0]};客户端等了 {R["slow"][1]:.1f} 秒')
    print(f'    SIGTERM 之后 {probe_at} 秒:新建连接请求 /fast → {R["new"]};已有的 keep-alive 连接再请求 /fast → {R["ka1"]}')
    print(f'    进程在 SIGTERM 之后 {exit_s:.1f} 秒退出,退出码 {rc}' if exit_s is not None else '    进程 30 秒内没有退出')
    for l in fmt_log(app): print('    日志:' + l[:150])
    for l in [x for x in app.log().splitlines() if x.startswith('RES ')]: print('    ' + re.sub(r' t=\d+', '', l[4:]))
print('Spring Boot 4.0.8 / JDK 21;内嵌 Tomcat;客户端是 Python http.client;SIGTERM 用 Popen.send_signal 发给 java 进程')
print('== 一:SIGTERM 到来时,一个正在处理的 3 秒请求会怎样(server.shutdown 取值)')
scenario('什么都不设(默认值)', {})
scenario('server.shutdown=immediate', {'server.shutdown': 'immediate'})
scenario('server.shutdown=graceful(阶段超时默认 30 秒)', {'server.shutdown': 'graceful'})
scenario('server.shutdown=graceful + spring.lifecycle.timeout-per-shutdown-phase=1s(比请求短)', {'server.shutdown': 'graceful', 'spring.lifecycle.timeout-per-shutdown-phase': '1s'})
print('== 二:负载均衡摘除有延迟时,新请求会不会失败(模拟 K8s:Pod 开始终止时刻为 t0,负载均衡在 t0+2.0 秒才真正停止发请求;preStop 睡 S 秒 = 推迟 S 秒再发 SIGTERM)')
def lb_sim(title, props, sleep_s):
    app = start(props); port = int(app.props['server.port']); R = {'ok': 0, 'bad': [], 'late': None}
    t0 = time.time(); stop_at = t0 + 2.0
    def sender():
        while time.time() < stop_at:
            s, _ = call(port, '/fast', timeout=3)
            if s.startswith('200'): R['ok'] += 1
            else: R['bad'].append(s)
            time.sleep(0.01)
    def late():  # 在负载均衡摘除前 0.1 秒发出的 3 秒请求
        time.sleep(1.9); R['late'] = call(port, '/slow?ms=3000')
    th = [threading.Thread(target=sender), threading.Thread(target=late)]; [t.start() for t in th]
    time.sleep(sleep_s); app.p.send_signal(signal.SIGTERM); [t.join() for t in th]
    try: app.p.wait(30)
    except subprocess.TimeoutExpired: app.stop()
    kinds = {}
    for s in R['bad']: kinds[s.split(':')[0][:40]] = kinds.get(s.split(':')[0][:40], 0) + 1
    print(f'  {title}')
    print(f'    摘除前共发出 {R["ok"] + len(R["bad"])} 个请求,成功 {R["ok"]} 个,失败 {len(R["bad"])} 个' + (f'({"、".join(f"{k} × {v}" for k, v in kinds.items())})' if kinds else '') + f';摘除前 0.1 秒发出的 3 秒请求 → {R["late"][0]}')
lb_sim('immediate,不睡(preStop 睡 0 秒)', {'server.shutdown': 'immediate'}, 0.0)
lb_sim('graceful,不睡', {'server.shutdown': 'graceful'}, 0.0)
lb_sim('什么都不设(默认值),不睡', {}, 0.0)
lb_sim('immediate,preStop 睡 3 秒', {'server.shutdown': 'immediate'}, 3.0)
lb_sim('graceful,preStop 睡 3 秒', {'server.shutdown': 'graceful'}, 3.0)
print('== 三:阶段超时的默认值(一个 40 秒的请求,SIGTERM 后进程要等多久)')
scenario('server.shutdown=graceful,没有设置 spring.lifecycle.timeout-per-shutdown-phase', {'server.shutdown': 'graceful'}, slow_ms=40000)
