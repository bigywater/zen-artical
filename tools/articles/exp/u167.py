import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import statistics, glob
tee('u167'); R = {}
MAIN = '''
    use serde::{Serialize, Deserialize};
    #[derive(Serialize, Deserialize, Debug)]
    struct P { a: i32, b: String }
    fn main() {
        let p = P { a: 1, b: "x".into() };
        let s = serde_json::to_string(&p).unwrap();
        let re = regex::Regex::new(r"\\d+").unwrap();
        println!("{} {}", s, re.is_match("a1"));
    }
'''
DEPS = 'serde = { version = "1", features = ["derive"] }\nserde_json = "1"\nregex = "1"\n'
d = proj('u167p', {'src/main.rs': MAIN}, deps=DEPS)
def tgt(name): return RS / f'target_u167_{name}'
def build(args, name, extra_env=None, clean_first=True, cwd=d):
    t = tgt(name)
    if clean_first: shutil.rmtree(t, ignore_errors=True)
    env = dict(ENVB, CARGO_TARGET_DIR=str(t)); env.update(extra_env or {})
    t0 = time.perf_counter(); rc, o, e = sh(['cargo', 'build', *args], cwd=cwd, env=env, timeout=900); return rc, tidy(clean(o + e)), time.perf_counter() - t0, t
def pr(txt, n=40, ind='    ', w=200):
    L = txt.split('\n'); print('\n'.join(ind + l[:w] for l in L[:n]))
    if len(L) > n: print(f'{ind}…(共 {len(L)} 行)')
print('== 一:cargo build --timings:被测项目(serde + serde_json + regex)与每个编译单元的耗时(从生成的 HTML 里的 UNIT_DATA 取出)')
print('  src/main.rs:'); print('\n'.join('    ' + l for l in numbered(MAIN).split('\n')))
print('  Cargo.toml 依赖:', DEPS.strip().replace('\n', ';  '))
rc, o, wall, t = build(['--timings'], 'tm'); print(f'  cargo build --timings:退出码 {rc};整体 {wall:.1f} 秒;最后一行:{o.splitlines()[-1].strip()}')
f = t / 'cargo-timings' / 'cargo-timing.html'; h = f.read_text(); m = re.search(r'const UNIT_DATA = (\[.*?\n\]);', h, re.S); U = json.loads(m.group(1))
print(f'  HTML 报告大小 {len(h) / 1024:.0f} KiB,共 {len(U)} 个编译单元(build script 的编译、运行与库各算一个)')
rows = sorted(U, key=lambda u: u['start'])
print(f'  {"单元":<22} {"类型":<14} {"开始(s)":>8} {"耗时(s)":>8} {"结束(s)":>8}')
R['units'] = []
for u in rows:
    kind = u['target'].strip() or 'lib'; kind = {'build-script': 'build script', 'run-custom-build': '运行 build script'}.get(kind, kind)
    print(f'  {u["name"] + " " + u["version"]:<22} {kind:<14} {u["start"]:>8.2f} {u["duration"]:>8.2f} {u["start"] + u["duration"]:>8.2f}')
    R['units'].append([u['name'], u['version'], kind, u['start'], u['duration']])
