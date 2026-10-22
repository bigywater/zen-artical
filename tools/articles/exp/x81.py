import sys, os, re, time, json, shutil, subprocess, statistics, glob; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x81')
CP = scp('org.springframework.boot:spring-boot-starter-webmvc', 'org.springframework.boot:spring-boot-starter-actuator')
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.web.bind.annotation.*; import org.slf4j.*; import org.springframework.boot.logging.*;
@SpringBootApplication @RestController
public class Main {
  final LoggingSystem ls; Main(LoggingSystem ls) { this.ls = ls; }
  @GetMapping("/log") String log(@RequestParam String n) { Logger l = LoggerFactory.getLogger(n); l.trace("trace 行"); l.debug("debug 行"); l.info("info 行"); l.warn("warn 行"); l.error("error 行"); return "ok"; }
  @GetMapping("/burst") String burst(@RequestParam int n, @RequestParam int size) { Logger l = LoggerFactory.getLogger("demo.burst"); String pad = "x".repeat(size); for (int i = 0; i < n; i++) l.info("行 {} {}", i, pad); return "ok"; }
  @GetMapping("/lvl") String lvl(@RequestParam String name) { LoggerFactory.getLogger(name); var c = ls.getLoggerConfiguration(name); return name + " configured=" + (c == null ? null : c.getConfiguredLevel()) + " effective=" + (c == null ? null : c.getEffectiveLevel()); }
  public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.run(a); }
}
'''
b = sbuild('x81', {'src/demo/Main.java': MAIN}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
WD = JT / 'x81_wd'
def start(props=None, cp=None, files=None):
    shutil.rmtree(WD, ignore_errors=True); WD.mkdir(parents=True); rc = WD / 'rc'; rc.mkdir()
    for k, v in (cp or {}).items(): (rc / k).write_text(v)
    for k, v in (files or {}).items(): (WD / k).write_text(v)
    pr = {'management.endpoints.web.exposure.include': 'loggers', 'server.port': free_port()}; pr.update(props or {})
    b2 = dict(b, cp=str(rc) + ':' + b['cp'], dir=WD)
    a = SApp(b2, 'demo.Main', props=pr, port=pr['server.port'], name='stdout'); a.start(); time.sleep(0.3); return a
def lines(a): return [l for l in a.log().splitlines() if l.strip()]
def shorten(l, n=190): return l if len(l) <= n else l[:n] + '…'
def g(a, p): return a.get(p)[1]
def gs(a, p): r = a.get(p); return f'{r[0]} {r[1]}'
print('Spring Boot 4.0.8 / JDK 21 / Logback(随 starter 来);webmvc + actuator;日志取自进程的标准输出,不是 tty 所以没有颜色')
print('== 一:默认格式、级别与结构化输出')
a = start(); ls_ = lines(a); a.stop()
print(f'  默认(root=INFO):启动到端口可连接一共输出 {len(ls_)} 行;第 1 行:'); print('    ' + shorten(ls_[0])); print('    最后一行:' + shorten(ls_[-1]))
for lab, pr in (('logging.level.root=DEBUG', {'logging.level.root': 'DEBUG'}), ('logging.level.org.springframework=DEBUG', {'logging.level.org.springframework': 'DEBUG'}), ('logging.level.root=TRACE', {'logging.level.root': 'TRACE'}), ('logging.level.root=WARN', {'logging.level.root': 'WARN'})):
    a = start(pr); n = len(lines(a)); a.stop(); print(f'  {lab}:启动共 {n} 行')
a = start({'logging.pattern.console': '%d{HH:mm:ss} %-5level [%thread] %logger{20} - %msg%n'}); l0 = lines(a)[0]; a.stop(); print('  logging.pattern.console 自定义之后第 1 行:' + shorten(l0))
for fmt in ('ecs', 'logstash', 'gelf'):
    a = start({'logging.structured.format.console': fmt}); ls2 = lines(a); a.stop()
    try: j = json.loads(ls2[-1]); print(f'  logging.structured.format.console={fmt}:一行 JSON,字段 {sorted(j)[:14]}{"…" if len(j) > 14 else ""}(共 {len(j)} 个)')
    except Exception as e: print(f'  logging.structured.format.console={fmt}:最后一行不是 JSON:{shorten(ls2[-1], 120)}')
print('== 二:logging.group 与 logging.level')
a = start({'logging.level.web': 'DEBUG'})
for n in ('org.springframework.web', 'org.springframework.http', 'org.springframework.web.servlet.DispatcherServlet', 'org.springframework.boot', 'demo'): print(f'  logging.level.web=DEBUG:{g(a, "/lvl?name=" + n)}')
a.stop()
a = start({'logging.level.sql': 'DEBUG'})
for n in ('org.hibernate.SQL', 'org.springframework.jdbc.core', 'org.jooq.tools.LoggerListener'): print(f'  logging.level.sql=DEBUG:{g(a, "/lvl?name=" + n)}')
a.stop()
a = start({'logging.group.mine': 'demo.a,demo.b', 'logging.level.mine': 'TRACE', 'logging.level.demo.b': 'WARN'})
for n in ('demo.a', 'demo.b', 'demo.c', 'demo.a.sub'): print(f'  logging.group.mine=demo.a,demo.b + level.mine=TRACE + level.demo.b=WARN:{g(a, "/lvl?name=" + n)}')
a.stop()
a = start({'logging.level.demo': 'DEBUG', 'logging.level.demo.x': 'ERROR'}); g(a, '/log?n=demo.x'); g(a, '/log?n=demo.y'); ls3 = [l for l in lines(a) if 'demo.' in l and ('行' in l)]; a.stop()
print('  logging.level.demo=DEBUG、demo.x=ERROR 时 /log 的输出(按 logger 名分):')
for l in ls3: print('    ' + shorten(re.sub(r'^\S+\s+', '', l), 120))
print('== 三:日志文件与滚动')
def rolling(props, burst):
    a = start(props); g(a, burst); time.sleep(0.5); a.stop(); fs = sorted(glob.glob(str(WD / 'logs' / '*')) + [f for f in glob.glob(str(WD / '*.log*')) if not f.endswith('stdout.log')])
    return [(os.path.relpath(f, WD), os.path.getsize(f)) for f in fs if os.path.isfile(f)]
r = rolling({'logging.file.name': 'logs/app.log'}, '/burst?n=10&size=20'); print('  logging.file.name=logs/app.log,写 10 行:' + '; '.join(f'{n} {s} 字节' for n, s in r))
r = rolling({'logging.file.path': 'logs'}, '/burst?n=10&size=20'); print('  logging.file.path=logs(不写文件名):' + '; '.join(f'{n} {s} 字节' for n, s in r))
r = rolling({'logging.file.name': 'logs/app.log', 'logging.logback.rollingpolicy.max-file-size': '4KB', 'logging.logback.rollingpolicy.max-history': '3', 'logging.logback.rollingpolicy.total-size-cap': '1MB'}, '/burst?n=300&size=100')
print(f'  max-file-size=4KB、max-history=3,写 300 行 × 约 100 字符 + 前缀:生成 {len(r)} 个文件:'); [print(f'    {n}  {s} 字节') for n, s in r]
r = rolling({'logging.file.name': 'logs/app.log', 'logging.logback.rollingpolicy.max-file-size': '4KB', 'logging.logback.rollingpolicy.file-name-pattern': 'logs/app-%d{yyyyMMdd}.%i.log'}, '/burst?n=300&size=100')
print(f'  file-name-pattern=logs/app-%d{{yyyyMMdd}}.%i.log(不带 .gz):{len(r)} 个文件:' + '; '.join(f'{n} {s} 字节' for n, s in r))
print('== 四:运行时改级别(Actuator loggers)')
a = start({'logging.level.demo': 'INFO'})
def count_dbg(a): 
    before = len([l for l in lines(a) if 'debug 行' in l]); g(a, '/log?n=demo.rt'); return len([l for l in lines(a) if 'debug 行' in l]) - before
print(f'  初始:GET /actuator/loggers/demo.rt → {gs(a, "/actuator/loggers/demo.rt")};/log?n=demo.rt 输出 debug 行数 {count_dbg(a)}')
st, body, _ = a.get('/actuator/loggers/demo', method='POST', body='{"configuredLevel":"DEBUG"}', headers={'Content-Type': 'application/json'}); print(f'  POST /actuator/loggers/demo {{"configuredLevel":"DEBUG"}} → {st}')
print(f'  之后:GET /actuator/loggers/demo.rt → {g(a, "/actuator/loggers/demo.rt")};/log?n=demo.rt 输出 debug 行数 {count_dbg(a)}(没有重启)')
st, body, _ = a.get('/actuator/loggers/demo', method='POST', body='{"configuredLevel":null}', headers={'Content-Type': 'application/json'}); print(f'  POST {{"configuredLevel":null}} → {st};GET /actuator/loggers/demo → {g(a, "/actuator/loggers/demo")};debug 行数 {count_dbg(a)}')
st, body, _ = a.get('/actuator/loggers/web', method='POST', body='{"configuredLevel":"TRACE"}', headers={'Content-Type': 'application/json'}); print(f'  对分组 web 发 POST /actuator/loggers/web {{"configuredLevel":"TRACE"}} → {st};GET /actuator/loggers/org.springframework.web → {g(a, "/actuator/loggers/org.springframework.web")}')
st, body, _ = a.get('/actuator/loggers/demo', method='POST', body='{"configuredLevel":"LOUD"}', headers={'Content-Type': 'application/json'}); print(f'  非法级别 LOUD → {st}')
a.stop()
print('== 五:logback.xml 与 logback-spring.xml')
XML = lambda tag: f'<configuration><appender name="C" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>[DEFAULT] %level %msg%n</pattern></encoder></appender>' + '<springProfile name="dev"><appender name="D" class="ch.qos.logback.core.ConsoleAppender"><encoder><pattern>[DEV-ONLY] %level %msg%n</pattern></encoder></appender><logger name="demo.p" level="DEBUG"><appender-ref ref="D"/></logger></springProfile><root level="INFO"><appender-ref ref="C"/></root></configuration>'
for fname in ('logback-spring.xml', 'logback.xml'):
    for prof in ('dev', None):
        a = start({'spring.profiles.active': prof} if prof else {}, cp={fname: XML(fname)}); g(a, '/log?n=demo.p'); ls4 = lines(a); a.stop()
        mine = [l for l in ls4 if ('DEFAULT' in l or 'DEV-ONLY' in l) and ' 行' in l]; errs = [l for l in ls4 if 'ERROR in' in l or 'no applicable action' in l.lower()]
        print(f'  {fname},profile={prof or "无"}:/log?n=demo.p 的输出 → ' + (' | '.join(l[:60] for l in mine) if mine else '(没有匹配的行)') + (f';Logback 的状态报错:{shorten(errs[0], 150)}' if errs else ''))
