import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u155'); R = {}
def flags_of(o, crate):
    for l in o.splitlines():
        if 'Running' in l and f'--crate-name {crate} ' in l:
            f = re.findall(r'-C (opt-level=\S+|debuginfo=\S+|debug-assertions=\S+|overflow-checks=\S+|incremental=\S*|codegen-units=\S+|panic=\S+|lto=\S+|strip=\S+|embed-bitcode=\S+)', l); return sorted(set(f))
    return None
MAIN = 'fn main() { println!("{}", itoa::Buffer::new().format(7u8)); }'
print('== 一:cargo -v 打印每个 profile 实际传给 rustc 的 -C 参数(dev / release / test)')
d = proj('u155', {'src/main.rs': MAIN + '\n#[cfg(test)] mod t { #[test] fn x() {} }'}, deps='itoa = "1"')
R['flags'] = {}
for label, args in [('dev', ['build']), ('release', ['build', '--release']), ('test(cargo test)', ['test', '--no-run'])]:
    shutil.rmtree(TG, ignore_errors=True) if False else None
    cargo(['clean'], d); rc, o = cargo(args + ['-v'], d, timeout=600); f = flags_of(o, 'u155'); print(f'  {label:<16} → {f}'); R['flags'][label] = f
print()
print('== 二:依赖单独调优:[profile.dev.package."*"] opt-level = 3 让所有依赖在 dev 里也优化,自己的代码保持 dev;对照 itoa 与 u155 各自的参数')
(d / 'Cargo.toml').write_text((d / 'Cargo.toml').read_text() + '\n[profile.dev.package."*"]\nopt-level = 3\n')
cargo(['clean'], d); rc, o = cargo(['build', '-v'], d, timeout=600); fi = flags_of(o, 'itoa'); fu = flags_of(o, 'u155'); print(f'  itoa(依赖)  → {fi}'); print(f'  u155(自己)  → {fu}'); R['pkg'] = [fi, fu]
print()
print('== 三:自定义 profile:[profile.fastdev] inherits = "dev" 再覆盖 opt-level;产物在 target/fastdev/;--profile 选择')
(d / 'Cargo.toml').write_text(re.sub(r'\n\[profile\.dev\.package\."\*"\]\nopt-level = 3\n', '\n', (d / 'Cargo.toml').read_text()) + '\n[profile.fastdev]\ninherits = "dev"\nopt-level = 2\ndebug = false\n')
cargo(['clean'], d); rc, o = cargo(['build', '--profile', 'fastdev', '-v'], d, timeout=600); f = flags_of(o, 'u155'); print(f'  fastdev → {f}'); R['custom'] = f
print(f'  产物目录:{sorted(p.name for p in TG.iterdir() if p.is_dir() and p.name in ("debug", "release", "fastdev"))}(target/fastdev 是单独的目录)'); R['dirs'] = sorted(p.name for p in TG.iterdir() if p.is_dir() and p.name in ('debug', 'release', 'fastdev'))
rc, o = cargo(['build', '--profile', 'nonexistent'], d, timeout=300); print('  不存在的 profile:', [l.strip() for l in o.splitlines() if 'error' in l][:1]); R['bad'] = [l.strip() for l in o.splitlines() if 'error' in l][:1]
print()
print('== 四:debug 信息的三档对二进制大小的影响:debug = 0 / "line-tables-only" / 2(release 优化,strip = false,同一程序):比较二进制本身与整个 target/release 目录的大小')
big = 'use std::collections::HashMap; fn main() { let mut m: HashMap<String, Vec<u32>> = HashMap::new(); for i in 0..100 { m.entry(format!("k{}", i % 7)).or_default().push(i); } let mut k: Vec<_> = m.iter().collect(); k.sort(); println!("{:?}", &k[..2]); }'
R['dbg'] = {}
for dbg in ('0', '"line-tables-only"', '2'):
    d2 = proj('u155d', {'src/main.rs': big}, toml_extra=f'[profile.release]\ndebug = {dbg}\nstrip = false'); shutil.rmtree(TG / 'release', ignore_errors=True); cargo(['build', '--release', '--quiet'], d2, timeout=600)
    b = TG / 'release' / 'u155d'; dsym = du(TG / 'release')
    print(f'  debug = {dbg:<20} 二进制 {b.stat().st_size:>9,} 字节   整个 target/release 目录 {dsym:>10,} 字节'); R['dbg'][dbg] = [b.stat().st_size, dsym]
print()
print('== 五:build-override:build.rs 与过程宏默认用 opt-level = 0 编译(与目标代码的优化级别分开):对比两者传给 rustc 的 -C 参数')
d3 = proj('u155b', {'src/main.rs': 'fn main() {}', 'build.rs': 'fn main() {}'}, toml_extra='[profile.release]\nopt-level = 3\n'); shutil.rmtree(TG / 'release', ignore_errors=True)
rc, o = cargo(['build', '--release', '-v'], d3, timeout=600); fb = None
for l in o.splitlines():
    if 'Running' in l and '--crate-name build_script_build' in l: fb = sorted(set(re.findall(r'-C (\S+)', l)))
fm = flags_of(o, 'u155b'); print(f'  build.rs(build_script_build)的 -C 参数 → {fb}(没有 opt-level=,即默认的 0)\n  目标代码 u155b → {fm}'); R['bo'] = [fb, fm]
save('u155', R)
