from lib import *
S = SS('u24')
steps = [
    step("只有一个输入引用时,返回的引用自动借自它(省略规则):first_word(s: &str) -> &str 返回 text 的前一个词(first_word = hello)。但返回值与 text 绑在一起:在 w 还要使用时 drop(text),报 error[E0505]: cannot move out of `text` because it is borrowed。", t=tl(S(1)), mark=lidx(S(1), 'error[E0505]'), done=lidx(S(1), 'first_word = hello'), kv=KV([['返回值借自', '唯一的输入引用'], ['提前 drop 被借的值', 'E0505']], ['提前 drop 被借的值'])),
    step("方法里有 &self 又有别的引用参数时,省略规则让返回值借自 self:pick(&self, _other: &str) -> &str。调用时传入的临时参数 tmp 在内层块里先死,但返回值 n 借自 c,不受影响,输出 n = prod。", t=tl(S(2)), done=lidx(S(2), 'n = prod'), kv=KV([['有 &self', '返回值借自 self'], ['其它参数先死', '不影响返回值']], ['有 &self'])),
    step("不能返回指向函数自己拥有的数据的引用:把局部 String 的 as_str() 返回,报 error[E0515]: cannot return value referencing local variable `s`;把按值传入的参数 s: String 的 &s 返回(声明为 &'static str 也一样),报 error[E0515]: cannot return reference to function parameter `s`。函数结束时它们都会被释放。", t=tl(S(3)), mark=lidx(S(3), 'error[E0515]'), kv=KV([['引用局部变量', 'E0515'], ['引用按值参数', 'E0515']], ['引用局部变量'])),
    step("返回借自集合的引用,生命周期绑在集合上:find<'a>(v: &'a [String], key: &str) -> Option<&'a String> 的返回值借自 v,所以 key 在内层块里先死没关系,输出 Some(\"bob\");但如果是集合 names 在内层块里先死、返回值在外面使用,就报 error[E0597]: `names` does not live long enough。", t=tl(S(4)), mark=lidx(S(4), 'error[E0597]'), done=lidx(S(4), 'Some("bob")'), kv=KV([['key 先死', '没关系'], ['集合先死', 'E0597']], ['集合先死'])),
    step("返回 &'static str:字符串字面量和 static 变量活在整个程序运行期间,可以安全返回:greeting(flag) 的 flag 早已出了作用域,返回的字符串仍然有效,输出「您好 全局名字」。", t=tl(S(5)), done=lidx(S(5), '您好'), kv=KV([["&'static", '字面量与 static 变量']], ["&'static"])),
]
A = mkart('u24', 24, 'Rust,生命周期,引用,E0515,真实验证,动画演示',
    '用真实编译验证函数返回引用的各种情形:单个输入引用时自动借自它(提前 drop 被借值报 E0505);方法里返回值借自 &self、其它参数先死无妨;返回指向局部变量或按值参数的引用报 E0515;返回借自集合的引用,集合先死报 E0597;返回 \'static 字面量。',
    '「函数能不能返回引用」是写 Rust 时最常撞上的编译错误之一。这篇把五种典型情形逐个编译:什么时候自动成立、返回值究竟借自哪个参数、哪些写法一定不行,以及为什么字面量永远可以。',
    [('E0515', '返回指向局部变量或按值参数的引用'), ('借自 self', '有 &self 时返回值默认借自 self'), ("'static", '字面量与 static 变量可以安全返回')],
    [('单个输入引用', None), ('&self 与其它参数', None), ('不能返回局部数据的引用', None), ('借自集合', None), ("返回 &'static", '<p>生命周期标注的含义见<a href="rust-lifetime-annotations.html">生命周期标注到底描述什么</a>,省略规则见<a href="rust-lifetime-elision.html">生命周期省略规则</a>。</p>')],
    steps, [ENV_U + '。错误信息为原样的 rustc 1.98.1 输出', '没有验证:返回 impl Trait + \'a、返回 Box<dyn Trait + \'a>、迭代器适配器的返回生命周期、async fn 返回借用'], '函数返回引用')
