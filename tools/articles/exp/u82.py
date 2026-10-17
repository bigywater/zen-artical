import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u82'); R = {}
base = RS / 'proj' / 'u82'; shutil.rmtree(base, ignore_errors=True)
(base / 'fm' / 'src').mkdir(parents=True); (base / 'app' / 'src').mkdir(parents=True)
(base / 'fm' / 'Cargo.toml').write_text('[package]\nname = "fm"\nversion = "0.1.0"\nedition = "2024"\n[lib]\nproc-macro = true\n[dependencies]\nsyn = { version = "2", features = ["full"] }\nquote = "1"\nproc-macro2 = "1"\n')
LIB = textwrap.dedent('''
    use proc_macro::TokenStream;
    use quote::quote;
    use syn::{parse_macro_input, Expr, LitInt, LitStr, Token, parse::{Parse, ParseStream}, punctuated::Punctuated};

    #[proc_macro]
    pub fn fib(input: TokenStream) -> TokenStream {
        let n: LitInt = parse_macro_input!(input as LitInt);
        let n: u32 = match n.base10_parse() { Ok(v) => v, Err(e) => return e.to_compile_error().into() };
        let (mut a, mut b) = (0u64, 1u64);
        for _ in 0..n { let t = a + b; a = b; b = t; }
        quote!(#a).into()
    }

    struct Entry { k: Expr, v: Expr }
    impl Parse for Entry { fn parse(i: ParseStream) -> syn::Result<Self> { let k = i.parse()?; i.parse::<Token![=>]>()?; let v = i.parse()?; Ok(Entry { k, v }) } }
    struct Entries(Punctuated<Entry, Token![,]>);
    impl Parse for Entries { fn parse(i: ParseStream) -> syn::Result<Self> { Ok(Entries(Punctuated::parse_terminated(i)?)) } }

    #[proc_macro]
    pub fn hashmap(input: TokenStream) -> TokenStream {
        let Entries(es) = parse_macro_input!(input as Entries);
        let (ks, vs): (Vec<_>, Vec<_>) = es.iter().map(|e| (&e.k, &e.v)).unzip();
        quote!({ let mut m = ::std::collections::HashMap::new(); #( m.insert(#ks, #vs); )* m }).into()
    }

    #[proc_macro]
    pub fn embed(input: TokenStream) -> TokenStream {
        let p: LitStr = parse_macro_input!(input as LitStr);
        let full = std::path::Path::new(&std::env::var("CARGO_MANIFEST_DIR").unwrap()).join(p.value());
        match std::fs::read_to_string(&full) {
            Ok(s) => { let s = s.trim().to_string(); quote!(#s).into() }
            Err(e) => syn::Error::new(p.span(), format!("读取 {} 失败: {}", p.value(), e)).to_compile_error().into(),
        }
    }
''')
(base / 'fm' / 'src' / 'lib.rs').write_text(LIB)
(base / 'app' / 'Cargo.toml').write_text('[package]\nname = "app"\nversion = "0.1.0"\nedition = "2024"\n[dependencies]\nfm = { path = "../fm" }\n')
(base / 'app' / 'version.txt').write_text('1.0\n')
def app(code): (base / 'app' / 'src' / 'main.rs').write_text(textwrap.dedent(code))
print('== 一:fib!(30) 在编译期算出来,运行期只剩一个字面量')
app('''
    use fm::fib;
    fn main() { const F30: u64 = fib!(30); println!("fib!(30) = {}   fib!(10) = {}", F30, fib!(10)); }
''')
rc, o = cargo(['build'], base / 'app', timeout=900)
rc, o, e, _ = run(TG / 'debug' / 'app'); print('  运行:', o.strip()); R['fib'] = o.strip()
rc, o2 = cargo(['rustc', '--quiet', '--', '-Z', 'unpretty=expanded'], base / 'app', env=dict(ENVB, RUSTC_BOOTSTRAP='1'), timeout=900)
L = o2.splitlines(); i = [k for k, l in enumerate(L) if l.startswith('fn main')][0]
print('  展开后的 main:'); print('\n'.join('    ' + l for l in L[i:i + 8])); R['fib_exp'] = L[i:i + 8]
print()
print('== 二:hashmap!{ k => v, ... } 自定义语法(macro_rules 也能写,但这里用 syn 解析 =>)')
app('''
    use fm::hashmap;
    fn main() {
        let m = hashmap!{ "a" => 1, "b" => 2 + 3, "c" => 4, };
        let mut kv: Vec<_> = m.iter().collect(); kv.sort();
        println!("{:?}", kv);
        let e: std::collections::HashMap<&str, i32> = hashmap!{}; println!("空: {}", e.len());
    }
''')
rc, o = cargo(['build'], base / 'app', timeout=900); print('  编译退出码', rc)
rc, o, e, _ = run(TG / 'debug' / 'app'); print('  运行:'); print('\n'.join('    ' + l for l in o.splitlines())); R['hm'] = o.splitlines()
print()
print('== 三:embed!("version.txt") 在编译期读文件;改了文件而没改 Rust 代码时,cargo 不会重新编译(陈旧值)')
app('''
    use fm::embed;
    fn main() { println!("版本 = {:?}", embed!("version.txt")); }
''')
rc, o = cargo(['build'], base / 'app', timeout=900); rc, o1, e, _ = run(TG / 'debug' / 'app'); print('  build 后运行:', o1.strip())
(base / 'app' / 'version.txt').write_text('2.0\n')
rc, o = cargo(['build'], base / 'app', timeout=900); print('  把 version.txt 改成 2.0 后 cargo build 输出:', [l.strip() for l in o.splitlines() if l.strip()])
rc, o2_, e, _ = run(TG / 'debug' / 'app'); print('  运行:', o2_.strip(), '← 仍是旧值(宏没有重新运行)')
(base / 'app' / 'src' / 'main.rs').write_text((base / 'app' / 'src' / 'main.rs').read_text() + '\n')
rc, o = cargo(['build'], base / 'app', timeout=900); rc, o3, e, _ = run(TG / 'debug' / 'app'); print('  改动 main.rs(加一个换行)再 build 后运行:', o3.strip())
R['embed'] = [o1.strip(), o2_.strip(), o3.strip()]
print()
print('== 四:宏里失败要给出带位置的错误')
app('''
    use fm::{embed, fib};
    fn main() { let _ = embed!("不存在.txt"); let _ = fib!(99999999999); let _ = fib!("x"); }
''')
rc, o = cargo(['build'], base / 'app', timeout=900); el = [l for l in o.splitlines() if l.strip() and not l.strip().startswith('Compiling')]
print('\n'.join('  ' + l for l in el[:18])); R['err'] = el[:18]
save('u82', R)
print()
print('== 五:对照:标准库的 include_str! 会被 cargo 追踪吗?(同样的改文件实验)')
app('''
    fn main() { println!("include_str 版本 = {:?}", include_str!("../version.txt").trim()); }
''')
(base / 'app' / 'version.txt').write_text('3.0\n')
rc, o = cargo(['build'], base / 'app', timeout=900); rc, a1, e, _ = run(TG / 'debug' / 'app'); print('  build 后运行:', a1.strip())
(base / 'app' / 'version.txt').write_text('4.0\n')
rc, o = cargo(['build'], base / 'app', timeout=900); print('  改文件为 4.0 后 cargo build:', [l.strip() for l in o.splitlines() if l.strip()][:2])
rc, a2, e, _ = run(TG / 'debug' / 'app'); print('  运行:', a2.strip(), '← 新值,cargo 追踪了 include_str! 读的文件')
R['include'] = [a1.strip(), a2.strip()]
save('u82', R)
