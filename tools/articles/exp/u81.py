import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u81'); R = {}
base = RS / 'proj' / 'u81'; shutil.rmtree(base, ignore_errors=True)
(base / 'attrs' / 'src').mkdir(parents=True); (base / 'app' / 'src').mkdir(parents=True)
(base / 'attrs' / 'Cargo.toml').write_text('[package]\nname = "attrs"\nversion = "0.1.0"\nedition = "2024"\n[lib]\nproc-macro = true\n[dependencies]\nsyn = { version = "2", features = ["full"] }\nquote = "1"\nproc-macro2 = "1"\n')
LIB = textwrap.dedent('''
    use proc_macro::TokenStream;
    use quote::quote;
    use syn::{parse_macro_input, ItemFn, LitStr, Token, parse::Parse, parse::ParseStream};

    #[proc_macro_attribute]
    pub fn timed(_attr: TokenStream, item: TokenStream) -> TokenStream {
        let f = parse_macro_input!(item as ItemFn);
        let (vis, sig, block, attrs) = (&f.vis, &f.sig, &f.block, &f.attrs);
        let name = sig.ident.to_string();
        quote! {
            #(#attrs)* #vis #sig {
                let __t = std::time::Instant::now();
                let __r = (|| #block)();
                println!("[timed] {} 返回了(耗时数量级 {})", #name, if __t.elapsed().as_millis() >= 1 { "毫秒" } else { "微秒以内" });
                __r
            }
        }.into()
    }

    struct RouteArgs { method: LitStr, path: LitStr }
    impl Parse for RouteArgs { fn parse(i: ParseStream) -> syn::Result<Self> { let method = i.parse()?; i.parse::<Token![,]>()?; let path = i.parse()?; Ok(RouteArgs { method, path }) } }

    #[proc_macro_attribute]
    pub fn route(attr: TokenStream, item: TokenStream) -> TokenStream {
        let args = parse_macro_input!(attr as RouteArgs);
        let f = parse_macro_input!(item as ItemFn);
        let (m, p, name) = (args.method.value(), args.path.value(), &f.sig.ident);
        let info = syn::Ident::new(&format!("ROUTE_{}", name.to_string().to_uppercase()), name.span());
        quote! {
            #f
            pub const #info: (&str, &str, &str) = (#m, #p, stringify!(#name));
        }.into()
    }

    #[proc_macro_attribute]
    pub fn vanish(_attr: TokenStream, _item: TokenStream) -> TokenStream { TokenStream::new() }
''')
(base / 'attrs' / 'src' / 'lib.rs').write_text(LIB)
(base / 'app' / 'Cargo.toml').write_text('[package]\nname = "app"\nversion = "0.1.0"\nedition = "2024"\n[dependencies]\nattrs = { path = "../attrs" }\n')
def app(code): (base / 'app' / 'src' / 'main.rs').write_text(textwrap.dedent(code))
print('== 一:#[timed] 在函数外包一层:原函数体被包进闭包,返回值原样返回')
app('''
    use attrs::timed;
    #[timed] fn add(a: i32, b: i32) -> i32 { a + b }
    #[timed] pub fn slow() -> &'static str { std::thread::sleep(std::time::Duration::from_millis(5)); "done" }
    fn main() { println!("add = {}", add(2, 3)); println!("slow = {}", slow()); }
''')
rc, o = cargo(['build'], base / 'app', timeout=900); print('  编译退出码', rc, [l for l in o.splitlines() if 'error' in l][:3])
rc, o, e, _ = run(TG / 'debug' / 'app'); print('  运行:'); print('\n'.join('    ' + l for l in o.splitlines())); R['timed'] = o.splitlines()
rc, o2 = cargo(['rustc', '--quiet', '--', '-Z', 'unpretty=expanded'], base / 'app', env=dict(ENVB, RUSTC_BOOTSTRAP='1'), timeout=900)
L = o2.splitlines(); i = [k for k, l in enumerate(L) if l.startswith('fn add')][0]
print('  展开后的 add:'); print('\n'.join('    ' + l for l in L[i:i + 12])); R['timed_exp'] = L[i:i + 12]
print()
print('== 二:带参数的属性宏 #[route("GET", "/users")]:参数用自定义 Parse 解析,原函数原样保留并额外生成一个常量')
app('''
    use attrs::route;
    #[route("GET", "/users")] fn list_users() -> &'static str { "users" }
    #[route("POST", "/users")] fn create_user() -> &'static str { "created" }
    fn main() {
        println!("{:?}", ROUTE_LIST_USERS);
        println!("{:?}", ROUTE_CREATE_USER);
        println!("原函数仍可调用: {} / {}", list_users(), create_user());
    }
''')
rc, o = cargo(['build'], base / 'app', timeout=900); print('  编译退出码', rc)
rc, o, e, _ = run(TG / 'debug' / 'app'); print('  运行:'); print('\n'.join('    ' + l for l in o.splitlines())); R['route'] = o.splitlines()
print()
print('== 三:参数写错了:syn 的解析错误指向参数的位置')
app('''
    use attrs::route;
    #[route("GET")] fn a() {}
    #[route(GET, "/x")] fn b() {}
    fn main() {}
''')
rc, o = cargo(['build'], base / 'app', timeout=900); el = [l for l in o.splitlines() if l.strip() and not l.strip().startswith('Compiling')]
print('\n'.join('  ' + l for l in el)); R['e_args'] = el
print()
print('== 四:属性宏的返回值会整个替换被修饰的条目:返回空 token,函数就消失了')
app('''
    use attrs::vanish;
    #[vanish] fn gone() -> i32 { 1 }
    fn main() { println!("{}", gone()); }
''')
rc, o = cargo(['build'], base / 'app', timeout=900); el = [l for l in o.splitlines() if l.strip() and not l.strip().startswith('Compiling')][:6]
print('\n'.join('  ' + l for l in el)); R['vanish'] = el
print()
print('== 五:属性宏可以用在 struct 上吗?#[timed] 放在 struct 上会被 ItemFn 解析拒绝')
app('''
    use attrs::timed;
    #[timed] struct NotFn;
    fn main() {}
''')
rc, o = cargo(['build'], base / 'app', timeout=900); el = [l for l in o.splitlines() if l.strip() and not l.strip().startswith('Compiling')][:6]
print('\n'.join('  ' + l for l in el)); R['struct'] = el
save('u81', R)
