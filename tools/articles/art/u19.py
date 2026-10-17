from lib import *
S = SS('u19')
steps = [
    step("&T 是只读借用,&mut T 是可写借用:read(&x) 返回 20,add_one(&mut x) 后 x 变成 11。通过只读引用修改被拒绝:fn bad(n: &i32) { *n += 1; } 报 error[E0594]: cannot assign to `*n`, which is behind a `&` reference,并建议改成可变引用。", t=tl(S(1)), mark=lidx(S(1), 'error[E0594]'), done=lidx(S(1), 'read(&x)', 'add_one'), kv=KV([['&T', '只读'], ['&mut T', '可写']], ['&mut T'])),
    step("同一时刻两条规则:已有 &s 时再取 &mut s,报 error[E0502]: cannot borrow `s` as mutable because it is also borrowed as immutable;同时取两个 &mut s,报 error[E0499]: cannot borrow `s` as mutable more than once at a time。要么多个只读,要么一个可写。", t=tl(S(2)), mark=lidx(S(2), 'error[E0502]', 'error[E0499]'), kv=KV([['& 与 &mut 同时', 'E0502'], ['两个 &mut', 'E0499']], ['两个 &mut'])),
    step("借用只持续到最后一次使用为止:let a = &s; 用完 a 之后(打印 a = hi),再取 &mut s 并 push('!') 是允许的(输出 b = hi!)。不需要等到块结束 —— 编译器看的是引用实际用到哪里(NLL,见后面的一篇)。", t=tl(S(3)), done=lidx(S(3), 'a = hi', 'b = hi!'), kv=KV([['a 最后一次使用之后', '可以再取 &mut']], ['a 最后一次使用之后'])),
    step("把 &mut 传给函数不会「用掉」它:inc(r); inc(r); *r += 10; 都合法,最后 x = 12 —— 编译器自动做了「重借用」(reborrow),每次传入的是 &mut *r。但如果显式写 let moved = r;,这是移动:之后再用 r 报 error[E0382]: borrow of moved value: `r`(&mut 引用不是 Copy)。", t=tl(S(4)), mark=lidx(S(4), 'error[E0382]'), done=lidx(S(4), 'x = 12'), kv=KV([['传给函数', '隐式重借用'], ['let moved = r', '移动,r 失效']], ['传给函数'])),
]
A = mkart('u19', 19, 'Rust,借用,&mut,重借用,真实验证,动画演示',
    '用真实编译验证借用的基本规则:&T 只读、&mut T 可写,通过 & 修改报 E0594;同一时刻要么多个 &T 要么一个 &mut T(E0502、E0499);借用到最后一次使用为止;传给函数时 &mut 自动重借用,显式赋值则是移动(E0382)。',
    '不可变借用与可变借用是所有权之后的第二块基石。这篇用真实的编译器报错把规则列清楚:能写什么、什么时候冲突、借用到哪里结束,以及一个容易被忽略的细节 —— &mut 传给函数时的重借用。',
    [('E0502 / E0499', '读写冲突 / 两个可变借用的错误码'), ('最后一次使用', '借用在最后一次使用处结束,不是块结束'), ('reborrow', '把 &mut 传给函数时自动重借用,r 之后仍可用')],
    [('& 与 &mut', None), ('两条规则', '<p>规则为什么成立:共享多个读者安全(见<a href="rust-multiple-shared-borrows.html">多个不可变借用为什么可以共存</a>),可变借用必须独占(见<a href="rust-exclusive-mut-borrow.html">可变借用为什么不能同时存在</a>)。</p>'), ('借用持续多久', '<p>编译器按引用的最后一次使用来计算借用范围,见<a href="rust-nll.html">NLL 非词法生命周期</a>。</p>'), ('重借用', None)],
    steps, [ENV_U + '。错误信息为原样的 rustc 1.98.1 输出', '没有验证:两阶段借用(v.push(v.len()) 为何合法)、对结构体不同字段的同时可变借用、闭包捕获时的借用、RefCell 把检查推迟到运行时的行为(见其它文章)'], '借用规则')
