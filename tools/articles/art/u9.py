from lib import *
R = J('u9')
S = SS('u9')
steps = [
    step("if let Some(x) = a 只处理一个模式,else 分支处理其余;while let Some(top) = stack.pop() 一直弹到 None 为止(依次 pop 3、2、1)。2024 edition 里还能用 && 把 let 与布尔条件连起来:if let Some(x) = a && x > 5(let chains),输出「a = 7 且大于 5」。", t=tl(S(1)), done=lidx(S(1), '有值', 'pop', 'let chain'), kv=KV([['if let', '只关心一个模式'], ['while let', '直到不匹配为止']], ['if let'])),
    step("let else:let Ok(p) = s.parse::<u16>() else { return None; }; 匹配成功时绑定 p 留在外层作用域继续用,失败时 else 块必须「发散」。parse_port 对 \"8080\" 返回 Some(8080),对 \"abc\"、\"99999\"(超出 u16)返回 None。如果 else 块不发散(只 println!),编译报 error[E0308]: `else` clause of `let...else` does not diverge,并提示用 return 或 panic!,或者改用 match。", t=tl(S(2)), mark=lidx(S(2), 'E0308'), done=lidx(S(2), 'Some(8080)'), kv=KV([['else 块', '必须 return / break / continue / panic'], ['绑定', '留在外层作用域']], ['else 块'])),
    step("普通 let 只接受「一定匹配」的模式:let Some(x) = o; 报 error[E0005]: refutable pattern in local binding,并建议用 let...else。反过来,对一定匹配的模式写 if let,只给警告 irrefutable `if let` pattern(this pattern will always match, so the `if let` is useless)并建议换成普通 let。", t=tl(S(3)), mark=lidx(S(3), 'error[E0005]', 'warning: irrefutable'), kv=KV([['let + 可能失败的模式', 'E0005'], ['if let + 必然匹配', '警告']], ['let + 可能失败的模式'])),
    step("同一份代码用不同 edition 编译,输出顺序不同:条件里有一个临时值 D(f(&D) 的参数),在 edition 2021 里临时值活到整个 if let…else 语句结束,所以先打印「else 分支」再 drop;在 edition 2024 里临时值在进入 else 之前就释放,先 drop 再「else 分支」。这是 2024 的有意改动(缩短 if let 条件里临时值的寿命)。", t=tl(S(4)), mark=lidx(S(4), 'drop(', 'else 分支'), kv=KV([['2021', 'else 分支 → drop'], ['2024', 'drop → else 分支']], ['2024'])),
]
A = dict(
    n=9, series='rust', tags='Rust,if let,let else,edition,真实验证,动画演示',
    desc='用真实编译验证 if let、while let、let else:let chains;let else 的 else 块必须发散(E0308)、成功时绑定留在外层;普通 let 用可失败模式报 E0005、if let 用必然匹配的模式只警告;同一份代码在 edition 2021 与 2024 下,if let 条件里临时值的释放顺序不同。',
    lead='match 太长、只想处理一种情况时,Rust 给了 if let、while let 和 let else。这篇验证它们各自的规则:什么时候必须发散、绑定在哪里生效、编译器怎么提醒你用错了,最后还有一个只有同时编译 2021 与 2024 才会看到的差别 —— 临时值什么时候被释放。',
    facts=[('E0308', 'let else 的 else 块不发散时的错误'), ('E0005', '普通 let 用可能失败的模式时的错误'), ('2021 ≠ 2024', 'if let 条件里的临时值:2021 在 else 之后释放,2024 在进入 else 之前释放')],
    body=[
        sec('if let 与 while let', '', term('', blk('u9', 1)), '<p>与 <a href="rust-match-exhaustive.html">match 的穷尽匹配</a>相比,if let 不要求列全,所以也不再有编译器的完整性检查。</p>'),
        sec('let else', '', term('', blk('u9', 2))),
        sec('refutable 与 irrefutable', '', term('', blk('u9', 3))),
        sec('edition 2024 里临时值的变化', '', term('', blk('u9', 4)), '<p>这个差别理论上会影响条件里持有锁(见<a href="rust-mutex-vs-rwlock.html">Mutex 与 RwLock</a>)或借用的临时值;我这里只用带 Drop 的临时值验证了释放顺序,没有拿 MutexGuard 实测。</p>'),
        sec('分步演示', '', demo('if let 与 let else', [('t', 'term', '编译与运行输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_U + '。let chains 需要 edition 2024 与较新的 rustc(本机 1.98);第 4 节分别用 --edition=2021 与 --edition=2024 编译同一份源码', '没有验证:if let 临时值变化对 MutexGuard 的实际影响、matches! 宏、let else 与 ? 运算符的组合'],
)
