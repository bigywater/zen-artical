from lib import *
S = SS('u80')
R = J('u80'); tb = R['t_build']; c0, c1 = R['cost']['False'], R['cost']['True']; per = (c1 - c0) / 2000 * 1000
steps = [
    step("用 syn 2 + quote 1 写 derive:parse_macro_input!(input as DeriveInput) 把 token 流解析成语法树;取 ast.ident(类型名)、split_for_impl() 取泛型三件套(impl 泛型、类型泛型、where 子句);遍历命名字段得到字段名;用 quote! 拼出 impl,#name、#n、#(#fields),* 插值。", t=tl(S(1)), done=lidx(S(1), 'parse_macro_input', 'split_for_impl', 'quote!'), kv=KV([['syn', '解析为 DeriveInput'], ['quote!', '生成 token'], ['split_for_impl', '处理泛型']], ['split_for_impl'])),
    step(f"cargo build(包含下载并编译 syn、quote、proc-macro2)用时 {tb} s。运行 app:User 3 个字段 [\"id\",\"name\",\"active\"],泛型的 Wrapper<i32> 2 个字段 [\"inner\",\"tag\"]。", t=tl(S(1)), done=lidx(S(1), 'cargo build', 'User: 3', 'Wrapper<i32>'), kv=KV([['User', '3 个字段'], ['Wrapper<T>', '2 个字段,泛型正确']], ['Wrapper<T>'])),
    step("编译器展开后的真实代码(-Z unpretty=expanded):User 得到 impl User { pub const FIELD_COUNT: usize = 3usize; pub fn field_names() -> [&'static str; 3usize] { [\"id\", \"name\", \"active\"] } };Wrapper 得到 impl<T: Clone> Wrapper<T> where T: Default { … },泛型参数与 where 子句被原样带上。", t=tl(S(2)), done=lidx(S(2), 'impl User', 'impl<T: Clone>'), kv=KV([['User', 'impl User { … }'], ['Wrapper', 'impl<T: Clone> Wrapper<T> where T: Default']], ['Wrapper'])),
    step("用错位置时 syn::Error::new_spanned(...).to_compile_error() 产生的错误指向具体位置:用在 enum Color 上报 error: FieldNames 只能用于 struct(src/main.rs:3:28);用在元组 struct Pair 上报 error: FieldNames 只支持有命名字段的 struct(src/main.rs:4:30)。cargo 汇总 2 个错误。", t=tl(S(3)), mark=lidx(S(3), 'error:'), kv=KV([['enum', 'src/main.rs:3:28'], ['元组 struct', 'src/main.rs:4:30']], ['enum'])),
    step(f"derive 展开本身有成本:2000 个 struct,没有 derive 时只重编 app 最快 {c0} s,加上 #[derive(FieldNames)] 是 {c1} s,差 {c1 - c0:.2f} s,平均每次展开约 {per:.2f} ms(每组 3 次取最小,仅 app 重编,不含 syn 的编译)。", t=tl(S(4)), done=lidx(S(4), '2000'), b=bars([['无 derive', c0, f'{c0} s'], ['有 derive', c1, f'{c1} s']], c1 * 1.1, done=[0, 1]), kv=KV([['无 derive', f'{c0} s'], ['有 derive', f'{c1} s'], ['每次展开', f'约 {per:.2f} ms']], ['每次展开'])),
]
A = mkart('u80', 80, 'Rust,derive,过程宏,syn,quote,真实验证,动画演示',
    f'真实下载 syn 2 + quote 1 写一个 derive(FieldNames):解析 DeriveInput、用 split_for_impl 处理泛型、quote! 生成 impl;编译器展开的代码;syn::Error 指出错误位置(enum 与元组 struct);2000 个 struct 上有无 derive 的编译时间 {c0} s 对 {c1} s。',
    'derive 宏是怎么从 struct 定义生成 impl 的?泛型怎么处理?错误怎么指到用户代码的位置?展开本身要花多少时间?这篇真实写一个 derive 宏,把每一步都跑出来。',
    [('3', '本文的 derive 用到的三个 crate:syn、quote、proc-macro2'), (f'{per:.2f} ms', '每次 derive 展开的平均额外编译时间(2000 个 struct)'), ('2 条', 'new_spanned 给出的带位置的编译错误数')],
    [('用 syn 与 quote 写 derive', '<p>过程宏运行的阶段见<a href="rust-proc-macro-phases.html">过程宏的执行阶段</a>。syn 2.x、quote 1.x、proc-macro2 1.x 从 crates.io 下载(需要联网)。</p>'), ('展开后的代码', '<p>标准库 derive(Clone、PartialEq 等)的展开见<a href="rust-derive-traits.html">derive 自动生成 Trait 实现</a>。</p>'), ('出错的位置', None), ('展开的成本', '<p>编译时间是本机测的小样本,受缓存和机器影响。</p>')],
    steps, [ENV_U + '。crates:syn 2、quote 1、proc-macro2 1(cargo 通过代理下载的当前版本)', '没有验证:带属性的 derive(#[field(...)])、枚举的 derive、syn 的 full 特性对编译时间的影响、过程宏的运行时间(只测了 app 重编的总时间)、cargo expand(未安装)'], 'derive 宏')
