import sys, os, re, time, json, shutil, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x71'); CP_V = scp('org.springframework.boot:spring-boot-starter-validation'); CP_S = scp('org.springframework.boot:spring-boot-starter')
HDR = 'package demo;\nimport org.springframework.boot.context.properties.*; import org.springframework.boot.context.properties.bind.*; import org.springframework.stereotype.Component; import org.springframework.beans.factory.annotation.Value; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty; import org.springframework.context.annotation.Configuration; import org.springframework.validation.annotation.Validated; import jakarta.validation.constraints.*; import jakarta.validation.Valid; import java.util.*; import java.time.Duration; import org.springframework.util.unit.*; import org.springframework.boot.convert.DurationUnit; import java.time.temporal.ChronoUnit;\n'
def cls(name, body): return (f'src/demo/{name}.java', HDR + body)
def cfg(case, *classes): return cls('Cfg_' + case, f'@Configuration @ConditionalOnProperty(name = "x71.case", havingValue = "{case}") @EnableConfigurationProperties({{{", ".join(c + ".class" for c in classes)}}}) public class Cfg_{case} {{}}\n')
FILES = dict([
 ('src/demo/Main.java', HDR + r'''
@org.springframework.boot.autoconfigure.SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  public static void main(String[] a) {
    org.springframework.boot.SpringApplication app = new org.springframework.boot.SpringApplication(Main.class); app.setBannerMode(org.springframework.boot.Banner.Mode.OFF); app.setWebApplicationType(org.springframework.boot.WebApplicationType.NONE);
    org.springframework.context.ConfigurableApplicationContext c = app.run(a);
    for (Object o : c.getBeansWithAnnotation(ConfigurationProperties.class).values()) if (o.getClass().getName().startsWith("demo.")) r(o.toString());
    if ("rebind".equals(System.getProperty("x71.case"))) {
      var env = c.getEnvironment(); Relaxed bean = c.getBean(Relaxed.class); Holder h = c.getBean(Holder.class);
      env.getPropertySources().addFirst(new org.springframework.core.env.MapPropertySource("late", Map.of("app.first-name", "changed")));
      r("启动之后在 Environment 最前面加 app.first-name=changed:");
      r("  Environment.getProperty        = " + env.getProperty("app.first-name"));
      r("  @ConfigurationProperties bean  = " + bean.getFirstName());
      r("  @Value 字段                    = " + h.v);
      r("  Binder.get(env).bind(...) 重新绑定 = " + Binder.get(env).bind("app", Relaxed.class).get().getFirstName());
    }
    System.exit(0);
  }
}
'''),
 cls('Relaxed', r'''
@ConfigurationProperties("app") public class Relaxed {
  private String firstName; private int maxConnections; private List<String> hosts = new ArrayList<>(); private Map<String, String> labels = new LinkedHashMap<>();
  public String getFirstName() { return firstName; } public void setFirstName(String v) { firstName = v; }
  public int getMaxConnections() { return maxConnections; } public void setMaxConnections(int v) { maxConnections = v; }
  public List<String> getHosts() { return hosts; } public void setHosts(List<String> v) { hosts = v; }
  public Map<String, String> getLabels() { return labels; } public void setLabels(Map<String, String> v) { labels = v; }
  public String toString() { return "firstName=" + firstName + ", maxConnections=" + maxConnections + ", hosts=" + hosts + ", labels=" + labels; }
}'''),
 cls('Holder', r'''@Component @ConditionalOnProperty(name = "x71.case", havingValue = "rebind") public class Holder { @Value("${app.first-name:none}") String v; }'''),
 cls('V', r'''
@ConfigurationProperties("v") @Validated public class V {
  @NotBlank private String name; @Min(1) @Max(10) private int pool = 5; private Inner inner = new Inner(); @Valid private Inner2 inner2 = new Inner2();
  public String getName() { return name; } public void setName(String v) { name = v; } public int getPool() { return pool; } public void setPool(int v) { pool = v; }
  public Inner getInner() { return inner; } public void setInner(Inner v) { inner = v; } public Inner2 getInner2() { return inner2; } public void setInner2(Inner2 v) { inner2 = v; }
  public static class Inner { @NotBlank private String url; public String getUrl() { return url; } public void setUrl(String v) { url = v; } }
  public static class Inner2 { @NotBlank private String url; public String getUrl() { return url; } public void setUrl(String v) { url = v; } }
  public String toString() { return "V{name=" + name + ", pool=" + pool + ", inner.url=" + inner.url + ", inner2.url=" + inner2.url + "}"; }
}'''),
 cls('NoVal', r'''
@ConfigurationProperties("nv") public class NoVal {
  @NotBlank private String name; public String getName() { return name; } public void setName(String v) { name = v; }
  public String toString() { return "NoVal{name=" + name + "}(类上没有 @Validated)"; }
}'''),
 cls('Getters', r'''
@ConfigurationProperties("g") public class Getters {
  private final String name = "init"; private int count = 1;
  public String getName() { return name; } public int getCount() { return count; }
  public String toString() { return "Getters{name=" + name + ", count=" + count + "}(两个字段都只有 getter,没有 setter)"; }
}'''),
 cls('Rec', r'''
@ConfigurationProperties("rec") public record Rec(String name, int count, List<String> tags, Map<String, String> m, Inner in, @DefaultValue Inner inDef, @DefaultValue("dflt") String withDef) {
  public record Inner(String url, @DefaultValue("8080") int port) {}
}'''),
 cls('Multi', r'''
@ConfigurationProperties("multi") public class Multi {
  private final String a; private final String b;
  public Multi(String a) { this.a = a; this.b = null; } public Multi(String a, String b) { this.a = a; this.b = b; }
  public String toString() { return "Multi{a=" + a + ", b=" + b + "}"; }
}'''),
 cls('Multi2', r'''
@ConfigurationProperties("multi2") public class Multi2 {
  private final String a; private final String b;
  public Multi2(String a) { this.a = a; this.b = null; } @ConstructorBinding public Multi2(String a, String b) { this.a = a; this.b = b; }
  public String toString() { return "Multi2{a=" + a + ", b=" + b + "}"; }
}'''),
 cls('Both', r'''
@ConfigurationProperties("both") public class Both {
  private final String a; private String b = "field-default";
  public Both(String a) { this.a = a; } public String getB() { return b; } public void setB(String v) { b = v; }
  public String toString() { return "Both{a=" + a + ", b=" + b + "}"; }
}'''),
 cfg('relaxed', 'Relaxed'), cfg('rebind', 'Relaxed'), cfg('v', 'V'), cfg('noval', 'NoVal'), cfg('getters', 'Getters'), cfg('rec', 'Rec'), cfg('multi', 'Multi'), cfg('multi2', 'Multi2'), cfg('both', 'Both'),
 ('src/demo/Conv.java', HDR + r'''
public class Conv {
  enum Mode { FAST_MODE, SLOW_MODE }
  static class A { @DurationUnit(ChronoUnit.SECONDS) Duration secs; }
  static void r(String s) { System.out.println("RES " + s); }
  static <T> void t(String title, Class<T> type, String... vals) {
    r(title);
    for (String v : vals) {
      try {
        var src = new org.springframework.boot.context.properties.source.MapConfigurationPropertySource(Map.of("p", v));
        Bindable<T> b = Bindable.of(type);
        if (title.startsWith("Duration(@DurationUnit(SECONDS))")) b = b.withAnnotations(A.class.getDeclaredField("secs").getAnnotation(DurationUnit.class));
        T o = new Binder(src).bind("p", b).orElse(null); r(String.format("  \"%s\" → %s", v, o));
      } catch (Exception e) { Throwable c = e; while (c.getCause() != null) c = c.getCause(); r(String.format("  \"%s\" → 失败:%s", v, c.getMessage().replaceAll("\\s+", " ").replace("Failed to convert from type [java.lang.String] to type", "String→"))); }
    }
  }
  public static void main(String[] a) {
    t("Duration(没有单位的数字默认毫秒)", Duration.class, "30s", "PT30S", "2m", "500", "1.5s", "30 s", "1d", "-5s", "PT-5S", "30seconds");
    t("Duration(@DurationUnit(SECONDS))", Duration.class, "500", "500ms", "2m");
    t("DataSize", DataSize.class, "10MB", "10mb", "1024", "1KB", "1.5MB", "10 MB", "2GB");
    t("boolean", Boolean.class, "true", "TRUE", "yes", "on", "1", "y", "no", "off", "0", "t", "");
    t("枚举 Mode{FAST_MODE,SLOW_MODE}", Mode.class, "FAST_MODE", "fast-mode", "fast_mode", "fastMode", "FAST-MODE", "fast mode", "fastmode", "Fast_Mode");
    t("int", Integer.class, "42", "042", "0x1F", "1,000", "3.0", "1000L", "");
    var lt = org.springframework.core.ResolvableType.forClassWithGenerics(List.class, String.class);
    r("List<String>(逗号分隔)");
    for (String v : new String[]{"a,b,c", "a, b ,c", "a,,c", "a", "", "a;b"}) {
      var src = new org.springframework.boot.context.properties.source.MapConfigurationPropertySource(Map.of("p", v));
      Object o = new Binder(src).bind("p", Bindable.of(lt)).orElse(null); r(String.format("  \"%s\" → %s", v, o));
    }
    System.exit(0);
  }
}
'''),
])
LB = '<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>%msg%n</pattern></encoder></appender><logger name="org.springframework.boot.diagnostics.LoggingFailureAnalysisReporter" level="ERROR"/><root level="OFF"><appender-ref ref="C"/></root></configuration>'
FILES['logback.xml'] = LB
b = sbuild('x71', FILES, CP_V)
if b['crc'] != 0: print(b['cout']); sys.exit()
WD = JT / 'x71_wd'
def run(case, props_file='', args=(), props=None, env=None, cp=None, main='demo.Main'):
    shutil.rmtree(WD, ignore_errors=True); WD.mkdir(parents=True)
    if props_file: (WD / 'application.properties').write_text(props_file)
    p = dict(props or {}); p['x71.case'] = case
    bb = dict(b, cp=cp) if cp else b
    r = srun(bb, main, args=list(args), props=p, env=env, cwd=str(WD), timeout=60); l = res(r)
    if l and r['rc'] == 0: return l
    o = r['out']; i = o.find('Description:')
    if i >= 0:
        txt = ' '.join(x.strip() for x in o[i:].splitlines() if x.strip()); txt = re.sub(r'Origin: [^ ]+ ?[^ ]* ?- ?\d+:\d+', 'Origin: …', txt)
        return ['启动失败:' + txt[:520]]
    ex = [x for x in o.splitlines() if re.match(r'^(Exception in thread "main" |Caused by: )?[\w.$]+(Exception|Error):', x)]
    return l + ['启动失败(没有 FailureAnalyzer 报告,堆栈里的异常):' + (ex[-1] if ex and ex[-1].startswith('Caused by') else (ex[0] if ex else o[-300:])).replace('Exception in thread "main" ', '')[:420]]
