from lib import *
R = J('u10')
S = SS('u10')
steps = [
    step("Option<T> 与 Result<T, E> 只是两个普通的枚举:自己写 enum MyOption<T> { None, Some(T) } 就能用 match 处理。标准库的版本一样:找第一个偶数得到 Some(4),解析 \"12x\" 得到 Err(ParseIntError { kind: InvalidDigit })。它们不是语言内置的特殊类型。", t=tl(S(1)), done=lidx(S(1), '找到偶数', 'Some(4)'), kv=KV([['Option', 'None | Some(T)'], ['Result', 'Ok(T) | Err(E)']], ['Option'])),
    step("Rust 没有 null:Option<i32> 与整数相加报 error[E0369]: cannot add `{integer}` to `Option<i32>`(Option<i32> 没有实现 Add)。「可能没有值」必须显式处理(match、if let、unwrap_or、?),不能当作普通值直接用。", t=tl(S(2)), mark=lidx(S(2), 'error[E0369]'), kv=KV([['Option<i32> + 1', 'E0369']], ['Option<i32> + 1'])),
    step("常用方法:unwrap_or 给默认值(3 与 0);map 只在有值时变换(Some(30)、None);and_then 链接会失败的步骤(Some(103));ok_or 把 Option 变成 Result(Ok(3)、Err(\"没有值\"));Result.ok() 变回 Option;? 在函数里提前返回 Err(parse_and_double(\"21\") 是 Ok(42),\"abc\" 是 Err);filter、take 也在这一族。", t=tl(S(3)), done=lidx(S(3), ':'), kv=KV([['map / and_then', '链式处理有值的情况'], ['ok_or / ok()', 'Option ↔ Result']], ['map / and_then'])),
    step("unwrap / expect 在 Err 或 None 时 panic:expect(\"配置里的端口必须是整数\") 失败时 panic 信息是「配置里的端口必须是整数: ParseIntError { kind: InvalidDigit }」,退出码 101。expect 比 unwrap 多一句你写的上下文,出问题时更好定位。", t=tl(S(4)), mark=lidx(S(4), 'panicked', '配置里'), kv=KV([['panic 退出码', 101], ['expect', '带上下文']], ['panic 退出码'])),
    step("Option 的开销:Option<&u64> 与 &u64 都是 8 字节,Option<Box<u64>> 与 Box<u64> 也都是 8 字节,Option<String> 与 String 都是 24 字节 —— 编译器利用「引用 / Box / String 内部指针永远不为 0」,拿 0 当作 None(niche 优化,没有额外标签)。而 Option<i32> 是 8 字节(i32 的所有位模式都合法,需要额外的标签)、Option<u64> 是 16 字节。", t=tl(S(5)), done=lidx(S(5), 'Option<&u64> = 8', 'Option<Box', 'Option<String>'), mark=lidx(S(5), 'Option<u64> = 16'), kv=KV([['Option<&T>', '无额外开销'], ['Option<u64>', '16 字节(需要标签)']], ['Option<&T>'])),
]
A = dict(
    n=10, series='rust', tags='Rust,Option,Result,niche优化,真实验证,动画演示',
    desc='用真实运行验证 Option 与 Result:两个普通枚举(可自己实现);没有 null,Option<i32> + 1 报 E0369;unwrap_or、map、and_then、ok_or、? 的行为;expect 的 panic 信息;Option<&T>、Option<Box<T>>、Option<String> 没有额外内存开销而 Option<u64> 是 16 字节。',
    lead='Option 与 Result 是 Rust 处理「可能没有」和「可能失败」的方式。这篇从最底层讲起:它们只是普通枚举,没有魔法;编译器怎样拒绝把 Option 当值用;一组常用方法实际怎么工作;panic 时信息长什么样;以及它们占多少内存 —— 为什么 Option<&T> 是免费的。',
    facts=[('E0369', 'Option<i32> + 1 的错误(没有 null,必须显式处理)'), ('8 = 8', 'Option<&u64> 与 &u64 同为 8 字节(niche 优化)'), ('16 字节', 'Option<u64>:所有位模式都合法,需要标签')],
    body=[
        sec('两个普通的枚举', '', term('', blk('u10', 1))),
        sec('没有 null', '', term('', blk('u10', 2))),
        sec('常用方法', '', term('', blk('u10', 3)), '<p>? 的展开方式见<a href="rust-question-mark-desugar.html">? 运算符展开过程</a>;错误传播见<a href="rust-result-propagation.html">Result 错误传播</a>。</p>'),
        sec('unwrap 与 expect', '', term('', blk('u10', 4)), '<p>什么时候该 panic、什么时候该返回 Result,见<a href="rust-panic-unwrap-expect.html">panic!、unwrap 与 expect</a>。</p>'),
        sec('内存占用', '', term('', blk('u10', 5)), '<p>niche 优化的原理见<a href="rust-option-ref-niche.html">Option&lt;&amp;T&gt; 的空指针优化</a>。</p>'),
        sec('分步演示', '', demo('Option 与 Result', [('t', 'term', '编译与运行输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_U + '。大小为 64 位目标、rustc 1.98.1 的结果(niche 优化是编译器的优化,不是语言规范保证的)', '没有验证:Option<NonZeroU32> 等的大小、Result<(), Box<dyn Error>> 的布局、unwrap_or_else 与 unwrap_or 的求值差别、Option 的 Ord 与排序规则'],
)
