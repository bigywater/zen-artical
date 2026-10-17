from lib import *
S = SS('u82')
steps = [
    step("函数式过程宏 fib!(30):宏在编译期用 Rust 代码算出斐波那契数,输出一个字面量。编译器展开后 main 里是 const F30: u64 = 832040u64; 以及 55u64,运行期没有任何计算。运行输出 fib!(30) = 832040   fib!(10) = 55。", t=tl(S(1)), done=lidx(S(1), '运行', 'const F30', '55u64'), kv=KV([['fib!(30)', '展开成 832040u64'], ['运行期', '没有计算']], ['fib!(30)'])),
    step("自定义语法:hashmap!{ \"a\" => 1, \"b\" => 2 + 3, \"c\" => 4, } 用 syn 的 Parse 解析 `键 => 值` 并允许结尾逗号,生成一串 insert。排序后得到 [(\"a\",1), (\"b\",5), (\"c\",4)];空的 hashmap!{} 得到长度 0。", t=tl(S(2)), done=lidx(S(2), '("a", 1)', '空: 0'), kv=KV([['输入', '键 => 值, …'], ['输出', '块 + HashMap::insert']], ['输出'])),
    step("编译期读文件的陷阱:embed!(\"version.txt\") 读到 \"1.0\"。把 version.txt 改成 2.0 之后再 cargo build,输出只有 Finished(0.01 秒,什么都没编译),运行仍是 \"1.0\" —— cargo 不知道宏读过这个文件,宏没有重新运行。", t=tl(S(3)), mark=lidx(S(3), '仍是旧值', 'Finished'), done=lidx(S(3), 'build 后运行'), kv=KV([['改了被读的文件', 'cargo 不会重新编译'], ['结果', '陈旧的 \"1.0\"']], ['结果'])),
    step("改动 main.rs(加一个换行)触发重新编译后,宏重新运行,读到新值 \"2.0\"。可见函数式宏读取的外部文件不会被 cargo 自动追踪。", t=tl(S(3)), done=lidx(S(3), '改动 main.rs'), kv=KV([['触碰 Rust 源码', '宏重新运行,读到 2.0']], ['触碰 Rust 源码'])),
    step("失败要给出带位置的错误:embed!(\"不存在.txt\") 报「读取 不存在.txt 失败: No such file or directory」并指向字符串字面量;fib!(99999999999) 报 error: number too large to fit in target type;fib!(\"x\") 报 error: expected integer literal,都带行列号和下划线。", t=tl(S(4)), mark=lidx(S(4), 'error:'), kv=KV([['syn::Error::new(span, …)', '指向输入的 token'], ['3 个错误', '一次编译全部报出']], ['syn::Error::new(span, …)'])),
    step("对照:标准库的 include_str!(\"../version.txt\") 就会被追踪 —— 同样把文件从 3.0 改成 4.0,cargo build 重新编译了 app,运行得到 \"4.0\"。编译器自己知道 include_str! 读了哪个文件;自定义的过程宏做不到这一点(这里没有验证 tracked_path 一类的不稳定 API)。", t=tl(S(5)), done=lidx(S(5), 'include_str'), kv=KV([['include_str!', '改文件会触发重编译'], ['自定义 embed!', '不会']], ['自定义 embed!'])),
]
A = mkart('u82', 82, 'Rust,函数式宏,过程宏,编译期计算,真实验证,动画演示',
    '真实写三个函数式过程宏:fib!(30) 在编译期算出 832040 并展开成字面量;hashmap!{ k => v } 用 syn 解析自定义语法;embed! 在编译期读文件,但改文件后 cargo 不重新编译(陈旧值),碰一下 main.rs 才更新;错误用 syn::Error 带位置。',
    '函数式过程宏能在编译期运行任意 Rust 代码:算常量、解析自定义语法、读文件。但它也有陷阱:cargo 不知道宏读过什么文件。这篇三种用法都真实跑通,并复现了那个「改了文件却没生效」的坑。',
    [('832040', 'fib!(30) 在编译期算出的字面量'), ('0.01 s', '改了被 embed 的文件后 cargo build 的耗时(什么都没重编)'), ('3 个', '一次编译同时报出的带位置的宏错误数')],
    [('编译期计算', '<p>过程宏的阶段见<a href="rust-proc-macro-phases.html">过程宏的执行阶段</a>。</p>'), ('自定义语法', '<p>声明宏版本的写法见<a href="rust-macro-rules.html">声明宏 macro_rules!</a>。</p>'), ('编译期读文件的陷阱', None), ('错误报告', None), ('对照 include_str!', '<p>想让自定义宏也在文件改动时重编译,可以尝试 build.rs 的 cargo:rerun-if-changed(见 <a href="rust-build-rs.html">Build Script build.rs</a>),这一点没有验证。</p>')],
    steps, [ENV_U + '。crates:syn 2、quote 1、proc-macro2 1', '没有验证:proc_macro::tracked_path 一类的不稳定 API、宏里读环境变量的追踪(tracked_env)、build.rs 配合 rerun-if-changed 是否能解决此陷阱'], '函数式宏')
