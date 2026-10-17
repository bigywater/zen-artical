from lib import *
S = SS('u48')
steps = [
    step("blanket impl 为「所有满足约束的类型」一次性实现 trait:impl<T: Display> Loud for T 之后,&str、i32、f64 和自定义的 Name(只要实现了 Display)都有 loud() 方法,输出 HELLO!!! 42!!! 3.5!!! RUST!!!。没实现 Display 的 NoDisplay 调用 loud() 报 error[E0599]: `NoDisplay` doesn't implement `std::fmt::Display`(trait bound was not satisfied)。", t=tl(S(1)), mark=lidx(S(1), 'error[E0599]'), done=lidx(S(1), 'HELLO!!!'), kv=KV([['满足约束的类型', '自动拥有方法'], ['不满足', 'E0599']], ['满足约束的类型'])),
    step("标准库里最典型的两个 blanket impl:只实现 Display 就免费得到 to_string()(36.6°C);只实现 From<Km> for Meters 就免费得到 Into(let m: Meters = Km(2.5).into(),得 2500 米)。反过来只实现 Into 不会得到 From:Meters::from(Km(1.0)) 报 error[E0308]: mismatched types,并建议「call `Into::into` on this expression」—— 所以实现转换时要实现 From 而不是 Into。", t=tl(S(2)), mark=lidx(S(2), 'error[E0308]'), done=lidx(S(2), '36.6', '2500 米'), kv=KV([['Display → ToString', 'blanket impl'], ['From → Into', 'blanket impl(反过来没有)']], ['From → Into'])),
    step("扩展 trait(extension trait)模式:trait StrExt 配合 impl<T: AsRef<str> + ?Sized> StrExt for T,就给 &str、String、Cow<str> 一起加上了 shout()/word_count():\"a b\".shout() = A B!,String 的 shout 与 word_count 得 HELLO RUST WORLD! 与 3,Cow 的得 COW STR! 与 2。", t=tl(S(3)), done=lidx(S(3), '&str:', 'String:', 'Cow:'), kv=KV([['StrExt', '一份实现覆盖 &str / String / Cow']], ['StrExt'])),
    step("引用也需要自己的实现:talk<S: Speak>(s: S) 只给 Dog 实现了 Speak 时,talk(&Dog) 报 error[E0277]: the trait bound `&Dog: Speak` is not satisfied(&Dog 是另一个类型)。加上 impl<T: Speak + ?Sized> Speak for &T 与 for Box<T> 这两个 blanket impl 后,talk(Dog)、talk(&Dog)、talk(Box::new(Dog)) 都输出「汪」。标准库对 Display、Iterator 等常用 trait 都做了这类转发实现。", t=tl(S(4)), mark=lidx(S(4), 'error[E0277]'), done=lidx(S(4), '汪 汪 汪'), kv=KV([['&Dog: Speak', '默认不满足'], ['impl Speak for &T', '让引用也满足']], ['impl Speak for &T'])),
]
A = mkart('u48', 48, 'Rust,Blanket Implementation,Trait,扩展trait,真实验证,动画演示',
    '用真实编译验证 blanket impl:impl<T: Display> Loud for T 使所有 Display 类型获得 loud(),不满足报 E0599;标准库的 Display → ToString、From → Into(反过来没有,E0308);扩展 trait 给 &str/String/Cow 加方法;为 &T 与 Box<T> 补充转发实现。',
    'blanket impl 是 Rust 里「为一类类型一次性实现 trait」的办法,标准库大量使用它:ToString、Into 都是。这篇验证它的工作方式、两个最典型的标准库例子、扩展 trait 模式,以及一个常被忽略的细节 —— 引用类型要不要单独实现。',
    [('to_string()', '只实现 Display 就免费得到'), ('Into', '只实现 From 就免费得到;反过来没有(E0308)'), ('&T', '引用要单独写转发 impl 才满足 trait 约束')],
    [('blanket impl', '<p>与孤儿规则的冲突限制见<a href="rust-orphan-rule-coherence.html">Trait 实现冲突与孤儿规则</a>。</p>'), ('标准库里的例子', '<p>From / Into 的详细用法见<a href="rust-from-into-conversion.html">From、Into 与类型转换</a>。</p>'), ('扩展 trait', None), ('引用的转发实现', None)],
    steps, [ENV_U + '。错误信息为原样的 rustc 1.98.1 输出', '没有验证:blanket impl 对编译时间与一致性检查的影响、给已有 trait 新增 blanket impl 是否构成破坏性变更、具体 std 里哪些 trait 对 &T 做了转发(只验证了自定义 trait 的转发写法)'], 'blanket impl')
