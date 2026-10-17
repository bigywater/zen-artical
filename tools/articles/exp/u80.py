import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u80'); R = {}
base = RS / 'proj' / 'u80'; shutil.rmtree(base, ignore_errors=True)
(base / 'derive_fields' / 'src').mkdir(parents=True); (base / 'app' / 'src').mkdir(parents=True)
(base / 'derive_fields' / 'Cargo.toml').write_text('[package]\nname = "derive_fields"\nversion = "0.1.0"\nedition = "2024"\n[lib]\nproc-macro = true\n[dependencies]\nsyn = { version = "2", features = ["full"] }\nquote = "1"\nproc-macro2 = "1"\n')
LIB = textwrap.dedent('''
    use proc_macro::TokenStream;
    use quote::quote;
    use syn::{parse_macro_input, Data, DeriveInput, Fields};

    #[proc_macro_derive(FieldNames)]
    pub fn field_names(input: TokenStream) -> TokenStream {
        let ast = parse_macro_input!(input as DeriveInput);
        let name = &ast.ident;
        let (impl_g, ty_g, where_c) = ast.generics.split_for_impl();
        let fields = match &ast.data {
            Data::Struct(s) => match &s.fields {
                Fields::Named(f) => f.named.iter().map(|f| f.ident.as_ref().unwrap().to_string()).collect::<Vec<_>>(),
                _ => return syn::Error::new_spanned(&ast.ident, "FieldNames 只支持有命名字段的 struct").to_compile_error().into(),
            },
            _ => return syn::Error::new_spanned(&ast.ident, "FieldNames 只能用于 struct").to_compile_error().into(),
        };
        let n = fields.len();
        quote! {
            impl #impl_g #name #ty_g #where_c {
                pub const FIELD_COUNT: usize = #n;
                pub fn field_names() -> [&'static str; #n] { [#(#fields),*] }
            }
        }.into()
    }
''')
(base / 'derive_fields' / 'src' / 'lib.rs').write_text(LIB)
(base / 'app' / 'Cargo.toml').write_text('[package]\nname = "app"\nversion = "0.1.0"\nedition = "2024"\n[dependencies]\nderive_fields = { path = "../derive_fields" }\n')
MAIN = textwrap.dedent('''
    use derive_fields::FieldNames;
    #[derive(FieldNames)] struct User { id: u32, name: String, active: bool }
    #[derive(FieldNames)] struct Wrapper<T: Clone> where T: Default { inner: T, tag: &'static str }
    fn main() {
        println!("User: {} 个字段 {:?}", User::FIELD_COUNT, User::field_names());
        println!("Wrapper<i32>: {} 个字段 {:?}", Wrapper::<i32>::FIELD_COUNT, Wrapper::<i32>::field_names());
        let _ = (User { id: 1, name: String::new(), active: true }, Wrapper { inner: 0, tag: "t" });
    }
''')
(base / 'app' / 'src' / 'main.rs').write_text(MAIN)
print('== 一:用 syn + quote 写一个 derive:为 struct 生成「字段名列表」(syn 2 + quote 1,真实下载编译)')
print('  derive 宏的实现(derive_fields/src/lib.rs):'); print('\n'.join('    ' + l for l in LIB.strip().splitlines()))
t0 = time.perf_counter(); rc, o = cargo(['build'], base / 'app', timeout=900); t_build = time.perf_counter() - t0
print(f'  cargo build(含下载编译 syn/quote/proc-macro2)用时 {t_build:.1f} s,退出码 {rc}')
rc, o, e, _ = run(TG / 'debug' / 'app'); print('  运行 app:'); print('\n'.join('    ' + l for l in o.splitlines())); R['run'] = o.splitlines(); R['t_build'] = round(t_build, 1)
print()
print('== 二:编译器展开后的真实代码(-Z unpretty=expanded)')
rc, o2 = cargo(['rustc', '--quiet', '--', '-Z', 'unpretty=expanded'], base / 'app', env=dict(ENVB, RUSTC_BOOTSTRAP='1'), timeout=900)
L = o2.splitlines(); keep = []; on = False
for l in L:
    if l.startswith('impl') and ('User' in l or 'Wrapper' in l): on = True
    if on: keep.append(l)
    if on and l == '}': on = False
print('\n'.join('  ' + l for l in keep)); R['expanded'] = keep
print()
print('== 三:用错了位置:自定义的 compile_error 指向出错的 span(用在 enum 与元组 struct 上)')
(base / 'app' / 'src' / 'main.rs').write_text(textwrap.dedent('''
    use derive_fields::FieldNames;
    #[derive(FieldNames)] enum Color { Red, Green }
    #[derive(FieldNames)] struct Pair(i32, i32);
    fn main() {}
'''))
rc, o = cargo(['build'], base / 'app', timeout=600); print('\n'.join('  ' + l for l in o.splitlines() if l.strip() and not l.strip().startswith('Compiling'))); R['err'] = [l for l in o.splitlines() if l.strip() and not l.strip().startswith('Compiling')]
print()
print('== 四:每个 derive 都有解析成本:同一个宏在 2000 个 struct 上展开的编译时间(只比较「有这个 derive」与「没有」)')
def gen(n, derive):
    return 'use derive_fields::FieldNames;\n' + ''.join(f'{"#[derive(FieldNames)] " if derive else ""}pub struct S{i} {{ a: u32, b: String, c: bool, d: Vec<u8> }}\n' for i in range(n)) + 'fn main() {}\n'
res = {}
for derive in (False, True):
    (base / 'app' / 'src' / 'main.rs').write_text(gen(2000, derive))
    ts = []
    for _ in range(3):
        shutil.rmtree(TG / 'debug' / 'incremental', ignore_errors=True)
        (base / 'app' / 'src' / 'main.rs').write_text(gen(2000, derive) + f'// {time.time()}\n')
        t0 = time.perf_counter(); rc, o = cargo(['build'], base / 'app', timeout=900); ts.append(time.perf_counter() - t0)
    res[derive] = min(ts); print(f'  {"有" if derive else "无"} derive:2000 个 struct,cargo build(只重编 app)最快 {min(ts):.2f} s')
R['cost'] = {str(k): round(v, 2) for k, v in res.items()}
save('u80', R)
