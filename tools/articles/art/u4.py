from lib import *
R = J('u4')
S = SS('u4')
steps = [
    step("shadowing(再写一次 let)可以改变类型:let spaces = \"   \"; let spaces = spaces.len(); 第二个 spaces 是 usize,运行输出 spaces = 3。同样的意图用 mut 写 —— let mut spaces = \"   \"; spaces = spaces.len(); —— 编译失败:error[E0308]: mismatched types。mut 只能改值,不能改类型。", t=tl(S(1)), done=[0], mark=lidx(S(1), 'error[E0308]'), kv=KV([['shadowing', '可以换类型'], ['mut', '不能换类型(E0308)']], ['shadowing'])),
    step("shadowing 的作用域:外层 x 是 5,第二行 let x = x + 1 得 6,内层块里 let x = x * 2 得 12(输出「内层 x = 12」),块结束后又回到外层的 6(输出「外层 x = 6」)。遮蔽只到当前块结束。", t=tl(S(2)), done=[0], kv=KV([['内层 x', 12], ['外层 x', 6]], ['内层 x'])),
    step("shadowing 创建的是新变量:debug 构建(opt-level=0)里取两次 x 的地址,不相同(false);mut 变量 y 重新赋值前后地址相同(true)。注意这只是 debug 构建的观察 —— 优化后编译器可能把两个变量放到同一个位置,语言本身只保证「它们是两个不同的变量」。", t=tl(S(3)), mark=lidx(S(3), '地址相同吗'), kv=KV([['shadowing', '新变量(地址不同)'], ['mut', '同一变量(地址相同)']], ['shadowing'])),
    step("被遮蔽的值不会被提前释放:两个带 Drop 的值,第二个 let a 遮蔽了第一个,但「第一个」直到作用域结束才被 drop,顺序是先 drop 第二个、再 drop 第一个(与创建相反)。所以遮蔽一个持有资源的变量(锁、文件、连接)并不会释放它 —— 需要提前释放要用 drop(x) 或缩小作用域。", t=tl(S(4)), mark=lidx(S(4), 'drop 第'), kv=KV([['drop 顺序', '第二个 → 第一个'], ['提前释放', '遮蔽做不到']], ['提前释放'])),
    step("遮蔽常与移动配合:let s = String::from(\"hello\"); let s = s + \", world\"; 旧的 s 被移动进 + 运算,新的 s 是结果,输出 hello, world。旧名字之后就不能再用了(它的值已经被移走),同名的新变量正好接管。", t=tl(S(5)), done=[0], kv=KV([['旧 s', '被移动'], ['新 s', 'hello, world']], ['新 s'])),
]
A = dict(
    n=4, series='rust', tags='Rust,Shadowing,mut,Drop,真实验证,动画演示',
    desc='shadowing 与 mut 的四个真实差别:shadowing 能换类型而 mut 报 E0308、作用域只到块结束、debug 下是不同的地址(新变量)、被遮蔽的值要到作用域结束才按相反顺序 drop(遮蔽不会提前释放资源)。',
    lead='再写一次 let 和写 let mut 看起来都是「改一个变量」,实际差别很大。这篇用真实的编译与运行结果比较两者:能不能换类型、作用域、是不是同一个变量,以及一个常被忽略的点 —— 被遮蔽的值什么时候释放。',
    facts=[('E0308', 'mut 想把 &str 变成 usize 时的错误;shadowing 可以'), ('新变量', 'shadowing 是另一个变量(debug 下地址不同),mut 是同一个'), ('不提前释放', '被遮蔽的值仍活到作用域结束才 drop')],
    body=[
        sec('换类型', '', term('', blk('u4', 1)), '<p>shadowing 的典型用途就是「把解析前的字符串变成解析后的数」而不必起两个名字(见<a href="rust-option-result.html">Option 与 Result</a>里的 parse)。</p>'),
        sec('作用域', '', term('', blk('u4', 2))),
        sec('新变量还是同一个变量', '', term('', blk('u4', 3)), '<p>地址只是一个旁证,不是语言保证。</p>'),
        sec('被遮蔽的值什么时候释放', '', term('', blk('u4', 4)), '<p>Drop 的顺序规则见<a href="rust-drop-trait.html">Drop Trait 与资源释放</a>。</p>'),
        sec('遮蔽与移动', '', term('', blk('u4', 5))),
        sec('分步演示', '', demo('shadowing 与 mut', [('t', 'term', '编译与运行输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_U + '。第 3 节用 -C opt-level=0 编译;其余用默认(debug)构建', '没有验证:优化构建下的地址与栈布局、闭包捕获被遮蔽变量、模式匹配中的遮蔽、for 循环变量的遮蔽'],
)
