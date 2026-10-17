import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import json as J_
tee('u15'); R = {}
def tree(d, skip=('target', '.git')):
    out = []
    for f in sorted(pathlib.Path(d).rglob('*')):
        rel = f.relative_to(d)
        if any(p in skip for p in rel.parts): continue
        out.append(str(rel) + ('/' if f.is_dir() else ''))
    return out
print('== 一:一个 package 可以同时有 lib 与 bin 两个 crate:src/lib.rs 与 src/main.rs')
shutil.rmtree(TG, ignore_errors=True)
d = proj('pkg2', {'src/lib.rs': 'pub fn greet() -> &\'static str { "来自 lib crate" }\n', 'src/main.rs': 'fn main() { println!("{}", pkg2::greet()); }\n'})
rc, o = cargo(['build', '-v'], d)
names = re.findall(r'--crate-name (\S+).*?--crate-type (\S+)', o); print('  $ cargo build -v 里的 rustc 调用(crate 名与类型):', names); R['crates'] = names
print('  目录:', tree(d)); rc, o = cargo(['run', '-q'], d); print('  $ cargo run -q →', o)
print()
print('== 二:workspace:根 Cargo.toml 只有 [workspace],成员各有自己的 Cargo.toml;共用一个 Cargo.lock 与一个 target')
shutil.rmtree(RS / 'proj' / 'ws', ignore_errors=True)
root = RS / 'proj' / 'ws'; (root / 'app' / 'src').mkdir(parents=True); (root / 'core' / 'src').mkdir(parents=True)
(root / 'Cargo.toml').write_text('[workspace]\nmembers = ["app", "core"]\nresolver = "3"\n')
(root / 'core' / 'Cargo.toml').write_text('[package]\nname = "core_lib"\nversion = "0.1.0"\nedition = "2024"\n')
(root / 'core' / 'src' / 'lib.rs').write_text('pub fn answer() -> u32 { 42 }\n')
(root / 'app' / 'Cargo.toml').write_text('[package]\nname = "app"\nversion = "0.1.0"\nedition = "2024"\n\n[dependencies]\ncore_lib = { path = "../core" }\n')
(root / 'app' / 'src' / 'main.rs').write_text('fn main() { println!("answer = {}", core_lib::answer()); }\n')
print('  根 Cargo.toml:', (root / 'Cargo.toml').read_text().replace('\n', ' ⏎ ')); print('  app/Cargo.toml 的依赖:', 'core_lib = { path = "../core" }')
shutil.rmtree(TG, ignore_errors=True); rc, o = cargo(['build'], root); print('  $ cargo build(在 workspace 根):'); print('\n'.join('    ' + l for l in o.splitlines()))
print('  目录(不含 target):', tree(root)); print('  只有根目录有 Cargo.lock:', (root / 'Cargo.lock').exists(), '| app/Cargo.lock 存在:', (root / 'app' / 'Cargo.lock').exists())
env2 = {k: v for k, v in ENVB.items() if k != 'CARGO_TARGET_DIR'}; rc, o = cargo(['build'], root / 'app', env=env2)
print('  不设 CARGO_TARGET_DIR、在 app/ 子目录里 cargo build 之后:ws/target 存在 =', (root / 'target').exists(), '| ws/app/target 存在 =', (root / 'app' / 'target').exists(), '(target 在 workspace 根)'); R['target_root'] = (root / 'target').exists() and not (root / 'app' / 'target').exists()
print()
print('== 三:在成员目录里 cargo 命令仍然作用于整个 workspace;-p 指定成员;cargo tree 看依赖')
rc, o = cargo(['run', '-q', '-p', 'app'], root); print('  $ cargo run -q -p app →', o)
rc, o = cargo(['run', '-q'], root / 'app'); print('  $ (cd app && cargo run -q) →', o)
rc, o = cargo(['tree'], root); print('  $ cargo tree'); print('\n'.join('    ' + l for l in o.splitlines()))
rc, o = cargo(['metadata', '--format-version=1', '--no-deps'], root)
try:
    md = J_.loads(o[o.index('{'):]); print('  cargo metadata:workspace_members 共', len(md['workspace_members']), '个;packages =', [p['name'] for p in md['packages']], '| workspace_root =', md['workspace_root'].replace(str(RS), '<实验目录>')); R['members'] = [p['name'] for p in md['packages']]
except Exception as e: print('  metadata 解析失败', e)
print()
print('== 四:包名与 crate 名:包名里的连字符在代码里变成下划线')
d3 = proj('my-pkg', {'src/lib.rs': 'pub fn f() -> u8 { 1 }\n'}); rc, o = cargo(['build', '-v'], d3); print('  包名 my-pkg → rustc 的 --crate-name:', re.findall(r'--crate-name (\S+)', o))
d4 = proj('use-hyphen', {'src/main.rs': 'fn main() { println!("{}", my-pkg::f()); }\n'}, deps='my-pkg = { path = "../my-pkg" }')
(d4 / 'src' / 'main.rs').write_text('fn main() { println!("{}", my_pkg::f()); }\n'); rc, o = cargo(['run', '-q'], d4); print('  依赖里写 my-pkg,代码里用 my_pkg::f() →', o); R['hyphen'] = o
save('u15', R)
