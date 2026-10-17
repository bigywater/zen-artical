from lib import *
S = SS('u79')
R = J('u79'); n1, n2, n3 = R['runs']
steps = [
    step("三种过程宏放在一个 proc-macro crate(Cargo.toml 里 [lib] proc-macro = true),不依赖 syn / quote,只用标准库的 proc_macro。使用者 app 里写 make_answer!(a b 3)、#[derive(Hello)] struct Point;、#[trace(level = 2)] fn compute(...)。", t=tl(S(1)), done=lidx(S(1), 'mac/src/lib.rs'), kv=KV([['函数式宏', 'make_answer!(…)'], ['derive 宏', '#[derive(Hello)]'], ['属性宏', '#[trace(…)]']], ['函数式宏'])),
    step("cargo build app 的输出里出现三行「[编译期]」:函数式宏拿到的输入 tokens 是 \"a b 3\";derive(Hello) 拿到整个条目 \"struct Point;\";#[trace] 同时拿到属性参数 \"level = 2\" 和被修饰的函数全文。这些 eprintln 是在编译 app 的过程中由编译器执行的。", t=tl(S(1)), mark=lidx(S(1), '[编译期]'), kv=KV([['函数式宏的输入', '括号里的 tokens'], ['derive 的输入', '整个 struct'], ['属性宏的输入', '参数 + 条目']], ['derive 的输入'])),
    step("运行 app 时只剩「[运行期]」输出:main 开始、进入 compute(#[trace] 生成的代码在函数体开头插入的 println!)、Hello from Point / 43(derive 生成的 impl 与 make_answer! 生成的 answer())。运行期没有任何宏在执行 —— 宏的产物是编译后的普通代码。", t=tl(S(1)), done=lidx(S(1), '[运行期]', 'Hello from Point'), kv=KV([['编译期', '宏运行,产出代码'], ['运行期', '只有生成的代码']], ['运行期'])),
    step(f"宏运行几次?让宏每次运行都往日志文件追加一行:第一次 build 后日志 {n1} 行;没有改动的第二次 build 日志仍是 {n2} 行(宏没有再运行,cargo 只是重放了上次缓存的编译器输出,所以屏幕上还能看到「[编译期]」行);改了 main.rs 里的一个字符串后再 build,日志变成 {n3} 行,三个宏全部重新运行(使用宏的整个 crate 重新编译)。", t=tl(S(2)), done=lidx(S(2), '第一次 build', '第二次'), mark=lidx(S(2), '改了 main.rs'), b=bars([['第一次 build 后', n1, f'{n1} 行'], ['没改动再 build', n2, f'{n2} 行'], ['改了 main.rs 后', n3, f'{n3} 行']], n3 + 1, done=[0, 1], cur=[2]), kv=KV([['没改动', '宏不重新运行'], ['改了使用者', '三个宏都重新运行']], ['改了使用者'])),
    step("proc-macro crate 的产物是动态库(libmac-….dylib),由 rustc 在编译 app 时加载并调用。proc-macro crate 里不能导出普通函数:pub fn not_a_macro() {} 报 error: `proc-macro` crate types currently cannot export any items other than functions tagged with `#[proc_macro]`, `#[proc_macro_derive]`, or `#[proc_macro_attribute]`。", t=tl(S(3)), mark=lidx(S(3), 'error:'), done=lidx(S(3), 'dylib'), kv=KV([['产物', 'dylib,由 rustc 加载'], ['导出限制', '只能导出宏函数']], ['导出限制'])),
]
A = mkart('u79', 79, 'Rust,过程宏,proc-macro,编译期,真实验证,动画演示',
    f'用一个真实的 proc-macro crate(不依赖 syn)验证过程宏的执行阶段:函数式宏、derive、属性宏的输入 tokens 各是什么;eprintln 只出现在 cargo build 时,运行 app 时没有宏在执行;宏运行次数日志 {n1} → {n2}(没改动)→ {n3}(改了使用者);proc-macro crate 只能导出宏函数。',
    '过程宏到底在什么时候运行?它收到什么输入?改了代码之后会不会重新运行?这篇自己写一个最小的 proc-macro crate,在宏里打印和记日志,把三种过程宏的阶段全部量出来。',
    [('编译期', '过程宏运行的阶段:cargo build 时,不是 app 运行时'), ('3 → 3 → 6', '宏运行日志行数:首次 build、没改动 build、改了使用者之后'), ('dylib', 'proc-macro crate 的产物类型')],
    [('三种过程宏与它们运行的阶段', '<p>声明宏见<a href="rust-macro-rules.html">声明宏 macro_rules!</a>;derive 展开见<a href="rust-derive-macro-codegen.html">Derive 宏如何生成代码</a>。</p>'), ('宏运行几次', None), ('proc-macro crate 的限制', None)],
    steps, [ENV_U + '。只用 proc_macro 标准库,不依赖 syn/quote;宏运行次数用写日志文件的方式统计', '没有验证:syn/quote 的解析与代码生成(在后面的 derive 一篇里用)、rust-analyzer 对过程宏的重复展开、cargo check 与 cargo build 对宏运行次数的影响、交叉编译时宏运行在哪个平台、proc-macro 的 Span 信息'], '过程宏的阶段')
