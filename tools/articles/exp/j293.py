import sys, os, re, time, hashlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j293'); R = {}
GR = HERE.parent / 'gradle/gradle-9.8.0'; GH = HERE.parent / 'gradle/home293'; shutil.rmtree(GH, ignore_errors=True); GH.mkdir()
d = jdir('j293a'); J = JDKS['21'] + '/bin/'; REPO = d / 'repo'; REPO.mkdir()
M2G = pathlib.Path.home() / '.m2/repository/lock'; assert not M2G.exists()
def pom(a, v, deps=()):
    ds = ''.join(f'<dependency><groupId>lock</groupId><artifactId>{x}</artifactId><version>{y}</version></dependency>' for x, y in deps)
    return f'<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>lock</groupId><artifactId>{a}</artifactId><version>{v}</version><dependencies>{ds}</dependencies></project>'
VERS = {}
def publish(a, v, deps=()):
    src = d / f'src_{a}_{v}'; shutil.rmtree(src, ignore_errors=True); (src / 'p').mkdir(parents=True)
    (src / 'p' / f'{a.title()}.java').write_text(f'package p; public class {a.title()} {{ public static String v() {{ return "{a} {v}"; }} }}')
    subprocess.run([J + 'javac', '-d', str(src / 'o'), str(src / 'p' / f'{a.title()}.java')], check=True)
    ad = REPO / 'lock' / a / v; ad.mkdir(parents=True, exist_ok=True)
    subprocess.run([J + 'jar', 'cf', str(ad / f'{a}-{v}.jar'), '-C', str(src / 'o'), '.'], check=True); (ad / f'{a}-{v}.pom').write_text(pom(a, v, deps))
    VERS.setdefault(a, []).append(v); vs = ''.join(f'<version>{x}</version>' for x in VERS[a])
    (REPO / 'lock' / a / 'maven-metadata.xml').write_text(f'<metadata><groupId>lock</groupId><artifactId>{a}</artifactId><versioning><latest>{VERS[a][-1]}</latest><release>{VERS[a][-1]}</release><versions>{vs}</versions></versioning></metadata>')
publish('core', '1.0'); publish('lib', '1.0', [('core', '[1.0,2.0)')])
def w(p, c): f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(textwrap.dedent(c).lstrip('\n'))
w('settings.gradle', "rootProject.name = 'app'\n"); w('gradle.properties', 'org.gradle.vfs.watch=false\n')
BG = lambda lock='': f"""plugins {{ id 'java' }}
repositories {{ maven {{ url = uri('{REPO}') }} }}
dependencies {{ implementation 'lock:lib:1.+' }}
{lock}"""
w('build.gradle', BG()); w('src/main/java/Main.java', 'public class Main { public static void main(String[] a) { System.out.println(p.Lib.v() + " / " + p.Core.v()); } }')
E = jenv('21', GRADLE_USER_HOME=str(GH))
def gr(*args):
    r = subprocess.run([str(GR / 'bin/gradle'), '--console=plain', '--offline', '-q', '-p', str(d), *args], env=E, capture_output=True, text=True, timeout=600, cwd=d); return r.returncode, tidy(r.stdout + r.stderr)
def res(*args):
    rc, t = gr('dependencies', '--configuration', 'runtimeClasspath', *args)
    return rc, ' '.join(f'{m.group(1)}:{m.group(2)}' + (f'→{m.group(3)}' if m.group(3) else '') for m in re.finditer(r'lock:(\w+):(\S+?)(?: -> (\S+))?(?: \(\*\))?$', t, re.M)) or t[:300]
def mresolve(*fl):
    pm = d / 'mvn/pom.xml'; r = subprocess.run(['mvn', '-B', *fl, '-f', str(pm), 'dependency:tree'], env=jenv('21'), capture_output=True, text=True, timeout=300); t = tidy(r.stdout + r.stderr)
    return r.returncode, ' '.join(a + ':' + b for a, b in re.findall(r'lock:(\w+):jar:(\S+?):', t)) or t[-300:]
