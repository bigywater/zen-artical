import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
V1 = {
 'lib/Api.java': '''package lib;
public class Api {
  public int add(int a, int b) { return a + b; }
  public void removed() {}
  public int ret() { return 1; }
  public static int stat() { return 1; }
  public void secret() {}
  public void thr() {}
  public Object get() { return "x"; }
  public int keep() { return 7; }
}''',
 'lib/Svc.java': 'package lib;\npublic interface Svc { void a(); static void callAll(Svc s) { s.a(); } }',
 'lib/Fin.java': 'package lib;\npublic class Fin { }',
 'lib/Color.java': 'package lib;\npublic enum Color { RED, GREEN, BLUE }',
 'lib/K.java': 'package lib;\npublic class K { public static final int MAX = 10; }',
 'lib/Base.java': 'package lib;\npublic class Base { }',
 'lib/Child.java': 'package lib;\npublic class Child extends Base { public String m() { return "m"; } }',
 'lib/Order.java': 'package lib;\npublic enum Order { A, B, C }',
 'lib/Abs.java': 'package lib;\npublic class Abs { }',
 'lib/Base2.java': 'package lib;\npublic class Base2 { public String fm() { return "base"; } }',
}
V2 = dict(V1)
V2['lib/Api.java'] = '''package lib;
public class Api {
  public int add(int a, long b) { return (int) (a + b); }
  public long ret() { return 1; }
  public int stat() { return 1; }
  protected void secret() {}
  public void thr() throws Exception {}
  public String get() { return "x"; }
  public int keep() { return 7; }
  public int extra() { return 8; }
}'''
V2['lib/Svc.java'] = 'package lib;\npublic interface Svc { void a(); void b(); static void callAll(Svc s) { s.a(); s.b(); } }'
V2['lib/Fin.java'] = 'package lib;\npublic final class Fin { }'
V2['lib/Color.java'] = 'package lib;\npublic enum Color { GREEN, BLUE }'
V2['lib/K.java'] = 'package lib;\npublic class K { public static final int MAX = 20; }'
V2['lib/Base.java'] = 'package lib;\npublic class Base { public String m() { return "m"; } }'
V2['lib/Child.java'] = 'package lib;\npublic class Child extends Base { }'
V2['lib/Order.java'] = 'package lib;\npublic enum Order { C, A, B }'
V2['lib/Abs.java'] = 'package lib;\npublic abstract class Abs { }'
V2['lib/Base2.java'] = 'package lib;\npublic class Base2 { public final String fm() { return "base"; } }'

import xml.etree.ElementTree as ET
from collections import Counter
tee('j292'); R = {}
d = jdir('j292a'); J = JDKS['21'] + '/bin/'
CP = mcp('com.github.siom79.japicmp:japicmp:0.23.1')
def build(name, F):
    write(d, {f'{name}/{k}': c for k, c in F.items()}); (d / name / 'cls').mkdir(exist_ok=True)
    r = subprocess.run([J + 'javac', '-d', str(d / name / 'cls'), *[str(d / name / k) for k in F]], capture_output=True, text=True); assert r.returncode == 0, r.stderr
    subprocess.run([J + 'jar', 'cf', str(d / f'{name}.jar'), '-C', str(d / name / 'cls'), '.'])