def pr_(title, lines):
    print(title)
    for l in lines: print('    ' + l)
print('Spring Boot 4.0.8 / JDK 21;每个场景一个独立 JVM,属性写在工作目录的 application.properties、-D 系统属性或环境变量里')
print('== 一:宽松绑定:同一个字段 firstName 能用哪些写法')
for k in ('app.first-name', 'app.firstName', 'app.first_name', 'app.firstname', 'app.FIRST-NAME'):
    pr_(f'  application.properties 里写 {k}=v:', run('relaxed', f'{k}=v\n'))
for k in ('APP_FIRSTNAME', 'APP_FIRST_NAME', 'APP_FIRST__NAME'):
    pr_(f'  操作系统环境变量 {k}=v:', run('relaxed', '', env={k: 'v'}))
print('== 二:列表与 Map:写法,以及不同来源的合并规则')
pr_('  app.hosts=a,b,c:', run('relaxed', 'app.hosts=a,b,c\n'))
pr_('  app.hosts[0]=x 与 app.hosts[1]=y:', run('relaxed', 'app.hosts[0]=x\napp.hosts[1]=y\n'))
pr_('  app.hosts[1]=y(没有 [0]):', run('relaxed', 'app.hosts[1]=y\n'))
pr_('  环境变量 APP_HOSTS_0=e0、APP_HOSTS_1=e1:', run('relaxed', '', env={'APP_HOSTS_0': 'e0', 'APP_HOSTS_1': 'e1'}))
pr_('  环境变量 APP_HOSTS=a,b:', run('relaxed', '', env={'APP_HOSTS': 'a,b'}))
pr_('  文件里 app.hosts=a,b,c,系统属性 -Dapp.hosts[0]=z(不同来源的列表合并还是替换):', run('relaxed', 'app.hosts=a,b,c\n', props={'app.hosts[0]': 'z'}))
pr_('  app.labels.env=prod:', run('relaxed', 'app.labels.env=prod\n'))
pr_('  app.labels.a.b=x(key 里有点号,不加方括号):', run('relaxed', 'app.labels.a.b=x\n'))
pr_('  app.labels[a.b]=x(加方括号):', run('relaxed', 'app.labels[a.b]=x\n'))
pr_('  环境变量 APP_LABELS_ENV=prod:', run('relaxed', '', env={'APP_LABELS_ENV': 'prod'}))
pr_('  文件里 app.labels.a=1,系统属性 -Dapp.labels.b=2(不同来源的 Map 合并还是替换):', run('relaxed', 'app.labels.a=1\n', props={'app.labels.b': '2'}))
print('== 三:类型转换(直接用 Binder,@ConfigurationProperties 底层就是它)')
r = srun(b, 'demo.Conv', timeout=60)
for l in res(r) or [r['out'][-800:]]: print('  ' + l if not l.startswith('  ') else l)
print('  -- 绑定失败时的启动报错')
pr_('  app.max-connections=abc:', run('relaxed', 'app.max-connections=abc\n'))
print('== 四:校验:@Validated 与 jakarta.validation')
pr_('  name 空白、pool=11,inner.url 与 inner2.url 都填了:', run('v', 'v.name=\nv.pool=11\nv.inner.url=u1\nv.inner2.url=u2\n'))
pr_('  name 与 pool 正常,inner.url(嵌套对象,没有 @Valid)缺失,inner2.url 填了:', run('v', 'v.name=ok\nv.inner2.url=u2\n'))
pr_('  name 与 pool 正常,inner2.url(嵌套对象,有 @Valid)缺失,inner.url 填了:', run('v', 'v.name=ok\nv.inner.url=u1\n'))
pr_('  类上没有 @Validated,字段上写了 @NotBlank,name 缺失:', run('noval', ''))
pr_('  类上有 @Validated,但运行时 classpath 里没有 hibernate-validator(只有 spring-boot-starter),name 空白、pool=11:', run('v', 'v.name=\nv.pool=11\n', cp=CP_S))
print('== 五:JavaBean 绑定与构造器绑定')
pr_('  字段是 final、只有 getter 没有 setter,配置 g.name=changed:', run('getters', 'g.name=changed\n'))
pr_('  字段不是 final、只有 getter 没有 setter,配置 g.count=7:', run('getters', 'g.count=7\n'))
pr_('  同样的类,g.name、g.count 都不配:', run('getters', ''))
pr_('  record,什么都不配:', run('rec', ''))
pr_('  record,配置 rec.name=n、rec.count=3、rec.tags=x,y、rec.m.k=v、rec.in.url=u、rec.in-def.url=u2、rec.with-def=given:', run('rec', 'rec.name=n\nrec.count=3\nrec.tags=x,y\nrec.m.k=v\nrec.in.url=u\nrec.in-def.url=u2\nrec.with-def=given\n'))
pr_('  类有两个构造器、都没有 @ConstructorBinding,配置 multi.a=1:', run('multi', 'multi.a=1\n'))
pr_('  类有两个构造器、其中一个标了 @ConstructorBinding,配置 multi2.a=1、multi2.b=2:', run('multi2', 'multi2.a=1\nmulti2.b=2\n'))
pr_('  类只有一个带参构造器(没有注解)又有 setter,配置 both.a=1、both.b=2:', run('both', 'both.a=1\nboth.b=2\n'))
print('== 六:绑定只发生一次')
pr_('  app.first-name=initial 启动,启动之后再往 Environment 里加新值:', run('rebind', 'app.first-name=initial\n'))
