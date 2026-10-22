import sys, os, re, time, json, shutil, subprocess, statistics, socket; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x85')
CP = scp('org.springframework.boot:spring-boot-starter-webmvc', 'org.springframework.boot:spring-boot-starter-jdbc', 'com.mysql:mysql-connector-j')
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty; import org.springframework.boot.context.properties.*; import org.springframework.boot.diagnostics.*; import org.springframework.context.annotation.*; import org.springframework.stereotype.Component; import org.springframework.beans.factory.annotation.Value; import jakarta.annotation.PostConstruct; import java.util.*;\n'
def cond(case): return f'@Configuration @ConditionalOnProperty(name = "x85.case", havingValue = "{case}")'
FILES = {
 'src/demo/Main.java': HDR + '''
@SpringBootApplication @EnableConfigurationProperties(Bp.class)
public class Main {
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); System.out.println("RES 启动成功"); if (System.getProperty("x85.exit") != null) System.exit(0); }
}
''',
 'src/demo/Bp.java': HDR + '@ConfigurationProperties("bp") @ConditionalOnProperty(name = "x85.case", havingValue = "binding") public class Bp { private int port; public int getPort() { return port; } public void setPort(int p) { port = p; } }\n',
 'src/demo/Cases.java': HDR + '''
interface MissingDep {}
interface Dup {}
@Component @ConditionalOnProperty(name = "x85.case", havingValue = "nobean") class NeedsMissing { NeedsMissing(MissingDep d) {} }
@Component @ConditionalOnProperty(name = "x85.case", havingValue = "twobeans") class Dup1 implements Dup {}
@Component @ConditionalOnProperty(name = "x85.case", havingValue = "twobeans") class Dup2 implements Dup {}
@Component @ConditionalOnProperty(name = "x85.case", havingValue = "twobeans") class NeedsDup { NeedsDup(Dup d) {} }
@Component @ConditionalOnProperty(name = "x85.case", havingValue = "cycle") class CycA { CycA(CycB b) {} }
@Component @ConditionalOnProperty(name = "x85.case", havingValue = "cycle") class CycB { CycB(CycA a) {} }
@Component @ConditionalOnProperty(name = "x85.case", havingValue = "placeholder") class Ph { Ph(@Value("${nope.value}") String v) {} }
@Component @ConditionalOnProperty(name = "x85.case", havingValue = "custom") class Cust { @PostConstruct void init() { throw new MyConfigException("缺少配置项 app.licence-key"); } }
@Component @ConditionalOnProperty(name = "x85.case", havingValue = "uncovered") class Unc { @PostConstruct void init() { throw new OtherException("没人给我写分析器"); } }
class MyConfigException extends RuntimeException { MyConfigException(String m) { super(m); } }
class OtherException extends RuntimeException { OtherException(String m) { super(m); } }
class MyAnalyzer extends AbstractFailureAnalyzer<MyConfigException> {
  @Override protected FailureAnalysis analyze(Throwable rootFailure, MyConfigException cause) { return new FailureAnalysis("应用缺少必需的配置:" + cause.getMessage(), "在 application.properties 里加上这个配置项,或者设置对应的环境变量。", cause); }
}
''',
 'src/demo/Lst.java': HDR + '''
public class Lst { public static void main(String[] a) {
  var l = org.springframework.core.io.support.SpringFactoriesLoader.forDefaultResourceLocation(Lst.class.getClassLoader()).load(FailureAnalyzer.class);
  System.out.println("RES 通过 SpringFactoriesLoader 加载到的 FailureAnalyzer 一共 " + l.size() + " 个");
  Map<String, Integer> byPkg = new TreeMap<>(); for (var x : l) byPkg.merge(x.getClass().getPackageName(), 1, Integer::sum);
  byPkg.forEach((k, v) -> System.out.println("RES   " + k + ":" + v + " 个"));
  List<String> n = new ArrayList<>(); for (var x : l) n.add(x.getClass().getSimpleName()); Collections.sort(n); System.out.println("RES   前 12 个类名(按字母序):" + n.subList(0, Math.min(12, n.size())));
  System.out.println("RES   其中有我自己的 MyAnalyzer:" + n.contains("MyAnalyzer"));
} }
''',
 'META-INF/spring.factories': 'org.springframework.boot.diagnostics.FailureAnalyzer=demo.MyAnalyzer\n',
}
b = sbuild('x85', FILES, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(case=None, props=None, args=(), jopts=(), cwd=None):
    pr = dict(props or {}); pr.setdefault('spring.autoconfigure.exclude', 'org.springframework.boot.jdbc.autoconfigure.DataSourceAutoConfiguration') if case != 'datasource-none' and not (props or {}).get('spring.main.web-application-type') else None
    if case: pr['x85.case'] = case
    r = srun(b, 'demo.Main', args=list(args), props=pr, jopts=list(jopts), timeout=60, cwd=cwd); return r
def block(o, n=18):
    L = o.splitlines(); i = next((k for k, l in enumerate(L) if 'APPLICATION FAILED TO START' in l), None)
    if i is None: return None
    out = []; seen_action = False
    for l in L[i:]:
        if re.match(r'^\d{4}-\d\d-\d\dT', l): break
        if l.startswith('Action:'): seen_action = True
        if seen_action and not l.strip() and out and out[-1].strip() != 'Action:': break
        if l.strip(): out.append(l)
    return out[:n]
def noreport(r):
    L = [l for l in r['out'].splitlines() if l.strip()]; ex = [l.strip() for l in L if re.match(r'^(Caused by: )?[\w.$]+(Exception|Error):', l.strip())]
    return f'没有失败报告;控制台共 {len(L)} 行,其中以 at 开头的堆栈帧 {sum(1 for l in L if l.strip().startswith("at "))} 行;最里面的异常:{(ex[-1] if ex else "?")[:200]}'
print('Spring Boot 4.0.8 / JDK 21;用 Boot 默认的日志配置(没有自己的 logback.xml),所以下面是用户在控制台上真实会看到的内容;每个场景一个独立 JVM')
print('== 一:几种常见的启动失败,Boot 打印的报告')
CASES = [('找不到依赖的 Bean', 'nobean', None), ('同类型有两个 Bean', 'twobeans', None), ('构造器循环依赖', 'cycle', None), ('@ConfigurationProperties 绑定失败(bp.port=abc)', 'binding', {'bp.port': 'abc'}), ('@Value 占位符没有值', 'placeholder', None), ('数据源:有 JDBC 驱动但没配 url', 'datasource-none', {'spring.main.web-application-type': 'none'})]
for lab, case, pr in CASES:
    r = run(case if case != 'datasource-none' else None, pr); bl = block(r['out'])
    print(f'  {lab}(退出码 {r["rc"]}):')
    if bl: [print('    ' + x[:230]) for x in bl]
    else: print('    ' + noreport(r))
print('  端口被占用:')
s = socket.socket(socket.AF_INET6); s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0); s.bind(('::', 0)); s.listen(1); port = s.getsockname()[1]; r = run(None, {'server.port': port}); s.close(); bl = block(r['out'])
print(f'  (先让别的进程占住 {port} 端口,退出码 {r["rc"]})'); [print('    ' + x[:230]) for x in (bl or ['(没有报告)'])]
print('== 二:报告是怎么生成的:FailureAnalyzer')
import zipfile
tot = 0; per = {}
for j in CP.strip().split(':'):
    if not j.endswith('.jar') or not os.path.exists(j): continue
    z = zipfile.ZipFile(j)
    for nm in ('META-INF/spring.factories',):
        if nm in z.namelist():
            t = z.read(nm).decode().replace('\\\n', '').replace('\\\r\n', '')
            m = re.search(r'org\.springframework\.boot\.diagnostics\.FailureAnalyzer\s*=\s*([^\n]*)', t)
            if m:
                ns = [x.strip() for x in m.group(1).split(',') if x.strip()]; per[os.path.basename(j)] = ns; tot += len(ns)
