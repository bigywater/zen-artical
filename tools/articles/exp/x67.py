import sys, os, re, time, json, zipfile; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x67')
CP = scp('org.springframework.boot:spring-boot-starter', 'org.springframework.boot:spring-boot-configuration-processor')
LOG = '<configuration><root level="OFF"/></configuration>'
# ---- 可选依赖 optlib ----
bo = sbuild('x67_opt', {'src/optlib/FancyFormatter.java': 'package optlib;\npublic class FancyFormatter { public String decorate(String s) { return "✨" + s + "✨"; } }\n'}, CP)
OPTJAR = JT / 'x67_opt.jar'
def jar(path, root, include=lambda n: True, extra=None):
    if path.exists(): path.unlink()
    with zipfile.ZipFile(path, 'w') as z:
        for dp, dn, fn in os.walk(root):
            for f in fn:
                full = os.path.join(dp, f); rel = os.path.relpath(full, root)
                if include(rel): z.write(full, rel)
        for k, v in (extra or {}).items(): z.writestr(k, v)
jar(OPTJAR, bo['out'])
# ---- 库 com.acme.greeting ----
L = {}
L['src/com/acme/greeting/GreetingProperties.java'] = '''package com.acme.greeting;
import org.springframework.boot.context.properties.ConfigurationProperties;
/** 问候语的配置。 */
@ConfigurationProperties("greeting")
public class GreetingProperties {
  /** 是否启用问候服务。 */ private boolean enabled = true;
  /** 问候前缀。 */ private String prefix = "Hello";
  /** 问候后缀。 */ private String suffix = "!";
  public boolean isEnabled() { return enabled; } public void setEnabled(boolean e) { enabled = e; }
  public String getPrefix() { return prefix; } public void setPrefix(String p) { prefix = p; }
  public String getSuffix() { return suffix; } public void setSuffix(String s) { suffix = s; }
}
'''
L['src/com/acme/greeting/GreetingDecorator.java'] = 'package com.acme.greeting;\npublic interface GreetingDecorator { String decorate(String s); }\n'
L['src/com/acme/greeting/GreetingService.java'] = '''package com.acme.greeting;
import java.util.List;
public class GreetingService { final GreetingProperties p; final List<GreetingDecorator> ds; public GreetingService(GreetingProperties p, List<GreetingDecorator> ds) { this.p = p; this.ds = ds; }
  public String greet(String name) { String s = p.getPrefix() + ", " + name + p.getSuffix(); for (var d : ds) s = d.decorate(s); return s; } }
'''
L['src/com/acme/greeting/GreetingAutoConfiguration.java'] = '''package com.acme.greeting;
import java.util.List; import org.springframework.beans.factory.ObjectProvider; import org.springframework.boot.autoconfigure.AutoConfiguration; import org.springframework.boot.autoconfigure.condition.*; import org.springframework.boot.context.properties.EnableConfigurationProperties; import org.springframework.context.annotation.Bean;
@AutoConfiguration @ConditionalOnProperty(prefix = "greeting", name = "enabled", matchIfMissing = true) @EnableConfigurationProperties(GreetingProperties.class)
public class GreetingAutoConfiguration {
  @Bean @ConditionalOnMissingBean public GreetingService greetingService(GreetingProperties p, ObjectProvider<GreetingDecorator> ds) { return new GreetingService(p, ds.orderedStream().toList()); }
}
'''
L['src/com/acme/greeting/FancyAutoConfiguration.java'] = '''package com.acme.greeting;
import optlib.FancyFormatter; import org.springframework.boot.autoconfigure.AutoConfiguration; import org.springframework.boot.autoconfigure.condition.*; import org.springframework.context.annotation.Bean;
@AutoConfiguration(before = GreetingAutoConfiguration.class) @ConditionalOnClass(FancyFormatter.class)
public class FancyAutoConfiguration { @Bean public GreetingDecorator fancyDecorator() { FancyFormatter f = new FancyFormatter(); return f::decorate; } }
'''
L['src/com/acme/greeting/BadAutoConfiguration.java'] = '''package com.acme.greeting;
import optlib.FancyFormatter; import org.springframework.boot.autoconfigure.AutoConfiguration; import org.springframework.boot.autoconfigure.condition.*; import org.springframework.context.annotation.Bean;
@AutoConfiguration
public class BadAutoConfiguration { @Bean @ConditionalOnClass(FancyFormatter.class) public FancyFormatter badFormatter() { return new FancyFormatter(); } }
'''
bl = sbuild('x67_lib', L, CP + ':' + str(bo['out']))
if bl['crc'] != 0: print(bl['cout']); sys.exit()
IMPORTS_GOOD = 'com.acme.greeting.GreetingAutoConfiguration\ncom.acme.greeting.FancyAutoConfiguration\n'
IMPORTS_BAD = IMPORTS_GOOD + 'com.acme.greeting.BadAutoConfiguration\n'
def mk(name, imports, with_bad):
    p = JT / f'x67_{name}.jar'; jar(p, bl['out'], include=lambda n: n.endswith('.class') and (with_bad or 'BadAutoConfiguration' not in n) or n.startswith('META-INF/spring-configuration-metadata'), extra=({'META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports': imports} if imports else None)); return str(p)
