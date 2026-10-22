import sys, os, re, time, json, shutil, subprocess, statistics, zipfile, hashlib, pathlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x77')
P = JT / 'x77proj'
POM = '''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>4.0.8</version></parent>
<groupId>demo</groupId><artifactId>app</artifactId><version>1.0.0</version><properties><java.version>21</java.version></properties>
<dependencies><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-webmvc</artifactId></dependency></dependencies>
<build><finalName>app</finalName><plugins><plugin><groupId>org.springframework.boot</groupId><artifactId>spring-boot-maven-plugin</artifactId></plugin></plugins></build></project>'''
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.context.event.ApplicationReadyEvent; import org.springframework.context.event.EventListener; import org.springframework.core.io.ClassPathResource; import org.springframework.web.bind.annotation.*;
@SpringBootApplication @RestController
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  @GetMapping("/ping") String ping() { return "pong"; }
  @EventListener void ready(ApplicationReadyEvent e) throws Exception {
    if (System.getProperty("x77.facts") != null) {
      r("Main 类的来源:" + Main.class.getProtectionDomain().getCodeSource().getLocation());
      r("Main 类的类加载器:" + Main.class.getClassLoader().getClass().getName());
      String cp = System.getProperty("java.class.path"); r("java.class.path:" + (cp.length() > 140 ? cp.substring(0, 140) + "…(共 " + cp.length() + " 个字符)" : cp));
      var res = new ClassPathResource("data.txt"); r("ClassPathResource(data.txt).getURL() = " + res.getURL());
      try { r("  getFile() = " + res.getFile()); } catch (Exception ex) { r("  getFile() 抛 " + ex.getClass().getSimpleName() + ":" + ex.getMessage()); }
      r("  getInputStream() 读到 " + new String(res.getInputStream().readAllBytes()).trim().length() + " 个字符:" + new String(res.getInputStream().readAllBytes()).trim());
    }
    if (System.getProperty("x77.exit") != null) System.exit(0);
  }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
LB = '<configuration><root level="OFF"/></configuration>'
def write_proj(extra=''):
    shutil.rmtree(P, ignore_errors=True); (P / 'src/main/java/demo').mkdir(parents=True); (P / 'src/main/resources').mkdir(parents=True)
    (P / 'pom.xml').write_text(POM); (P / 'src/main/java/demo/Main.java').write_text(MAIN + extra); (P / 'src/main/resources/data.txt').write_text('hello from data.txt\n'); (P / 'src/main/resources/logback.xml').write_text(LB)
def build():
    e = jenv('21', MAVEN_OPTS='-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=1087 -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=1087'); t = time.time()
    r = subprocess.run(['mvn', '-q', '-f', str(P / 'pom.xml'), 'package', '-DskipTests'], env=e, capture_output=True, text=True, timeout=900)
    if r.returncode != 0: print((r.stdout + r.stderr)[-1500:]); sys.exit(1)
    return time.time() - t
write_proj(); secs = build(); JAR = P / 'target' / 'app.jar'
print('Spring Boot 4.0.8 / JDK 21 / spring-boot-maven-plugin(版本由 starter-parent 管理);应用 = webmvc + 一个 /ping + resources/data.txt')
print('== 一:可执行 jar 里面有什么')
z = zipfile.ZipFile(JAR); infos = z.infolist()
print(f'  mvn package 用时 {secs:.0f} 秒;app.jar 大小 {JAR.stat().st_size / 1024 / 1024:.2f} MB,共 {len(infos)} 个条目')
mf = z.read('META-INF/MANIFEST.MF').decode().replace('\r\n', '\n').strip().splitlines()
print('  META-INF/MANIFEST.MF:')
for l in mf: print('    ' + l)
top = {}
for i in infos:
    k = i.filename.split('/')[0] + ('/' + i.filename.split('/')[1] if i.filename.startswith(('BOOT-INF', 'META-INF')) and '/' in i.filename.rstrip('/') else '')
    top.setdefault(k, []).append(i)
print('  顶层结构(按目录汇总条目数):')
for k in sorted(top): print(f'    {k}:{len(top[k])} 个条目')
libs = [i for i in infos if i.filename.startswith('BOOT-INF/lib/') and i.filename.endswith('.jar')]
print(f'  BOOT-INF/lib 里嵌套的 jar:{len(libs)} 个,合计 {sum(i.file_size for i in libs) / 1024 / 1024:.1f} MB;压缩方式:' + '、'.join(f'{ {0: "STORED(不压缩)", 8: "DEFLATED(压缩)"}.get(c, c)} × {n}' for c, n in sorted({c: sum(1 for i in libs if i.compress_type == c) for c in {i.compress_type for i in libs}}.items())))
cls = [i for i in infos if i.filename.startswith('BOOT-INF/classes/')]
print('  BOOT-INF/classes 里的条目:' + '、'.join(i.filename[len('BOOT-INF/classes/'):] for i in cls if not i.is_dir()))
for nm in ('BOOT-INF/classpath.idx', 'BOOT-INF/layers.idx'):
    if nm in z.namelist():
        t = z.read(nm).decode().strip().splitlines(); print(f'  {nm}({len(t)} 行),前 6 行:'); [print('    ' + l) for l in t[:6]]
print('== 二:四种跑法的启动时间(进程启动到 ApplicationReadyEvent 后 System.exit(0),各 7 次取中位数)')
def timed(cmd, n=7, props=('-Dx77.exit=1',), cwd=None):
    ts = []
    for _ in range(n):
        t = time.time(); r = subprocess.run(['java', *props, *cmd], env=jenv('21'), capture_output=True, text=True, cwd=cwd, timeout=120); ts.append((time.time() - t) * 1000)
        if r.returncode != 0: print('  失败:', (r.stdout + r.stderr)[-400:]); break
    return statistics.median(ts), min(ts), max(ts)
