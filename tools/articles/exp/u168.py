import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u168'); R = {}
MAIN = '''
    use serde::{Deserialize, Serialize};
    #[derive(Serialize, Deserialize, Debug)]
    struct P { a: i32, b: String }
    fn main() {
        let arg = std::env::args().nth(1).unwrap_or_default();
        let p: P = serde_json::from_str(&arg).unwrap_or(P { a: 0, b: String::new() });
        let re = regex::Regex::new(&arg).unwrap();
        println!("{} {}", serde_json::to_string(&p).unwrap(), re.is_match("abc123"));
    }
'''
HELLO = 'fn main() { println!("hello {}", std::env::args().count()); }\n'
def mk(name, regex_dep='regex = "1"', main=MAIN):
    d = proj(name, {'src/main.rs': main}, deps='serde = { version = "1", features = ["derive"] }\nserde_json = "1"\n' + regex_dep + '\n'); return d
d = mk('u168p'); TGT = RS / 'target_u168'
ENVS = dict(ENVN, CARGO_TARGET_DIR=str(TGT))
def cm(args, cwd=d, extra=None, timeout=900):
    env = dict(ENVS); env.update(extra or {}); t0 = time.perf_counter(); rc, o, e = sh(['cargo', *args], cwd=cwd, env=env, timeout=timeout); return rc, tidy(clean(o)), tidy(clean(e)), time.perf_counter() - t0
def size_of(name, cwd=d, extra=None):
    rc, o, e, t = cm(['build', '--release'], cwd, extra); assert rc == 0, e[-400:]
    return (TGT / 'release' / name).stat().st_size
def pr(txt, n=40, ind='    ', w=200):
    L = txt.split('\n'); print('\n'.join(ind + l[:w] for l in L[:n]))
    if len(L) > n: print(f'{ind}…(共 {len(L)} 行)')
print('== 一:被测程序:serde 派生 + serde_json + regex;对比只有 println! 的 hello。release 构建的文件大小,与 size / nm 看到的构成')
print('  src/main.rs:'); print('\n'.join('    ' + l for l in numbered(MAIN).split('\n')))
hd = proj('u168h', {'src/main.rs': HELLO}); hs = size_of('u168h', hd)
sz = size_of('u168p'); exe = TGT / 'release' / 'u168p'
print(f'  hello(只有 println!):{hs / 1024:.0f} KiB;本程序:{sz / 1024:.0f} KiB(约 {sz / hs:.1f} 倍)'); R['hello'] = hs; R['size'] = sz
rc, o, e = sh(['size', '-m', str(exe)], env=ENVN); print('  size -m(Mach-O 各段):'); L = [l for l in o.split('\n') if l.startswith(('Segment', '\tSection')) or l.startswith('total')]; print('\n'.join('    ' + l.replace('\t', '  ')[:100] for l in L[:16])); R['size_m'] = L[:16]
rc, o, e = sh(['nm', str(exe)], env=ENVN); nsym = len([l for l in o.split('\n') if l.strip()]); print(f'  nm 看到的符号数:{nsym}'); R['nsym'] = nsym
cp = RS / 'bin' / 'u168p_stripped'; shutil.copy(exe, cp); sh(['strip', str(cp)], env=ENVN); print(f'  用 strip 命令再剥一次:{exe.stat().st_size / 1024:.0f} KiB → {cp.stat().st_size / 1024:.0f} KiB'); R['strip_cmd'] = [exe.stat().st_size, cp.stat().st_size]
rc, o, e = sh(['nm', str(cp)], env=ENVN); print(f'  剥完后 nm 的符号数:{len([l for l in o.split(chr(10)) if l.strip() and not l.startswith("nm:")])}(nm 的提示:{e.strip()[:60]})')
print()
print('== 二:cargo bloat --release --crates:各个 crate 在 .text 里占多少')
rc, o, e, t = cm(['bloat', '--release', '--crates', '-n', '12']); print(f'  退出码 {rc}'); pr(o, 20); R['crates'] = o.split('\n')[:20]
print()
print('== 三:cargo bloat --release:占空间最大的 10 个函数')
rc, o, e, t = cm(['bloat', '--release', '-n', '10']); pr(o, 20, w=170); R['funcs'] = o.split('\n')[:20]
print()
print('== 四:依赖的特征:regex 默认特征 vs 关掉 Unicode 与性能特征(default-features = false, features = ["std", "perf"] 以及再关 perf)')
variants = [('regex 默认特征', 'regex = "1"'), ('std + perf(无 unicode)', 'regex = { version = "1", default-features = false, features = ["std", "perf"] }'), ('std(无 unicode、无 perf)', 'regex = { version = "1", default-features = false, features = ["std"] }')]
R['feat'] = {}
print(f'  {"regex 特征":<28} {"release 大小(KiB)":>18}')
for lab, dep in variants:
    dv = mk('u168v', dep); s_ = size_of('u168v', dv); R['feat'][lab] = s_; print(f'  {lab:<28} {s_ / 1024:>18.0f}')