JG, JN, JB = mk('good', IMPORTS_GOOD, False), mk('noimports', None, False), mk('bad', IMPORTS_BAD, True)
meta = bl['out'] / 'META-INF' / 'spring-configuration-metadata.json'
# ---- 使用方应用 ----
MAIN = r'''
package demo;
import java.util.*; import com.acme.greeting.*;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.ConfigurableApplicationContext; import org.springframework.context.annotation.Bean;
@SpringBootApplication
public class Main {
  @Bean @org.springframework.boot.autoconfigure.condition.ConditionalOnProperty("user.service") GreetingService myService(GreetingProperties p) { return new GreetingService(p, List.of()) { public String greet(String n) { return "用户自己的 GreetingService 说:" + n; } }; }
  static void r(String s) { System.out.println("RES " + s); }
  public static void main(String[] a) {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    try { ConfigurableApplicationContext c = app.run(a);
      Map<String, GreetingService> m = c.getBeansOfType(GreetingService.class); r("  GreetingService Bean = " + m.keySet() + (m.isEmpty() ? "" : ",greet(\"Tom\") = " + m.values().iterator().next().greet("Tom")) + ",GreetingDecorator Bean = " + c.getBeansOfType(GreetingDecorator.class).keySet());
      System.exit(0);
    } catch (Throwable e) { Throwable root = e; while (root.getCause() != null && root.getCause() != root) root = root.getCause(); r("  启动失败:" + e.getClass().getSimpleName() + " ← … ← " + root.getClass().getSimpleName() + ": " + String.valueOf(root.getMessage()).replaceAll("\\s+", " ")); System.exit(1); }
  }
}
'''
bm = sbuild('x67_app', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP + ':' + JG)
if bm['crc'] != 0: print(bm['cout']); sys.exit()
def run(title, jars, props=None, head=True):
    b2 = dict(bm, cp=CP + ':' + ':'.join(jars)); r = srun(b2, 'demo.Main', props=props or {}, timeout=60); l = res(r)
    print(f'  {title}:'); [print('  ' + x) for x in (l or [r['out'][-500:]])]
print('Spring Boot 4.0.8 / JDK 21;自己写的库 com.acme.greeting(GreetingProperties、GreetingService、GreetingAutoConfiguration、可选集成 FancyAutoConfiguration),打成 jar 后放进使用方应用的 classpath')
print('== 一:库编译时,spring-boot-configuration-processor 生成的元数据')
md = json.load(open(meta)); print('  META-INF/spring-configuration-metadata.json 里的属性:')
for p in md['properties']: print(f'    {p["name"]}  类型 {p["type"]}  默认值 {p.get("defaultValue")}  说明「{p.get("description", "")}」')
print('== 二:使用方只要把 jar 放进 classpath')
run('库 jar(带 imports 文件)', [JG]); run('greeting.prefix=Hi、greeting.suffix=?', [JG], {'greeting.prefix': 'Hi', 'greeting.suffix': '?'}); run('greeting.enabled=false', [JG], {'greeting.enabled': 'false'}); run('使用方自己定义了 GreetingService(user.service=true)', [JG], {'user.service': 'true'})
print('== 三:库里忘了写 AutoConfiguration.imports')
run('库 jar(没有 imports 文件)', [JN])
print('== 四:可选依赖 optlib:有没有这个 jar')
run('类路径上没有 optlib', [JG]); run('类路径上有 optlib', [JG, str(OPTJAR)])
print('== 五:陷阱:@ConditionalOnClass 写在方法上,而方法的返回类型就是那个可选类')
run('库 jar(BadAutoConfiguration 已列入 imports),类路径上没有 optlib', [JB]); run('同一个库 jar,类路径上有 optlib', [JB, str(OPTJAR)])
