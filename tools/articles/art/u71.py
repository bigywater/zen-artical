from lib import *
S = SS('u71')
steps = [
    step("? 成功时取出 Ok 里的值继续往下走:parse_sum(\"3\", \"4\") 打印两次解析、再相加,得 Ok(7)。", t=tl(S(1)), done=lidx(S(1), '成功:'), kv=KV([['Ok(v)', '取出 v 继续']], ['Ok(v)'])),
    step("失败时立刻从当前函数返回 Err,后面的语句不再执行:第二个参数 \"x\" 失败时,输出只有「解析 a」「解析 b」,没有「两个都成功」,返回 Err(ParseIntError { kind: InvalidDigit });第一个参数 \"\" 失败时连「解析 b」都不打印,返回 Err(ParseIntError { kind: Empty })。", t=tl(S(1)), mark=lidx(S(1), 'Err('), kv=KV([['Err(e)', '立即 return Err(e)']], ['Err(e)'])),
    step("? 只能用在返回 Result 或 Option 的函数里:fn main() { let n: i32 = \"5\".parse()?; } 报 error[E0277]: the `?` operator can only be used in a function that returns `Result` or `Option` (or another type that implements `FromResidual`),help 建议把 main 的返回类型改成 Result<(), Box<dyn std::error::Error>>。", t=tl(S(2)), mark=lidx(S(2), 'error[E0277]'), kv=KV([['返回 ()的函数里用 ?', 'E0277']], ['返回 ()的函数里用 ?'])),
    step("错误类型不一致时,? 会通过 From 转换:函数返回 Result<i32, MyErr> 却对 ParseIntError 用 ?,报 error[E0277]: `?` couldn't convert the error to `MyErr`,note 写明「`MyErr` needs to implement `From<ParseIntError>`」。", t=tl(S(3)), mark=lidx(S(3), 'error[E0277]', 'From<ParseIntError>'), kv=KV([['缺少 From 实现', 'E0277']], ['缺少 From 实现'])),
    step("实现了 impl From<ParseIntError> for MyErr 之后:f(\"7\") 得 Ok(7)、f(\"-7\") 得 Err(Neg),都没有调用 From;只有 f(\"abc\") 失败时才打印「From<ParseIntError> 被调用」,得到 Err(Parse(ParseIntError { kind: InvalidDigit }))。成功路径上没有转换开销。", t=tl(S(3)), done=lidx(S(3), 'Ok(7)', 'Err(Neg)'), mark=lidx(S(3), 'From<ParseIntError> 被调用'), kv=KV([['成功路径', '不调用 From'], ['失败路径', '调用一次 From::from']], ['失败路径'])),
    step("Option 上也能用 ?:first_even(&[]) 得 None(first() 是 None 就直接返回 None)、&[2,3] 得 Some(2)、&[1] 得 None。要在返回 Result 的函数里处理 Option,先用 ok_or 变成 Result:to_res(&[]) 得 Err(\"空切片\")。直接对 Option 用 ? 报 error[E0277]: the `?` operator can only be used on `Result`s, not `Option`s, in a function that returns `Result`。", t=tl(S(4)), done=lidx(S(4), 'None Some(2) None', 'Err("空切片")'), mark=lidx(S(4), 'error[E0277]'), kv=KV([['Option 里 ?', '返回 None'], ['Result 函数里的 Option', 'ok_or 转换']], ['Result 函数里的 Option'])),
    step("main 也可以返回 Result:\"abc\" 解析失败时程序打印「开始」,stderr 输出 Error: ParseIntError { kind: InvalidDigit },进程退出码是 1,「不会执行到这里」那行没有打印。", t=tl(S(5)), mark=lidx(S(5), '退出码 1', 'Error:'), kv=KV([['退出码', '1'], ['stderr', 'Error: + Debug 格式']], ['退出码'])),
]
A = mkart('u71', 71, 'Rust,Result,错误处理,问号运算符,真实验证,动画演示',
    '用真实运行验证 ? 的传播行为:成功取值、失败立刻 return;只能用在返回 Result/Option 的函数(E0277);错误类型不同需要 From(缺少时 E0277);成功路径不调用 From;Option 的 ? 与 ok_or;main 返回 Err 时退出码 1。',
    '? 让 Rust 的错误处理简洁,但每一个细节都有规则:什么函数里才能用、错误类型怎么转换、Option 与 Result 能不能混用、main 里出错会怎样。这篇每一条规则都用编译与运行结果验证。',
    [('E0277', '? 用在返回 () 的函数里,或错误类型无法转换时的错误码'), ('0 次', '成功路径上 From::from 的调用次数'), ('1', 'main 返回 Err 时的进程退出码')],
    [('传播的行为', None), ('只能用在 Result / Option 的函数里', None), ('错误类型转换', '<p>展开成什么代码见<a href="rust-question-mark-desugar.html">? 运算符展开过程</a>。</p>'), ('Option 与 Result', '<p>Option 与 Result 的基础见<a href="rust-option-result.html">Option 与 Result</a>。</p>'), ('main 返回 Result', '<p>自定义错误类型的写法见<a href="rust-custom-error-type.html">自定义错误类型</a>。</p>')],
    steps, [ENV_U, '没有验证:在闭包里使用 ?、Box<dyn Error> 作为错误类型(放在后面的文章)、? 用在 async 函数里、Try trait(不稳定)、main 返回 ExitCode 的写法'], '? 传播')