# 无 unicode 时 \\d 之类依然能用?运行一下
dv = mk('u168v', variants[2][1]); size_of('u168v', dv); rr = subprocess.run([str(TGT / 'release' / 'u168v'), '[a-c]+1'], capture_output=True, text=True); print(f'  无 unicode 的版本用 [a-c]+1 运行:退出码 {rr.returncode},输出 {rr.stdout.strip() or rr.stderr.strip()[:100]}')
rr = subprocess.run([str(TGT / 'release' / 'u168v'), r'\w+'], capture_output=True, text=True); print(f'  同一个程序用 \\w+ 运行(Unicode 模式的 \\w 需要 unicode 特征):退出码 {rr.returncode}'); print('    ' + (rr.stdout.strip() or rr.stderr.strip())[:200].replace(chr(10), ' ')); R['nounicode'] = [rr.returncode, (rr.stdout.strip() or rr.stderr.strip())[:200]]
print()
print('== 五:编译选项叠加:每一行在上一行基础上再加一个选项(release 大小)')
steps_ = [('release 默认', {}), ('+ strip = true', {'CARGO_PROFILE_RELEASE_STRIP': 'true'}), ('+ panic = "abort"', {'CARGO_PROFILE_RELEASE_PANIC': 'abort'}), ('+ opt-level = "z"', {'CARGO_PROFILE_RELEASE_OPT_LEVEL': 'z'}), ('+ lto = true', {'CARGO_PROFILE_RELEASE_LTO': 'true'}), ('+ codegen-units = 1', {'CARGO_PROFILE_RELEASE_CODEGEN_UNITS': '1'})]
acc = {}; R['knobs'] = []; prev = None
print(f'  {"配置":<24} {"大小(KiB)":>10} {"相对上一行":>10}')
for lab, ex in steps_:
    acc.update(ex); s_ = size_of('u168p', d, dict(acc)); R['knobs'].append([lab, s_]); print(f'  {lab:<24} {s_ / 1024:>10.0f} {"" if prev is None else f"{(s_ - prev) / prev * 100:+.0f}%":>10}'); prev = s_
rr = subprocess.run([str(TGT / 'release' / 'u168p'), '[a-c]+1'], capture_output=True, text=True); print(f'  最终的最小版本照常运行(参数 [a-c]+1):退出码 {rr.returncode},输出 {rr.stdout.strip()}'); R['final_run'] = rr.stdout.strip()
print()
print('== 六:cargo llvm-lines:哪些函数生成的 LLVM IR 最多(泛型被实例化的份数 = Copies)')
rc, o, e, t = cm(['llvm-lines', '--release'], timeout=900); L = o.split('\n'); print(f'  退出码 {rc};前 12 行:'); pr('\n'.join(L[:12]), 12, w=170); R['llvm'] = L[:12]
save('u168', R)
