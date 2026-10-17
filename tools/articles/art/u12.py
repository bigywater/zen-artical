from lib import *
S = SS('u12')
steps = [
    step("类型别名 type Meters = f64 不创建新类型:speed(d: Meters, t: Seconds) 把两个参数写反 speed(s, m),编译器一句话没说,算出 0.0958 而不是 10.44。把 Meters 与 Seconds 改成元组结构体(newtype)后,同样的错误调用被拦下:error[E0308]: arguments to this function are incorrect,还建议「swap these arguments」。", t=tl(S(1)), mark=lidx(S(1), 'error[E0308]', '编译器没有报任何错误'), kv=KV([['type 别名', '不报错,结果错'], ['newtype', 'E0308']], ['newtype'])),
    step("newtype 是零成本的:size_of::<f64>() 与 size_of::<Meters>() 都是 8 字节;add_raw(f64) 与 add_new(Meters) 两个函数 -O 编译后只有 fadd、ret 两条指令,LLVM 甚至把其中一个合并成另一个的别名。类型安全完全是编译期的。", t=tl(S(2)), done=lidx(S(2), 'size_of', '共同的机器码'), kv=KV([['大小', '8 = 8 字节'], ['机器码', 'fadd + ret,完全相同']], ['机器码'])),
    step("孤儿规则:impl fmt::Display for Vec<String> 报 error[E0117]: only traits defined in the current crate can be implemented for types defined outside of the crate(trait 与类型都不是本 crate 的),并提示「define and implement a trait or new type instead」。用 struct Wrapper(Vec<String>) 包一层再实现 Display 就合法,输出 w = [hello, world]。", t=tl(S(3)), mark=lidx(S(3), 'error[E0117]'), done=lidx(S(3), 'w = ['), kv=KV([['外部 trait + 外部类型', 'E0117'], ['newtype 包一层', '合法']], ['newtype 包一层'])),
    step("newtype 包住之后,默认连内部类型的方法也没有了:n.len() 报 error[E0599]: no method named `len` found for struct `Names`(并指出字段 0 里有同名方法)。为 Names 实现 Deref<Target = Vec<String>> 后,len()、first()、iter() 都能直接调用:len = 2,first = Some(\"a\"),拼接 = a+b。", t=tl(S(4)), mark=lidx(S(4), 'error[E0599]'), done=lidx(S(4), 'len = 2'), kv=KV([['不实现 Deref', 'E0599'], ['实现 Deref', '方法转发']], ['实现 Deref'])),
]
A = mkart('u12', 12, 'Rust,Newtype,类型安全,孤儿规则,真实验证,动画演示',
    '用真实编译验证 newtype:type 别名不创建新类型(参数写反不报错,算出 0.0958),newtype 报 E0308 并建议交换参数;newtype 与 f64 同为 8 字节且机器码相同;用 newtype 绕过孤儿规则 E0117 实现 Display;用 Deref 转发内部类型的方法。',
    'Newtype 是 Rust 里最轻的抽象:一个只有一个字段的元组结构体。它能让「米」和「秒」不再互相混淆,能让你为别人的类型实现别人的 trait。这篇用真实的编译结果逐条验证它的好处、零成本,以及它带来的小麻烦(失去内部类型的方法)和解法(Deref)。',
    [('E0308', 'newtype 把 speed(秒, 米) 的错误调用拦在编译期(type 别名拦不住)'), ('8 = 8', 'f64 与 struct Meters(f64) 的字节数,机器码相同'), ('E0117', '直接为 Vec<String> 实现 Display 违反孤儿规则')],
    [('别名与 newtype', None), ('零成本', '<p>「零成本抽象」的更多例子见<a href="rust-zero-cost-abstraction.html">Zero-Cost Abstraction</a>。</p>'), ('绕过孤儿规则', '<p>孤儿规则本身见<a href="rust-orphan-rule-coherence.html">Trait 实现冲突与孤儿规则</a>。</p>'), ('方法转发与 Deref', '<p>为所有 newtype 都实现 Deref 并不总是好主意(它让内部类型的方法全部暴露出来,削弱了封装);这里只验证了它能转发,没有讨论取舍。</p>')],
    steps, [ENV_U + '。汇编用 --emit=asm -O 生成,目标 aarch64-apple-darwin', '没有验证:derive_more 等 crate 简化 newtype 的样板、Deref 对自动解引用与方法解析顺序的影响、#[repr(transparent)] 与 FFI'], 'newtype')
