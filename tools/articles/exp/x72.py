import sys, os, re, time, json, shutil, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x72'); CP = scp('org.springframework.boot:spring-boot-starter')
LB = '<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>%msg%n</pattern></encoder></appender><logger name="org.springframework.boot.diagnostics.LoggingFailureAnalysisReporter" level="ERROR"/><root level="OFF"><appender-ref ref="C"/></root></configuration>'
HDR = 'package demo;\nimport org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.ConfigurableApplicationContext; import org.springframework.context.annotation.*; import org.springframework.core.env.*; import java.util.*;\n'
MAIN = HDR + r'''
@SpringBootApplication @org.springframework.context.annotation.PropertySource(value = "classpath:/extra72.properties", ignoreResourceNotFound = true)
public class Main {
  record Mark(String id) {}
  static void r(String s) { System.out.println("RES " + s); }
  @Configuration static class Beans {
    @Bean @Profile("dev") Mark b1() { return new Mark("dev"); }
    @Bean @Profile("!prod") Mark b2() { return new Mark("!prod"); }
    @Bean @Profile("dev & cloud") Mark b3() { return new Mark("dev & cloud"); }
    @Bean @Profile("dev | test") Mark b4() { return new Mark("dev | test"); }
    @Bean @Profile("(dev | test) & !cloud") Mark b5() { return new Mark("(dev | test) & !cloud"); }
    @Bean @Profile({"x", "y"}) Mark b6() { return new Mark("{x, y}"); }
    @Bean @Profile("default") Mark b7() { return new Mark("default"); }
    @Bean @Profile({"dev", "!cloud"}) Mark b8() { return new Mark("{dev, !cloud}"); }
    @Bean @Profile("dev,test") Mark b9() { return new Mark("dev,test"); }
  }
  public static void main(String[] a) {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    if (System.getProperty("x72.additional") != null) app.setAdditionalProfiles(System.getProperty("x72.additional").split(","));
    ConfigurableApplicationContext c = app.run(a); ConfigurableEnvironment env = c.getEnvironment();
    r("active=" + Arrays.toString(env.getActiveProfiles()) + " default=" + Arrays.toString(env.getDefaultProfiles()));
    String keys = System.getProperty("x72.keys");
    if (keys != null) for (String k : keys.split(",")) {
      String src = "-"; for (org.springframework.core.env.PropertySource<?> ps : env.getPropertySources()) if (!ps.getName().equals("configurationProperties") && ps.containsProperty(k)) { src = ps.getName(); break; }
      r(String.format("%s = %s ←| %s", k, env.getProperty(k), src.replace("Config resource ", "").replaceAll("' via location.*", "'").replace("class path resource [", "classpath:[").replace("file [", "file:[")));
    }
    if (System.getProperty("x72.beans") != null) { List<String> l = new ArrayList<>(); for (Object o : c.getBeansOfType(Mark.class).values()) l.add(((Mark) o).id()); r("生效的 @Profile Bean:" + (l.isEmpty() ? "(没有)" : String.join("、", l))); }
    System.exit(0);
  }
}
'''
b = sbuild('x72', {'src/demo/Main.java': MAIN, 'logback.xml': LB}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
WD = JT / 'x72_wd'
def run(files=None, cp=None, args=(), props=None, env=None, keys=None, beans=False, bb=None):
    shutil.rmtree(WD, ignore_errors=True); WD.mkdir(parents=True); rc = WD / 'rc'; rc.mkdir()
    for k, v in (files or {}).items(): (WD / k).parent.mkdir(parents=True, exist_ok=True); (WD / k).write_text(v)
    for k, v in (cp or {}).items(): (rc / k).write_text(v)
    p = dict(props or {})
    if keys: p['x72.keys'] = keys
    if beans: p['x72.beans'] = '1'
    b2 = dict(bb or b); b2['cp'] = str(rc) + ':' + b2['cp']
    r = srun(b2, 'demo.Main', args=list(args), props=p, env=env, cwd=str(WD), timeout=60); l = res(r)
    if l and r['rc'] == 0: return l
    o = r['out']; i = o.find('Description:')
    if i >= 0: return ['启动失败:' + ' '.join(x.strip() for x in o[i:].splitlines() if x.strip())[:420]]
    ex = [x for x in o.splitlines() if re.match(r'^(Exception in thread "main" |Caused by: )?[\w.$]+(Exception|Error):', x)]
    return ['启动失败(没有 FailureAnalyzer 报告,堆栈里的异常):' + (ex[-1] if ex and ex[-1].startswith('Caused by') else (ex[0] if ex else o[-300:])).replace('Exception in thread "main" ', '')[:420]]
def pr_(title, lines):
    print(title)
    for l in lines: print('    ' + l)
print('Spring Boot 4.0.8 / JDK 21;每个场景一个独立 JVM,工作目录是临时目录;active 是 Environment.getActiveProfiles(),default 是 getDefaultProfiles()')
print('== 一:激活 profile 的方式与优先级')
K = 'app.v'
pr_('  什么都不设:', run(keys=K, beans=True, files={'application.properties': 'app.v=base\n', 'application-dev.properties': 'app.v=dev\n'}))
FILES1 = {'application.properties': 'app.v=base\n', 'application-dev.properties': 'app.v=dev\n', 'application-prod.properties': 'app.v=prod\n', 'application-qa.properties': 'app.v=qa\n', 'application-fallback.properties': 'app.v=fallback\n'}
pr_('  application.properties 里写 spring.profiles.active=dev:', run(dict(FILES1, **{'application.properties': 'app.v=base\nspring.profiles.active=dev\n'}), keys=K))
pr_('  -Dspring.profiles.active=dev,prod(系统属性,两个 profile):', run(FILES1, props={'spring.profiles.active': 'dev,prod'}, keys=K))
pr_('  环境变量 SPRING_PROFILES_ACTIVE=qa:', run(FILES1, env={'SPRING_PROFILES_ACTIVE': 'qa'}, keys=K))
pr_('  命令行 --spring.profiles.active=prod,文件里写的是 dev:', run(dict(FILES1, **{'application.properties': 'app.v=base\nspring.profiles.active=dev\n'}), args=['--spring.profiles.active=prod'], keys=K))
pr_('  系统属性 -Dspring.profiles.active=prod,环境变量 SPRING_PROFILES_ACTIVE=qa:', run(FILES1, props={'spring.profiles.active': 'prod'}, env={'SPRING_PROFILES_ACTIVE': 'qa'}, keys=K))
pr_('  代码里 setAdditionalProfiles("qa") 再配 --spring.profiles.active=dev:', run(FILES1, props={'x72.additional': 'qa'}, args=['--spring.profiles.active=dev'], keys=K))
pr_('  spring.profiles.include=qa,配 --spring.profiles.active=dev:', run(dict(FILES1, **{'application.properties': 'app.v=base\nspring.profiles.include=qa\n'}), args=['--spring.profiles.active=dev'], keys=K))
pr_('  spring.profiles.default=fallback(没有激活任何 profile):', run(dict(FILES1, **{'application.properties': 'app.v=base\nspring.profiles.default=fallback\n'}), keys=K, beans=True))
pr_('  spring.profiles.default=fallback,同时激活 dev:', run(dict(FILES1, **{'application.properties': 'app.v=base\nspring.profiles.default=fallback\n'}), args=['--spring.profiles.active=dev'], keys=K, beans=True))
print('== 二:@Profile 的表达式(9 个 Bean,标签就是它们的 @Profile 表达式)')
for pset in ('', 'dev', 'prod', 'dev,cloud', 'test', 'x', 'cloud', 'Dev'):
    l = run(props={'spring.profiles.active': pset} if pset else None, beans=True)
    print(f'  激活 [{pset or "无"}]:'); [print('    ' + x) for x in l]
print('  -- 写错的表达式')
def mal(expr):
    src = HDR + 'import org.springframework.context.annotation.Profile;\n@SpringBootApplication public class Main { record Mark(String id) {}\n  @Configuration static class Beans { @Bean @Profile("' + expr + '") Mark m() { return new Mark("m"); } }\n  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE); var c = app.run(a); System.out.println("RES 启动成功,Bean 存在=" + c.containsBean("m")); System.exit(0); }\n}\n'
    bm = sbuild('x72m', {'src/demo/Main.java': src, 'logback.xml': LB}, CP)
    if bm['crc'] != 0: return ['编译失败:' + bm['cout'][:300]]
    return run(props={'spring.profiles.active': 'dev'}, bb=bm) + ['(不激活任何 profile)'] + run(bb=bm)
for expr in ('dev & cloud | test', '(dev | test', 'dev &', ''):
    pr_(f'  @Profile("{expr}"),激活 dev:', mal(expr))
print('== 三:profile 组与 include')
GF = {'application-prod.properties': 'app.v=prod\n', 'application-proddb.properties': 'app.v=db\ndb.url=jdbc:prod\n', 'application-prodmq.properties': 'app.v=mq\nmq.host=prodmq\n'}
pr_('  spring.profiles.group.prod=proddb,prodmq,激活 prod:', run(dict(GF, **{'application.properties': 'spring.profiles.group.prod=proddb,prodmq\n'}), args=['--spring.profiles.active=prod'], keys='app.v,db.url,mq.host'))
pr_('  顺序反过来 spring.profiles.group.prod=prodmq,proddb:', run(dict(GF, **{'application.properties': 'spring.profiles.group.prod=prodmq,proddb\n'}), args=['--spring.profiles.active=prod'], keys='app.v'))
pr_('  不激活 prod(组不会生效):', run(dict(GF, **{'application.properties': 'spring.profiles.group.prod=proddb,prodmq\n'}), keys='app.v,db.url'))
pr_('  spring.profiles.group.prod 写在 application-prod.properties 里(profile 专属文件):', run(dict(GF, **{'application-prod.properties': 'app.v=prod\nspring.profiles.group.prod=proddb\n'}), args=['--spring.profiles.active=prod'], keys='app.v'))
pr_('  spring.profiles.include=proddb 写在 application-prod.properties 里:', run(dict(GF, **{'application-prod.properties': 'app.v=prod\nspring.profiles.include=proddb\n'}), args=['--spring.profiles.active=prod'], keys='app.v'))
pr_('  组里套组:group.a=b、group.b=c,激活 a:', run({'application.properties': 'spring.profiles.group.a=b\nspring.profiles.group.b=c\n', 'application-c.properties': 'app.v=c\n'}, args=['--spring.profiles.active=a'], keys='app.v'))
print('== 四:多个 profile 的文件顺序与 profile 名称')
AB = {'application-a.properties': 'app.v=a\nonly.a=1\n', 'application-b.properties': 'app.v=b\nonly.b=1\n'}
pr_('  --spring.profiles.active=a,b(两个文件都写了 app.v):', run(AB, args=['--spring.profiles.active=a,b'], keys='app.v,only.a,only.b'))
pr_('  --spring.profiles.active=b,a:', run(AB, args=['--spring.profiles.active=b,a'], keys='app.v'))
for name in ('dev_1', 'dev-1', 'dev.1', 'dev+x', 'dev@x', 'dev$x', 'dev x', ''):
    pr_(f'  --spring.profiles.active="{name}":', run({'application-dev.properties': 'app.v=dev\n'}, args=[f'--spring.profiles.active={name}'], keys='app.v'))
print('== 五:spring.profiles.active 写在不该写的地方')
pr_('  写在 @PropertySource 加载的文件里(extra72.properties 里 spring.profiles.active=dev):', run({'application-dev.properties': 'app.v=dev\n'}, cp={'extra72.properties': 'spring.profiles.active=dev\n'}, keys='app.v,spring.profiles.active', beans=True))
pr_('  对照:同样内容写在 application.properties 里:', run({'application-dev.properties': 'app.v=dev\n', 'application.properties': 'spring.profiles.active=dev\n'}, keys='app.v,spring.profiles.active', beans=True))
