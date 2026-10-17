import sys, os, re, time, zipfile; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j290'); R = {}
d = jdir('j290a'); E = jenv('21', MAVEN_OPTS='-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=1087 -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=1087')
M2LC = pathlib.Path.home() / '.m2/repository/lc'
assert not M2LC.exists()
POM = '''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>lc.demo</groupId><artifactId>lc</artifactId><version>1.0</version>
<properties><maven.compiler.release>17</maven.compiler.release><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties>
<dependencies><dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter</artifactId><version>5.10.2</version><scope>test</scope></dependency></dependencies>%s</project>'''
FILES = {'src/main/java/App.java': 'public class App { public static int add(int a, int b) { return a + b; } }', 'src/main/resources/a.txt': 'hello',
         'src/test/java/AppTest.java': 'import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; public class AppTest { @Test void t() { assertEquals(3, App.add(1, 2)); } }'}
def setup(build=''):
    shutil.rmtree(d / 'target', ignore_errors=True); write(d, {**FILES, 'pom.xml': POM % build})
def mv(*args, tmo=300):
    t = time.time(); r = subprocess.run(['mvn', '-B', '-o', '-f', str(d / 'pom.xml'), *args], env=E, capture_output=True, text=True, timeout=tmo); wall = time.time() - t
    txt = tidy(r.stdout + r.stderr); goals = re.findall(r'--- (\S+?):\S+?:(\S+) \((\S+)\) @', txt)
    return dict(rc=r.returncode, txt=txt, goals=['%s:%s' % (p, g) for p, g, _ in goals], ids=[i for _, _, i in goals], wall=wall)
def gl(r): return ' → '.join(r['goals']) if r['goals'] else '(无)'
# ---- 一
print('== 一:阶段与默认绑定:jar 打包下,每个阶段会执行哪些插件目标(JDK 21,Maven 3.10.0,离线 -o,每次先删除 target)')
setup(); r = mv('no-such-phase'); m = re.search(r'Available lifecycle phases are: ([^.]*?)\.\s', r['txt'].replace('\n', ' ') + ' ')
if m: ph = [x.strip() for x in m.group(1).split(',')]; print(f'  mvn no-such-phase 的错误信息列出的合法阶段:{len(ph)} 个:' + ','.join(ph[:30]))
else: print('  (未解析到阶段列表)'); print(r['txt'][-600:])
prev = 0
for ph_ in ('validate', 'compile', 'test', 'package', 'verify', 'install'):
    setup(); r = mv(ph_) if ph_ != 'install' else mv('install'); print(f'  mvn {ph_}:rc={r["rc"]},执行 {len(r["goals"])} 个目标:{gl(r)}')
    R[ph_] = r
