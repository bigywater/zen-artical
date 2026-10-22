import sys, os, re, time, json, zipfile; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x66')
STARTERS = ['spring-boot-starter', 'spring-boot-starter-webmvc', 'spring-boot-starter-webflux', 'spring-boot-starter-data-jpa', 'spring-boot-starter-security', 'spring-boot-starter-actuator', 'spring-boot-starter-validation', 'spring-boot-starter-test']
print('Spring Boot 4.0.8;每个 starter 单独解析出完整 classpath(含传递依赖),统计 jar 个数和总大小')
print('== 一:各个 starter 拉来多少 jar')
CPS = {}
for st in STARTERS:
    cp = scp('org.springframework.boot:' + st); CPS[st] = cp; jars = [j for j in cp.split(':') if j]; mb = sum(os.path.getsize(j) for j in jars if os.path.exists(j)) / 1048576
    boot = [os.path.basename(j) for j in jars if os.path.basename(j).startswith('spring-boot-') and 'starter' not in os.path.basename(j)]
    print(f'  {st:<34} {len(jars):>3} 个 jar,共 {mb:5.1f} MB;其中 spring-boot-* 模块 {len(boot)} 个,starter 自身 {sum(1 for j in jars if "starter" in os.path.basename(j))} 个')
print('== 二:starter 的 jar 里面有什么')
for st in ['spring-boot-starter-webmvc', 'spring-boot-starter-data-jpa']:
    j = [x for x in CPS[st].split(':') if os.path.basename(x).startswith(st + '-4')][0]; z = zipfile.ZipFile(j); names = z.namelist()
    cls = [n for n in names if n.endswith('.class')]; print(f'  {os.path.basename(j)}:共 {len(names)} 个条目,其中 .class 文件 {len(cls)} 个,大小 {os.path.getsize(j)} 字节;条目 = {[n for n in names if not n.endswith("/")]}')
print('== 三:starter 的 pom 声明了哪些直接依赖(spring-boot-starter-webmvc)')
j = [x for x in CPS['spring-boot-starter-webmvc'].split(':') if os.path.basename(x).startswith('spring-boot-starter-webmvc-4')][0]
pom = j.replace('.jar', '.pom')
if os.path.exists(pom):
    t = open(pom).read(); deps = re.findall(r'<dependency>\s*<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>(?:\s*<version>[^<]*</version>)?(?:\s*<scope>([^<]+)</scope>)?', t)
    for g, a, sc in deps: print(f'  {g}:{a}  {sc or "compile"}')
else: print('  (没有找到 pom 文件)')
print('== 四:只有一个 starter 与加了 webmvc 之后,同一份启动代码的差别')
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.ConfigurableApplicationContext;
@SpringBootApplication
public class Main { public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); long t0 = System.currentTimeMillis(); ConfigurableApplicationContext c = app.run(a); long ms = System.currentTimeMillis() - t0;
  boolean dispatcher; try { Class.forName("org.springframework.web.servlet.DispatcherServlet"); dispatcher = true; } catch (Throwable e) { dispatcher = false; }
  System.out.println("RES 应用类型 = " + app.getWebApplicationType() + ",Bean 总数 = " + c.getBeanDefinitionCount() + ",类路径上有 DispatcherServlet = " + dispatcher + ",有 Tomcat 的 Bean = " + c.containsBean("tomcatServletWebServerFactory") + ",启动用时 " + ms + " ms");
  System.exit(0); } }
'''
for st in ['spring-boot-starter', 'spring-boot-starter-webmvc']:
    b = sbuild('x66_' + st[-6:], {'src/demo/Main.java': MAIN, 'logback.xml': '<configuration><root level="OFF"/></configuration>'}, CPS[st])
    if b['crc'] != 0: print(b['cout']); continue
    r = srun(b, 'demo.Main', props={'server.port': '0'}, timeout=60); l = res(r); print(f'  类路径 = {st}:' + (l[0] if l else r['out'][-400:]))
