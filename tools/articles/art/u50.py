from lib import *
S = SS('u50')
steps = [
    step("TryFrom 是「可能失败」的转换。数值上与 as 对比:300i32 as u8 悄悄变成 44、-1 as u8 变成 255、256 as u8 变成 0;u8::try_from 则返回 Err(TryFromIntError(PosOverflow))、Err(NegOverflow)、Err(PosOverflow),只有 200、255 返回 Ok。i32::try_from(3_000_000_000u64)、u32::try_from(-5i64) 同样是 Err;300i32.try_into::<u8>() 也是。", t=tl(S(1)), done=lidx(S(1), 'Ok(200)', 'Ok(255)'), mark=lidx(S(1), 'Err(TryFromIntError'), kv=KV([['300 as u8', '44(悄悄截断)'], ['u8::try_from(300)', 'Err(PosOverflow)']], ['u8::try_from(300)'])),
    step("为自己的类型实现 TryFrom<i32> for Port:校验负数、超出 u16、保留端口(< 1024),每种失败有自己的错误:8080 → Ok(Port(8080));-1 → Err(Negative);70000 → Err(TooBig(70000));80 → Err(Reserved(80));443.try_into() 同样走这个实现,得 Err(Reserved(443))。实现 TryFrom 之后自动得到 TryInto。", t=tl(S(2)), done=lidx(S(2), 'Ok(Port'), mark=lidx(S(2), 'Err('), kv=KV([['TryFrom<i32> for Port', '带校验与自定义错误'], ['TryInto', '自动获得']], ['TryFrom<i32> for Port'])),
    step("无损转换也有 TryFrom(自动得到):u64::try_from(5u32) 返回 Result<u64, Infallible>,是 Ok(5)。Infallible 是一个没有值的类型(size_of 为 0),说明「这个错误永远不会发生」,所以 Err 分支可以用 match never {} 排除。", t=tl(S(3)), done=lidx(S(3), 'Ok(5)', '一定成功'), kv=KV([['u32 → u64', 'try_from 的 Error = Infallible'], ['size_of::<Infallible>()', 0]], ['u32 → u64'])),
    step("切片转数组也是 TryFrom:bytes[..4].try_into() 得到 [u8; 4]([12, 34, 56, 78],大端 u32 = 0x12345678);5 个字节转 [u8; 4] 返回 Err(TryFromSliceError(()))。长度不符是运行时才知道的,所以用 TryFrom 而不是 From。", t=tl(S(4)), done=lidx(S(4), '前 4 个字节'), mark=lidx(S(4), 'TryFromSliceError'), kv=KV([['&[u8] → [u8; 4]', 'TryFrom,长度不符则 Err']], ['&[u8] → [u8; 4]'])),
]
A = mkart('u50', 50, 'Rust,TryFrom,TryInto,类型转换,真实验证,动画演示',
    '用真实运行验证 TryFrom:数值转换越界返回 Err(PosOverflow / NegOverflow),而 as 会悄悄截断(300 as u8 = 44);自己的类型 Port 实现 TryFrom<i32> 带多种校验;无损转换的 TryFrom 错误类型是 Infallible(0 字节);切片转 [u8; 4] 长度不符返回 TryFromSliceError。',
    '上一篇的 From 只处理「一定成功」的转换。需要处理失败时用 TryFrom。这篇用对比表验证它与 as 的差别、怎么为自己的类型写带校验的转换、无损转换里那个看起来奇怪的 Infallible,以及切片转定长数组这个常见场景。',
    [('44 vs Err', '300i32 as u8 悄悄得到 44,u8::try_from(300) 返回 Err'), ('Infallible', '无损转换的 TryFrom 错误类型,0 字节,永远不会发生'), ('TryFromSliceError', '切片长度与数组长度不符')],
    [('数值转换', '<p>as 转换的更多规则见<a href="rust-primitive-types-inference.html">基本类型与类型推断</a>。</p>'), ('自己的类型', None), ('Infallible', '<p>无损转换的 From 见<a href="rust-from-into-conversion.html">From、Into 与类型转换</a>。</p>'), ('切片转数组', None)],
    steps, [ENV_U, '没有验证:TryFrom 与 FromStr(parse)的取舍、TryFrom<&str>、Infallible 与 never 类型 ! 的关系(! 仍不稳定)、num 类 crate 的 NumCast'], 'TryFrom')
