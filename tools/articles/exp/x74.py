import sys, os, re, time, json, shutil, subprocess, statistics, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x74'); CPW = scp('org.springframework.boot:spring-boot-starter-webmvc', 'org.springframework.boot:spring-boot-starter-actuator', 'org.springframework.boot:spring-boot-starter-validation')
LB = '<configuration><root level="OFF"/></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.context.event.*; import org.springframework.context.*; import org.springframework.context.event.*; import org.springframework.stereotype.*; import org.springframework.beans.factory.annotation.Autowired; import java.util.*;\n'
NB = 150
FILES = {
 'src/demo/Main.java': HDR + r'''
import org.springframework.core.metrics.StartupStep; import org.springframework.boot.context.metrics.buffering.BufferingApplicationStartup;
@SpringBootApplication
public class Main {
  static final long T0 = System.nanoTime(); static final long WALL0 = System.currentTimeMillis();
  static void r(String s) { System.out.println("RES " + s); }
  static long[] t = new long[8];
  public static void main(String[] a) {
    long jvmStart = java.lang.management.ManagementFactory.getRuntimeMXBean().getStartTime();
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF);
    BufferingApplicationStartup bas = new BufferingApplicationStartup(200000); if (System.getProperty("x74.steps") != null) app.setApplicationStartup(bas);
    app.addListeners((ApplicationListener<ApplicationEvent>) e -> {
      long n = System.nanoTime();
      if (e instanceof ApplicationStartingEvent) t[0] = n; else if (e instanceof ApplicationEnvironmentPreparedEvent) t[1] = n; else if (e instanceof ApplicationPreparedEvent) t[2] = n;
      else if (e instanceof ContextRefreshedEvent) t[3] = n; else if (e instanceof ApplicationReadyEvent) { t[4] = n;
        long ms = 1_000_000;
        r(String.format("phases|JVM启动→main %d|main→Starting %d|Starting→EnvPrepared %d|EnvPrepared→Prepared %d|Prepared→Refreshed(refresh) %d|Refreshed→Ready %d|main→Ready %d", Main.WALL0 - jvmStart, (t[0] - T0) / ms, (t[1] - t[0]) / ms, (t[2] - t[1]) / ms, (t[3] - t[2]) / ms, (t[4] - t[3]) / ms, (t[4] - T0) / ms));
        ConfigurableApplicationContext c = ((ApplicationReadyEvent) e).getApplicationContext();
        r("stats|singletons=" + c.getBeanFactory().getSingletonCount() + "|definitions=" + c.getBeanDefinitionCount());
        if (System.getProperty("x74.steps") != null) {
          List<StartupStep.Tag> none = List.of(); var evs = bas.getBufferedTimeline().getEvents();
          Map<String, double[]> agg = new TreeMap<>(); for (var ev : evs) { double[] x = agg.computeIfAbsent(ev.getStartupStep().getName(), k -> new double[2]); x[0]++; x[1] += ev.getDuration().toNanos() / 1e6; }
          for (var en : agg.entrySet()) r(String.format("step|%s|次数 %d|合计 %.1f ms", en.getKey(), (int) en.getValue()[0], en.getValue()[1]));
          List<String> top = new ArrayList<>(); for (var ev : evs) if (ev.getStartupStep().getName().equals("spring.beans.instantiate")) { String bn = ""; for (var tg : ev.getStartupStep().getTags()) if (tg.getKey().equals("beanName")) bn = tg.getValue(); top.add(String.format("%08.3f|%s", ev.getDuration().toNanos() / 1e6, bn)); }
          Collections.sort(top, Collections.reverseOrder()); for (int i = 0; i < Math.min(8, top.size()); i++) r("slow|" + top.get(i));
        }
      }
    });
    app.run(a);
  }
}
''',
 'src/demo/Ctl.java': HDR + '@org.springframework.web.bind.annotation.RestController public class Ctl { final B' + str(NB - 1) + ' last; Ctl(B' + str(NB - 1) + ' last) { this.last = last; } @org.springframework.web.bind.annotation.GetMapping("/ping") String ping() { return "pong" + last.depth(); } }\n',
 'logback.xml': LB,
}
for i in range(NB):
    prev = f'B{i-1}' if i % 10 else None
    FILES[f'src/demo/B{i}.java'] = HDR + f'@Service public class B{i} {{ final int d; B{i}(' + (f'B{i-1} p' if prev else '') + f') {{ d = ' + ('p.depth() + 1' if prev else '0') + f'; }} public int depth() {{ return d; }} }}\n'
b = sbuild('x74', FILES, CPW)
if b['crc'] != 0: print(b['cout']); sys.exit()
def trial(props=None, jopts=(), steps=False):
    pr = {'server.port': free_port()}; pr.update(props or {})
    if steps: pr['x74.steps'] = '1'
    app = SApp(b, 'demo.Main', props=pr, jopts=list(jopts), port=pr['server.port'], name='x74')
    t0 = time.time(); app.start(timeout=60); t_up = (time.time() - t0) * 1000
    t1 = time.time(); st, body, _ = app.get('/ping'); first = (time.time() - t1) * 1000
    t2 = time.time(); app.get('/ping'); second = (time.time() - t2) * 1000
    time.sleep(0.15); log = [l[4:] for l in app.log().splitlines() if l.startswith('RES ')]; rss = app.rss_mb(); app.stop()
    return dict(up=t_up, first=first, second=second, log=log, rss=rss, body=body)
def med(xs): return statistics.median(xs)
def many(n, **kw):
    rs = [trial(**kw) for _ in range(n)]; return rs
