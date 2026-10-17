from lib import *
S = SS('u74')
R = J('u74'); en = R['expanded_n']
steps = [
    step("thiserror 2.0.21:一个 enum 加 #[derive(Error)] 与几个属性,就有了 Display(#[error(\"…\")] 的格式串)、Error::source(#[source] / #[from])、From(#[from])。运行:缺少的键显示「键 missing 不存在」且 source 为 None;io 错误的 source 是 io::Error;\"abc\" 经 #[from] 的 From 自动转成 Parse,source 是 ParseIntError。StoreError 为 32 字节。", t=tl(S(1)), done=lidx(S(1), 'missing', 'io ', 'abc'), kv=KV([['#[error(\"…\")]', '生成 Display'], ['#[source]', '生成 source()'], ['#[from]', '生成 From + source()']], ['#[from]'])),
    step(f"cargo rustc -- -Z unpretty=expanded 看 thiserror 真正生成了什么:与 StoreError 相关的 impl 共 {en} 行 —— impl Error 里的 source() 对每个变体 match(NotFound 返回 None,Io 与 Parse 返回 Some(source))、impl Display 里按 #[error] 的格式串 write_fmt、impl From<ParseIntError> for StoreError 构造 Parse 变体。就是手写版本的样板代码。", t=tl(S(2)), done=lidx(S(2), 'fn source', 'impl ::core::fmt::Display', 'impl ::core::convert::From'), kv=KV([['source()', '按变体 match'], ['Display', 'write_fmt'], ['From', '构造变体']], ['source()'])),
    step("anyhow 的 Result<T> 是应用层「什么错误都能装」:bail! 直接返回字符串错误,with_context / context 在原错误外叠加说明。输入 \"\"(bail)、\"80\"(anyhow!)、\"abc\"(解析失败)三种错误,{} 只显示最外层「启动服务失败」;{:#} 把整条链用「: 」连成一行。", t=tl(S(3)), done=lidx(S(3), '{}   :', '{:#}  :'), kv=KV([['{}', '只有最外层'], ['{:#}', '整条链一行']], ['{:#}'])),
    step("{:?}(Debug)输出多行的「Caused by:」列表:\"abc\" 的链是 0: 解析端口 \"abc\" 失败、1: invalid digit found in string;chain() 迭代整条原因链。anyhow::Error 只有 8 字节(Result<(), anyhow::Error> 也是 8 字节),并且能 downcast_ref::<ParseIntError>() 还原出最底层的错误。", t=tl(S(3)), done=lidx(S(3), 'Caused by', '原因链', 'size_of', 'downcast_ref'), kv=KV([['{:?}', 'Caused by 多行'], ['体积', '8 字节'], ['downcast_ref', '可还原']], ['{:?}'])),
    step("边界:库返回 thiserror 的 LibErr 枚举时,调用方可以直接 match 到 Timeout(5) 并按秒数重试;库若返回 anyhow::Error,调用方拿到的只是文本「超时 5 秒」,必须 downcast_ref::<LibErr>() 才能还原 Timeout(5)。所以:库用 thiserror(调用方要区分错误),应用顶层用 anyhow(只需要报告)。", t=tl(S(4)), done=lidx(S(4), 'typed', 'downcast_ref'), kv=KV([['库', 'thiserror:调用方可 match'], ['应用', 'anyhow:只报告 + 加上下文']], ['库'])),
]
A = mkart('u74', 74, 'Rust,thiserror,anyhow,错误处理,真实验证,动画演示',
    f'下载并真实编译 thiserror 2.0.21 与 anyhow 1.0.104:thiserror 的 derive 展开成 Display/source/From 三个 impl({en} 行);anyhow 的 context 链、{{:#}} 与 {{:?}} 输出、8 字节体积、downcast;库返回枚举时调用方可 match,返回 anyhow 时只能 downcast。',
    'thiserror 与 anyhow 常被放在一起比较,其实它们解决的是两件事。这篇真的下载编译这两个 crate,展开 thiserror 的宏看它生成了什么,再用 anyhow 的链式上下文,最后用一个例子说明两者的边界。',
    [('8 字节', 'anyhow::Error 的大小'), (f'{en} 行', 'thiserror 为一个 3 变体枚举生成的 impl 代码行数(含 Debug)'), ('2', '这两个 crate 各解决的问题:定义错误类型 / 报告并叠加上下文')],
    [('thiserror 的 derive', '<p>手写版本见<a href="rust-custom-error-type.html">自定义错误类型</a>。thiserror 从 crates.io 下载编译(2.0.21),需要联网。</p>'), ('宏展开后的代码', None), ('anyhow 的上下文链、Debug 与体积', None), ('库与应用的边界', '<p>? 的展开见<a href="rust-question-mark-desugar.html">? 运算符展开过程</a>。</p>')],
    steps, [ENV_U + '。crates:thiserror 2.0.21、anyhow 1.0.104(通过代理从 crates.io 下载)', '没有验证:anyhow 的 backtrace(需要环境变量与 std 支持)、编译时间对比、no_std 场景、thiserror 的 #[error(transparent)] 与 #[backtrace]、eyre / snafu 等替代品'], 'thiserror 与 anyhow')
