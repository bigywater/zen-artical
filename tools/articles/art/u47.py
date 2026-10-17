from lib import *
R = J('u47'); S = SS('u47')
steps = [
    step("孤儿规则:为类型实现 trait 时,trait 与类型至少有一个是本 crate 的。六种情形各编译一次:外部 trait + 外部类型(Display for Vec<u8>)报 error[E0117];本地 trait + 外部类型(MyTr for Vec<u8>)通过;外部 trait + 本地类型(Display for Local)通过;外部 trait + 外部类型但 trait 的类型参数是本地类型(From<Local> for Vec<u8>)通过;外部 trait + Box<本地类型> 通过(Box 是 #[fundamental]);外部 trait + Vec<本地类型> 报 E0117(Vec 不是 fundamental)。", t=tl(S(1)), mark=lidx(S(1), '失败'), done=lidx(S(1), '编译通过'), kv=KV([['E0117', 'Display for Vec<u8>、Display for Vec<Local>'], ['通过', '本地 trait / 本地类型 / From<Local> / Box<Local>']], ['E0117'])),
    step("一致性(coherence):同一个类型对同一个 trait 的实现不能重叠。有 blanket 实现 impl<T: Display> Describe for T 之后,再写 impl Describe for i32 报 error[E0119]: conflicting implementations of trait `Describe` for type `i32`(i32 本身就满足 Display)。", t=tl(S(2)), mark=lidx(S(2), 'error[E0119]'), kv=KV([['blanket 与具体实现重叠', 'E0119']], ['blanket 与具体实现重叠'])),
    step("连「现在不满足 Display」的 Vec<u8> 也不能再写具体实现:同样报 E0119,note 解释「upstream crates may add a new impl of trait `std::fmt::Display` for type `std::vec::Vec<u8>` in future versions」—— 上游将来可能给它加 Display,到时候你的代码就会冲突,所以现在就拒绝。本地类型 Mine 就没问题(上游永远不可能为它实现 Display),输出「我的类型 显示:5」。", t=tl(S(3)), mark=lidx(S(3), 'upstream crates may add'), done=lidx(S(3), '我的类型'), kv=KV([['外部类型', '上游将来可能加实现,所以拒绝'], ['本地类型', '没问题']], ['外部类型'])),
    step("绕开孤儿规则的两个办法:newtype 包一层(Bytes(Vec<u8>) 实现 Display,输出「3 字节」);自己定义 trait(Hex)再为外部类型 Vec<u8> 实现(输出 dead)。", t=tl(S(4)), done=lidx(S(4), '3 字节'), kv=KV([['newtype', '包一层'], ['自己的 trait', '本地 trait 可以给任何类型实现']], ['newtype'])),
]
A = mkart('u47', 47, 'Rust,孤儿规则,一致性,Trait,E0117,E0119,真实验证,动画演示',
    '用真实编译验证孤儿规则与一致性:六种 trait/类型组合(Display for Vec<u8> 报 E0117,From<Local> for Vec<u8>、Display for Box<Local> 通过,Display for Vec<Local> 报 E0117);blanket 实现与具体实现冲突 E0119;上游将来可能添加实现的提示;newtype 与自定义 trait 两种绕开办法。',
    '孤儿规则和一致性是 Rust trait 系统里最「反直觉」的两条限制。这篇不背规则,而是把各种组合都编译一遍,让编译器自己说明:什么能写、什么不能写、为什么连「看起来没冲突」的实现也会被拒绝。',
    [('E0117', '外部 trait + 外部类型的错误'), ('E0119', '实现重叠的错误,含「upstream crates may add a new impl」的提示'), ('fundamental', 'Box<Local> 可以而 Vec<Local> 不行的原因(Box 是 #[fundamental])')],
    [('孤儿规则', '<p>newtype 的做法见<a href="rust-newtype-pattern.html">Newtype 模式</a>。</p>'), ('一致性', None), ('上游可能新增实现', '<p>blanket 实现的更多例子见<a href="rust-blanket-impl.html">Blanket Implementation</a>。</p>'), ('绕开的办法', None)],
    steps, [ENV_U + '。错误信息为原样的 rustc 1.98.1 输出', '没有验证:#[fundamental] 属性的完整列表(只测了 Box 与 Vec 的对比)、negative impls、specialization、多 crate 场景下的孤儿规则(这里只有单 crate)、依赖升级导致的一致性破坏'], '孤儿规则')