def mpom(ver): return f'<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>x</groupId><artifactId>app</artifactId><version>1</version><repositories><repository><id>loc</id><url>file://{REPO}</url><snapshots><enabled>false</enabled></snapshots></repository></repositories><dependencies><dependency><groupId>lock</groupId><artifactId>lib</artifactId><version>{ver}</version></dependency></dependencies></project>'
print('== 一:没有锁的时候:动态版本会漂移(本地 file:// 仓库里依次发布 lock:lib 与它的传递依赖 lock:core)')
w('mvn/pom.xml', mpom('[1.0,2.0)')); rc, a1 = mresolve(); print(f'  仓库里只有 lib 1.0 / core 1.0:Maven 版本范围 [1.0,2.0) 解析为 {a1}(rc={rc});Gradle lock:lib:1.+ 解析为 ' + res()[1])
publish('lib', '1.1', [('core', '[1.0,2.0)')]); publish('core', '1.1'); publish('core', '1.2')
print(f'  之后发布了 lib 1.1、core 1.1、core 1.2,什么都没改:Maven [1.0,2.0) 解析为 {mresolve()[1]}(本地仓库缓存了仓库元数据,默认一天内不再检查);加 -U 强制更新后解析为 {mresolve("-U")[1]};Gradle 1.+ 加 --refresh-dependencies 解析为 {res("--refresh-dependencies")[1]}')
w('mvn/pom.xml', mpom('1.0')); print(f'  把 Maven 依赖写成固定版本 1.0(加 -U):解析为 {mresolve("-U")[1]}(lib 自己的依赖范围 [1.0,2.0) 仍然让传递依赖 core 取最新版)')
print('== 二:Gradle 依赖锁定:写锁文件、发布新版本、更新锁')
w('build.gradle', BG('dependencyLocking { lockAllConfigurations() }')); rc, t = gr('dependencies', '--write-locks'); lf = (d / 'gradle.lockfile').read_text().strip().splitlines()
print(f'  gradle dependencies --write-locks:rc={rc};生成 gradle.lockfile,{len([x for x in lf if not x.startswith("#")])} 行:' + ' | '.join(x for x in lf if not x.startswith('#')))
print(f'  锁文件写好之后解析:{res()[1]}')
publish('lib', '1.2', [('core', '[1.0,2.0)')]); publish('core', '1.3')
print(f'  再发布 lib 1.2 与 core 1.3(仓库里 lib 有 {",".join(VERS["lib"])}、core 有 {",".join(VERS["core"])}),加 --refresh-dependencies 解析:{res("--refresh-dependencies")[1]}(仍然是锁里的版本)')
rc, t = gr('dependencies', '--update-locks', 'lock:lib'); lf = [x for x in (d / 'gradle.lockfile').read_text().strip().splitlines() if not x.startswith('#')]
print(f'  gradle dependencies --update-locks lock:lib:rc={rc};锁文件变成:' + ' | '.join(lf) + f';解析:{res()[1]}(只更新了 lib,没有传递依赖 core)')
rc, t = gr('dependencies', '--update-locks', 'lock:*'); lf = [x for x in (d / 'gradle.lockfile').read_text().strip().splitlines() if not x.startswith('#')]; print(f'  gradle dependencies --update-locks \'lock:*\':锁文件变成:' + ' | '.join(lf))
print('== 三:锁文件与声明不一致、新增依赖时,三种 lockMode(DEFAULT / STRICT / LENIENT)的行为')
def wrong(t): L = t.splitlines(); i = next((k for k, l in enumerate(L) if 'What went wrong' in l), None); return ' / '.join(x.strip() for x in L[i + 1:i + 4] if x.strip() and 'Execution failed' not in x) if i is not None else '(无错误)'
publish('other', '1.0')
LK = [l for l in (d / 'gradle.lockfile').read_text().strip().splitlines() if not l.startswith('#') and not l.startswith('empty')]
print('  锁文件当前内容:' + ' | '.join(x.split('=')[0] for x in LK) + ' (lib 1.2 / core 1.3)')
for mode in ('DEFAULT', 'STRICT', 'LENIENT'):
    lk = f"dependencyLocking {{ lockAllConfigurations(); lockMode = LockMode.{mode} }}"
    w('build.gradle', BG(lk)); rc0, _ = gr('compileJava')
    w('build.gradle', BG(lk).replace("implementation 'lock:lib:1.+'", "implementation 'lock:lib:1.+'\n  implementation 'lock:other:1.0'")); rc1, t1 = gr('compileJava')
    w('build.gradle', BG(lk).replace("'lock:lib:1.+'", "'lock:lib:[1.0,1.1]'")); rc2, t2 = gr('compileJava'); rr = res()[1]
    w('build.gradle', BG(lk)); os.rename(d / 'gradle.lockfile', d / 'gradle.lockfile.bak'); rc3, t3 = gr('compileJava'); os.rename(d / 'gradle.lockfile.bak', d / 'gradle.lockfile')
    print(f'  {mode}:声明与锁一致 compileJava rc={rc0};新增不在锁文件里的依赖 lock:other:1.0 rc={rc1}' + ('(' + wrong(t1)[:130] + ')' if rc1 else '') + f';声明改成 lock:lib:[1.0,1.1](锁里是 lib 1.2)rc={rc2}' + ('(' + wrong(t2)[:200] + ')' if rc2 else f',解析为 {rr}') + f';删掉锁文件后 rc={rc3}' + ('(' + wrong(t3)[:130] + ')' if rc3 else ''))
print('== 四:依赖校验(verification-metadata.xml):被篡改的 jar 能被发现吗')
w('build.gradle', BG()); shutil.rmtree(d / 'gradle.lockfile', ignore_errors=True)
rc, t = gr('--write-verification-metadata', 'sha256', 'dependencies', '--configuration', 'runtimeClasspath'); vm = (d / 'gradle/verification-metadata.xml').read_text()
comp = re.findall(r'<component group="([^"]+)" name="([^"]+)" version="([^"]+)"', vm); print(f'  gradle --write-verification-metadata sha256:rc={rc};verification-metadata.xml 里 {len(comp)} 个 component:' + ','.join(f'{b}:{c}' for a, b, c in comp) + f';sha256 条目 {vm.count("<sha256")} 个')
rc, t = gr('compileJava'); print(f'  没有改动时 compileJava:rc={rc}')
jar = REPO / 'lock/lib/1.2/lib-1.2.jar'; orig = jar.read_bytes(); jar.write_bytes(orig + b'\0')
rc, t = gr('compileJava', '--refresh-dependencies'); print(f'  篡改了仓库里的 lib-1.2.jar(末尾多一个字节):rc={rc};错误:' + ' / '.join(l.strip() for l in t.splitlines() if 'verification' in l.lower() or 'sha256' in l.lower() or 'expected' in l.lower())[:420])
jar.write_bytes(orig); rc, t = gr('compileJava', '--refresh-dependencies'); print(f'  还原后 compileJava:rc={rc}')
subprocess.run([str(GR / 'bin/gradle'), '--stop'], env=E, capture_output=True, cwd=d)
shutil.rmtree(M2G, ignore_errors=True)
