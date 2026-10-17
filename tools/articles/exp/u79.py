import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u79'); R = {}
print('== 一:三种过程宏放在一个 proc-macro crate 里,用 eprintln 标出「宏在什么时候运行」(不依赖 syn / quote)')
base = RS / 'proj' / 'u79'; shutil.rmtree(base, ignore_errors=True)
(base / 'mac' / 'src').mkdir(parents=True); (base / 'app' / 'src').mkdir(parents=True)
(base / 'mac' / 'Cargo.toml').write_text('[package]\nname = "mac"\nversion = "0.1.0"\nedition = "2024"\n[lib]\nproc-macro = true\n')
(base / 'mac' / 'src' / 'lib.rs').write_text(textwrap.dedent('''
    use proc_macro::TokenStream;
    fn log(name: &str) { use std::io::Write; let p = std::path::Path::new(&std::env::var("CARGO_MANIFEST_DIR").unwrap()).join("../macro_runs.log"); writeln!(std::fs::OpenOptions::new().create(true).append(true).open(p).unwrap(), "{}", name).unwrap(); }
    #[proc_macro]
    pub fn make_answer(input: TokenStream) -> TokenStream {
        eprintln!("[编译期] 函数式宏 make_answer! 运行了,输入 tokens = {:?}", input.to_string());
        log("make_answer");
        "fn answer() -> i32 { 42 }".parse().unwrap()
    }
    #[proc_macro_derive(Hello)]
    pub fn derive_hello(input: TokenStream) -> TokenStream {
        let s = input.to_string();
        eprintln!("[编译期] derive(Hello) 运行了,输入 = {:?}", s);
        log("derive_hello");
        let name = s.split_whitespace().skip_while(|t| *t != "struct").nth(1).unwrap().trim_end_matches(|c| c == ';' || c == '{').to_string();
        format!("impl {} {{ fn hello() -> &'static str {{ \\"Hello from {}\\" }} }}", name, name).parse().unwrap()
    }
    #[proc_macro_attribute]
    pub fn trace(attr: TokenStream, item: TokenStream) -> TokenStream {
        eprintln!("[编译期] #[trace] 运行了,属性参数 = {:?},被修饰的条目 = {:?}", attr.to_string(), item.to_string());
        log("trace");
        let s = item.to_string();
        let name = s.split_whitespace().skip_while(|t| *t != "fn").nth(1).unwrap().split('(').next().unwrap().to_string();
        let body_start = s.find('{').unwrap();
        format!("{} {{ println!(\\"[运行期] 进入 {}\\"); {} }}", &s[..body_start], name, &s[body_start + 1..s.rfind('}').unwrap()]).parse().unwrap()
    }
'''))
(base / 'app' / 'Cargo.toml').write_text('[package]\nname = "app"\nversion = "0.1.0"\nedition = "2024"\n[dependencies]\nmac = { path = "../mac" }\n')
(base / 'app' / 'src' / 'main.rs').write_text(textwrap.dedent('''
    use mac::{make_answer, trace, Hello};
    make_answer!(a b 3);
    #[derive(Hello)] struct Point;
    #[trace(level = 2)] fn compute(x: i32) -> i32 { x + answer() }
    fn main() { println!("[运行期] main 开始"); println!("{} / {}", Point::hello(), compute(1)); }
'''))
print('  mac/src/lib.rs(proc-macro crate)与 app/src/main.rs(使用者)已创建;crate 类型 proc-macro')
rc, o = cargo(['build'], base / 'app', timeout=600)
lines = [l for l in o.splitlines() if l.strip() and not l.strip().startswith(('Compiling', 'Finished'))]
print('  cargo build app 的输出(宏的 eprintln 出现在编译期):'); print('\n'.join('    ' + l for l in lines)); R['build'] = lines
rc, o, e, _ = run(TG / 'debug' / 'app'); print('  运行 app 的输出:'); print('\n'.join('    ' + l for l in o.splitlines())); R['run'] = o.splitlines()
print()
print('== 二:宏到底运行了几次?宏每次运行都往日志文件追加一行;连续 build 三次(第二次没改动,第三次改了使用者的一个字符串)')
logf = base / 'macro_runs.log'
def runs(): return len(logf.read_text().splitlines()) if logf.exists() else 0
n1 = runs(); print(f'  第一次 build 之后日志共 {n1} 行(3 个宏各运行 1 次)')
rc, o = cargo(['build'], base / 'app'); n2 = runs()
print(f'  第二次 cargo build(没改动):日志仍是 {n2} 行 —— 宏没有再运行;但 cargo 输出里仍能看到 [编译期] 行吗?', any('[编译期]' in l for l in o.splitlines()), '(cargo 会重放上次缓存的编译器输出)')
(base / 'app' / 'src' / 'main.rs').write_text((base / 'app' / 'src' / 'main.rs').read_text().replace('[运行期] main 开始', '[运行期] main 开始了'))
rc, o = cargo(['build'], base / 'app'); n3 = runs()
print(f'  改了 main.rs 的一个字符串后再 build:日志 {n3} 行(新增 {n3 - n2} 行:三个宏全部重新运行,因为使用它们的 crate 整个重新编译)')
R['runs'] = [n1, n2, n3]
print()
print('== 三:宏运行的时间点:先编译 proc-macro crate 得到动态库,再由 rustc 加载它来编译 app;proc-macro crate 里不能导出普通函数')
rc, o = cargo(['build', '-v'], base / 'app'); print('  proc-macro crate 的产物:'); 
dylib = sorted((TG / 'debug' / 'deps').glob('libmac-*.dylib')); print('   ', [p.name for p in dylib][:2], '(动态库,由 rustc 在编译 app 时加载)'); R['dylib'] = [p.name for p in dylib][:2]
(base / 'mac' / 'src' / 'lib.rs').write_text((base / 'mac' / 'src' / 'lib.rs').read_text() + '\npub fn not_a_macro() {}\n')
rc, o = cargo(['build'], base / 'app'); l = [x for x in o.splitlines() if x.strip()][:6]
print('  在 proc-macro crate 里 pub fn 一个普通函数:'); print('\n'.join('    ' + x for x in l)); R['e_export'] = l
save('u79', R)