build('v1', V1); build('v2', V2)
SC = [
 ('S01', 'Api', 'add', 'add(int,int) 改成 add(int,long)', 'return "" + new Api().add(1, 2);'),
 ('S02', 'Api', 'removed', '删除 removed()', 'new Api().removed(); return "ok";'),
 ('S03', 'Api', 'ret', 'int ret() 改成 long ret()', 'int x = new Api().ret(); return "" + x;'),
 ('S04', 'Api', 'stat', 'static int stat() 改成实例方法', 'return "" + Api.stat();'),
 ('S05', 'Api', 'secret', 'public secret() 改成 protected', 'new Api().secret(); return "ok";'),
 ('S06', 'Api', 'thr', 'thr() 新增 throws Exception', 'new Api().thr(); return "ok";'),
 ('S07', 'Api', 'get', 'Object get() 改成 String get()', 'Object o = new Api().get(); return "" + o;'),
 ('S08', 'Svc', 'b', '接口 Svc 新增抽象方法 b()', 'Svc.callAll(new My()); return "ok";'),
 ('S09', 'Fin', None, 'class Fin 改成 final', 'new Sub(); return "ok";'),
 ('S10', 'Color', 'RED', '删除枚举常量 RED', 'return Color.RED.name();'),
 ('S13', 'Child', 'm', 'Child.m() 上移到父类 Base', 'return new Child().m();'),
 ('S14', 'Abs', None, 'class Abs 改成 abstract', 'new Abs(); return "ok";'),
 ('S15', 'Base2', 'fm', '父类方法 fm() 改成 final(子类覆盖了它)', 'return new Sub().fm();'),
 ('S17', 'Api', 'keep', '对照:keep() 没有改,同类里新增了 extra()', 'return "" + new Api().keep();'),
 ('S11', 'Order', None, '枚举 Order 常量顺序 A,B,C 改成 C,A,B', 'return Order.values()[1].name();'),
 ('S12', 'K', 'MAX', '常量 K.MAX 由 10 改成 20', 'return "" + K.MAX;'),
]
EXTRA = {'S08': 'static class My implements Svc { public void a() {} }', 'S09': 'static class Sub extends Fin {}', 'S15': 'static class Sub extends Base2 { public String fm() { return "sub"; } }'}
for sid, cls, mem, desc, code in SC:
    write(d, {f'client/{sid}.java': f'import lib.*; public class {sid} {{ {EXTRA.get(sid, "")} public static String run() {{ {code} }} }}'})