tot = max(u['start'] + u['duration'] for u in U)
ev = sorted([(u['start'], 1) for u in U] + [(u['start'] + u['duration'], -1) for u in U]); cur = mx = 0
for _, dlt in ev: cur += dlt; mx = max(mx, cur)
print(f'  最后一个单元结束于 {tot:.2f} 秒;同一时刻最多并行 {mx} 个单元;单元耗时总和 {sum(u["duration"] for u in U):.2f} 秒')
fe = sum(s[1]['end'] - s[1]['start'] for u in U if u['sections'] for s in u['sections'] if s[0] == 'frontend'); cg = sum(s[1]['end'] - s[1]['start'] for u in U if u['sections'] for s in u['sections'] if s[0] == 'codegen')
print(f'  有分段信息的单元里:frontend 合计 {fe:.2f} 秒、codegen 合计 {cg:.2f} 秒')
R['tot'] = tot; R['par'] = mx; R['sum'] = sum(u['duration'] for u in U); R['fe'] = fe; R['cg'] = cg; R['htmlkb'] = round(len(h) / 1024)
last = rows[-1]; print(f'  最后开始的单元是 {last["name"]}(开始于 {last["start"]:.2f} 秒):它要等所有依赖的 rmeta 就绪')
last_deps = [u['name'] for u in U if last['i'] in u['unblocked_units'] or last['i'] in u['unblocked_rmeta_units']]; print(f'  直接解锁 {last["name"]} 的单元:{last_deps}'); R['unblock'] = last_deps
print()
print('== 二:并行度:同一个项目,-j 1 与默认(本机 10 核)的干净构建耗时,各 3 次取中位数')
R['jobs'] = {}
for lab, a in (('-j 1', ['-j', '1']), ('默认', [])):
    ts = [build(a, 'j')[2] for _ in range(3)]; R['jobs'][lab] = statistics.median(ts); print(f'  {lab:<6} 3 次:{", ".join(f"{x:.1f}" for x in ts)} 秒;中位数 {statistics.median(ts):.1f} 秒')
print()
def gen(n, dyn):
    s = ['trait T { fn f(&self, x: u64) -> u64; }']
    for i in range(n): s.append(f'struct S{i}(u64); impl T for S{i} {{ fn f(&self, x: u64) -> u64 {{ x.wrapping_mul({i + 3}).wrapping_add(self.0) }} }}')
    if dyn: s.append('fn work(t: &dyn T) -> u64 { let mut a = 0u64; for i in 0..10u64 { a = a.wrapping_add(t.f(i)); } a }')
    else: s.append('fn work<X: T>(t: &X) -> u64 { let mut a = 0u64; for i in 0..10u64 { a = a.wrapping_add(t.f(i)); } a }')
    s.append('fn main() { let mut s = 0u64;'); s += [f'    s = s.wrapping_add(work(&S{i}({i})));' for i in range(n)]; s.append('    println!("{}", s); }'); return '\n'.join(s) + '\n'