EX = P / 'target' / 'exploded'; shutil.rmtree(EX, ignore_errors=True); EX.mkdir(); zipfile.ZipFile(JAR).extractall(EX)
TOOLS = P / 'target' / 'extracted'; shutil.rmtree(TOOLS, ignore_errors=True)
r = subprocess.run(['java', '-Djarmode=tools', '-jar', str(JAR), 'extract', '--destination', str(TOOLS)], env=jenv('21'), capture_output=True, text=True, timeout=120)
print(f'  java -Djarmode=tools -jar app.jar extract --destination …:退出码 {r.returncode};输出 {tidy(r.stdout + r.stderr)[:200]!r}')
if TOOLS.exists(): print('    解出来的内容:' + '、'.join(sorted(p.name + ('/' if p.is_dir() else '') for p in TOOLS.iterdir())) + f';lib 目录里 {len(list((TOOLS / "lib").glob("*.jar")))} 个 jar')
mfx = zipfile.ZipFile(TOOLS / 'app.jar').read('META-INF/MANIFEST.MF').decode().replace('\r\n', '\n').replace('\n ', '').strip().splitlines()
print('    解出来的 app.jar 的 MANIFEST:' + ';'.join(l[:110] for l in mfx if l.startswith(('Main-Class', 'Class-Path'))))
rows = [('胖 jar:java -jar app.jar', ['-jar', str(JAR)]), ('解压后的目录:java -cp BOOT-INF/classes:BOOT-INF/lib/* demo.Main', ['-cp', f'{EX}/BOOT-INF/classes:{EX}/BOOT-INF/lib/*', 'demo.Main']), ('解压后的目录:java org.springframework.boot.loader.launch.JarLauncher', ['-cp', str(EX), 'org.springframework.boot.loader.launch.JarLauncher']), ('tools extract 之后:java -jar extracted/app.jar', ['-jar', str(TOOLS / 'app.jar')])]
for lab, cmd in rows:
    m, lo, hi = timed(cmd); print(f'  {lab}:中位 {m:.0f} ms(范围 {lo:.0f}~{hi:.0f})')
print('== 三:分层 jar:每一层是什么,改一行代码哪些层会变')
r = subprocess.run(['java', '-Djarmode=tools', '-jar', str(JAR), 'list-layers'], env=jenv('21'), capture_output=True, text=True, timeout=60)
print(f'  list-layers(退出码 {r.returncode}):' + (' '.join((r.stdout + r.stderr).split()) if r.returncode == 0 else tidy(r.stdout + r.stderr)[:300]))
def extract_layers(dest):
    shutil.rmtree(dest, ignore_errors=True); r = subprocess.run(['java', '-Djarmode=tools', '-jar', str(JAR), 'extract', '--layers', '--destination', str(dest)], env=jenv('21'), capture_output=True, text=True, timeout=120)
    if r.returncode != 0: print('  extract --layers 失败:', tidy(r.stdout + r.stderr)[:400])
def layer_stats(dest):
    out = {}
    for d in sorted(p for p in dest.iterdir() if p.is_dir()):
        files = sorted(f for f in d.rglob('*') if f.is_file()); h = hashlib.sha256()
        for f in files: h.update(str(f.relative_to(d)).encode()); h.update(f.read_bytes())
        out[d.name] = (len(files), sum(f.stat().st_size for f in files), h.hexdigest()[:10])
    return out
L1 = P / 'target' / 'layers1'; extract_layers(L1); s1 = layer_stats(L1)
print('  每一层(文件数、大小、内容指纹前 10 位):')
for k, (n, sz, h) in s1.items(): print(f'    {k}:{n} 个文件,{sz / 1024:.0f} KB,指纹 {h}')
# 改一行业务代码再打包
write_proj('\n// x77: 业务代码多一个方法\nclass Extra { String hello() { return "hello"; } }\n'); build()
L2 = P / 'target' / 'layers2'; extract_layers(L2); s2 = layer_stats(L2)
print('  只在应用里多加一个类、重新打包之后:')
for k in s1: print(f'    {k}:' + ('指纹没变' if s1[k][2] == s2.get(k, (0, 0, ""))[2] else f'指纹变了({s1[k][2]} → {s2.get(k, (0, 0, "-"))[2]})') + f';大小 {s1[k][1] / 1024:.0f} KB → {s2.get(k, (0, 0, ""))[1] / 1024:.0f} KB')
print(f'  新 app.jar 大小 {JAR.stat().st_size / 1024 / 1024:.2f} MB;分层提取之后,没变的层(dependencies 等)在 Docker 里可以复用缓存,变的只有 application 层')
print('== 四:在胖 jar 里读 classpath 资源')
EX = P / 'target' / 'exploded2'; shutil.rmtree(EX, ignore_errors=True); EX.mkdir(); zipfile.ZipFile(JAR).extractall(EX)
for lab, cmd in (('胖 jar', ['-jar', str(JAR)]), ('解压后的目录', ['-cp', f'{EX}/BOOT-INF/classes:{EX}/BOOT-INF/lib/*', 'demo.Main'])):
    r = subprocess.run(['java', '-Dx77.exit=1', '-Dx77.facts=1', *cmd], env=jenv('21'), capture_output=True, text=True, timeout=120)
    print(f'  {lab}:')
    for l in res(dict(rc=r.returncode, out=r.stdout)): print('    ' + tidy(l).replace(str(P), '<项目>'))