def summ(title, rs, extra=True):
    ups = [r['up'] for r in rs]; f = [r['first'] for r in rs]; s = [r['second'] for r in rs]; rss = [r['rss'] for r in rs]
    ready = [int(re.search(r'main→Ready (\d+)', [l for l in r['log'] if l.startswith('phases')][0]).group(1)) for r in rs]
    st = [l for l in rs[0]['log'] if l.startswith('stats')][0]
    print(f'  {title}')
    print(f'    进程启动到端口可连接(外部计时):中位 {med(ups):.0f} ms(范围 {min(ups):.0f}~{max(ups):.0f},{len(rs)} 次);应用内 main→Ready 中位 {med(ready)} ms')
    print(f'    第 1 次请求 /ping 中位 {med(f):.1f} ms,第 2 次中位 {med(s):.1f} ms;进程常驻内存中位 {med(rss):.0f} MB;{st.replace("stats|", "").replace("|", ",")}')
    return med(ups)
print('Spring Boot 4.0.8 / JDK 21;应用 = webmvc + actuator + validation + 150 个 @Service(每 10 个一条依赖链)+ 一个 /ping 接口;外部计时从 Popen 到端口可连接,每组各自重复多次取中位数,机器上没有别的负载')
print('== 一:时间花在哪里(单次运行 + ApplicationStartup 打点)')
r = trial(steps=True)
for l in r['log']:
    if l.startswith('phases'): print('  ' + l.replace('phases|', '各阶段(ms):').replace('|', ';'))
for l in r['log']:
    if l.startswith('stats'): print('  ' + l.replace('stats|', '').replace('|', ','))
steps = [l for l in r['log'] if l.startswith('step|')]
print('  ApplicationStartup 缓冲到的步骤(名称、次数、各次耗时合计;嵌套的步骤会重复计入父步骤):')
for l in steps:
    _, name, cnt, tot = l.split('|')
    if any(k in name for k in ('spring.boot', 'spring.context.refresh', 'spring.context.beans.post-process', 'spring.context.bean-factory.post-process', 'spring.beans.instantiate', 'spring.context.config-classes.parse', 'spring.context.beans.instantiate', 'spring.context.base-packages.scan', 'spring.context.annotated-bean-reader.create', 'spring.context.component-classes.register', 'spring.context.beandef-registry.post-process')): print(f'    {name}:{cnt},{tot}')
print('  最慢的 8 个 spring.beans.instantiate(含它依赖的 Bean 的创建时间):')
for l in r['log']:
    if l.startswith('slow|'): print('    ' + l.split('|')[2] + f'  {float(l.split("|")[1]):.1f} ms')
print('== 二:懒加载 spring.main.lazy-initialization')
base = summ('默认(非懒加载)', many(7))
lazy = summ('spring.main.lazy-initialization=true', many(7, props={'spring.main.lazy-initialization': 'true'}))
print(f'  外部计时中位数:{lazy:.0f} ms 对 {base:.0f} ms,相差 {base - lazy:.0f} ms')
print('== 三:JVM 参数')
summ('-XX:TieredStopAtLevel=1(只用 C1 编译器)', many(5, jopts=['-XX:TieredStopAtLevel=1']))
summ('-XX:+UseSerialGC', many(5, jopts=['-XX:+UseSerialGC']))
summ('-XX:TieredStopAtLevel=1 -XX:+UseSerialGC -Xshare:auto', many(5, jopts=['-XX:TieredStopAtLevel=1', '-XX:+UseSerialGC', '-Xshare:auto']))
print('== 四:AppCDS(动态归档,-XX:ArchiveClassesAtExit;应用类先打成 jar,因为 classpath 里有普通目录时归档生成不了)')
JAR = JT / 'x74' / 'app.jar'; JAR.unlink(missing_ok=True)
subprocess.run(['jar', 'cf', str(JAR), '-C', str(b['out']), '.'], env=jenv('21'), check=True); b = dict(b, out=JAR)
JSA = JT / 'x74_app.jsa'; JSA2 = JT / 'x74_app_onrefresh.jsa'
for f in (JSA, JSA2): f.unlink(missing_ok=True)
pr = {'server.port': free_port()}
app = SApp(b, 'demo.Main', props=pr, jopts=[f'-XX:ArchiveClassesAtExit={JSA}'], port=pr['server.port'], name='x74train'); app.start(timeout=90); app.get('/ping'); app.get('/ping'); app.stop(wait=60)
time.sleep(1.5)
print(f'  训练 1:启动、请求 2 次 /ping、SIGTERM 结束 → 归档文件 {JSA.stat().st_size / 1024 / 1024:.1f} MB' if JSA.exists() else '  训练 1:没有生成归档文件')
r2 = srun(b, 'demo.Main', props={'spring.context.exit': 'onRefresh', 'server.port': free_port()}, jopts=[f'-XX:ArchiveClassesAtExit={JSA2}'], timeout=90)
print(f'  训练 2:-Dspring.context.exit=onRefresh(refresh 之后立即退出,退出码 {r2["rc"]}) → 归档文件 {JSA2.stat().st_size / 1024 / 1024:.1f} MB' if JSA2.exists() else f'  训练 2:没有生成归档文件(退出码 {r2["rc"]})')
base2 = summ('不用归档(同一批代码,对照)', many(7))
if JSA.exists(): summ('用训练 1 的归档 -XX:SharedArchiveFile', many(7, jopts=[f'-XX:SharedArchiveFile={JSA}']))
if JSA2.exists(): summ('用训练 2 的归档 -XX:SharedArchiveFile', many(7, jopts=[f'-XX:SharedArchiveFile={JSA2}']))
if JSA.exists(): summ('训练 1 的归档 + -XX:TieredStopAtLevel=1', many(5, jopts=[f'-XX:SharedArchiveFile={JSA}', '-XX:TieredStopAtLevel=1']))
