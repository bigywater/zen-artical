import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x11'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><root level="OFF"/></configuration>'
PROPS = 'app.name=from app.properties\nonly.file=only in file\nport=8080\nflag=yes\ngreeting=hello ${who:world}\nwho=spring\nregion=cn\nurl.cn=https://cn.example\nurl.us=https://us.example\nurl=${url.${region}}\n'
ZH = 'title=中文标题\n'
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.beans.factory.annotation.Value; import org.springframework.context.annotation.*; import org.springframework.context.support.PropertySourcesPlaceholderConfigurer;
import org.springframework.core.env.ConfigurableEnvironment; import org.springframework.core.env.Environment; import org.springframework.core.env.MapPropertySource;
public class Main {
  @Configuration @PropertySource("classpath:app.properties") static class WithFile { }
  public static class Holder { @Value("${missing.key}") String lit; @Value("${missing.key:默认值}") String withDefault; @Value("${app.name}") String name; @Value("#{systemProperties['user.language']}") String spel; }
  @Configuration @PropertySource("classpath:app.properties") static class NoPspc { @Bean Holder h() { return new Holder(); } }
  @Configuration @PropertySource("classpath:app.properties") static class WithPspc { @Bean static PropertySourcesPlaceholderConfigurer p() { return new PropertySourcesPlaceholderConfigurer(); } @Bean Holder h() { return new Holder(); } }
  @Configuration @PropertySource("classpath:zh.properties") static class ZhDefault { }
  @Configuration @PropertySource(value = "classpath:zh.properties", encoding = "UTF-8") static class ZhUtf8 { }
  @Configuration @PropertySource(value = "classpath:nope.properties", ignoreResourceNotFound = true) static class Ignore { }
  @Configuration @PropertySource("classpath:nope.properties") static class NotIgnore { }
  public static void main(String[] args) throws Exception {
    String m = args[0]; AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext();
    ConfigurableEnvironment env = c.getEnvironment();
    switch (m) {
      case "order" -> {
        System.setProperty("app.name", "from -D system property");
        c.register(WithFile.class); c.refresh();
        System.out.println("RES PropertySource 的顺序(先找前面的):" + env.getPropertySources().stream().map(org.springframework.core.env.PropertySource::getName).toList());
        System.out.println("RES app.name = " + env.getProperty("app.name") + "(系统属性、环境变量、app.properties 里都可能有)");
        System.out.println("RES only.file = " + env.getProperty("only.file") + ";MY_NAME(环境变量)用 my.name 取 = " + env.getProperty("my.name") + ";用 MY_NAME 取 = " + env.getProperty("MY_NAME"));
        env.getPropertySources().addFirst(new MapPropertySource("runtime", Map.of("app.name", "运行时 addFirst 加的")));
        System.out.println("RES addFirst 一个 MapPropertySource 之后 app.name = " + env.getProperty("app.name"));
        env.getPropertySources().remove("runtime"); env.getPropertySources().addLast(new MapPropertySource("late", Map.of("app.name", "addLast 加的", "late.only", "晚到的")));
        System.out.println("RES 再用 addLast 加一个同名键:app.name = " + env.getProperty("app.name") + "(addLast 排在最后,赢不了);late.only = " + env.getProperty("late.only"));
      }
      case "placeholder" -> {
        c.register(WithFile.class); c.refresh();
        System.out.println("RES resolvePlaceholders(\"${nope}\") = " + env.resolvePlaceholders("${nope}") + "(宽松,保持原样)");
        try { env.resolveRequiredPlaceholders("${nope}"); } catch (Exception e) { System.out.println("RES resolveRequiredPlaceholders(\"${nope}\") → " + e.getClass().getSimpleName() + ": " + e.getMessage()); }
        System.out.println("RES ${nope:默认} → " + env.resolvePlaceholders("${nope:默认}") + ";${who} → " + env.resolvePlaceholders("${who}") + ";嵌套默认值 greeting → " + env.getProperty("greeting"));
        System.out.println("RES 嵌套占位符:url=${url.${region}},region=cn → ${url} = " + env.resolvePlaceholders("${url}"));
      }
      case "value" -> {
        c.register(m.equals("value") && args[1].equals("pspc") ? WithPspc.class : NoPspc.class);
        try { c.refresh(); Holder h = c.getBean(Holder.class); System.out.println("RES " + args[1] + ":@Value(\"${missing.key}\") = [" + h.lit + "];带默认值的 = [" + h.withDefault + "];@Value(\"${app.name}\") = [" + h.name + "];SpEL #{systemProperties['user.language']} = [" + h.spel + "]"); }
        catch (Exception e) { Throwable t = e; while (t.getCause() != null) t = t.getCause(); System.out.println("RES " + args[1] + ":启动失败 " + t.getClass().getSimpleName() + ": " + t.getMessage()); }
      }
      case "convert" -> {
        c.register(WithFile.class); c.refresh(); Map<String, Object> m2 = new LinkedHashMap<>();
        for (String v : new String[]{"true", "yes", "on", "1", "false", "no", "off", "0", "TRUE", "abc"}) { env.getPropertySources().addFirst(new MapPropertySource("t", Map.of("b", v))); try { m2.put(v, env.getProperty("b", Boolean.class)); } catch (Exception e) { m2.put(v, e.getClass().getSimpleName()); } env.getPropertySources().remove("t"); }
        System.out.println("RES 字符串 → Boolean:" + m2);
        System.out.println("RES port 作为 Integer = " + env.getProperty("port", Integer.class) + ";不存在的键 getProperty(\"x\", Integer.class) = " + env.getProperty("x", Integer.class) + ";带默认值 = " + env.getProperty("x", Integer.class, 9090) + ";getRequiredProperty 不存在的键 → " + tryReq(env));
      }
      case "enc" -> { c.register(args[1].equals("utf8") ? ZhUtf8.class : ZhDefault.class); c.refresh(); String t = env.getProperty("title"); System.out.println("RES " + args[1] + ":title = [" + t + "] 字符数 " + t.length() + "(期望“中文标题”4 个字符)"); }
      case "ignore" -> { c.register(args[1].equals("ignore") ? Ignore.class : NotIgnore.class); try { c.refresh(); System.out.println("RES " + args[1] + ":启动成功"); } catch (Exception e) { Throwable t = e; while (t.getCause() != null) t = t.getCause(); System.out.println("RES " + args[1] + ":" + t.getClass().getSimpleName() + ": " + t.getMessage()); } }
    }
  }
  static String tryReq(Environment e) { try { e.getRequiredProperty("x"); return "?"; } catch (Exception ex) { return ex.getClass().getSimpleName() + ": " + ex.getMessage(); } }
}
'''
b = sbuild('x11', {'src/demo/Main.java': MAIN, 'app.properties': PROPS, 'zh.properties': ZH, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(*a, env=None): r = srun(b, 'demo.Main', args=list(a), env=env); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-500:]]
print('Spring Framework 7.0.9。Environment 与 PropertySource。app.properties 里有:app.name、only.file、port=8080、flag=yes、greeting=hello ${who:world}、who=spring')
print('== 一:属性源的优先级。同一个键 app.name 同时在 -D 系统属性(代码里用 System.setProperty 设置)和 app.properties(@PropertySource)里;环境变量 MY_NAME=来自环境变量。看查找顺序、谁赢、addFirst / addLast 的效果,以及环境变量名的映射')
[print('  ' + l) for l in run('order', env={'MY_NAME': '来自环境变量'})]
print('== 二:占位符。resolvePlaceholders 与 resolveRequiredPlaceholders 的差别,默认值,嵌套')
[print('  ' + l) for l in run('placeholder')]
print('== 三:@Value 里的占位符。(a)没有 PropertySourcesPlaceholderConfigurer;(b)有 PropertySourcesPlaceholderConfigurer。@Value("${missing.key}") 这个键不存在')
for k_ in ('nopspc', 'pspc'): [print('  ' + l) for l in run('value', k_)]
print('== 四:类型转换。getProperty(key, Boolean.class) 对各种字符串的结果;Integer、默认值、Required')
[print('  ' + l) for l in run('convert')]
print('== 五:@PropertySource 读 .properties 文件的编码。zh.properties 里是 title=中文标题(文件本身是 UTF-8)。默认读法与 encoding = "UTF-8"')
for k_ in ('default', 'utf8'): [print('  ' + l) for l in run('enc', k_)]
print('== 六:@PropertySource 指向不存在的文件')
for k_ in ('ignore', 'noignore'): [print('  ' + l) for l in run('ignore', k_)]
