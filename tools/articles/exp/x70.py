import sys, os, re, time, json, shutil, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x70'); CP = scp('org.springframework.boot:spring-boot-starter')
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.ConfigurableApplicationContext; import org.springframework.core.env.*;
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  static String clean(String n) { return n.replace("Config resource ", "").replaceAll("' via location.*", "'").replace("class path resource [", "classpath:[").replace("file [", "file:["); }
  public static void main(String[] a) {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    ConfigurableApplicationContext c = app.run(a); ConfigurableEnvironment env = c.getEnvironment();
    for (String k : System.getProperty("x70.keys").split(",")) {
      if (k.equals("@profiles")) { r("active profiles = " + java.util.Arrays.toString(env.getActiveProfiles())); continue; }
      if (k.equals("@dev")) { java.util.List<String> l = new java.util.ArrayList<>(); for (PropertySource<?> ps : env.getPropertySources()) if (ps.getName().startsWith("Config resource")) l.add(clean(ps.getName()).replace("'", "").replace("[", "").replace("]", "").replace("classpath:", "classpath:")); int i = 0; while (!l.get(i).contains("-dev.")) i++; r("dev 文件排第 " + (i + 1) + " 位(共 " + l.size() + " 个),比它优先的:" + (i == 0 ? "(没有)" : String.join("、", l.subList(0, i))) + ";比它低的:" + (i == l.size() - 1 ? "(没有)" : String.join("、", l.subList(i + 1, l.size())))); continue; }
      if (k.equals("@sources")) { int i = 0; for (PropertySource<?> ps : env.getPropertySources()) if (ps.getName().startsWith("Config resource") || ps.getName().startsWith("Config tree")) r(String.format("%2d. %s", ++i, clean(ps.getName()))); continue; }
      String src = "-"; for (PropertySource<?> ps : env.getPropertySources()) if (!ps.getName().equals("configurationProperties") && ps.containsProperty(k)) { src = ps.getName(); break; }
      String v = env.getProperty(k); r(String.format("%-14s = %-18s ←| %s", k, v == null ? "null" : "[" + v.replace("\n", "\\n") + "]" + (System.getProperty("x70.len") != null ? " 长度 " + v.length() : ""), clean(src)));
    }
    System.exit(0);
  }
}
'''
LB = '<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>%msg%n</pattern></encoder></appender><logger name="org.springframework.boot.diagnostics.LoggingFailureAnalysisReporter" level="ERROR"/><root level="OFF"><appender-ref ref="C"/></root></configuration>'
b = sbuild('x70', {'src/demo/Main.java': MAIN, 'logback.xml': LB}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
WD = JT / 'x70_wd'
def run(cwd=None, cp=None, args=(), props=None, keys='app.name', env=None, show_fail=True):
    """cwd / cp:{相对路径: 内容};返回结果行,失败时返回 Description 与 Action 的内容。"""
    shutil.rmtree(WD, ignore_errors=True); WD.mkdir(parents=True); rc = WD / 'rc'; rc.mkdir()
    for k, v in (cwd or {}).items(): (WD / k).parent.mkdir(parents=True, exist_ok=True); (WD / k).write_text(v)
    for k, v in (cp or {}).items(): (rc / k).parent.mkdir(parents=True, exist_ok=True); (rc / k).write_text(v)
    b2 = dict(b, cp=str(rc) + ':' + b['cp']); p = dict(props or {}); p['x70.keys'] = keys
    r = srun(b2, 'demo.Main', args=list(args), props=p, env=env, cwd=str(WD), timeout=60); l = res(r)
    if l: return l
    o = r['out']; i = o.find('Description:')
    if i >= 0: return ['启动失败:' + ' '.join(x.strip() for x in o[i:].splitlines() if x.strip())[:420]]
    ex = [x for x in o.splitlines() if re.match(r'^(Exception in thread "main" |Caused by: )?[\w.$]+(Exception|Error):', x)]
    return ['启动失败(没有 FailureAnalyzer 报告,堆栈里的异常):' + (ex[-1] if re.match('Caused by', ex[-1] if ex else '') else (ex[0] if ex else o[-300:])).replace('Exception in thread "main" ', '')[:420]]
def pr_(title, lines):
    print(title)
    for l in lines: print('    ' + l)
print('Spring Boot 4.0.8 / JDK 21;每个场景一个独立 JVM,工作目录是临时目录;「←|」后面是第一个包含该属性的 PropertySource')
CPF = {'application.properties': 'app.name=classpath\nonly.classpath=yes\n'}
CWDF = {'config/application.properties': 'app.name=cwd-config\nonly.cwd=yes\n', 'custom/application.properties': 'app.name=custom\n', 'custom/other.properties': 'app.name=other\n'}
K = 'app.name,only.classpath,only.cwd'
print('== 一:spring.config.location / additional-location / name')
pr_('  不设置(默认位置):', run(CWDF, CPF, keys=K))
pr_('  -Dspring.config.location=file:./custom/(替换默认位置):', run(CWDF, CPF, props={'spring.config.location': 'file:./custom/'}, keys=K))
pr_('  -Dspring.config.additional-location=file:./custom/(追加在默认位置之上):', run(CWDF, CPF, props={'spring.config.additional-location': 'file:./custom/'}, keys=K))
pr_('  -Dspring.config.name=other(换文件名,默认位置不变):', run(dict(CWDF, **{'config/other.properties': 'app.name=cwd-config-other\n'}), dict(CPF, **{'other.properties': 'app.name=classpath-other\n'}), props={'spring.config.name': 'other'}, keys=K))
pr_('  -Dspring.config.location=file:./custom/other.properties(直接指定文件):', run(CWDF, CPF, props={'spring.config.location': 'file:./custom/other.properties'}, keys=K))
pr_('  -Dspring.config.location=file:./custom(目录末尾没有斜杠):', run(CWDF, CPF, props={'spring.config.location': 'file:./custom'}, keys=K))
pr_('  -Dspring.config.location=file:./nope/(目录不存在,没写 optional:):', run(CWDF, CPF, props={'spring.config.location': 'file:./nope/'}, keys=K))
pr_('  -Dspring.config.location=optional:file:./nope/:', run(CWDF, CPF, props={'spring.config.location': 'optional:file:./nope/'}, keys=K))
pr_('  -Dspring.config.location=classpath:/,file:./custom/(多个位置用逗号,后面的优先):', run(CWDF, CPF, props={'spring.config.location': 'classpath:/,file:./custom/'}, keys=K))
pr_('  -Dspring.config.location=file:./custom/,classpath:/(顺序反过来):', run(CWDF, CPF, props={'spring.config.location': 'file:./custom/,classpath:/'}, keys=K))
print('== 二:spring.config.import')
IMP = {'imp.properties': 'app.name=imported\nonly.imp=1\n', 'imp2.properties': 'app.name=imported2\n'}
K2 = 'app.name,only.imp,x'
pr_('  application.properties 自己写 app.name=main 并 import 一个也写了 app.name 的文件:', run(dict(IMP, **{'application.properties': 'app.name=main\nx=from-main\nspring.config.import=file:./imp.properties\n'}), None, keys=K2))
pr_('  同一行 import 两个文件(imp.properties,imp2.properties):', run(dict(IMP, **{'application.properties': 'app.name=main\nspring.config.import=file:./imp.properties,file:./imp2.properties\n'}), None, keys=K2))
pr_('  顺序反过来(imp2.properties,imp.properties):', run(dict(IMP, **{'application.properties': 'app.name=main\nspring.config.import=file:./imp2.properties,file:./imp.properties\n'}), None, keys=K2))
pr_('  被导入的文件再 import 别的文件(链式):', run({'application.properties': 'app.name=main\nspring.config.import=file:./a.properties\n', 'a.properties': 'app.name=a\nspring.config.import=file:./b.properties\n', 'b.properties': 'app.name=b\nx=from-b\n'}, None, keys=K2))
pr_('  import 的文件不存在,没写 optional:', run({'application.properties': 'spring.config.import=file:./missing.properties\n'}, None, keys=K2))
pr_('  import 的文件不存在,写了 optional:', run({'application.properties': 'app.name=main\nspring.config.import=optional:file:./missing.properties\n'}, None, keys=K2))
pr_('  import 的位置写在命令行 --spring.config.import:', run(dict(IMP, **{'application.properties': 'app.name=main\n'}), None, args=['--spring.config.import=file:./imp.properties'], keys=K2))
pr_('  命令行又写 --app.name=cmdline,文件里 import 的 app.name 还赢吗:', run(dict(IMP, **{'application.properties': 'spring.config.import=file:./imp.properties\n'}), None, args=['--app.name=cmdline'], keys=K2))
pr_('  import 的文件放在 jar 里(classpath:):', run({'application.properties': 'app.name=main\nspring.config.import=classpath:imp.properties\n'}, {'imp.properties': 'app.name=cp-imp\n'}, keys=K2))
print('== 三:没有扩展名的文件与 configtree:(Kubernetes 挂载 Secret / ConfigMap 的形式)')
pr_('  import 一个没有扩展名的文件,不指定格式:', run({'application.properties': 'spring.config.import=file:./secret\n', 'secret': 'db.password=s3cret\n'}, None, keys='db.password'))
pr_('  加上 [.properties] 指定格式:', run({'application.properties': 'spring.config.import=file:./secret[.properties]\n', 'secret': 'db.password=s3cret\n'}, None, keys='db.password'))
pr_('  加上 [.yaml] 指定格式:', run({'application.properties': 'spring.config.import=file:./secret[.yaml]\n', 'secret': 'db:\n  password: yaml-secret\n'}, None, keys='db.password'))
TREE = {'application.properties': 'spring.config.import=optional:configtree:./tree/\n', 'tree/db.password': 'pw-with-newline\n', 'tree/db.user': 'root', 'tree/app/name': 'from-tree'}
pr_('  configtree:./tree/(目录里每个文件名是 key,文件内容是 value):', run(TREE, None, keys='db.password,db.user,app.name'))
pr_('  文件内容末尾的换行、空格有没有被保留(只看长度;pw1="abc\\n"、pw2="abc\\n\\n"、pw3=" abc "、pw4="abc"):', run({'application.properties': 'spring.config.import=configtree:./tree/\n', 'tree/pw1': 'abc\n', 'tree/pw2': 'abc\n\n', 'tree/pw3': ' abc ', 'tree/pw4': 'abc'}, None, props={'x70.len': '1'}, keys='pw1,pw2,pw3,pw4'))
pr_('  configtree 的目录不存在,没写 optional:', run({'application.properties': 'spring.config.import=configtree:./nope/\n'}, None, keys='db.password'))
print('== 四:多文档文件与 profile 激活')
MD = 'app.name=base\nx=base\n#---\nspring.config.activate.on-profile=dev\napp.name=dev\n#---\nspring.config.activate.on-profile=prod\napp.name=prod\nx=prod\n#---\ny=last\n'
for pf in ('(不激活)', 'dev', 'prod'):
    pr_(f'  一个 application.properties 里用 #--- 分成 4 个文档,profile {pf}:', run({'application.properties': MD}, None, args=[] if pf[0] == '(' else ['--spring.profiles.active=' + pf], keys='app.name,x,y'))
MD2 = 'spring.config.activate.on-profile=dev\napp.name=dev-first\n#---\napp.name=plain-after\n'
pr_('  profile 专属的文档写在前面、普通文档写在后面,激活 dev:', run({'application.properties': MD2}, None, args=['--spring.profiles.active=dev'], keys='app.name'))
YML = 'app:\n  name: base\n---\nspring:\n  config:\n    activate:\n      on-profile: dev\napp:\n  name: yaml-dev\n'
pr_('  同样的写法用 application.yaml(--- 分文档),激活 dev:', run({'application.yaml': YML}, None, args=['--spring.profiles.active=dev'], keys='app.name'))
pr_('  application.properties 和 application.yaml 同时存在,都写 app.name:', run({'application.properties': 'app.name=props\n', 'application.yaml': 'app:\n  name: yaml\n'}, None, keys='app.name'))
BOTH = 'app.name=base\n#---\nspring.config.activate.on-profile=dev\nspring.profiles.active=prod\n'
pr_('  第二个文档 on-profile=dev 里写了 spring.profiles.active=prod,不激活 dev:', run({'application.properties': BOTH}, None, keys='app.name,@profiles'))
pr_('  同上,--spring.profiles.active=dev:', run({'application.properties': BOTH}, None, args=['--spring.profiles.active=dev'], keys='app.name,@profiles'))
pr_('  application-dev.properties 里写 spring.profiles.active=prod,--spring.profiles.active=dev:', run({'application-dev.properties': 'spring.profiles.active=prod\napp.name=x\n'}, None, args=['--spring.profiles.active=dev'], keys='app.name,@profiles'))
IMPD = {'application.properties': 'app.name=base\n#---\nspring.config.activate.on-profile=dev\nspring.config.import=file:./imp.properties\n', 'imp.properties': 'app.name=imported-by-dev\n'}
pr_('  on-profile=dev 的文档里写 spring.config.import,激活 dev:', run(IMPD, None, args=['--spring.profiles.active=dev'], keys='app.name'))
pr_('  同上,不激活 dev(import 不会发生):', run(IMPD, None, keys='app.name'))
print('== 五:profile 专属文件、import、子目录一起出现时的最终顺序')
ALL_CP = {'application.properties': 'app.name=classpath\n', 'config/application.properties': 'app.name=classpath-config\n'}
ALL_CWD = {'application.properties': 'app.name=cwd\nspring.config.import=file:./imp.properties\n', 'application-dev.properties': 'app.name=cwd-dev\n', 'imp.properties': 'app.name=imported\n',
           'config/application.properties': 'app.name=cwd-config\n', 'config/sub1/application.properties': 'app.name=sub1\n', 'config/sub2/application.properties': 'app.name=sub2\n'}
pr_('  不激活 profile,Environment 里的配置来源(第 1 个优先级最高):', run(ALL_CWD, ALL_CP, keys='app.name,@sources'))
pr_('  激活 dev(多了 application-dev.properties):', run(ALL_CWD, ALL_CP, args=['--spring.profiles.active=dev'], keys='app.name,@sources'))
pr_('  只在 application.properties 里 import,同时有 application-dev.properties,激活 dev:', run({'application.properties': 'spring.config.import=file:./imp.properties\n', 'application-dev.properties': 'app.name=cwd-dev\n', 'imp.properties': 'app.name=imported\n'}, None, args=['--spring.profiles.active=dev'], keys='app.name'))
print('  -- 同样的 profile 专属文件(dev),只放在下面这一个位置;其余位置只有不带 profile 的 application.properties(classpath:/、classpath:/config/、file:./、file:./config/、file:./config/sub1/ 各一个)')
PLAIN_CP = {'application.properties': 'app.name=cp\n', 'config/application.properties': 'app.name=cp-config\n'}
PLAIN_CWD = {'application.properties': 'app.name=cwd\n', 'config/application.properties': 'app.name=cwd-config\n', 'config/sub1/application.properties': 'app.name=sub1\n'}
for where in ['cp:application-dev.properties', 'cp:config/application-dev.properties', 'cwd:application-dev.properties', 'cwd:config/application-dev.properties', 'cwd:config/sub1/application-dev.properties']:
    cp_, cwd_ = dict(PLAIN_CP), dict(PLAIN_CWD); kind, path = where.split(':'); (cp_ if kind == 'cp' else cwd_)[path] = 'app.name=DEV\n'
    pr_('  dev 文件只放在 ' + ('classpath:/' if kind == 'cp' else 'file:./') + path.replace('application-dev.properties', '') + ':', run(cwd_, cp_, args=['--spring.profiles.active=dev'], keys='app.name,@dev'))
