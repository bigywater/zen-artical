from lib import *
S = SS('u39')
steps = [
    step("Trait Object 让不同类型放进同一个集合:Vec<Box<dyn Shape>> 里装 Circle、Rect、Tri,遍历时按各自的实现调用(圆 3.14、矩形 6.00、三角形 10.00,总面积 19.14)。调用哪个 area 是运行时决定的(动态分发)。", t=tl(S(1)), done=lidx(S(1), '面积', '总面积'), kv=KV([['Box<dyn Shape>', '不同类型放同一个 Vec'], ['分发', '运行时(动态)']], ['分发'])),
    step("dyn Trait 的大小不固定,不能直接放在栈上:let x: dyn T = A; 报 error[E0277]: the size for values of type `dyn T` cannot be known at compilation time(同时有 E0308),必须放在指针后面。指向 dyn 的指针是胖指针:&Circle 之类的普通引用 8 字节,而 &dyn Shape、Box<dyn Shape>、Rc<dyn Shape> 都是 16 字节(数据指针 + vtable 指针);Box<f64> 是 8 字节。", t=tl(S(2)), mark=lidx(S(2), 'error[E0277]', '&dyn Shape', 'Box<dyn Shape>'), kv=KV([['普通引用 / Box<f64>', '8 字节'], ['&dyn / Box<dyn>', '16 字节(数据 + vtable)']], ['&dyn / Box<dyn>'])),
    step("偷看胖指针:把 &dyn Shape 当作两个 usize 读出来。Circle 的两个对象,数据地址不同、vtable 地址相同(同一类型共用一张 vtable);Circle、Big、Unit 三种类型的 vtable 各不相同。用观察到的布局([drop_in_place, size, align, 方法…])从 vtable 里读出 size 与 align:Circle 8/8、Big 40/8、Unit 0/1,与 size_of / align_of 完全一致 —— vtable 记着类型的大小,所以 Box<dyn Trait> 才知道释放多少内存。(布局是实现细节,这里只是观察。)", t=tl(S(3)), mark=lidx(S(3), 'vtable 里读出'), done=lidx(S(3), '数据地址不同', '不同:true'), kv=KV([['同类型', '共用一张 vtable'], ['vtable 里有', 'size、align、drop 与方法指针']], ['同类型'])),
    step("泛型 vs trait 对象的代码量:total_dyn(&dyn Shape) 只生成 1 个函数,A 与 B 的调用都指向它;total_gen<S: Shape> 单态化出 2 个函数(total_gen::<A>、total_gen::<B>)。trait 对象用一次间接调用换取更小的代码、也允许运行时才决定类型。", t=tl(S(4)), mark=lidx(S(4), '调用依次指向'), b=bars([['total_dyn 的函数个数', 1, '1'], ['total_gen 的函数个数', 2, '2']], 3, done=[0, 1]), kv=KV([['&dyn', '1 份代码'], ['泛型', '每个类型 1 份']], ['&dyn'])),
]
A = mkart('u39', 39, 'Rust,Trait Object,动态分发,vtable,真实验证,动画演示',
    '用真实运行与汇编验证 trait object:Vec<Box<dyn Shape>> 运行时按类型分发;dyn 不能直接放栈上(E0277),&dyn / Box<dyn> 是 16 字节胖指针;用 transmute 读出数据指针与 vtable 指针,同类型共用 vtable,vtable 里能读出 size/align(8/8、40/8、0/1);&dyn 版本只生成 1 个函数而泛型生成 2 个。',
    '泛型在编译期选择实现,trait object 在运行时选择。这篇把 dyn Trait 拆开看:它为什么只能放在指针后面、胖指针里装了什么、vtable 里记着什么,以及它和泛型在代码生成上的差别。',
    [('16 字节', '&dyn Trait / Box<dyn Trait> 的大小(数据指针 + vtable 指针)'), ('8 / 40 / 0', '从 vtable 里读出的 Circle / Big / Unit 的 size,与 size_of 一致'), ('1 vs 2', '&dyn 函数与泛型函数(两个类型)生成的函数个数')],
    [('动态分发', None), ('不定大小与胖指针', None), ('vtable 里有什么', '<p>vtable 的布局不是语言保证的稳定接口,这里只是在当前编译器版本上观察。胖指针的更多内容见<a href="rust-trait-object-fat-pointer.html">Trait Object 的胖指针</a>。</p>'), ('与泛型对比', '<p>性能对比见<a href="rust-static-vs-dynamic-dispatch.html">静态分发与动态分发性能对比</a>;哪些 trait 能做成对象见<a href="rust-dyn-object-safety.html">dyn Trait 的对象安全</a>。</p>')],
    steps, [ENV_U + '。vtable 读取依赖当前编译器的内部布局(unsafe,仅用于观察),在其它版本可能失效', '没有验证:dyn Trait + Send、trait upcasting、dyn Any 的向下转型、多个 trait 组合的对象、生命周期对 dyn 的影响(Box<dyn Trait + \'a>)'], 'trait object')
