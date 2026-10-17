from lib import *
S = SS('u119')
steps = [
    step("ManuallyDrop<T> 包住的值不会自动 drop:size_of::<ManuallyDrop<Noisy>>() 与 Noisy 同样是 16 字节;ManuallyDrop::new(Noisy(\"忘记\")) 作用域结束时没有任何 drop 输出(泄漏);通过 Deref 照常读内部值(b.0 = \"手动\"),ManuallyDrop::drop(&mut b) 才打印「Noisy(手动) drop」;into_inner 取回所有权后恢复正常 drop 规则(「Noisy(取出) drop」)。", t=tl(S(1)), done=lidx(S(1), 'size_of', 'Deref', 'Noisy(手动) drop', 'Noisy(取出) drop'), mark=lidx(S(1), '忘记'), kv=KV([['ManuallyDrop::new', '包住就不自动 drop'], ['ManuallyDrop::drop', '手动 drop,unsafe'], ['into_inner', '恢复自动 drop']], ['ManuallyDrop::drop'])),
    step("控制字段的 drop 顺序:默认按声明顺序,先 first 再 second;把字段包成 ManuallyDrop,并在自己的 Drop 里先 drop second、再 drop first,顺序就反过来:Noisy(second) drop → Noisy(first) drop。", t=tl(S(2)), done=lidx(S(2), '默认', '用 ManuallyDrop 反过来'), kv=KV([['默认', 'first → second'], ['ManuallyDrop + 自己的 Drop', 'second → first']], ['ManuallyDrop + 自己的 Drop'])),
    step("实现了 Drop 的类型不能把字段移出去:let s = g.data 报 error[E0509]: cannot move out of type `Guard`, which implements the `Drop` trait,help 建议借用或 clone。", t=tl(S(3)), mark=lidx(S(3), 'error[E0509]'), kv=KV([['Drop 类型的字段', '不能 move 出来:E0509']], ['Drop 类型的字段'])),
    step("用 ManuallyDrop 绕开:Guard 的字段是 ManuallyDrop<String>,into_data(self) 先把 self 包进 ManuallyDrop(阻止 Guard 自己的 Drop 运行),再 take 出字段。结果取出 \"payload\",输出里没有 Guard::drop 的那一行;另一个正常离开作用域的 _g2 才打印「Guard::drop 运行了」。", t=tl(S(3)), done=lidx(S(3), 'into_data', 'Guard::drop 运行了'), kv=KV([['into_data', '取出字段,不运行 Guard::drop'], ['普通 drop', '运行 Guard::drop']], ['into_data'])),
    step("配合 Vec 的原始部件:把 Vec 包进 ManuallyDrop 后拆出 ptr、len = 4、cap = 4,原 Vec 不再负责释放;from_raw_parts 重新组装成 [1, 2, 3, 4],缓冲区只会被释放一次(避免双重释放)。", t=tl(S(4)), done=lidx(S(4), '拆出', 'from_raw_parts'), kv=KV([['拆开', 'ManuallyDrop 阻止原 Vec 释放'], ['重组', 'from_raw_parts,释放一次']], ['重组'])),
    step("与 mem::forget 的区别:forget(a) 立即放弃值,之后既没法用也没法 drop;ManuallyDrop 保留值 —— 之后还能读(ManuallyDrop 之后还能读: ManuallyDrop),也能手动 drop(打印「Noisy(ManuallyDrop) drop」),forget 的 Noisy 则永远没有 drop 输出。", t=tl(S(5)), done=lidx(S(5), 'ManuallyDrop 之后还能读', 'Noisy(ManuallyDrop) drop'), kv=KV([['forget', '放弃,不可恢复'], ['ManuallyDrop', '保留,可用可 drop']], ['ManuallyDrop'])),
]
A = mkart('u119', 119, 'Rust,ManuallyDrop,Drop,unsafe,真实验证,动画演示',
    '用真实运行验证 ManuallyDrop:不自动 drop、大小同 T、Deref 可用、手动 drop 与 into_inner;改变字段 drop 顺序;绕过 E0509 的 take 写法(into_data 不运行 Guard::drop);配合 Vec::from_raw_parts 避免双重释放;与 mem::forget 的区别。',
    'ManuallyDrop 把「什么时候 drop」的决定权交还给你。这篇用带打印的 Drop 验证它的行为,并用三个典型场景(改 drop 顺序、从 Drop 类型里取出字段、拆装 Vec)说明它为什么存在。',
    [('0 行', 'ManuallyDrop 包住的值在作用域结束时的 drop 输出'), ('E0509', '从实现了 Drop 的类型里移出字段的错误码'), ('16 字节', 'ManuallyDrop<Noisy> 与 Noisy 的大小(没有额外开销)')],
    [('值不会自动 drop', '<p>Drop 的规则见<a href="rust-drop-trait.html">Drop Trait 与资源释放</a>。</p>'), ('改变 drop 顺序', None), ('从 Drop 类型里移出字段', None), ('Vec 的原始部件', '<p>未初始化内存见<a href="rust-maybeuninit.html">MaybeUninit</a>。</p>'), ('与 forget 的区别', None)],
    steps, [ENV_U, '没有验证:ManuallyDrop 内部值被 drop 后再访问的后果(UB,不演示)、panic 时的 drop 行为、ManuallyDrop 与 Pin 的组合、结构体字段 drop 顺序的语言保证条款'], 'ManuallyDrop')
