from lib import *
R = J('u5')
S = SS('u5')
steps = [
    step("标量类型的大小(std::mem::size_of)与范围:i8/u8 1 字节、i16/u16 2、i32/u32 4、i64/u64 8、i128/u128 16;isize/usize 在这台 64 位机器上是 8 字节;f32 4、f64 8;bool 1;char 4 字节(是一个 Unicode 标量值,不是一个字节);() 0 字节。", t=tl(S(1)), done=lidx(S(1), 'i32', 'usize', 'char'), kv=KV([['i32 / i64', '4 / 8 字节'], ['char', '4 字节'], ['()', '0 字节']], ['char'])),
    step("没有任何标注时的默认类型:整数字面量 42 是 i32,浮点 2.5 是 f64,true 是 bool,'x' 是 char,\"hi\" 是 &str,[1,2,3] 是 [i32; 3],(1,2.0,'c') 是 (i32, f64, char)。用 std::any::type_name 打印的是编译器真正推断出的类型。", t=tl(S(2)), done=[0], kv=KV([['整数默认', 'i32'], ['浮点默认', 'f64']], ['整数默认'])),
    step("类型可以由后文的使用决定:let a = 5; 之后 takes_u8(a) 把它定成 u8;Vec::new() 之后 push(1.5f32) 把它定成 Vec<f32>。信息不够时编译器拒绝猜:let n = \"5\".parse().unwrap(); 报 error[E0284]: type annotations needed,并建议写 let n: /* Type */ = ...。", t=tl(S(3)), mark=lidx(S(3), 'error[E0284]'), kv=KV([['推断来源', '后文的使用'], ['信息不足', 'E0284 要求标注']], ['信息不足'])),
    step("整数溢出:u8 值 255 加 1 —— debug 构建里普通的 + 在运行时 panic:attempt to add with overflow(退出码 101);release 构建(-O)里同样的代码回绕成 0,不报错。想要确定的行为要显式写:checked_add → None、wrapping_add → 0、saturating_add → 255、overflowing_add → (0, true)。", t=tl(S(4)), mark=lidx(S(4), 'attempt to add', 'n + 1 = 0'), kv=KV([['debug 的 n + 1', 'panic(退出码 101)'], ['release 的 n + 1', '0(回绕)']], ['debug 的 n + 1'])),
    step("as 转换的规则:整数之间按位截断或扩展(300i32 as u8 = 44,-1i32 as u32 = 4294967295,200u8 as i8 = -56);浮点转整数向零取整并饱和(3.99 → 3,-3.99 → -3,1e20 → 2147483647,NaN → 0);u8 as char 得 'A','中' as u32 是 20013,true as i32 是 1。as 不会报错,所以每一次都要想清楚是否会丢信息。", t=tl(S(5)), done=lidx(S(5), 'as '), kv=KV([['300i32 as u8', 44], ['f64::NAN as i32', 0], ['1e20 as i32', '饱和成 i32::MAX']], ['300i32 as u8'])),
]
A = dict(
    n=5, series='rust', tags='Rust,基本类型,类型推断,整数溢出,真实验证,动画演示',
    desc='用真实运行验证基本类型:各整数/浮点/bool/char/() 的字节数与范围;没有标注时的默认类型(i32、f64);类型推断来自后文使用,信息不足报 E0284;整数溢出在 debug 下 panic、release 下回绕及四种显式写法;as 转换的截断与饱和规则。',
    lead='基本类型看起来是最无聊的一章,但很多真实的坑藏在这里:i32 为什么是默认整数、类型推断什么时候放弃、同一份代码在 debug 和 release 下对溢出的反应为什么不同、as 转换到底会丢什么。这篇每条都用真实的编译与运行结果回答。',
    facts=[('4 字节', 'char 的大小(Unicode 标量值),bool 是 1 字节,() 是 0 字节'), ('101 vs 0', '255u8 + 1 在 debug 下 panic(退出码 101),release 下回绕成 0'), ('饱和', 'f64 as i32 对越界值取饱和、NaN 变 0')],
    body=[
        sec('大小与范围', '', term('', blk('u5', 1))),
        sec('默认类型', '', term('', blk('u5', 2))),
        sec('推断与标注', '', term('', blk('u5', 3)), '<p>推断是函数内的局部推断:函数签名里的类型必须写出来。</p>'),
        sec('整数溢出', '', term('', blk('u5', 4)), '<p>debug 与 release 的这个差别来自 <code>overflow-checks</code> 设置(见<a href="rust-cargo-profile.html">Cargo Profile</a>、<a href="rust-debug-vs-release.html">Debug 与 Release 构建差异</a>)。release 下的回绕是定义好的行为,不是未定义行为。</p>'),
        sec('as 转换', '', term('', blk('u5', 5))),
        sec('分步演示', '', demo('基本类型', [('t', 'term', '编译与运行输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_U + '。目标 aarch64-apple-darwin(64 位),isize/usize 为 8 字节;溢出实验用同一份代码分别以默认(debug)与 -O 编译', '没有验证:32 位目标上的 usize、浮点的 NaN 比较与排序、i128 的性能、overflow-checks 在 release 下手动打开的行为、宽度不同的整数混合运算为何必须显式转换'],
)
