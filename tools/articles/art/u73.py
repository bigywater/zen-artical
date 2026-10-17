from lib import *
S = SS('u73')
steps = [
    step("一个完整的自定义错误:enum ConfigError { Io, Parse { key, source }, Missing },实现 Display(给人看)、Error(source() 返回底层原因)、From<io::Error>(让 ? 自动转换)。load 读取配置文件,port 一行解析成功得 Ok(8080)。", t=tl(S(1)), done=lidx(S(1), 'port ->'), kv=KV([['Display', '人类可读的消息'], ['Error::source', '底层原因'], ['From', '让 ? 自动转换']], ['Error::source'])),
    step("workers = many 解析失败:顶层消息「配置项 workers 不是有效整数」,沿 source() 往下走一层:「由 invalid digit found in string 引起」;Debug 输出 Parse { key: \"workers\", source: ParseIntError { kind: InvalidDigit } } 保留了结构化信息。", t=tl(S(1)), done=lidx(S(1), 'workers 不是', 'invalid digit'), kv=KV([['顶层', '配置项 workers 不是有效整数'], ['source', 'invalid digit found in string']], ['source'])),
    step("缺少配置项 timeout:Missing 没有底层原因,source() 返回 None,只有一行消息。读取不存在的文件:顶层是「读取配置文件失败」,source 是 io 错误「No such file or directory (os error 2)」,Debug 里能看到 kind: NotFound。", t=tl(S(1)), done=lidx(S(1), '缺少配置项', '读取配置文件失败', 'No such file'), kv=KV([['Missing', 'source = None'], ['Io', 'source = io::Error']], ['Io'])),
    step("只实现 Error 不实现 Display 无法编译:error[E0277]: `MyErr` doesn't implement `std::fmt::Display`,note 说明 Error 的 supertrait 要求 Display(与 Debug)。", t=tl(S(2)), mark=lidx(S(2), 'error[E0277]', 'Display'), kv=KV([['impl Error', '需要 Debug + Display']], ['impl Error'])),
    step("Box<dyn Error> 可以向下转型还原具体类型:run(0) 抛出的是 Quota,downcast_ref::<Quota>() 得到内部值 100;run(1) 抛出的是 ParseIntError,第二个 downcast_ref 命中。Box<dyn Error> 是 16 字节的胖指针。", t=tl(S(3)), done=lidx(S(3), 'k=0', 'k=1'), kv=KV([['downcast_ref::<T>()', '按具体类型还原'], ['Box<dyn Error>', '16 字节']], ['downcast_ref::<T>()'])),
    step("错误类型的大小会拖累 Result:Small 2 字节、WithString 24 字节、Big 129 字节;Result<u32, Small> 8、Result<u32, WithString> 24、Result<u32, Big> 132 字节,而 Result<u32, Box<Big>> 只有 16 字节。io::Error 8 字节、ParseIntError 1 字节。大错误装箱可以让成功路径保持小。", t=tl(S(4)), done=lidx(S(4), 'Small 2', 'Result<u32, Small>', 'io::Error'), b=bars([['Result<u32, Small>', 8, '8'], ['Result<u32, WithString>', 24, '24'], ['Result<u32, Big>', 132, '132'], ['Result<u32, Box<Big>>', 16, '16']], 140, cur=[2], done=[0, 1, 3]), kv=KV([['Result<u32, Big>', '132 字节'], ['Result<u32, Box<Big>>', '16 字节']], ['Result<u32, Box<Big>>'])),
]
A = mkart('u73', 73, 'Rust,自定义错误,Error trait,source,真实验证,动画演示',
    '用真实运行验证自定义错误类型:enum + Display + Error + From,沿 source() 逐层打印原因,Debug 保留结构;缺少 Display 时 E0277;Box<dyn Error> 用 downcast_ref 还原具体类型;错误大小拖累 Result(Big 129 字节 → Result 132 字节,装箱后 16 字节)。',
    '写一个能让调用方好好处理的错误类型,需要实现哪些 trait?source 链怎么用?Box<dyn Error> 与 downcast 怎么配合?错误太大会怎样?这篇用一个会读配置文件的例子,把这些一次跑通。',
    [('4 项', '本文的错误类型实现的内容:Debug、Display、Error、From'), ('129 → 132', 'Big 错误枚举与 Result<u32, Big> 的字节数'), ('16 字节', 'Result<u32, Box<Big>> 的大小')],
    [('完整的错误类型', '<p>? 的转换规则见<a href="rust-result-propagation.html">Result 错误传播</a>。</p>'), ('缺少 Display', None), ('Box<dyn Error> 与 downcast', None), ('错误的大小', '<p>thiserror 与 anyhow 把这些样板代码自动化,见<a href="rust-thiserror-vs-anyhow.html">thiserror 与 anyhow 的边界</a>。</p>')],
    steps, [ENV_U + '。配置文件写在系统临时目录并在结束后删除', '没有验证:backtrace 的捕获、Error::description 与 cause 的废弃状态、error provide API(不稳定)、跨线程传递错误所需的 Send + Sync 约束'], '自定义错误')
