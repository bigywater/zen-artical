from lib import *
S = SS('u43')
steps = [
    step("关联类型:trait Container 里声明 type Item,每个实现者确定它(Words 的 Item 是 String,Nums 的 Item 是 i32)。泛型函数用 C::Item 引用它:show 对两种容器都能用,输出 size=2 first=Some(\"a\") 与 size=3 first=Some(7)。", t=tl(S(1)), done=lidx(S(1), 'size='), kv=KV([['type Item', '由实现者决定'], ['引用', 'C::Item']], ['type Item'])),
    step("与泛型参数的 trait 对比:trait From2<T> 可以为同一个类型实现多次(N 同时实现 From2<i64> 与 From2<String>),调用 n.conv() 必须用类型标注来选(let a: i64 = …),不写就报 error[E0283]: type annotations needed(multiple `impl`s satisfying `N: From2<_>` found)。关联类型的 trait 一个类型只能实现一次:再写一个 impl Container for N 报 error[E0119]: conflicting implementations of trait `Container` for type `N`。", t=tl(S(2)), mark=lidx(S(2), 'error[E0283]', 'error[E0119]'), done=lidx(S(2), '5 5'), kv=KV([['泛型参数 trait', '可实现多次,要消歧(E0283)'], ['关联类型 trait', '只能实现一次(E0119)']], ['关联类型 trait'])),
    step("在约束里写关联类型的几种方式:Iterator<Item = u32> 指定具体类型(sum_all 输出 6);where I: Iterator, I::Item: Debug 对关联类型再加约束;Add<Output = T> 要求运算结果还是 T(add_twice(2) = 4,add_twice(1.5) = 3);<T as Add>::Output 是完整路径写法(i32 + i32 的 Output 是 i32)。它也解释了 1 + 2.0 为什么不行:error[E0277]: cannot add a float to an integer。", t=tl(S(3)), mark=lidx(S(3), 'error[E0277]'), done=lidx(S(3), '6', '4 3', 'Output'), kv=KV([['Iterator<Item = u32>', '指定关联类型'], ['I::Item: Debug', '约束关联类型']], ['Iterator<Item = u32>'])),
    step("标准库里到处都是关联类型:vec::IntoIter<u8> 的 Item 是 u8;Box<String> 的 Deref::Target 是 String、String 的 Target 是 str;String + &str 的 Add::Output 是 String。用 std::any::type_name 打印的就是编译器解析出的真实类型。", t=tl(S(4)), done=lidx(S(4), '='), kv=KV([['Iterator::Item', '迭代出的元素类型'], ['Deref::Target', '解引用得到的类型'], ['Add::Output', '运算结果类型']], ['Deref::Target'])),
]
A = mkart('u43', 43, 'Rust,关联类型,Trait,泛型,真实验证,动画演示',
    '用真实编译验证关联类型:type Item 由实现者确定;与泛型参数 trait 的区别(后者可多次实现但调用要消歧 E0283,前者一个类型只能实现一次 E0119);Iterator<Item = u32>、I::Item: Debug、Add<Output = T> 的约束写法;标准库里的 Item、Target、Output 用 type_name 打印验证。',
    '关联类型和泛型参数都能让 trait「带一个类型」,但它们的语义不同:关联类型是「这个类型实现 trait 时确定的一个类型」。这篇用编译器的报错把两者的区别摆出来,再看约束里的几种写法和标准库里最常见的三个关联类型。',
    [('E0119', '关联类型的 trait 对同一类型只能实现一次'), ('E0283', '泛型参数的 trait 多次实现后调用要标注类型'), ('Item / Target / Output', '标准库里最常见的三个关联类型')],
    [('定义与使用', None), ('关联类型 vs 泛型参数', None), ('约束里的写法', None), ('标准库中的例子', '<p>更高一层的泛型关联类型(GAT)见<a href="rust-generic-associated-type.html">Generic Associated Type</a>;迭代器的 Item 见<a href="rust-iterator-trait.html">Iterator Trait</a>。</p>')],
    steps, [ENV_U + '。错误信息为原样的 rustc 1.98.1 输出', '没有验证:关联类型的默认值(不稳定)、关联类型与关联常量的组合、dyn Trait<Item = T> 的对象类型写法的细节'], '关联类型')