shutil.rmtree(M2LC, ignore_errors=True)
# ---- 二
print('== 二:把插件目标绑定到阶段:同一个阶段里的执行顺序(用 resources:copy-resources 绑定在 process-resources,pom 里声明顺序 zz → aa)')
BUILD = '''<build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-resources-plugin</artifactId><version>3.5.0</version><executions>
<execution><id>zz-first</id><phase>process-resources</phase><goals><goal>copy-resources</goal></goals><configuration><outputDirectory>${project.build.directory}/extra1</outputDirectory><resources><resource><directory>src/main/resources</directory></resource></resources></configuration></execution>
<execution><id>aa-second</id><phase>process-resources</phase><goals><goal>copy-resources</goal></goals><configuration><outputDirectory>${project.build.directory}/extra2</outputDirectory><resources><resource><directory>src/main/resources</directory></resource></resources></configuration></execution>
<execution><id>early</id><phase>validate</phase><goals><goal>copy-resources</goal></goals><configuration><outputDirectory>${project.build.directory}/extra0</outputDirectory><resources><resource><directory>src/main/resources</directory></resource></resources></configuration></execution>
</executions></plugin></plugins></build>'''
setup(BUILD); r = mv('compile'); print(f'  mvn compile:执行 {len(r["goals"])} 个目标(含 id):' + ' → '.join(f'{g}[{i}]' for g, i in zip(r['goals'], r['ids'])))
print('  target 下生成的目录:' + ','.join(sorted(p.name for p in (d / 'target').iterdir())))
# ---- 三
print('== 三:直接调用插件目标(插件前缀:目标),不经过生命周期的前置阶段')
setup(); r = mv('compiler:compile'); print(f'  全新项目 mvn compiler:compile:rc={r["rc"]},执行 {len(r["goals"])} 个目标:{gl(r)};target/classes 内容:' + ','.join(sorted(p.name for p in (d / 'target/classes').iterdir())) + ';src/main/resources 的 a.txt 被复制了吗:' + str((d / 'target/classes/a.txt').exists()))
setup(); r = mv('jar:jar'); jars = list((d / 'target').glob('*.jar')); names = zipfile.ZipFile(jars[0]).namelist() if jars else []
print(f'  全新项目 mvn jar:jar(没有先编译):rc={r["rc"]},执行 {len(r["goals"])} 个目标:{gl(r)};jar 里的条目数 {len(names)},其中 .class {sum(n.endswith(".class") for n in names)} 个;警告:' + '; '.join(l.replace('[WARNING] ', '') for l in r['txt'].splitlines() if 'JAR will be empty' in l))
setup(); mv('compile'); r = mv('jar:jar'); names = zipfile.ZipFile(list((d / 'target').glob('*.jar'))[0]).namelist()
print(f'  先 mvn compile 再 mvn jar:jar:jar 条目数 {len(names)},其中 .class {sum(n.endswith(".class") for n in names)} 个,a.txt {sum(n=="a.txt" for n in names)} 个')
setup(); r = mv('compile', 'surefire:test'); print(f'  mvn compile surefire:test(阶段与目标混用):执行 {len(r["goals"])} 个目标:{gl(r)}')
# ---- 四
print('== 四:跳过测试的两个开关,与第二次构建的增量')
setup(); r1 = mv('package'); r2 = mv('package')
print(f'  第一次 mvn package:{len(r1["goals"])} 个目标,日志 "Compiling" 行:' + '; '.join(re.sub(r'\s+to .*', '', l.replace('[INFO] ', '')) for l in r1['txt'].splitlines() if 'Compiling' in l))
print(f'  第二次 mvn package(没有改动):{len(r2["goals"])} 个目标,日志:' + '; '.join(l.replace('[INFO] ', '') for l in r2['txt'].splitlines() if 'Nothing to compile' in l or 'Tests run:' in l and 'Time' not in l) + ';"Building jar" 日志行数:第一次 ' + str(r1['txt'].count('Building jar')) + ',第二次 ' + str(r2['txt'].count('Building jar')) + '(jar 没有改动时 jar 目标不再重新打包,也不打日志)')
setup(); r3 = mv('package', '-DskipTests'); print(f'  mvn package -DskipTests:{len(r3["goals"])} 个目标:{gl(r3)}')
print('      日志:' + '; '.join(l.replace('[INFO] ', '') for l in r3['txt'].splitlines() if 'skipped' in l.lower() or 'Compiling' in l))
setup(); r4 = mv('package', '-Dmaven.test.skip=true'); print(f'  mvn package -Dmaven.test.skip=true:{len(r4["goals"])} 个目标:{gl(r4)}')
print('      日志:' + '; '.join(l.replace('[INFO] ', '') for l in r4['txt'].splitlines() if 'skip' in l.lower() or 'Not compiling' in l))
print('      target 下是否有 test-classes:' + str((d / 'target/test-classes').exists()))
# ---- 五
print('== 五:某个阶段失败,后面的阶段不再执行')
FAIL = dict(FILES); FAIL['src/test/java/AppTest.java'] = 'import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; public class AppTest { @Test void t() { assertEquals(4, App.add(1, 2)); } }'
write(d, {**FAIL, 'pom.xml': POM % ''}); shutil.rmtree(d / 'target', ignore_errors=True); r = mv('package')
print(f'  测试失败时 mvn package:rc={r["rc"]},执行 {len(r["goals"])} 个目标:{gl(r)};生成 jar:{bool(list((d / "target").glob("*.jar")))};结果:' + next((l.replace('[INFO] ', '') for l in r['txt'].splitlines() if 'BUILD' in l), ''))
shutil.rmtree(d / 'target', ignore_errors=True); r = mv('package', '-Dmaven.test.failure.ignore=true')
print(f'  加 -Dmaven.test.failure.ignore=true:rc={r["rc"]},执行 {len(r["goals"])} 个目标:{gl(r)};生成 jar:{bool(list((d / "target").glob("*.jar")))};' + next((l.replace('[ERROR] ', '').strip()[:100] for l in r['txt'].splitlines() if 'Tests run:' in l and 'Failures: 1' in l and 'Time' not in l), ''))
shutil.rmtree(d, ignore_errors=True)
