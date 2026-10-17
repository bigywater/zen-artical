from lib import *
S = SS('u83')
steps = [
    step("dbg! 输出到 stderr(stdout 里只有正常的 println 内容 b = 7、x = 10 y = s):格式是 [文件:行:列] 表达式文本 = 值。dbg!(a * 3) 打印 [..:3:13] a * 3 = 6,并把 6 作为表达式的值返回,所以 let b = dbg!(a * 3) + 1 仍得 b = 7。", t=tl(S(1)), done=lidx(S(1), 'a * 3 = 6', 'stdout:'), kv=KV([['输出位置', 'stderr'], ['格式', '[文件:行:列] 表达式 = 值'], ['返回值', '原值']], ['输出位置'])),
    step("dbg!(&v) 用 {:#?} 美化输出,Vec 被多行缩进;dbg!() 没有参数时只打印位置 [..:7:5];dbg!(10, \"s\") 对每个参数各打印一行并返回元组,所以 let (x, y) = dbg!(10, \"s\") 得 x = 10、y = \"s\"。", t=tl(S(1)), done=lidx(S(1), '&v = [', '[<实验目录>/src/u83a.rs:7:5]', '10 = 10', '"s" = "s"'), kv=KV([['dbg!()', '只打印位置'], ['dbg!(a, b)', '每个一行,返回元组']], ['dbg!(a, b)'])),
    step("dbg!(v) 会拿走所有权:紧接着 println!(\"{:?}\", v) 报 error[E0382]: borrow of moved value: `v`,help 建议改成借用。要继续使用就写 dbg!(&v)。", t=tl(S(2)), mark=lidx(S(2), 'error[E0382]'), kv=KV([['dbg!(v)', '移动 v'], ['dbg!(&v)', '只借用']], ['dbg!(v)'])),
    step("release 构建里 dbg! 照样输出:debug 和 release 两种构建,stderr 都是一行 [..:1:21] 1 + 1 = 2。dbg! 不会在发布构建里被自动去掉,提交代码前要手动删。", t=tl(S(3)), done=lidx(S(3), 'debug  :', 'release:'), kv=KV([['debug', '输出'], ['release', '也输出']], ['release'])),
    step("编译器展开 dbg!(a + 1):match a + 1 { tmp => { eprintln!(\"[{}:{}:{}] {} = {:#?}\", 文件, 行, 列, \"a + 1\", &&tmp); tmp } }。值只求值一次:带副作用的块 { n.set(n.get() + 1); n.get() } 被求值 1 次,值 = 1。", t=tl(S(4)), done=lidx(S(4), 'match a + 1', 'tmp =>', '被求值 1 次'), kv=KV([['实现', 'match 绑定 tmp → eprintln → 返回 tmp'], ['求值次数', '1']], ['求值次数'])),
    step("对比 println!(\"{:?}\", p) 的单行 P { name: \"a\", tags: [1, 2], pos: (3, 4) }(在 stdout),dbg!(&p) 在 stderr 用 {:#?} 逐字段多行缩进输出,嵌套的 Vec 与元组也展开。", t=tl(S(5)), done=lidx(S(5), 'stdout:', '&p = P {'), kv=KV([['println!(\"{:?}\")', 'stdout,单行'], ['dbg!', 'stderr,{:#?} 多行']], ['dbg!'])),
]
A = mkart('u83', 83, 'Rust,dbg!,调试,宏,真实验证,动画演示',
    '用真实运行验证 dbg!:输出到 stderr,格式为 [文件:行:列] 表达式 = 值,并原样返回值;多个参数返回元组,无参数只打印位置;dbg!(v) 会移动 v(E0382);release 构建同样输出;展开是 match tmp 只求值一次;用 {:#?} 美化。',
    'dbg! 比 println! 调试好用在哪?它到底输出到哪、会不会拿走所有权、release 里还在不在、背后怎么实现。这篇用真实运行和编译器展开把它的每个行为都验证了一遍。',
    [('stderr', 'dbg! 的输出位置(println! 在 stdout)'), ('E0382', 'dbg!(v) 之后再使用 v'), ('1 次', '展开后表达式被求值的次数')],
    [('输出格式', None), ('所有权', None), ('release 里仍然输出', None), ('展开成什么', '<p>展开使用 RUSTC_BOOTSTRAP=1 -Z unpretty=expanded。Display 与 Debug 的区别见<a href="rust-display-debug.html">Display 与 Debug</a>。</p>'), ('美化输出', None)],
    steps, [ENV_U + '。展开用 RUSTC_BOOTSTRAP=1 -Z unpretty=expanded', '没有验证:dbg! 在多线程里输出交错的情况、stderr 重定向到文件时的格式、dbg! 对不实现 Debug 的类型的报错(未测)、macro-backtrace'], 'dbg!')
