import sys, os, re, time, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x99'); CP = scp('org.springframework.boot:spring-boot-starter-flyway', 'org.flywaydb:flyway-mysql', 'com.mysql:mysql-connector-j', 'org.springframework.boot:spring-boot-starter-jdbc')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import org.springframework.boot.*; import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication
public class Main { public static void main(String[] a) { SpringApplication app = new SpringApplication(Main.class); app.setBannerMode(Banner.Mode.OFF); app.setWebApplicationType(WebApplicationType.NONE); app.run(a); System.out.println("RES 启动成功"); System.exit(0); } }
'''
b = sbuild('x99', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
my = mysql('x99'); URL = jdbc(my)
WD = JT / 'x99_wd'
def reset(): my.q('drop database if exists demo'); my.q('create database demo')
def run(files, props=None):
    shutil.rmtree(WD, ignore_errors=True); mig = WD / 'rc' / 'db' / 'migration'; mig.mkdir(parents=True)
    for k, v in files.items(): (mig / k).write_text(v)
    b2 = dict(b, cp=str(WD / 'rc') + ':' + b['cp'])
    pr = {'spring.datasource.url': URL, 'spring.datasource.username': 'app', 'spring.datasource.password': 'app'}; pr.update(props or {})
    r = srun(b2, 'demo.Main', props=pr, timeout=120, cwd=str(WD)); return r
def err(r):
    o = r['out']
    if 'RES 启动成功' in o: return None
    ex = [x.strip() for x in o.splitlines() if re.match(r'^(Exception in thread "main" |Caused by: )?[\w.$]+(Exception|Error):', x.strip())]
    msgs = [x.replace('Exception in thread "main" ', '') for x in ex if 'flywaydb' in x]
    det = [x.strip() for x in o.splitlines() if re.search(r'checksum mismatch|Applied to database|Resolved locally|Detected resolved migration|Detected failed migration|Migration .* failed|SQL State|Message\s+:|Statement\s*:|Line\s*:', x)]
    return ((msgs[-1] if msgs else (ex[-1] if ex else o[-400:])) + ((' ‖ ' + ' ‖ '.join(dict.fromkeys(det))) if det else ''))[:1100]
def hist():
    try: rows = my.q('select installed_rank, version, description, type, script, checksum, success from demo.flyway_schema_history order by installed_rank')
    except Exception as e: return '(没有 flyway_schema_history)'
    return [f'rank {r[0]} version {r[1]} "{r[2]}" {r[3]} checksum {r[5]} success={r[6]}' for r in rows]
def tables(): return sorted(x[0] for x in my.q('show tables from demo') if x[0] != 'flyway_schema_history')
def show(title, r):
    e = err(r); print(f'  {title}:' + ('启动成功' if e is None else '启动失败')); 
    if e: print('    ' + e)
    h = hist(); print('    历史表:' + ('' if isinstance(h, str) else ''), end='')
    if isinstance(h, str): print(h)
    else:
        print(f'{len(h)} 行'); [print('      ' + x) for x in h]
    print('    业务表:' + str(tables()))
print('Spring Boot 4.0.8 / Flyway 11.14.1(spring-boot-starter-flyway + flyway-mysql)/ MySQL 26.7.0(自己起的实例);迁移脚本放在 classpath:db/migration')
print('== 一:迁移的执行顺序是按版本号,不是按文件名排序')
reset(); show('V1、V2、V10、V1_1 四个脚本', run({'V1__create_a.sql': 'create table a(id int);', 'V2__create_b.sql': 'create table b(id int);', 'V10__create_c.sql': 'create table c(id int);', 'V1_1__alter_a.sql': 'alter table a add column v int;'}))
print('== 二:改了已经执行过的脚本(校验和)')
reset(); run({'V1__create_a.sql': 'create table a(id int);', 'V2__create_b.sql': 'create table b(id int);'})
show('V2 的内容被改了一个字符之后再启动', run({'V1__create_a.sql': 'create table a(id int);', 'V2__create_b.sql': 'create table b(id bigint);'}))
reset(); run({'V1__create_a.sql': 'create table a(id int);', 'R__view_a.sql': 'create or replace view va as select id from a;'})
show('可重复迁移 R__view_a.sql 改了内容之后再启动', run({'V1__create_a.sql': 'create table a(id int);', 'R__view_a.sql': 'create or replace view va as select id, id + 1 as n from a;'}))
print('== 三:乱序:V1.5 补在 V2 已经执行之后')
reset(); run({'V1__create_a.sql': 'create table a(id int);', 'V2__create_b.sql': 'create table b(id int);'})
f3 = {'V1__create_a.sql': 'create table a(id int);', 'V1_5__late.sql': 'create table late(id int);', 'V2__create_b.sql': 'create table b(id int);'}
show('默认(out-of-order=false)', run(f3))
reset(); run({'V1__create_a.sql': 'create table a(id int);', 'V2__create_b.sql': 'create table b(id int);'}); show('spring.flyway.out-of-order=true', run(f3, {'spring.flyway.out-of-order': 'true'}))
print('== 四:脚本中途失败(MySQL 的 DDL 不能回滚)')
reset(); bad = {'V1__create_a.sql': 'create table a(id int);', 'V2__two_statements.sql': 'create table t2(id int);\ninsert into no_such_table values (1);'}
show('V2 里第一条建表成功、第二条出错', run(bad))
show('不改任何东西再启动一次', run(bad))
print('== 五:已有表的库第一次接入 Flyway')
reset(); my.q('create table demo.legacy(id int)'); show('库里已有 legacy 表、没有历史表', run({'V1__create_a.sql': 'create table a(id int);', 'V2__create_b.sql': 'create table b(id int);'}))
reset(); my.q('create table demo.legacy(id int)'); show('spring.flyway.baseline-on-migrate=true', run({'V1__create_a.sql': 'create table a(id int);', 'V2__create_b.sql': 'create table b(id int);'}, {'spring.flyway.baseline-on-migrate': 'true'}))
my.stop()
