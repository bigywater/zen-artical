import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u153'); R = {}
def mk(base, files):
    for p, c in files.items(): f = base / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(textwrap.dedent(c).lstrip('\n'))
print('== 一:一个带 feature 的库:default / 可选依赖(itoa)/ 互不依赖的两个 feature;用 cfg!(feature = "...") 在运行期报告编译了什么')
base = RS / 'proj' / 'u153'; shutil.rmtree(base, ignore_errors=True)
mk(base, {
  'fmtx/Cargo.toml': '''
    [package]
    name = "fmtx"
    version = "0.1.0"
    edition = "2024"
    [features]
    default = ["std-fmt"]
    std-fmt = []
    fast = ["dep:itoa"]
    extra = []
    [dependencies]
    itoa = { version = "1", optional = true }
  ''',
  'fmtx/src/lib.rs': '''
    pub fn features() -> Vec<&'static str> { let mut v = vec![]; if cfg!(feature = "std-fmt") { v.push("std-fmt"); } if cfg!(feature = "fast") { v.push("fast"); } if cfg!(feature = "extra") { v.push("extra"); } v }
    #[cfg(feature = "fast")] pub fn int(n: u64) -> String { itoa::Buffer::new().format(n).to_string() }
    #[cfg(not(feature = "fast"))] pub fn int(n: u64) -> String { format!("{}", n) }
    #[cfg(feature = "extra")] pub fn extra() -> &'static str { "extra 功能存在" }
  ''',
  'app/Cargo.toml': '''
    [package]
    name = "app"
    version = "0.1.0"
    edition = "2024"
    [dependencies]
    fmtx = { path = "../fmtx", default-features = false }
    [features]
    use-fast = ["fmtx/fast"]
    use-extra = ["fmtx/extra"]
    use-std = ["fmtx/std-fmt"]
  ''',
  'app/src/main.rs': '''
    fn main() { println!("fmtx 编译时启用的 feature:{:?};int(42) = {}", fmtx::features(), fmtx::int(42)); #[cfg(feature = "use-extra")] println!("{}", fmtx::extra()); }
  ''',
})
env = ENVB; app = base / 'app'
for label, args in [('default-features = false(不启用任何)', []), ('--features use-std', ['--features', 'use-std']), ('--features use-fast', ['--features', 'use-fast']), ('--features use-fast,use-extra', ['--features', 'use-fast,use-extra'])]:
    rc, o = cargo(['run', '--quiet'] + args, app, timeout=600); print(f'  {label:<40} → {o.strip().replace(chr(10), " | ")}'); R.setdefault('runs', {})[label] = o.strip()
print()
print('== 二:cargo tree -e features:每个 feature 是被谁启用的')
rc, o = cargo(['tree', '-e', 'features', '--features', 'use-fast'], app, timeout=300); print('\n'.join('  ' + l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip())); R['tree'] = [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip()]
print()
print('== 三:feature 统一(unification):两个依赖各自启用同一个库的不同 feature,最终该库只编译一次、启用的是它们的并集')
mk(base, {
  'left/Cargo.toml': '[package]\nname = "left"\nversion = "0.1.0"\nedition = "2024"\n[dependencies]\nfmtx = { path = "../fmtx", default-features = false, features = ["fast"] }\n', 'left/src/lib.rs': 'pub fn f() -> String { fmtx::int(1) }\n',
  'right/Cargo.toml': '[package]\nname = "right"\nversion = "0.1.0"\nedition = "2024"\n[dependencies]\nfmtx = { path = "../fmtx", default-features = false, features = ["extra"] }\n', 'right/src/lib.rs': 'pub fn g() -> &\'static str { fmtx::extra() }\n',
  'both/Cargo.toml': '[package]\nname = "both"\nversion = "0.1.0"\nedition = "2024"\n[dependencies]\nleft = { path = "../left" }\nright = { path = "../right" }\nfmtx = { path = "../fmtx", default-features = false }\n',
  'both/src/main.rs': 'fn main() { println!("app 自己没有启用任何 feature,但 fmtx 实际启用了:{:?}", fmtx::features()); println!("left 用到 fast:{};right 用到 extra:{}", left::f(), right::g()); }\n',
})
rc, o = cargo(['run', '--quiet'], base / 'both', timeout=600); print('  ' + o.strip().replace('\n', '\n  ')); R['unify'] = o.strip()
rc, o = cargo(['tree', '-e', 'features', '-i', 'fmtx'], base / 'both', timeout=300); print('  cargo tree -e features -i fmtx:'); print('\n'.join('    ' + l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip())); R['tree_i'] = [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip()]
print()
print('== 四:feature 必须是「可加」的:互斥的 feature 会在统一后同时启用,导致冲突(用 compile_error! 演示)')
mk(base, {'excl/Cargo.toml': '[package]\nname = "excl"\nversion = "0.1.0"\nedition = "2024"\n[features]\nbackend-a = []\nbackend-b = []\n', 'excl/src/lib.rs': '#[cfg(all(feature = "backend-a", feature = "backend-b"))] compile_error!("backend-a 与 backend-b 不能同时启用");\n',
         'xl/Cargo.toml': '[package]\nname = "xl"\nversion = "0.1.0"\nedition = "2024"\n[dependencies]\nexcl = { path = "../excl", features = ["backend-a"] }\nxr = { path = "../xr" }\n', 'xl/src/main.rs': 'fn main() {}\n',
         'xr/Cargo.toml': '[package]\nname = "xr"\nversion = "0.1.0"\nedition = "2024"\n[dependencies]\nexcl = { path = "../excl", features = ["backend-b"] }\n', 'xr/src/lib.rs': ''})
rc, o = cargo(['build'], base / 'xl', timeout=600); L = [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if 'error' in l or 'backend' in l][:3]; print('  两个依赖各启用一个互斥 feature,统一后同时启用:'); print('\n'.join('    ' + l for l in L)); R['excl'] = L
print()
print('== 五:可选依赖只在启用对应 feature 时才出现在依赖树里:cargo tree 分别在 --no-default-features 与 --features fast 下的结果')
rc, o = cargo(['tree', '--manifest-path', str(base / 'fmtx' / 'Cargo.toml'), '--no-default-features'], base, timeout=300); print('  cargo tree --no-default-features(fmtx):', [l for l in o.splitlines() if l.strip()]); R['nodef'] = [l for l in o.splitlines() if l.strip()]
rc, o = cargo(['tree', '--manifest-path', str(base / 'fmtx' / 'Cargo.toml'), '--features', 'fast'], base, timeout=300); print('  cargo tree --features fast(fmtx):', [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip()]); R['fast'] = [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip()]
save('u153', R)