print('== 三:rustc -Z time-passes:一个生成的文件(300 个类型实现同一个 trait,泛型函数被 300 次实例化)的各阶段耗时,取最耗时的前 10 项(去掉 total 与三个耗时完全相同的链接包装层)')
f_ = src_file('u167_tp', gen(300, False)); out = RS / 'bin' / 'u167_tp'
rc, o, e = sh(['rustc', '--edition=2024', '-Z', 'time-passes', str(f_), '-o', str(out)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
passes = []
for l in (o + e).split('\n'):
    m = re.match(r'time:\s+([\d.]+);\s+rss:\s+(\d+)MB\s+->\s+(\d+)MB\s+\(\s*([+-]?\d+)MB\)\s+(\S+)', l.strip())
    if m: passes.append((float(m.group(1)), m.group(5)))
tot_ = [s_ for s_, n in passes if n == 'total']; wrap = ('total', 'link', 'link_crate', 'link_binary')
lk = {n: s_ for s_, n in passes if n in wrap}; passes = sorted([x for x in passes if x[1] not in wrap], reverse=True)
print(f'  退出码 {rc};共 {len(passes)} 个阶段(另有 total = {tot_[0] if tot_ else None} 秒;link / link_crate / link_binary 分别为 {lk.get("link")}/{lk.get("link_crate")}/{lk.get("link_binary")} 秒);耗时前 10:'); print(f'  {"阶段":<42} {"秒":>7}')
for s_, n in passes[:10]: print(f'  {n:<42} {s_:>7.3f}')
R['passes'] = passes[:10]; R['npasses'] = len(passes); R['tp_total'] = tot_[0] if tot_ else None; R['tp_link'] = lk
print()
print('== 四:泛型实例化的代价:同一个泛型函数被 N 个不同类型实例化,与只用一份 dyn Trait,调试构建的编译耗时(每个 3 次取中位数)')
print(f'  {"N":>5} {"泛型 (秒)":>10} {"dyn (秒)":>10}  {"泛型单态化项数":>16} {"dyn 单态化项数":>16}')
R['mono'] = []
for n in (50, 200, 800):
    row = [n]
    for dyn in (False, True):
        f_ = src_file(f'u167_g{n}{"d" if dyn else ""}', gen(n, dyn)); ts = []
        for _ in range(3):
            t0 = time.perf_counter(); rc, o, e = sh(['rustc', '--edition=2024', '-C', 'debuginfo=0', str(f_), '-o', str(RS / 'bin' / 'u167_g')], env=ENVB); ts.append(time.perf_counter() - t0); assert rc == 0, e[:300]
        rc, o, e = sh(['rustc', '--edition=2024', '-C', 'debuginfo=0', '-Z', 'print-mono-items=yes', str(f_), '-o', str(RS / 'bin' / 'u167_g')], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
        nm = len([l for l in (o + e).split('\n') if re.match(r'MONO_ITEM fn work\b', l)])
        row += [statistics.median(ts), nm]
    print(f'  {n:>5} {row[1]:>10.2f} {row[3]:>10.2f}  {row[2]:>16} {row[4]:>16}'); R['mono'].append(row)
print()
print('== 五:构建配置:同一个项目(serde + serde_json + regex)的干净构建耗时与可执行文件大小,各 3 次取中位数')
print(f'  {"配置":<34} {"耗时(秒)":>10} {"可执行文件(KiB)":>16}')
R['prof'] = {}
for lab, a, ex in (('dev(默认,debuginfo=2)', [], {}), ('dev + debug=0', [], {'CARGO_PROFILE_DEV_DEBUG': '0'}), ('dev + opt-level=1', [], {'CARGO_PROFILE_DEV_OPT_LEVEL': '1'}), ('dev + 依赖 opt-level=3', [], {'CARGO_PROFILE_DEV_PACKAGE_$ALL_OPT_LEVEL': '3'}), ('release', ['--release'], {})):
    if '$ALL' in str(ex): continue
    ts = []
    for _ in range(3): rc, o, w, t = build(a, 'p', extra_env=ex); ts.append(w); assert rc == 0, o[-300:]
    exe = t / ('release' if a else 'debug') / 'u167p'; R['prof'][lab] = [statistics.median(ts), exe.stat().st_size / 1024]; print(f'  {lab:<34} {statistics.median(ts):>10.1f} {exe.stat().st_size / 1024:>16.0f}')
print()
print('== 六:增量重编:改一行 main.rs 之后只重编最后一个包;对比改 Cargo.toml 的特征(serde_json 开 preserve_order)')
rc, o, w0, t = build([], 'inc'); print(f'  干净构建 {w0:.1f} 秒')
def rebuild(): return build([], 'inc', clean_first=False)
rc, o, w1, _ = rebuild(); print(f'  没有任何改动再构建:{w1:.2f} 秒')
(d / 'src' / 'main.rs').write_text(show(MAIN).replace('"x"', '"yy"') + '\n'); rc, o, w2, _ = rebuild(); n2 = len([l for l in o.split('\n') if 'Compiling' in l]); print(f'  改 main.rs 里的一个字符串:{w2:.2f} 秒,重编 {n2} 个包')
(d / 'Cargo.toml').write_text((d / 'Cargo.toml').read_text().replace('serde_json = "1"', 'serde_json = { version = "1", features = ["preserve_order"] }')); rc, o, w3, _ = rebuild(); n3 = [l.strip() for l in o.split('\n') if 'Compiling' in l]; print(f'  给 serde_json 加 preserve_order 特征:{w3:.2f} 秒,重编 {len(n3)} 个包:{", ".join(x.split()[1] for x in n3)}')
R['inc'] = dict(clean=w0, noop=w1, edit=w2, edit_n=n2, feat=w3, feat_n=[x.split()[1] for x in n3])
save('u167', R)
