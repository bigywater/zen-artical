from lib import *
S = SS('u126')
R = J('u126'); B = R['bodies']; AL = R['alias']; DF = R['defs']; Z = {r[0]: (r[1], r[2]) for r in R['sizes']}
steps = [
    step(f"-Z print-mono-items 让 rustc 自己列出单态化出来的每个实例:largest<T> 被 i32、f64、u8、char 各实例化一次(4 个 MONO_ITEM fn largest::<…>),连同每个类型 PartialOrd::gt 的实现(4 个,Internal)和 use_all,共 {len(R['items'])} 个。每用一种具体类型,编译器就生成一份独立的函数。", t=tl(S(1)), done=lidx(S(1), 'largest::<char>', 'largest::<f64>', 'largest::<i32>', 'largest::<u8>'), kv=KV([['largest<T>', '4 个实例(i32/f64/u8/char)'], ['实例总数', str(len(R['items']))]], ['largest<T>'])),
    step(f"每个实例是为那个类型专门生成的机器码(aarch64,-O):largest::<f64> 是 {' ; '.join(B['f64'])};largest::<i32> 是 {' ; '.join(B['i32'])};largest::<u32> 是 {' ; '.join(B['u32'])}。同样的源码,f64 用浮点比较 fcmp/fcsel,整数用 cmp/csel,而且有符号 i32 用 gt,无符号 u32 用 hi —— 泛型代码按具体类型选择指令。", t=tl(S(2)), done=lidx(S(2), 'largest::<f64>', 'largest::<i32>', 'largest::<u32>'), kv=KV([['f64', 'fcmp + fcsel'], ['i32', 'cmp + csel gt(有符号)'], ['u32', 'cmp + csel hi(无符号)']], ['u32'])),
    step(f"完全相同的实例会被合并:add_pair<T> 对 i32、u32、f32 实例化,汇编里 add_pair<u32> 变成 add_pair<i32> 的别名(__R…add_pairm = …add_pairl),add_u32 也成了 add_i32 的别名(_add_u32 = _add_i32);只有 f32 有独立的函数体。有符号与无符号的加法是同一条 add 指令,LLVM 发现后合并。", t=tl(S(3)), done=lidx(S(3), '别名'), kv=KV([['add_pair<u32>', '= add_pair<i32>(别名)'], ['add_pair<f32>', '独立函数']], ['add_pair<u32>'])),
    step(f"代码体积:同一个泛型函数(describe<T: Debug>,里面一个 format!)实例化 1、4、16 种类型,目标文件 {Z[1][0]:,}、{Z[4][0]:,}、{Z[16][0]:,} 字节;换成 &dyn Debug 版本是 {Z[1][1]:,}、{Z[4][1]:,}、{Z[16][1]:,} 字节。在这个例子里两者几乎一样:每个类型的包装函数(g0…g15)和 Debug 的实现占了大头,泛型函数体本身很小,所以单态化的「代码膨胀」不是必然的,要看函数体多大、实例化多少次。", t=tl(S(4)), done=lidx(S(4), '实例数'), b=bars([['泛型 ×1', Z[1][0], f'{Z[1][0]:,}'], ['泛型 ×16', Z[16][0], f'{Z[16][0]:,}'], ['dyn ×16', Z[16][1], f'{Z[16][1]:,}']], Z[16][0], done=[0, 1, 2]), kv=KV([['泛型 1 / 4 / 16', f'{Z[1][0]:,} / {Z[4][0]:,} / {Z[16][0]:,}'], ['dyn 1 / 4 / 16', f'{Z[1][1]:,} / {Z[4][1]:,} / {Z[16][1]:,}']], ['泛型 1 / 4 / 16'])),
]
A = mkart('u126', 126, 'Rust,单态化,泛型,代码生成,真实验证,动画演示',
    f'用 -Z print-mono-items 与汇编验证单态化生成的代码:largest<T> 得到 i32/f64/u8/char 4 个实例;f64 是 fcmp+fcsel、i32 是 cmp+csel gt、u32 是 csel hi;相同指令的 add_pair<u32> 与 add_pair<i32> 被合并成别名;泛型与 &dyn 版本 16 个类型的目标文件 {Z[16][0]:,} 对 {Z[16][1]:,} 字节。',
    '“泛型会生成多份代码”具体是什么样?每份有什么不同?什么情况下会被合并?体积到底涨多少?这篇让 rustc 列出单态化实例,读汇编,再量目标文件大小。',
    [(f'{len(R["items"])} 个', '这个小例子里的单态化实例总数'), ('4 份', 'largest<T> 的实例数(每个类型一份)'), (f'{Z[16][0]:,} 对 {Z[16][1]:,}', '16 种类型的泛型版与 &dyn 版目标文件字节数')],
    [('实例列表', '<p>单态化的基础见<a href="rust-monomorphization.html">泛型单态化</a>;输出使用 RUSTC_BOOTSTRAP=1 -Z print-mono-items。</p>'), ('每个实例的机器码', None), ('相同代码被合并', '<p>函数合并是 LLVM 的优化,在 -O 下发生。</p>'), ('代码体积', '<p>静态与动态分发的耗时对比见<a href="rust-static-vs-dynamic-dispatch.html">静态分发与动态分发性能对比</a>。</p>')],
    steps, [ENV_U + '。汇编为 aarch64', '没有验证:share-generics 在 debug 下跨 crate 复用实例、更大的泛型函数体(膨胀会更明显)、codegen-units 对合并的影响、x86_64 上的指令选择、-C link-dead-code 与 GC sections 对最终二进制的影响'], '单态化生成的代码')
