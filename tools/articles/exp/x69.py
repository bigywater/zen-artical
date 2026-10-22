import sys, os, re, time, json, shutil, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x69'); CP = scp('org.springframework.boot:spring-boot-starter')
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.ConfigurableApplicationContext; import org.springframework.core.env.*;
@SpringBootApplication @org.springframework.context.annotation.PropertySource(value = "classpath:/extra.properties", ignoreResourceNotFound = true)
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  public static void main(String[] a) {
    SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE);
    if (System.getProperty("x69.default") != null) app.setDefaultProperties(java.util.Map.of("app.name", "default-properties"));
    ConfigurableApplicationContext c = app.run(a); ConfigurableEnvironment env = c.getEnvironment();
    String mode = System.getProperty("x69.mode", "ladder");
    if (mode.equals("ladder")) {
      String src = "(无)"; for (PropertySource<?> ps : env.getPropertySources()) if (!ps.getName().equals("configurationProperties") && ps.containsProperty("app.name")) { src = ps.getName(); break; }
      r(env.getProperty("app.name") + " ←|← " + src.replace("Config resource ", "").replace("'class path resource ", "classpath:").replace("'file [", "file:[").replaceAll("' via location.*", ""));
    } else {
      for (String n : System.getProperty("x69.names").split(",")) r(String.format("  getProperty(%-16s) = %s", "\"" + n + "\"", env.getProperty(n)));
    }
    System.exit(0);
  }
}
'''
b = sbuild('x69', {'src/demo/Main.java': MAIN, 'logback.xml': '<configuration><root level="OFF"/></configuration>'}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
WD = JT / 'x69_wd'
LEVELS = [  # 从高到低
    ('命令行参数 --app.name=cmdline', dict(args=['--app.name=cmdline'])),
    ('环境变量 SPRING_APPLICATION_JSON', dict(env={'SPRING_APPLICATION_JSON': '{"app":{"name":"spring-application-json"}}'})),
    ('JVM 系统属性 -Dapp.name=sysprop', dict(props={'app.name': 'sysprop'})),
    ('操作系统环境变量 APP_NAME', dict(env={'APP_NAME': 'os-env'})),
    ('jar 外:./config/application-dev.properties(profile=dev)', dict(cwd={'config/application-dev.properties': 'app.name=cwd-config-dev'}, profile=True)),
    ('jar 内:classpath:application-dev.properties(profile=dev)', dict(cp={'application-dev.properties': 'app.name=classpath-dev'}, profile=True)),
    ('jar 外:./config/application.properties', dict(cwd={'config/application.properties': 'app.name=cwd-config'})),
    ('jar 外:./application.properties', dict(cwd={'application.properties': 'app.name=cwd'})),
    ('jar 内:classpath:/config/application.properties', dict(cp={'config/application.properties': 'app.name=classpath-config'})),
    ('jar 内:classpath:/application.properties', dict(cp={'application.properties': 'app.name=classpath'})),
    ('@PropertySource("classpath:/extra.properties")', dict(cp={'extra.properties': 'app.name=property-source'})),
    ('SpringApplication.setDefaultProperties', dict(props={'x69.default': '1'})),
]
def run_levels(enabled, mode='ladder', names=None):
    shutil.rmtree(WD, ignore_errors=True); (WD / 'config').mkdir(parents=True); rc = WD / 'rc'; (rc / 'config').mkdir(parents=True); args, props, env, prof = [], {}, {}, False
    for _, d in enabled:
        for k, v in d.get('cwd', {}).items(): (WD / k).write_text(v + '\n')
        for k, v in d.get('cp', {}).items(): (rc / k).write_text(v + '\n')
        args += d.get('args', []); props.update(d.get('props', {})); env.update(d.get('env', {})); prof = prof or d.get('profile', False)
    if prof: args.append('--spring.profiles.active=dev')
    if mode != 'ladder': props.update({'x69.mode': mode, 'x69.names': names})
    b2 = dict(b, cp=str(rc) + ':' + b['cp'])
    r = srun(b2, 'demo.Main', args=args, props=props, env=env, cwd=str(WD), timeout=60); return res(r) or [r['out'][-500:]]
print('Spring Boot 4.0.8 / JDK 21;同一个属性 app.name 同时出现在多个来源,逐个去掉优先级最高的来源,看谁接着赢')
print('== 一:优先级阶梯:每一行 = 在上一行的基础上拿掉最高优先级的那个来源')
for i in range(len(LEVELS)):
    l = run_levels(LEVELS[i:]); print(f'  剩下 {len(LEVELS) - i:>2} 个来源,最高的是「{LEVELS[i][0]}」→ {l[0]}')
print('== 二:同一个 key 的不同写法能不能读到(宽松绑定)')
print('  配置:application.properties 里 my.app-name=from-properties;环境变量 MY_OTHER_NAME=from-env、OTHERNAME=env2')
def relaxed(files, env, names):
    shutil.rmtree(WD, ignore_errors=True); (WD).mkdir(parents=True); rc = WD / 'rc'; rc.mkdir()
    for k, v in files.items(): (rc / k).write_text(v)
    b2 = dict(b, cp=str(rc) + ':' + b['cp']); r = srun(b2, 'demo.Main', props={'x69.mode': 'names', 'x69.names': names}, env=env, cwd=str(WD), timeout=60); return res(r) or [r['out'][-500:]]
for l in relaxed({'application.properties': 'my.app-name=from-properties\nmy.camelCase=camel\nmy.snake_case=snake\n'}, {'MY_OTHER_NAME': 'from-env', 'MY_UPPER': 'x'}, 'my.app-name,my.appName,my.app_name,MY.APP-NAME,my.camelcase,my.camel-case,my.snake-case,my.snake_case,my.other-name,my.otherName,my.other_name,MY_OTHER_NAME,my.upper'): print(l)
print('== 三:占位符、默认值与 random')
for l in relaxed({'application.properties': 'base=B\nfull=${base}-suffix\nref=${missing:fallback}\nnested=${full}!\nr=${random.int[100,200]}\nu=${random.uuid}\nesc=a\\\\${base}\n'}, {}, 'base,full,ref,nested,missing,r,u,esc'): print(l)
