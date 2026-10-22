import sys, os, re, time, json, shutil, subprocess, statistics, socket, signal, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x84')
GRAAL = pathlib.Path('/private/tmp/claude-501/-Users-w-Desktop-zen/ba230915-496f-4157-87cf-8cee4040b1b9/scratchpad/graal/graalvm-community-openjdk-25.0.2+10.1/Contents/Home')
if not GRAAL.exists():
    cands = list(GRAAL.parent.parent.parent.glob('*/Contents/Home')) if GRAAL.parent.parent.parent.exists() else []
    GRAAL = cands[0] if cands else GRAAL
P = JT / 'x84proj'
POM = '''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>4.0.8</version></parent>
<groupId>demo</groupId><artifactId>app</artifactId><version>1.0.0</version><properties><java.version>21</java.version></properties>
<dependencies><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-webmvc</artifactId></dependency></dependencies>
<build><finalName>app</finalName><plugins><plugin><groupId>org.springframework.boot</groupId><artifactId>spring-boot-maven-plugin</artifactId></plugin>
<plugin><groupId>org.graalvm.buildtools</groupId><artifactId>native-maven-plugin</artifactId><configuration><buildArgs><buildArg>-J-Xmx6g</buildArg></buildArgs></configuration></plugin></plugins></build></project>'''
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*; import org.springframework.context.*; import org.springframework.context.annotation.*; import org.springframework.aot.hint.*;
@SpringBootApplication @RestController @ImportRuntimeHints(Main.Hints.class)
public class Main {
  static class Hints implements RuntimeHintsRegistrar { public void registerHints(RuntimeHints h, ClassLoader cl) { h.reflection().registerType(Hinted.class, MemberCategory.INVOKE_DECLARED_CONSTRUCTORS); } }
  final ApplicationContext ctx; Main(ApplicationContext c) { ctx = c; }
  @GetMapping("/ping") String ping() { return "pong"; }
  @GetMapping("/reflect") String reflect(@RequestParam String cls) { try { Class<?> c = Class.forName(cls); return "loaded " + c.getName() + " → " + c.getDeclaredConstructor().newInstance(); } catch (Throwable e) { return "FAIL " + e.getClass().getSimpleName() + ": " + e.getMessage(); } }
  @GetMapping("/beans") String beans() { return "devMarker 存在=" + ctx.containsBean("devMarker") + ";activeProfiles=" + java.util.Arrays.toString(ctx.getEnvironment().getActiveProfiles()); }
  @GetMapping("/runtime") String runtime() { return "java.vm.name=" + System.getProperty("java.vm.name") + ";org.graalvm.nativeimage.imagecode=" + System.getProperty("org.graalvm.nativeimage.imagecode"); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
class Hidden { public String toString() { return "Hidden 实例"; } }
class Hinted { public String toString() { return "Hinted 实例"; } }
@Configuration @Profile("dev") class DevCfg { @Bean String devMarker() { return "dev"; } }
'''
def write_proj():
    shutil.rmtree(P, ignore_errors=True); (P / 'src/main/java/demo').mkdir(parents=True); (P / 'src/main/resources').mkdir(parents=True)
    (P / 'pom.xml').write_text(POM); (P / 'src/main/java/demo/Main.java').write_text(MAIN); (P / 'src/main/resources/logback.xml').write_text('<configuration><root level="OFF"/></configuration>')
def mvn(args, home, timeout=3000):
    e = jenv('21', MAVEN_OPTS='-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=1087 -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=1087'); e['JAVA_HOME'] = str(home); e['PATH'] = str(home) + '/bin:' + os.environ['PATH']
    t = time.time(); r = subprocess.run(['/usr/bin/time', '-l', 'mvn', '-q', '-f', str(P / 'pom.xml'), *args], env=e, capture_output=True, text=True, timeout=timeout); el = time.time() - t
    m = re.search(r'(\d+)\s+maximum resident set size', r.stderr)
    if r.returncode != 0: print((r.stdout + r.stderr)[-2500:]); sys.exit(1)
    return el, (int(m.group(1)) / 1048576 if m else None)
def serve(cmd, port, env=None):
    t0 = time.time(); p = subprocess.Popen(cmd, env=env or jenv('21'), stdout=open(P / 'run.log', 'w'), stderr=subprocess.STDOUT, cwd=P)
    while time.time() - t0 < 60:
        if p.poll() is not None: raise RuntimeError('退出:' + (P / 'run.log').read_text()[-800:])
        try: socket.create_connection(('127.0.0.1', port), 0.2).close(); return p, (time.time() - t0) * 1000
        except OSError: time.sleep(0.005)
    raise RuntimeError('超时')
def rss(p): return int(subprocess.run(['ps', '-o', 'rss=', '-p', str(p.pid)], capture_output=True, text=True).stdout.strip() or 0) / 1024
def get(port, path, timeout=10):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout); c.request('GET', path); r = c.getresponse(); b = r.read().decode(); c.close(); return r.status, b
def stop(p):
    p.send_signal(signal.SIGTERM)
    try: p.wait(15)
    except subprocess.TimeoutExpired: p.kill(); p.wait()
write_proj()
print('Spring Boot 4.0.8 / Spring Framework 7.0.9;JVM 模式用 OpenJDK 21.0.12;原生镜像用 GraalVM Community 25.0.2(native-image),应用 = webmvc + /ping + 几个演示用的接口;构建用 mvn,-J-Xmx6g 限制 native-image 的堆')
print('== 一:构建')
el, rssm = mvn(['-DskipTests', 'package'], JDKS['21']); JAR = P / 'target' / 'app.jar'
print(f'  普通构建 mvn package:{el:.0f} 秒;app.jar {JAR.stat().st_size / 1048576:.1f} MB')
el, rssm = mvn(['-Pnative', '-DskipTests', 'native:compile'], GRAAL); BIN = P / 'target' / 'app'
print(f'  原生构建 mvn -Pnative native:compile:{el:.0f} 秒(含下载依赖之外的全部步骤);/usr/bin/time -l 报告的最大常驻内存(含子进程中最大的一个)约 {rssm:.0f} MB' if rssm else f'  原生构建 {el:.0f} 秒')
print(f'  原生可执行文件 target/app:{BIN.stat().st_size / 1048576:.1f} MB(一个文件,不需要 JDK);Spring AOT 生成的东西(target/spring-aot/main):' + ', '.join(sorted(p.name for p in (P / 'target/spring-aot/main').iterdir())))
gen = [p for p in (P / 'target/spring-aot/main/sources').rglob('*.java')]; print(f'    生成的 Java 源文件 {len(gen)} 个,例如:{sorted(p.name for p in gen)[:4]}')
print('== 二:启动、内存、第一次请求(各 5 次取中位数)')
import jl
CPD = scp('org.springframework.boot:spring-boot-starter-webmvc')
modes = [('JVM:java -jar app.jar', lambda port: (['java', '-jar', str(JAR), f'--server.port={port}'], None)),
         ('JVM + Spring AOT:java -Dspring.aot.enabled=true -cp target/classes:target/spring-aot/main/classes:依赖', lambda port: (['java', '-Dspring.aot.enabled=true', '-cp', f'{P}/target/classes:{P}/target/spring-aot/main/classes:{CPD}', 'demo.Main', f'--server.port={port}'], None)),
         ('原生镜像:./target/app', lambda port: ([str(BIN), f'--server.port={port}'], dict(os.environ)))]
for lab, mk in modes:
    ups, r0, fr, r1 = [], [], [], []
    for _ in range(5):
        port = free_port(); cmd, env = mk(port); p, up = serve(cmd, port, env); ups.append(up); r0.append(rss(p)); t = time.time(); get(port, '/ping'); fr.append((time.time() - t) * 1000); get(port, '/ping'); r1.append(rss(p)); stop(p)
    print(f'  {lab}:端口可连接 中位 {statistics.median(ups):.0f} ms(范围 {min(ups):.0f}~{max(ups):.0f});第 1 次请求 {statistics.median(fr):.1f} ms;常驻内存 启动后 {statistics.median(r0):.0f} MB,2 次请求后 {statistics.median(r1):.0f} MB')
print('== 三:封闭世界:运行时才知道的东西')
for lab, mk in modes[0:1] + modes[2:]:
    port = free_port(); cmd, env = mk(port); p, up = serve(cmd, port, env)
    print(f'  {lab}:')
    for path in ('/runtime', '/reflect?cls=demo.Hidden', '/reflect?cls=demo.Hinted'): print(f'    GET {path} → {get(port, path)[1]}')
    stop(p)
    port = free_port(); cmd, env = mk(port); cmd = cmd + ['--spring.profiles.active=dev']; p, up = serve(cmd, port, env); print(f'    启动时加 --spring.profiles.active=dev:GET /beans → {get(port, "/beans")[1]}'); stop(p)
print('== 四:预热之后的吞吐(JDK HttpClient + 虚拟线程,并发 64,预热 3 秒再测 6 秒,3 轮)')
LOAD = JT / 'x84load'; shutil.rmtree(LOAD, ignore_errors=True); LOAD.mkdir()
src60 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'x60.py')).read(); LOADGEN = re.search(r"LOADGEN = r'''(.*?)'''", src60, re.S).group(1)
(LOAD / 'Load.java').write_text(LOADGEN); (LOAD / 'demo').mkdir(); shutil.move(str(LOAD / 'Load.java'), str(LOAD / 'demo' / 'Load.java'))
subprocess.run(['javac', '-d', str(LOAD / 'out'), str(LOAD / 'demo' / 'Load.java')], env=jenv('21'), check=True, capture_output=True)
def load(port):
    r = subprocess.run(['java', '-cp', str(LOAD / 'out'), 'demo.Load', f'http://127.0.0.1:{port}/ping', '64', '3', '6'], env=jenv('21'), capture_output=True, text=True, timeout=120); m = re.search(r'RES (\d+) ([\d.]+) ([\d.]+) ([\d.]+)', r.stdout); return (float(m.group(2)), float(m.group(4))) if m else None
for lab, mk in (modes[0], modes[2]):
    port = free_port(); cmd, env = mk(port); p, up = serve(cmd, port, env); rs = [load(port) for _ in range(3)]; rr = rss(p); stop(p)
    print(f'  {lab}:' + ' / '.join(f'{r[0]:.0f}' for r in rs) + f' 请求/秒;中位 {statistics.median(r[0] for r in rs):.0f};p99 ' + ' / '.join(f'{r[1]:.1f}' for r in rs) + f' ms;压测后常驻内存 {rr:.0f} MB')
