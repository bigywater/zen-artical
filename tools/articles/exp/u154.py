import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import json
tee('u154'); R = {}
def mk(base, files):
    for p, c in files.items(): f = base / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(textwrap.dedent(c).lstrip('\n'))
base = RS / 'proj' / 'u154'; shutil.rmtree(base, ignore_errors=True)
mk(base, {
 'Cargo.toml': '''
   [workspace]
   members = ["crates/core", "crates/util", "crates/cli"]
   resolver = "3"
   [workspace.package]
   version = "0.5.0"
   edition = "2024"
   license = "MIT"
   [workspace.dependencies]
   itoa = "1"
   core = { path = "crates/core", package = "u154_core" }
   util = { path = "crates/util", package = "u154_util" }
 ''',
 'crates/core/Cargo.toml': '[package]\nname = "u154_core"\nversion.workspace = true\nedition.workspace = true\nlicense.workspace = true\n[dependencies]\nitoa.workspace = true\n', 'crates/core/src/lib.rs': 'pub fn fmt(n: u32) -> String { itoa::Buffer::new().format(n).to_string() }\n',
 'crates/util/Cargo.toml': '[package]\nname = "u154_util"\nversion.workspace = true\nedition.workspace = true\n[dependencies]\ncore = { workspace = true }\nitoa.workspace = true\n', 'crates/util/src/lib.rs': 'pub fn twice(n: u32) -> String { format!("{}{}", core::fmt(n), core::fmt(n)) }\n',
 'crates/cli/Cargo.toml': '[package]\nname = "u154_cli"\nversion.workspace = true\nedition.workspace = true\n[dependencies]\nutil.workspace = true\n', 'crates/cli/src/main.rs': 'fn main() { println!("{}", util::twice(7)); }\n',
})
print('== 一:一个工作区三个 crate:共享一个 Cargo.lock 与一个 target 目录;成员用 xxx.workspace = true 继承版本、edition 与依赖声明')
rc, o = cargo(['build', '--workspace'], base, timeout=600); comp = [l.strip() for l in o.splitlines() if 'Compiling' in l]; print('  cargo build --workspace 编译的 crate(按顺序):'); print('\n'.join('    ' + l.replace(str(RS), '<实验目录>') for l in comp)); R['order'] = [l.replace(str(RS), '<实验目录>') for l in comp]
files = sorted(str(p.relative_to(base)) for p in base.rglob('*') if p.is_file() and 'target' not in p.parts)
print(f'  工作区里的 Cargo.lock 个数:{sum(1 for f in files if f.endswith("Cargo.lock"))};成员目录里是否有自己的 target / Cargo.lock:{any("crates/" in f and ("target" in f or f.endswith("Cargo.lock")) for f in files)}'); R['files'] = files
R['itoa_n'] = (base / 'Cargo.lock').read_text().count('name = "itoa"'); print(f"  itoa 在 Cargo.lock 里出现 {R['itoa_n']} 次(三个成员共用同一份)")
rc, so, se, _ = run(TG / 'debug' / 'u154_cli'); print('  运行 u154_cli:', so.strip()) if False else None
print()
print('== 二:cargo metadata 看继承的结果:三个成员的版本都是 0.5.0(来自 [workspace.package]),依赖版本要求来自 [workspace.dependencies]')
rc, o = cargo(['metadata', '--no-deps', '--format-version', '1'], base, timeout=300); md = json.loads(o); R['members'] = []
for p in md['packages']:
    deps = [f"{d['name']}{d['req']}" + (' (path)' if d.get('path') else '') for d in p['dependencies']]
    print(f'  {p["name"]:<10} version {p["version"]}  edition {p["edition"]}  license {p.get("license")}  依赖 {deps}'); R['members'].append([p['name'], p['version'], p['edition'], p.get('license'), deps])
print()
print('== 三:改一处,全体生效:把 [workspace.package] 的 version 与 [workspace.dependencies] 里 itoa 的要求各改一次,三个成员都变')
t = (base / 'Cargo.toml').read_text().replace('version = "0.5.0"', 'version = "0.6.0"').replace('itoa = "1"', 'itoa = "=1.0.9"'); (base / 'Cargo.toml').write_text(t)
rc, o = cargo(['update'], base, timeout=300); rc, o, e = sh(['cargo', 'metadata', '--format-version', '1'], cwd=base, env=ENVB, timeout=300); md = json.loads(o)
print('  版本:', {p['name']: p['version'] for p in md['packages'] if p['name'].startswith('u154')}); print('  itoa 解析为:', [p['version'] for p in md['packages'] if p['name'] == 'itoa']); R['changed'] = [{p['name']: p['version'] for p in md['packages'] if p['name'].startswith('u154')}, [p['version'] for p in md['packages'] if p['name'] == 'itoa']]
print()
print('== 四:-p 只构建指定的成员(已编译好的不重复编译);在成员目录里运行 cargo 仍然使用工作区根的 target,成员目录里不会生成 target 或 Cargo.lock')
shutil.rmtree(TG, ignore_errors=True) if False else None
sub = base / 'crates' / 'util'; env = dict(ENVB, CARGO_TARGET_DIR=str(base / 'target')); 
rc, o, e = sh(['cargo', 'clean'], cwd=base, env=env); 
for label, args, cwd in [('cargo build -p u154_core', ['build', '-p', 'u154_core'], base), ('cargo build -p u154_util', ['build', '-p', 'u154_util'], base), ('在 crates/util 目录里 cargo build', ['build'], sub)]:
    rc, o, e = sh(['cargo'] + args, cwd=cwd, env=env, timeout=600); comp = re.findall(r'Compiling (\S+)', o + e); print(f'  {label:<32} 编译了 {comp}'); R.setdefault('p', {})[label] = comp
print(f'  在 crates/util 目录运行 cargo 时用的是哪个 target / lock:', 'target 在工作区根' if (base / 'target').exists() and not (sub / 'target').exists() else '?', '| 成员目录下 Cargo.lock:', (sub / 'Cargo.lock').exists()); R['where'] = [(base / 'target').exists(), (sub / 'target').exists(), (sub / 'Cargo.lock').exists()]
print()
print('== 五:对照:三个互相独立的项目各自依赖 itoa,各自编译一次 itoa;工作区只编译一次')
cnt = 0
for i in range(3):
    d = proj(f'u154sep{i}', {'src/main.rs': 'fn main() { println!("{}", itoa::Buffer::new().format(1u8)); }'}, deps='itoa = "1"'); cargo(['clean'], d)
    rc, o, e = sh(['cargo', 'build'], cwd=d, env=dict(ENVB, CARGO_TARGET_DIR=str(d / 'tgt')), timeout=600); cnt += len(re.findall(r'Compiling itoa', o + e))
print(f'  3 个独立项目(各用各的 target 目录)合计 Compiling itoa 出现 {cnt} 次'); R['sep_itoa'] = cnt
shutil.rmtree(base / 'target', ignore_errors=True); rc, o, e = sh(['cargo', 'build', '--workspace'], cwd=base, env=env, timeout=600); w = len(re.findall(r'Compiling itoa', o + e)); print(f'  工作区(三个成员都依赖 itoa)Compiling itoa 出现 {w} 次'); R['ws_itoa'] = w
save('u154', R)
