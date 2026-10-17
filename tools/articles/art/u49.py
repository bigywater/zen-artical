from lib import *
S = SS('u49')
steps = [
    step("From 定义「怎样从 A 构造出我」。标准库为无损转换实现了 From:i64::from(7i32)、f64::from(3u8)、String::from(\"text\")、String::from('c')、Vec::from([1, 2, 3])、Vec::from(\"hi\")、HashMap::from([(\"a\", 1), (\"b\", 2)]) 都能直接用。有损的没有 From:i32::from(5i64) 报 error[E0277]: the trait bound `i32: From<i64>` is not satisfied,u8::from(300u32) 同理(列出 i32 能 From 的只有 bool、i8、i16、u8、u16 等更小的类型)—— 需要失败处理的转换见 TryFrom。", t=tl(S(1)), mark=lidx(S(1), 'error[E0277]'), done=lidx(S(1), '长度'), kv=KV([['无损', 'From'], ['有损(i64 → i32)', '没有 From,E0277']], ['有损(i64 → i32)'])),
    step("为自己的类型实现 From:impl From<ParseIntError> for AppError,函数里 s.parse()? 遇到错误时用 From 自动把 ParseIntError 转成 AppError:\"42\" → Ok(42);\"abc\" → Err(解析失败:invalid digit found in string);\"-5\" → Err(-5 是负数)。这就是 ? 运算符能「自动转换错误类型」的原因。", t=tl(S(2)), done=lidx(S(2), '→ Ok', '→ Err'), kv=KV([['? 遇到 Err', '调用 From::from 转换错误类型']], ['? 遇到 Err'])),
    step("参数里用 impl Into<String>:new_user(\"bob\")(&str)与 new_user(owned)(String)都能传。用计数分配器统计:传 &str 分配 1 次(要新建 String),传 String 分配 0 次 —— String 到 String 的 Into 是恒等转换,直接移动。所以 impl Into<String> 的参数是「调用者有 String 就别浪费」的好办法。", t=tl(S(3)), mark=lidx(S(3), '传 &str'), kv=KV([['传 &str', '分配 1 次'], ['传 String', '分配 0 次']], ['传 String'])),
    step("From 是自反的(From<T> for T),所以 T: Into<f64> 对 f64 自己也成立:total(vec![1u8, 2]) = 3、total(vec![1.5f32, 2.5]) = 4、total(vec![2.5f64, 0.5]) = 3 —— 一个泛型函数同时接受整数、f32、f64。", t=tl(S(4)), done=lidx(S(4), '3 4 3'), kv=KV([['Into<f64>', 'u8、f32、f64 都满足']], ['Into<f64>'])),
]
A = mkart('u49', 49, 'Rust,From,Into,类型转换,真实验证,动画演示',
    '用真实编译与计数分配器验证 From / Into:标准库的无损转换(i64::from(i32)、String::from、Vec::from、HashMap::from)与有损转换没有 From(E0277);为自己的类型实现 From 让 ? 自动转换错误;impl Into<String> 参数传 &str 分配 1 次、传 String 分配 0 次;From 自反。',
    'From 与 Into 是 Rust 里最常见的类型转换 trait。这篇验证它们的边界:标准库认为哪些转换是「无损」可以用 From、? 运算符怎么借 From 转换错误、写 impl Into<String> 参数能省多少分配,以及为什么泛型代码里 T: Into<U> 总是成立。',
    [('E0277', 'i32::from(i64) 这类有损转换没有 From'), ('1 vs 0', '传 &str 与传 String 给 impl Into<String> 参数的堆分配次数'), ('?', '遇到 Err 时通过 From 自动转换错误类型')],
    [('标准库的 From', None), ('自己的类型与 ?', '<p>? 的展开过程见<a href="rust-question-mark-desugar.html">? 运算符展开过程</a>;自定义错误类型见<a href="rust-custom-error-type.html">自定义错误类型</a>。</p>'), ('impl Into 参数', '<p>有可能失败的转换见<a href="rust-try-from.html">TryFrom 与失败转换</a>。</p>'), ('自反性', None)],
    steps, [ENV_U + '。分配次数为 release 构建的单次运行', '没有验证:From<&String> for String、From<Box<str>>、Into 的 where 子句写法的差别、From 实现对类型推断的影响、From<Vec<T>> for Box<[T]> 的分配行为'], 'From 与 Into')
