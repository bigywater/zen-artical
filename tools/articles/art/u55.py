from lib import *
S = SS('u55')
steps = [
    step("局部变量按声明的相反顺序 drop:先声明 a、b、c,输出 drop c → drop b → drop a。", t=tl(S(1)), done=lidx(S(1), 'drop c', 'drop b', 'drop a'), kv=KV([['局部变量', '后声明的先 drop']], ['局部变量'])),
    step("结构体字段按声明顺序 drop(p.first 先于 p.second);Vec 元素按下标顺序 drop(v0 → v1 → v2)。顺序和局部变量正好相反。", t=tl(S(1)), done=lidx(S(1), 'drop p.first', 'drop p.second', 'drop v0', 'drop v1', 'drop v2'), kv=KV([['结构体字段', '声明顺序'], ['Vec 元素', '下标顺序']], ['结构体字段'])),
    step("`let _ = D(\"临时\")` 不绑定变量,值在语句结束就 drop(先看到 drop 临时,再看到「之后」那行);`let _keep = D(\"绑定\")` 则活到作用域结束才 drop。", t=tl(S(1)), mark=lidx(S(1), '临时', '绑定'), kv=KV([['let _ =', '语句结束就 drop'], ['let _keep =', '作用域结束才 drop']], ['let _ ='])),
    step("drop(a) 提前释放:输出 drop(a) 之前 → drop early → drop(a) 之后。mem::forget 之后没有 drop forgotten 这一行,值被「忘掉」而不运行 Drop;作用域结束时只 drop end。", t=tl(S(2)), done=lidx(S(2), 'drop early', 'drop end'), mark=lidx(S(2), 'forget'), kv=KV([['mem::drop', '立刻运行 Drop'], ['mem::forget', '不运行 Drop']], ['mem::forget'])),
    step("手动调用 d.drop() 编译失败:error[E0040]: explicit use of destructor method,help 建议改用 `drop(d)`。Drop::drop 只能由编译器插入的 drop glue 调用。", t=tl(S(2)), mark=lidx(S(2), 'error[E0040]'), kv=KV([['d.drop()', 'E0040']], ['d.drop()'])),
    step("值被移动后只 drop 一次,由最后的所有者负责:consume(a) 里先打印「拿到 a」,函数结束时 drop a;b 在没有被移动的分支下一直留到 main 结束才 drop b。", t=tl(S(3)), done=lidx(S(3), 'drop a', 'drop b'), kv=KV([['移动', 'drop 由新所有者执行,且只一次']], ['移动'])),
    step("panic 展开时已创建的值会被 drop:stdout 里有 drop guard,进程退出码 101。std::process::exit(0) 则立刻结束进程,stdout 里只有「即将 exit」,没有 drop guard。", t=tl(S(4)), done=lidx(S(4), 'drop guard'), mark=lidx(S(4), 'process::exit', '没有 drop'), kv=KV([['panic(默认 unwind)', 'drop 会运行'], ['process::exit', 'drop 不运行']], ['process::exit'])),
]
A = mkart('u55', 55, 'Rust,Drop,析构,所有权,真实验证,动画演示',
    '用真实运行验证 Drop 的执行时机与顺序:局部变量逆序、结构体字段与 Vec 元素按顺序;let _ 与 let _x 的区别;mem::drop 提前释放、mem::forget 跳过、手动调用 .drop() 报 E0040;移动后只 drop 一次;panic 展开会 drop,process::exit 不会。',
    'Drop 什么时候运行、按什么顺序运行,是写资源管理代码(锁、文件、连接)的基础。这篇给一个会打印自己名字的类型,把每种情形的 drop 顺序都真实跑出来,包括最容易误会的 `let _ =` 和 process::exit。',
    [('逆序', '同一作用域里局部变量的 drop 顺序'), ('E0040', '手动调用 .drop() 的编译错误'), ('101', 'panic 后进程退出码,但 guard 仍被 drop')],
    [('drop 的顺序', '<p>所有权与移动见<a href="rust-move-semantics.html">Move 语义真实验证</a>。</p>'), ('提前释放与 forget', None), ('移动之后', None), ('panic 与 exit', '<p>panic 的展开机制不在这篇范围,这里只验证了 drop 是否运行。</p>')],
    steps, [ENV_U + '。每个实验都是单文件 rustc 编译运行', '没有验证:panic 发生在 drop 里的行为(双重 panic 会 abort)、catch_unwind、panic=abort 配置下的 drop、drop 顺序的更多嵌套组合(枚举、闭包捕获)'], 'Drop')