write(d, {'run/Main.java': 'public class Main { public static void main(String[] a) throws Exception { try { System.out.println("OK " + Class.forName(a[0]).getMethod("run").invoke(null)); } catch (java.lang.reflect.InvocationTargetException e) { Throwable t = e.getCause(); String m = String.valueOf(t.getMessage()).replace((char) 10, (char) 32); System.out.println("ERR " + t.getClass().getSimpleName() + ": " + (m.length() > 90 ? m.substring(0, 90) : m)); } catch (Throwable t) { System.out.println("ERR " + t.getClass().getSimpleName() + ": " + t.getMessage()); } } }'})
for n in ('c1', 'c2', 'run'): (d / n).mkdir(exist_ok=True)
subprocess.run([J + 'javac', '-d', str(d / 'run'), str(d / 'run/Main.java')], check=True)
def jv(cdir, jar, sid): r = subprocess.run([J + 'java', '-cp', f'{d}/run:{cdir}:{jar}', 'Main', sid], capture_output=True, text=True, timeout=60); return (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else '(无输出)'
def comp(cdir, jar, sid): r = subprocess.run([J + 'javac', '-cp', str(jar), '-d', str(cdir), str(d / f'client/{sid}.java')], capture_output=True, text=True); return r.returncode, tidy(r.stderr)
def japi(old, new, *extra): return subprocess.run([J + 'java', '-cp', CP, 'japicmp.JApiCmp', '-o', str(old), '-n', str(new), *extra], capture_output=True, text=True)
japi(d / 'v1.jar', d / 'v2.jar', '--xml-file', str(d / 'r.xml')); root = ET.parse(d / 'r.xml').getroot()
def changes(cls, mem):
    out = []
    for c in root.iter('class'):
        if c.get('fullyQualifiedName') != 'lib.' + cls: continue
        if mem is None:
            cc = c.find('compatibilityChanges'); out += [(x.get('type'), x.get('binaryCompatible') == 'true', x.get('sourceCompatible') == 'true') for x in (cc if cc is not None else [])]
        for tag in ('method', 'field', 'constructor'):
            for m in c.find(tag + 's').findall(tag):
                if m.get('name') == mem:
                    cc = m.find('compatibilityChanges'); out += [(x.get('type'), x.get('binaryCompatible') == 'true', x.get('sourceCompatible') == 'true') for x in (cc if cc is not None else [])]
    return out
ROWS = []
for sid, cls, mem, desc, code in SC:
    for n in ('c1', 'c2'): shutil.rmtree(d / n, ignore_errors=True); (d / n).mkdir()
    rc1, e1 = comp(d / 'c1', d / 'v1.jar', sid); assert rc1 == 0, e1
    ch = changes(cls, mem); pb = all(b for _, b, _ in ch); ps = all(s for _, _, s in ch)
    r1 = jv(d / 'c1', d / 'v1.jar', sid); r2 = jv(d / 'c1', d / 'v2.jar', sid)
    rc2, e2 = comp(d / 'c2', d / 'v2.jar', sid); r3 = jv(d / 'c2', d / 'v2.jar', sid) if rc2 == 0 else None
    err1 = next((l.split(': ', 1)[1] if ': ' in l else l for l in e2.splitlines() if 'error:' in l), '') if rc2 else ''
    outcome = 'error' if r2.startswith('ERR') else ('same' if r2 == r1 else 'changed')
    ROWS.append(dict(sid=sid, cls=cls, mem=mem, desc=desc, ch=sorted(set(t for t, _, _ in ch)), pb=pb, ps=ps, r1=r1, r2=r2, rc2=rc2, err=err1, r3=r3, outcome=outcome))
def tf(x): return '兼容' if x else '不兼容'
print('== 一:japicmp 0.23.1 对 v1 → v2 的预测,与旧 client(针对 v1 编译)在 v2 上的真实运行、重新编译的结果对照(JDK 21)')
for x in ROWS[:14]:
    print(f"  {x['sid']} {x['desc']}:japicmp 二进制{tf(x['pb'])}、源码{tf(x['ps'])}({','.join(x['ch']) or '无变更记录'});旧 client 在 v1:{x['r1']};在 v2:{x['r2']};针对 v2 重新编译:" + ('通过' + (',运行 ' + x['r3'] if x['r3'] else '') if x['rc2'] == 0 else '编译失败:' + x['err'][:80]))
okb = sum(1 for x in ROWS[:14] if (x['pb'] and x['outcome'] != 'error') or (not x['pb'] and x['outcome'] == 'error')); oks = sum(1 for x in ROWS[:14] if (x['ps'] and x['rc2'] == 0) or (not x['ps'] and x['rc2'] != 0))
print(f'  汇总:14 个场景里 japicmp 的二进制兼容预测与旧 client 运行结果一致 {okb} 个;源码兼容预测与 javac 重新编译结果一致 {oks} 个;二进制不兼容 {sum(1 for x in ROWS[:14] if not x["pb"])} 个、源码不兼容 {sum(1 for x in ROWS[:14] if not x["ps"])} 个、二进制兼容但源码不兼容 {sum(1 for x in ROWS[:14] if x["pb"] and not x["ps"])} 个、二进制不兼容但源码兼容 {sum(1 for x in ROWS[:14] if not x["pb"] and x["ps"])} 个')
print('== 二:没有报错、也没有被报告的变化:枚举顺序与常量值')
for x in ROWS[14:]:
    print(f"  {x['sid']} {x['desc']}:japicmp 的变更记录 {','.join(x['ch']) or '无'}(二进制{tf(x['pb'])}、源码{tf(x['ps'])});旧 client 在 v1:{x['r1']};在 v2:{x['r2']};针对 v2 重新编译后在 v2:{x['r3']}")
r = japi(d / 'v1.jar', d / 'v2.jar'); print('  日志里 K 与 Order 的状态:' + ';'.join(l.strip().split('  ')[0] + ' ' + l.strip().split(' lib.')[-1].split()[0] for l in r.stdout.splitlines() if ' lib.K ' in l or ' lib.Order ' in l))
# ---- 三:真实库
print('== 三:真实库两个版本之间的 API 变更报告:commons-lang3 3.12.0 → 3.18.0')
cpl = lambda v: mcp(f'org.apache.commons:commons-lang3:{v}').split(':')[0]
o, n = cpl('3.12.0'), cpl('3.18.0'); r = japi(o, n, '--xml-file', str(d / 'cl.xml'), '--ignore-missing-classes'); rt = ET.parse(d / 'cl.xml').getroot()
cls = list(rt.iter('class')); st = Counter(c.get('changeStatus') for c in cls); bi = [c for c in cls if c.get('binaryCompatible') == 'false']; si = [c for c in cls if c.get('sourceCompatible') == 'false']
ty = Counter(); tys = Counter()
for c in cls:
    for x in c.iter('compatibilityChange'):
        if x.get('binaryCompatible') == 'false': ty[x.get('type')] += 1
        if x.get('sourceCompatible') == 'false': tys[x.get('type')] += 1
print(f'  类共 {len(cls)} 个:{dict(st)};二进制不兼容的类 {len(bi)} 个;源码不兼容的类 {len(si)} 个;二进制不兼容的变更条数 {sum(ty.values())}、源码不兼容的变更条数 {sum(tys.values())}')
print('  源码不兼容变更的类型:' + ';'.join(f'{k} × {v}' for k, v in tys.most_common(6)))
ms = [(c.get('fullyQualifiedName').split('.')[-1], m.get('name'), x.get('type')) for c in si for m in c.iter('method') for x in m.iter('compatibilityChange') if x.get('sourceCompatible') == 'false']; print(f'  源码不兼容的例子:' + '、'.join(f'{a}.{b}({t})' for a, b, t in ms[:4]) + f';二进制不兼容的变更 {sum(ty.values())} 条(旧 jar 仍能直接链接,但用新版本重新编译的源码可能要改)')
def sv(o, n, *x): r = japi(o, n, '-s', '--ignore-missing-classes', '-m', '-b', *x); return (r.stdout.strip().splitlines() or ['(空)'])[-1]
# ---- 四
print('== 四:把检查接入构建:--error-on-* 开关的退出码')
V3 = dict(V1); V3['lib/Api.java'] = V1['lib/Api.java'].replace('public int keep() { return 7; }', 'public int keep() { return 7; }\n  public int extra() { return 8; }'); build('v3', V3)
V4 = dict(V1); V4['lib/Api.java'] = V1['lib/Api.java'].replace('public void thr() {}', 'public void thr() throws Exception {}'); build('v4', V4)
for lab, new in (('v1 → v3(只新增了一个 public 方法)', 'v3'), ('v1 → v4(只给 thr() 新增 throws Exception)', 'v4'), ('v1 → v2(多种破坏性变更)', 'v2')):
    cells = []
    for flag in ('--error-on-binary-incompatibility', '--error-on-source-incompatibility', '--error-on-modifications'):
        r = japi(d / 'v1.jar', d / f'{new}.jar', flag); cells.append(f'{flag.replace("--error-on-", "")} → rc={r.returncode}')
    print(f'  {lab}:' + ';'.join(cells))
print('  --semantic-versioning 建议的版本号变化:commons-lang3 3.12.0 → 3.18.0:' + sv(o, n) + ';v1 → v3(只新增方法):' + sv(d / 'v1.jar', d / 'v3.jar') + ';v1 → v4(只新增 throws):' + sv(d / 'v1.jar', d / 'v4.jar') + ';v1 → v2(多种破坏性变更):' + sv(d / 'v1.jar', d / 'v2.jar') + ';v1 → v1(没有变化):' + sv(d / 'v1.jar', d / 'v1.jar') + '(0.0.1 = 补丁、0.1.0 = 次版本、1.0.0 = 主版本)')
r = japi(d / 'v1.jar', d / 'v2.jar', '--error-on-binary-incompatibility', '-b'); print('  v1 → v2 加 -b 只输出二进制不兼容的类:' + str(sum(1 for l in r.stdout.splitlines() if l.startswith(('***!', '---!', '+++!', '===!')))) + ' 个类行;stderr 最后一行:' + (r.stderr.strip().splitlines() or ['(空)'])[-1][:150])
shutil.rmtree(d, ignore_errors=True)
