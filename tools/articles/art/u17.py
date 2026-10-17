from lib import *
R = J('u17'); S = SS('u17')
yes = [t for t, ok in R['rows'] if ok]; no = [t for t, ok in R['rows'] if not ok]
b = [l for l in R['bench'].strip().split('\n')]
steps = [
    step("Copy 类型赋值后两个变量都能用:let a = 5; let b = a; 输出 a = 5, b = 5;元组 (1, 2.5) 也一样(p 与 q 都能打印),没有任何移动。", t=tl(S(1)), done=lidx(S(1), 'a =', 'p ='), kv=KV([['i32、(i32, f64)', '赋值后原变量仍可用']], ['i32、(i32, f64)'])),
    step("哪些类型是 Copy(对每个类型编译一次 fn needs_copy<T: Copy>() 判断):是 —— " + '、'.join(yes) + "。否 —— " + '、'.join(no) + "。规律:所有标量、不可变引用、由 Copy 组成的元组与数组、函数指针是 Copy;任何拥有堆资源(String、Vec、Box、Rc)、可变引用 &mut、内部可变的 Cell,以及 Range 都不是。", t=tl(S(2)), done=lidx(S(2), '是 '), mark=lidx(S(2), '否 '), kv=KV([['Copy', f'{len(yes)} 种(标量、&T、元组、数组…)'], ['非 Copy', f'{len(no)} 种(String、Vec、&mut、Cell、Range…)']], ['非 Copy'])),
    step("#[derive(Copy)] 必须同时 derive(Clone):只写 Copy 报 error[E0277]: the trait bound `P: Clone` is not satisfied(Copy 的定义要求 Clone,建议加 #[derive(Clone)])。Copy 与 Drop 互斥:给 Copy 类型实现 Drop 报 error[E0184]: the trait `Copy` cannot be implemented for this type; the type has a destructor。", t=tl(S(3)), mark=lidx(S(3), 'error[E0277]', 'error[E0184]'), kv=KV([['Copy 不带 Clone', 'E0277'], ['Copy + Drop', 'E0184']], ['Copy + Drop'])),
    step("Copy 是按位复制,成本随大小增长:release 构建下每次赋值一个 [u8; N]:N = 16 约 1 ns,N = 4096 约 129 ns,N = 1 MiB 约 20,866 ns(≈ 21 µs)。小类型的 Copy 几乎免费,但大数组如果标成 Copy,每次传值都是一次 memcpy —— 数据大时更适合传引用。", t=tl(S(4)), mark=lidx(S(4), '1048576'), b=bars([['[u8; 16]', 1, '1 ns'], ['[u8; 4096]', 129, '129 ns'], ['[u8; 1 MiB]', 20866, '20,866 ns']], 21000, mark=[2], done=[0, 1]), kv=KV([['16 字节', '约 1 ns'], ['1 MiB', '约 21 µs']], ['1 MiB'])),
]
A = mkart('u17', 17, 'Rust,Copy,Clone,所有权,真实验证,动画演示',
    '用真实编译与计时验证 Copy:对 21 种类型逐个判断是否 Copy(标量、&T、元组、数组、函数指针是;String、Vec、Box、Rc、&mut、Cell、Range 不是);derive(Copy) 必须带 Clone(E0277)、与 Drop 互斥(E0184);按位复制的成本随大小增长([u8;16] 约 1 ns,1 MiB 约 21 µs)。',
    '上一篇说赋值会移动,但 let b = a 对 i32 就没有移动 —— 因为它是 Copy。这篇把「哪些类型是 Copy」直接编译出来,再验证 Copy 的两个限制(必须带 Clone、不能有 Drop)和 Copy 的真实代价:它就是一次按位复制。',
    [('21 种', '逐个编译判断是否 Copy 的类型数'), ('E0184', 'Copy 类型实现 Drop 的错误'), ('≈ 21 µs', '复制一个 1 MiB 的 [u8; N](release)')],
    [('Copy 类型', None), ('哪些是 Copy', None), ('derive(Copy) 的限制', None), ('Copy 的成本', '<p>计时用 <code>std::hint::black_box</code> 防止编译器把复制优化掉,数字是单次运行的结果;小到 1 ns 的值已经接近计时本身的精度。</p>')],
    steps, [ENV_U + '。计时使用 release 构建与 Instant,数字每次运行会有抖动', '没有验证:Copy 在泛型代码里的单态化代价、闭包是否 Copy(取决于捕获,这里没有测)、Copy 对 ABI(寄存器传参还是栈传参)的影响、clone 对 Copy 类型是否被优化成复制'], 'Copy')
