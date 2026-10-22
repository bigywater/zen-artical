import sys, os, re, time, json, shutil, subprocess, threading, socket; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x73'); CP = scp('org.springframework.boot:spring-boot-starter'); CPW = scp('org.springframework.boot:spring-boot-starter-webmvc')
LB = '<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>%msg%n</pattern></encoder></appender><logger name="org.springframework.boot.diagnostics.LoggingFailureAnalysisReporter" level="ERROR"/><root level="OFF"><appender-ref ref="C"/></root></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.bootstrap.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.context.event.*; import org.springframework.boot.availability.*; import org.springframework.context.*; import org.springframework.context.event.*; import org.springframework.core.annotation.Order; import org.springframework.core.env.*; import org.springframework.stereotype.Component; import java.util.*; import jakarta.annotation.PostConstruct; import java.time.Duration;\n'
def common(web):
    return {
 'src/demo/Main.java': HDR + r'''
@SpringBootApplication
public class Main {
  static final long T0 = System.nanoTime();
  static void ev(String tag, String name, String detail) { System.out.println("RES ev|" + tag + "|" + name + "|" + (System.nanoTime() - T0) / 1_000_000 + "|" + System.currentTimeMillis() + "|" + detail); }
  static String ctx(Object c) { ConfigurableApplicationContext x = (ConfigurableApplicationContext) c; return "Bean 定义 " + x.getBeanDefinitionCount() + " 个, isActive=" + x.isActive(); }
  public static void main(String[] a) {
    ev("main", "main() 开始", "");
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(''' + ('WebApplicationType.SERVLET' if web else 'WebApplicationType.NONE') + r''');
    app.addListeners(new ALis());
    ConfigurableApplicationContext c = app.run(a);
    ev("main", "app.run() 返回", "");
    if ("exit42".equals(System.getProperty("x73.mode"))) { int code = SpringApplication.exit(c, () -> 42); ev("main", "SpringApplication.exit 返回", "code=" + code); System.exit(code); }
    if (!''' + ('true' if web else 'false') + r''') System.exit(0);
  }
}
''',
 'src/demo/Lis.java': HDR + r'''
public class Lis implements ApplicationListener<ApplicationEvent> {
  static final Set<String> SHOW = Set.of("ApplicationStartingEvent", "ApplicationEnvironmentPreparedEvent", "ApplicationContextInitializedEvent", "ApplicationPreparedEvent", "ContextRefreshedEvent", "ServletWebServerInitializedEvent", "ApplicationStartedEvent", "AvailabilityChangeEvent", "ApplicationReadyEvent", "ApplicationFailedEvent", "ContextClosedEvent", "ExitCodeEvent");
  final String tag; Lis(String tag) { this.tag = tag; }
  public void onApplicationEvent(ApplicationEvent e) {
    String n = e.getClass().getSimpleName(); if (!SHOW.contains(n)) return; String d = "";
    if (e instanceof ApplicationEnvironmentPreparedEvent p) d = "此时 app.v=" + p.getEnvironment().getProperty("app.v");
    else if (e instanceof ApplicationContextInitializedEvent p) d = Main.ctx(p.getApplicationContext());
    else if (e instanceof ApplicationPreparedEvent p) d = Main.ctx(p.getApplicationContext());
    else if (e instanceof ContextRefreshedEvent p) d = Main.ctx(p.getApplicationContext());
    else if (e instanceof ApplicationStartedEvent p) d = Main.ctx(p.getApplicationContext());
    else if (e instanceof ApplicationReadyEvent p) d = Main.ctx(p.getApplicationContext());
    else if (e instanceof AvailabilityChangeEvent<?> p) d = p.getState().getClass().getSimpleName() + "." + p.getState();
    else if (e instanceof ApplicationFailedEvent p) d = p.getException().getClass().getSimpleName() + ": " + p.getException().getMessage();
    else if (e instanceof ExitCodeEvent p) d = "exitCode=" + p.getExitCode();
    Main.ev(tag, n, d);
  }
}
''',
 'src/demo/ALis.java': HDR + 'public class ALis extends Lis { public ALis() { super("A"); } }\n',
 'src/demo/CLis.java': HDR + 'public class CLis extends Lis { public CLis() { super("C"); } }\n',
 'src/demo/BLis.java': HDR + '@Component public class BLis extends Lis { public BLis() { super("B"); } }\n',
 'src/demo/RunLis.java': HDR + r'''
public class RunLis implements SpringApplicationRunListener {
  public RunLis(SpringApplication app, String[] args) {}
  public void starting(ConfigurableBootstrapContext c) { Main.ev("R", "starting", ""); }
  public void environmentPrepared(ConfigurableBootstrapContext c, ConfigurableEnvironment e) { Main.ev("R", "environmentPrepared", "此时 app.v=" + e.getProperty("app.v")); }
  public void contextPrepared(ConfigurableApplicationContext c) { Main.ev("R", "contextPrepared", Main.ctx(c)); }
  public void contextLoaded(ConfigurableApplicationContext c) { Main.ev("R", "contextLoaded", Main.ctx(c)); }
  public void started(ConfigurableApplicationContext c, Duration t) { Main.ev("R", "started", ""); }
  public void ready(ConfigurableApplicationContext c, Duration t) { Main.ev("R", "ready", ""); }
  public void failed(ConfigurableApplicationContext c, Throwable t) { Main.ev("R", "failed", t.getClass().getSimpleName()); }
}
''',
 'src/demo/Life.java': HDR + r'''@Component public class Life implements SmartLifecycle { boolean on; public void start() { on = true; Main.ev("life", "SmartLifecycle.start()", ""); } public void stop() { on = false; } public boolean isRunning() { return on; } }
''',
 'src/demo/Bad.java': HDR + r'''@Component public class Bad { @PostConstruct void init() { Main.ev("bean", "某个 Bean 的 @PostConstruct", ""); if ("postconstruct".equals(System.getProperty("x73.fail"))) throw new IllegalStateException("boom in postconstruct"); } }
''',
 'src/demo/Runners.java': HDR + r'''
@Component @Order(1) class R1 implements CommandLineRunner { public void run(String... a) { Main.ev("run", "R1 CommandLineRunner @Order(1)", "args=" + Arrays.toString(a)); } }
@Component @Order(2) class R2 implements ApplicationRunner { public void run(ApplicationArguments a) { Main.ev("run", "R2 ApplicationRunner @Order(2)", "options=" + new TreeSet<>(a.getOptionNames()) + " nonOption=" + a.getNonOptionArgs() + " foo=" + a.getOptionValues("foo") + " flag=" + a.getOptionValues("flag")); } }
@Component class R3 implements CommandLineRunner { public void run(String... a) throws Exception {
  Main.ev("run", "R3 CommandLineRunner(没有 @Order)", "");
  if ("runner".equals(System.getProperty("x73.fail"))) throw new IllegalStateException("boom in runner");
  long ms = Long.getLong("x73.slow", 0); if (ms > 0) { Thread.sleep(ms); Main.ev("run", "R3 慢 runner 结束", "睡了 " + ms + " ms"); } } }
''',
 'META-INF/spring.factories': 'org.springframework.context.ApplicationListener=demo.CLis\norg.springframework.boot.SpringApplicationRunListener=demo.RunLis\n',
 'logback.xml': LB,
}
F = common(False)
b = sbuild('x73', F, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
WD = JT / 'x73_wd'
def parse(r):
    out = []
    for l in res(r):
        if l.startswith('ev|'): tag, name, ms, wall, d = l[3:].split('|', 4); out.append((tag, name, int(ms), int(wall), d))
        else: out.append(l)
    return out
def run(args=(), props=None, files=None, env=None, bb=None):
    shutil.rmtree(WD, ignore_errors=True); WD.mkdir(parents=True)
    for k, v in (files or {}).items(): (WD / k).write_text(v)
    r = srun(bb or b, 'demo.Main', args=list(args), props=props or {}, env=env, cwd=str(WD), timeout=60); return parse(r), r
def fmt(ev, tags=('A', 'R', 'life', 'bean', 'run', 'main')):
    for e in ev:
        if isinstance(e, str): print('  ' + e); continue
        tag, name, ms, wall, d = e
        if tag in tags: print(f'  +{ms:>4} ms  [{tag}] {name}' + (f'  ({d})' if d else ''))
def failure_text(r):
    o = r['out']; i = o.find('Description:')
    if i >= 0: return ' '.join(x.strip() for x in o[i:].splitlines() if x.strip())[:300]
    ex = [x for x in o.splitlines() if re.match(r'^(Exception in thread "main" |Caused by: )?[\w.$]+(Exception|Error):', x)]
    return (ex[0] if ex else o[-200:]).replace('Exception in thread "main" ', '')[:300]
print('Spring Boot 4.0.8 / JDK 21;四个监听器同时登记:A = app.addListeners(...),B = @Component,C = META-INF/spring.factories 里的 ApplicationListener,R = spring.factories 里的 SpringApplicationRunListener;时间是从 main() 第一行起的毫秒数,每次运行会有抖动')
ev, r = run(['--foo=bar', '--flag', 'baz'], files={'application.properties': 'app.v=from-file\n'})
print('== 一:一次正常启动的时间线(--foo=bar --flag baz;只列 A、R 与应用里自己打点的行)')
fmt(ev)
print('  退出码 %s' % r['rc'])
print('== 二:四种登记方式各自收到了哪些事件')
for tag, what in (('A', 'app.addListeners(...)'), ('B', '@Component'), ('C', 'spring.factories 的 ApplicationListener'), ('R', 'spring.factories 的 SpringApplicationRunListener')):
    names = [e[1] for e in ev if not isinstance(e, str) and e[0] == tag]
    print(f'  [{tag}] {what}:共 {len(names)} 个' + ('——' + '、'.join(n.replace('Event', '') for n in names) if names else ''))
print('== 三:异常与退出码')
for title, props in (('Bean 的 @PostConstruct 抛异常', {'x73.fail': 'postconstruct'}), ('最后一个 runner 抛异常', {'x73.fail': 'runner'})):
    ev2, r2 = run(props=props); print(f'  -- {title}:')
    fmt(ev2, tags=('A', 'R', 'run', 'bean', 'main')); print(f'  退出码 {r2["rc"]};堆栈里的异常:{failure_text(r2)}')
ev3, r3 = run(props={'x73.mode': 'exit42'}); print('  -- 用 SpringApplication.exit(ctx, () -> 42) 主动退出:'); fmt(ev3, tags=('A', 'main')); print(f'  退出码 {r3["rc"]}')
print('== 四:内嵌 Web 容器:端口什么时候开,readiness 什么时候变')
FW = common(True)
FW['src/demo/Web.java'] = HDR + r'''
@org.springframework.web.bind.annotation.RestController public class Web {
  final ApplicationAvailability av; Web(ApplicationAvailability av) { this.av = av; }
  @org.springframework.web.bind.annotation.GetMapping("/state") String s() { return "liveness=" + av.getLivenessState() + " readiness=" + av.getReadinessState(); }
}
'''
bw = sbuild('x73w', FW, CPW)
if bw['crc'] != 0: print(bw['cout']); sys.exit()
port = free_port(); shutil.rmtree(WD, ignore_errors=True); WD.mkdir(parents=True)
app = SApp(bw, 'demo.Main', props={'x73.slow': '1500', 'server.port': port}, port=port, name='x73w'); app.start(wait_port=False)
t_conn = t_first = None; first_body = None; t_end = time.time() + 30
while time.time() < t_end:
    try:
        socket.create_connection(('127.0.0.1', port), 0.05).close(); t_conn = time.time() * 1000; break
    except OSError: time.sleep(0.005)
try: st, body, _ = app.get('/state'); t_first = time.time() * 1000; first_body = f'HTTP {st} {body}'
except Exception as ex: first_body = '失败:%r' % ex
time.sleep(2.2)
st2, body2, _ = app.get('/state'); lines = [l for l in app.log().splitlines() if l.startswith('RES ev|')]
app.stop()
evs = []
for l in lines: tag, name, ms, wall, d = l[7:].split('|', 4); evs.append((tag, name, int(ms), int(wall), d))
w0 = [e for e in evs if e[1] == 'main() 开始'][0][3]
rows = [(e[3] - w0, i, f'[{e[0]}] {e[1]}' + (f'  ({e[4]})' if e[4] else '')) for i, e in enumerate(evs) if e[0] in ('A', 'life', 'run', 'bean')]
rows += [(int(t_conn - w0), 10**6, '【外部客户端】第一次连上端口'), (int(t_first - w0), 10**6 + 1, f'【外部客户端】GET /state 收到响应:{first_body}')]
for ms, _, text in sorted(rows): print(f'  +{ms:>4} ms  {text}')
print(f'  runner 结束之后再请求一次:HTTP {st2} {body2}')
