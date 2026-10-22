import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x65'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
LOG = '<configuration><root level="OFF"/></configuration>'
F = {}
F['src/demo/lib/Greeter.java'] = 'package demo.lib;\npublic interface Greeter { String greet(); }\n'
F['src/demo/lib/GreetingAutoConfiguration.java'] = '''package demo.lib;
import org.springframework.boot.autoconfigure.AutoConfiguration; import org.springframework.boot.autoconfigure.condition.*; import org.springframework.context.annotation.Bean;
@AutoConfiguration @ConditionalOnClass(Greeter.class) @ConditionalOnProperty(prefix = "greeting", name = "enabled", havingValue = "true", matchIfMissing = true)
public class GreetingAutoConfiguration {
  @Bean @ConditionalOnMissingBean public Greeter defaultGreeter() { return () -> "default greeter(来自自动配置)"; }
}
'''
F['src/demo/lib/DecoratorAutoConfiguration.java'] = '''package demo.lib;
import org.springframework.boot.autoconfigure.AutoConfiguration; import org.springframework.boot.autoconfigure.condition.*; import org.springframework.context.annotation.Bean;
@AutoConfiguration(after = GreetingAutoConfiguration.class) @ConditionalOnBean(Greeter.class)
public class DecoratorAutoConfiguration { @Bean public String afterMarker() { return "after-greeting"; } }
'''
F['src/demo/lib/TooEarlyAutoConfiguration.java'] = '''package demo.lib;
import org.springframework.boot.autoconfigure.AutoConfiguration; import org.springframework.boot.autoconfigure.condition.*; import org.springframework.context.annotation.Bean;
@AutoConfiguration(before = GreetingAutoConfiguration.class) @ConditionalOnBean(Greeter.class)
public class TooEarlyAutoConfiguration { @Bean public String tooEarlyMarker() { return "too-early"; } }
'''
F['src/demo/lib/GhostAutoConfiguration.java'] = '''package demo.lib;
import org.springframework.boot.autoconfigure.AutoConfiguration; import org.springframework.boot.autoconfigure.condition.*; import org.springframework.context.annotation.Bean;
@AutoConfiguration @ConditionalOnClass(name = "com.nowhere.Missing")
public class GhostAutoConfiguration { @Bean public String ghostMarker() { return "ghost"; } }
'''
F['src/demo/lib/UnlistedAutoConfiguration.java'] = '''package demo.lib;
import org.springframework.boot.autoconfigure.AutoConfiguration; import org.springframework.context.annotation.Bean;
@AutoConfiguration
public class UnlistedAutoConfiguration { @Bean public String unlistedMarker() { return "unlisted"; } }
'''
F['META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports'] = '# 自己的自动配置(注意:UnlistedAutoConfiguration 故意没有列在这里)\ndemo.lib.GreetingAutoConfiguration\ndemo.lib.DecoratorAutoConfiguration\ndemo.lib.TooEarlyAutoConfiguration\ndemo.lib.GhostAutoConfiguration\n'
F['src/demo/UserConfig.java'] = '''package demo;
import demo.lib.Greeter; import org.springframework.boot.autoconfigure.condition.*; import org.springframework.context.annotation.*;
@Configuration
public class UserConfig {
  @Bean @ConditionalOnBean(Greeter.class) public String userDependsOnGreeter() { return "user-config-saw-greeter"; }
  @Bean @ConditionalOnProperty("user.greeter") public Greeter userGreeter() { return () -> "user greeter(用户自己定义)"; }
}
'''
F['src/demo/UserConfig2.java'] = '''package demo;
import demo.lib.Greeter; import org.springframework.boot.autoconfigure.condition.*; import org.springframework.context.annotation.*;
@Configuration @ConditionalOnProperty("user.greeter")
public class UserConfig2 {
  @Bean @ConditionalOnBean(Greeter.class) public String user2DependsOnGreeter() { return "user-config-2-saw-greeter(用户的 Greeter 已经定义)"; }
}
'''
F['src/demo/Main.java'] = r'''
package demo;
import java.util.*; import demo.lib.Greeter;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.autoconfigure.condition.*; import org.springframework.context.ConfigurableApplicationContext;
@SpringBootApplication
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  public static void main(String[] a) {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    ConfigurableApplicationContext ctx = app.run(a); String sc = System.getProperty("scenario", "basic");
    for (String m : List.of("afterMarker", "tooEarlyMarker", "ghostMarker", "unlistedMarker", "userDependsOnGreeter", "user2DependsOnGreeter")) r(String.format("  %-24s %s", m, ctx.containsBean(m) ? "存在" : "不存在"));
    var gs = ctx.getBeansOfType(Greeter.class); r("  Greeter 类型的 Bean = " + gs.keySet() + ",greet() = " + gs.values().stream().map(Greeter::greet).toList());
    var rep = ConditionEvaluationReport.get(ctx.getBeanFactory()); var by = rep.getConditionAndOutcomesBySource();
    r("  --- 自己写的几个配置类在条件报告里的结果 ---");
    for (String k : new TreeSet<>(by.keySet())) if (k.startsWith("demo.")) { var co = by.get(k); r(String.format("  %s → %s", k.replace("demo.lib.", "lib.").replace("demo.", ""), co.isFullMatch() ? "匹配" : "不匹配")); for (var c : co) r("        " + (c.getOutcome().isMatch() ? "✓ " : "✗ ") + c.getCondition().getClass().getSimpleName() + ": " + c.getOutcome().getMessage()); }
    long cand = by.keySet().stream().filter(k -> k.startsWith("org.springframework.boot.") && k.endsWith("AutoConfiguration")).count(); long full = by.entrySet().stream().filter(e -> e.getKey().startsWith("org.springframework.boot.") && e.getKey().endsWith("AutoConfiguration") && e.getValue().isFullMatch()).count();
    r("  Boot 自带的 *AutoConfiguration 在条件报告里出现 " + cand + " 个,其中条件全部满足(生效)的 " + full + " 个;spring.autoconfigure.exclude 排除掉的 = " + rep.getExclusions());
    r("  Bean 总数 = " + ctx.getBeanDefinitionCount());
    System.exit(0);
  }
}
'''
F['logback.xml'] = LOG
b = sbuild('x65', F, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def go(title, props=None):
    r = srun(b, 'demo.Main', props=props or {}, timeout=90); print(f'== {title}' if title.startswith('一') or title[0] in '二三四五六' else f'  -- {title}'); l = res(r)
    if not l: print(r['out'][-1500:])
    for x in l: print(x)
print('Spring Boot 4.0.8 / JDK 21;spring-boot-starter-webmvc 的类路径,非 Web 模式启动;自己写了 5 个自动配置类,其中 4 个列在 META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports 里')
go('一:默认:哪些配置类生效、哪些不生效,以及为什么')
go('二:greeting.enabled=false(@ConditionalOnProperty 关掉)', {'greeting.enabled': 'false'})
go('三:用户自己定义了 Greeter(user.greeter=true):@ConditionalOnMissingBean 让路', {'user.greeter': 'true'})
go('四:spring.autoconfigure.exclude=demo.lib.GreetingAutoConfiguration', {'spring.autoconfigure.exclude': 'demo.lib.GreetingAutoConfiguration'})
