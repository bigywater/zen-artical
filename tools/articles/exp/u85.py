import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u85'); R = {}
base = RS / 'proj' / 'u85'; shutil.rmtree(base, ignore_errors=True); (base / 'src').mkdir(parents=True)
(base / 'Cargo.toml').write_text('[package]\nname = "app"\nversion = "0.3.1"\nedition = "2024"\nbuild = "build.rs"\n')
(base / 'data.txt').write_text('alpha\n')
(base / 'build.rs').write_text(textwrap.dedent('''
    use std::{env, fs, path::Path};
    fn main() {
        println!("cargo:rerun-if-changed=data.txt");
        println!("cargo:rerun-if-changed=build.rs");
        let out = env::var("OUT_DIR").unwrap();
        let text = fs::read_to_string("data.txt").unwrap();
        let n = text.lines().count();
        fs::write(Path::new(&out).join("gen.rs"), format!("pub const LINES: usize = {};\\npub const FIRST: &str = {:?};\\n", n, text.lines().next().unwrap_or(""))).unwrap();
        println!("cargo:rustc-env=BUILT_BY=build.rs-{}", env::var("CARGO_PKG_VERSION").unwrap());
        println!("cargo:rustc-cfg=has_data");
        println!("cargo:warning=build.rs 运行了:读到 {} 行", n);
        { use std::io::Write; let log = Path::new(&env::var("CARGO_MANIFEST_DIR").unwrap()).join("../u85_runs.log"); writeln!(fs::OpenOptions::new().create(true).append(true).open(log).unwrap(), "run").unwrap(); }
    }
'''))
(base / 'src' / 'main.rs').write_text(textwrap.dedent('''
    include!(concat!(env!("OUT_DIR"), "/gen.rs"));
    fn main() {
        println!("LINES = {}  FIRST = {:?}", LINES, FIRST);
        println!("BUILT_BY = {}", env!("BUILT_BY"));
        #[cfg(has_data)] println!("cfg(has_data) 为真");
        #[cfg(not(has_data))] println!("cfg(has_data) 为假");
    }
'''))
print('== 一:build.rs 在编译 app 之前运行:生成代码到 OUT_DIR、设置 env 与 cfg、打印 warning')
rc, o = cargo(['build'], base, timeout=600)
keep = [l for l in o.splitlines() if l.strip() and (l.lstrip().startswith(('Compiling', 'Finished', 'warning:')) or 'rustc-check-cfg' in l)]
print('  cargo build 输出(只保留关键行):'); print('\n'.join('    ' + l.strip() for l in keep)); R['b1'] = [l.strip() for l in keep]
rc, o, e, _ = run(TG / 'debug' / 'app'); print('  运行 app:'); print('\n'.join('    ' + l for l in o.splitlines())); R['run1'] = o.splitlines()
od = sorted((TG / 'debug' / 'build').glob('app-*/out/gen.rs')); print('  OUT_DIR 里生成的 gen.rs 内容:'); print('\n'.join('    ' + l for l in od[0].read_text().splitlines())); R['gen'] = od[0].read_text().splitlines()
print()
logf = base.parent / 'u85_runs.log'
def runs(): return len(logf.read_text().splitlines()) if logf.exists() else 0
print('== 二:rerun-if-changed:build.rs 每次运行都往日志追加一行,统计它运行了几次')
n1 = runs(); rc, o = cargo(['build'], base); n2 = runs()
(base / 'data.txt').write_text('alpha\nbeta\ngamma\n'); rc, o = cargo(['build'], base); n3 = runs()
rc, o, e, _ = run(TG / 'debug' / 'app'); first = o.splitlines()[0]
(base / 'src' / 'main.rs').write_text((base / 'src' / 'main.rs').read_text() + '\n'); rc, o = cargo(['build'], base); n4 = runs()
print(f'  第一次 build 之后:{n1} 次;没改动再 build:{n2} 次;改了 data.txt 之后 build:{n3} 次(运行 app:{first});只改 main.rs 之后 build:{n4} 次')
R['runs'] = [n1, n2, n3, n4]; R['run3'] = first
print()
print('== 三:去掉 rerun-if-changed:默认只要包内文件变了就重新运行 build.rs')
src = (base / 'build.rs').read_text().replace('println!("cargo:rerun-if-changed=data.txt");', '').replace('println!("cargo:rerun-if-changed=build.rs");', '')
(base / 'build.rs').write_text(src); rc, o = cargo(['build'], base); m1 = runs()
(base / 'src' / 'main.rs').write_text((base / 'src' / 'main.rs').read_text() + '\n'); rc, o = cargo(['build'], base); m2 = runs()
print(f'  去掉 rerun-if-changed 并 build 一次后累计 {m1} 次;只改 main.rs 再 build:累计 {m2} 次(新增 {m2 - m1})')
R['norerun'] = [m1, m2]
print()
print('== 四:build.rs 里 panic 或 exit 非零,整个构建失败;cargo:warning 不会中断')
(base / 'build.rs').write_text('fn main() { panic!("build.rs 故意失败"); }\n'); rc, o = cargo(['build'], base)
print('  退出码', rc); print('\n'.join('    ' + l for l in o.splitlines() if l.strip() and 'Compiling' not in l)[:700]); R['fail'] = [l for l in o.splitlines() if l.strip() and 'Compiling' not in l][:8]
print()
print('== 五:build.rs 能看到的环境变量(只列几个)与它运行时所在目录')
(base / 'build.rs').write_text(textwrap.dedent('''
    fn main() {
        for k in ["CARGO_PKG_NAME", "CARGO_PKG_VERSION", "TARGET", "HOST", "PROFILE", "OPT_LEVEL", "CARGO_MANIFEST_DIR"] { println!("cargo:warning={}={}", k, std::env::var(k).unwrap_or("(无)".into())); }
        println!("cargo:warning=cwd 是 manifest 目录: {}", std::env::current_dir().unwrap() == std::path::Path::new(&std::env::var("CARGO_MANIFEST_DIR").unwrap()));
        println!("cargo:rustc-env=BUILT_BY=x"); println!("cargo:rustc-env=_u=1");
        std::fs::write(std::path::Path::new(&std::env::var("OUT_DIR").unwrap()).join("gen.rs"), "pub const LINES: usize = 0; pub const FIRST: &str = \\"\\";").unwrap();
    }
'''))
rc, o = cargo(['build'], base); l = [x.strip() for x in o.splitlines() if 'warning: app@' in x or 'cwd' in x]
print('\n'.join('  ' + x.replace(str(RS), '<实验目录>') for x in l)); R['env'] = l
save('u85', R)