print(f'  扫描 classpath 上全部 jar 的 META-INF/spring.factories,登记在 FailureAnalyzer 名下的类一共 {tot} 个,分布在 {len(per)} 个 jar 里:')
for k, v in per.items(): print(f'    {k}:{len(v)} 个,例如 {[x.split(".")[-1] for x in v[:3]]}')
imps = 0
for j in CP.strip().split(':'):
    if j.endswith('.jar') and os.path.exists(j):
        z = zipfile.ZipFile(j); imps += sum(1 for n in z.namelist() if n.startswith('META-INF/spring/') and 'FailureAnalyzer' in n)
print(f'  另外 META-INF/spring/*.FailureAnalyzer.imports 形式的文件:{imps} 个')
print('== 三:自己写一个 FailureAnalyzer(在 META-INF/spring.factories 里登记)')
r = run('custom'); bl = block(r['out']); print(f'  抛 MyConfigException 的 @PostConstruct,登记了 MyAnalyzer(退出码 {r["rc"]}):'); [print('    ' + x[:230]) for x in (bl or ['(没有报告)'])]
r = run('uncovered'); bl = block(r['out']); L = [l for l in r['out'].splitlines() if l.strip()]
print(f'  抛 OtherException,没有登记分析器(退出码 {r["rc"]}):' + ('出现了 APPLICATION FAILED TO START 报告' if bl else noreport(r)))
print('== 四:同一个失败,报告与堆栈各有多少行;--debug 之后')
r1 = run('nobean'); L1 = [l for l in r1['out'].splitlines() if l.strip()]; r2 = run('nobean', args=['--debug']); L2 = [l for l in r2['out'].splitlines() if l.strip()]
print(f'  找不到依赖的 Bean:默认控制台 {len(L1)} 行(其中失败报告 {len(block(r1["out"], 99) or [])} 行,堆栈帧 {sum(1 for l in L1 if l.strip().startswith("at "))} 行);加 --debug 之后 {len(L2)} 行,其中堆栈帧(以 at 开头的行)有 {sum(1 for l in L2 if l.strip().startswith("at "))} 行,另外出现了条件评估报告:{any("CONDITIONS EVALUATION REPORT" in l for l in L2)}')
print('  --debug 之后多出来的内容里,以 Caused by 或异常类名开头的行:')
for l in [l.strip() for l in L2 if l.strip().startswith(("Caused by", "org.springframework.beans.factory"))][:4]: print('    ' + l[:200])
