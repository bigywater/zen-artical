import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x68'); CP = scp('org.springframework.boot:spring-boot-starter-webmvc')
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.context.annotation.Bean; import tools.jackson.databind.json.JsonMapper;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
@SpringBootApplication
public class Main {
  @Bean @ConditionalOnProperty("user.mapper") JsonMapper myMapper() { return JsonMapper.builder().build(); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE); app.run(a); System.exit(0); }
}
'''
b = sbuild('x68', {'src/demo/Main.java': MAIN}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def report(args=(), props=None):
    r = srun(b, 'demo.Main', args=args, props=props or {}, timeout=90); return r['out']
def sections(out):
    secs = {}; cur = None
    for l in out.splitlines():
        m = re.match(r'^(Positive matches|Negative matches|Exclusions|Unconditional classes):$', l)
        if m: cur = m.group(1); secs[cur] = []; continue
        if re.match(r'^\d{4}-\d\d-\d\d', l): cur = None
        if cur and l.strip() and not l.startswith('---'): secs[cur].append(l)
    return secs
def entries(lines): return [l for l in lines if re.match(r'^   \S', l) and not l.startswith('      ')]
print('Spring Boot 4.0.8 / JDK 21(spring-boot-starter-webmvc,非 Web 模式启动);不改一行代码,只加命令行参数')
print('== 一:没有 --debug 与有 --debug')
o1 = report(); print(f'  不加参数:输出里有 "CONDITIONS EVALUATION REPORT" = {"CONDITIONS EVALUATION REPORT" in o1},输出共 {len(o1.splitlines())} 行')
o2 = report(args=['--debug']); print(f'  --debug:输出里有 "CONDITIONS EVALUATION REPORT" = {"CONDITIONS EVALUATION REPORT" in o2},输出共 {len(o2.splitlines())} 行')
o3 = report(props={'debug': 'true'}); print(f'  -Ddebug=true:输出里有报告 = {"CONDITIONS EVALUATION REPORT" in o3}')
o4 = report(props={'logging.level.org.springframework.boot.autoconfigure.logging': 'DEBUG'}); print(f'  只调高 logging.level.org.springframework.boot.autoconfigure.logging=DEBUG:输出里有报告 = {"CONDITIONS EVALUATION REPORT" in o4}')
print('== 二:报告的结构')
S2 = sections(o2)
for k in ['Positive matches', 'Negative matches', 'Exclusions', 'Unconditional classes']: print(f'  {k}:{len(entries(S2.get(k, [])))} 项')
print('== 三:一个生效的、一个没生效的例子(原文)')
def block(out, name, kind):
    ls = S2.get(kind, []); res_ = []; on = False
    for l in ls:
        if re.match(r'^   \S', l) and not l.startswith('      '):
            on = name in l
        if on: res_.append(l)
    return res_
for kind, name in [('Positive matches', 'JacksonAutoConfiguration#jacksonJsonMapper'), ('Negative matches', 'WebMvcAutoConfiguration'), ('Negative matches', 'MessageSourceAutoConfiguration'), ('Negative matches', 'ProjectInfoAutoConfiguration#buildProperties'), ('Negative matches', 'Main#myMapper')]:
    bl = block(o2, name, kind); print(f'  [{kind}] {name}:'); [print('    ' + x[:200]) for x in (bl[:6] or ['(没找到)'])]
print('== 四:「为什么我的 Bean 没生效」:Jackson 的 JsonMapper,用户定义前后')
for props, lab in [({}, '用户没定义'), ({'user.mapper': 'true'}, '用户定义了 myMapper')]:
    o = report(args=['--debug'], props=props); Sx = sections(o)
    for kind in ['Positive matches', 'Negative matches']:
        for l in Sx.get(kind, []):
            if re.match(r'^   \S', l) and l.strip().startswith('JacksonAutoConfiguration#jacksonJsonMapper'): 
                idx = Sx[kind].index(l); print(f'  {lab} → [{kind}]'); [print('    ' + x[:210]) for x in Sx[kind][idx:idx + 3]]
print('== 五:报告的代价')
import statistics
ts = {}
for lab, args in [('不加 --debug', []), ('--debug', ['--debug'])]:
    xs = []
    for _ in range(3):
        t0 = time.time(); srun(b, 'demo.Main', args=args, timeout=90); xs.append(round((time.time() - t0) * 1000))
    ts[lab] = xs; print(f'  {lab}:3 次进程总用时(ms){xs}')
