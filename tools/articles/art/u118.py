from lib import *
import re
S = SS('u118')
R = J('u118')
b = re.search(r'清零\)\s+每次\s+([\d.]+) µs.*\n.*不清零\)\s+每次\s+([\d.]+) µs', R['bench']); bz, bu = b.group(1), b.group(2); br = round(float(bz) / float(bu))
steps = [
    step("安全 Rust 不允许读没初始化的变量:let x: u32; println!(\"{}\", x) 编译期报 error[E0381]: used binding `x` isn't initialized。需要「暂时没初始化」时用 MaybeUninit<T>,它把这件事显式地交给程序员。", t=tl(S(1)), mark=lidx(S(1), 'error[E0381]'), kv=KV([['普通变量', '读未初始化 → E0381'], ['MaybeUninit<T>', '显式的未初始化']], ['MaybeUninit<T>'])),
    step("MaybeUninit<u64> 与 u64 一样大(8 字节)、一样对齐(8);Option<u64> 却要 16 字节 —— MaybeUninit 没有标签,不记录自己是否已初始化,这是程序员要自己负责的事。write(42) 之后 assume_init() 得到 42。", t=tl(S(1)), done=lidx(S(1), 'size_of::<u64>()', 'size_of::<Option<u64>>()', 'write 之后'), kv=KV([['MaybeUninit<u64>', '8 字节,无标签'], ['Option<u64>', '16 字节']], ['MaybeUninit<u64>'])),
    step("逐个初始化数组:[MaybeUninit<String>; 4] 每个槽 write(format!(…)),最后 transmute 成 [String; 4],得到 [\"item-0\", \"item-1\", \"item-4\", \"item-9\"],与安全的 std::array::from_fn 结果相同(true)。能用 from_fn 就用 from_fn;MaybeUninit 用在没有安全写法的场合。", t=tl(S(2)), done=lidx(S(2), '逐个 write', 'from_fn'), kv=KV([['MaybeUninit 数组', '逐个 write 再整体转换'], ['array::from_fn', '安全的等价写法']], ['array::from_fn'])),
    step("MaybeUninit 不负责析构:MaybeUninit<Noisy> write 了值,离开作用域时没有看到 Noisy(1) drop —— 值泄漏了;手动 assume_init_drop() 才打印 Noisy(2) drop;数组只初始化了前 2 个,就只能手动 drop 这 2 个(Noisy(10)、Noisy(11)),不能碰没初始化的槽。", t=tl(S(3)), mark=lidx(S(3), '没有看到 Noisy(1)'), done=lidx(S(3), 'Noisy(2) drop', 'Noisy(10) drop', 'Noisy(11) drop'), kv=KV([['忘记 drop', '泄漏(不是 UB)'], ['部分初始化', '只 drop 已初始化的']], ['忘记 drop'])),
    step(f"省掉清零的好处:创建 1 MiB 缓冲区并只写其中一小部分,vec![0u8; 1 MiB](清零)每次 {bz} µs,Vec::with_capacity + set_len(不清零,MaybeUninit 思路)每次 {bu} µs,约 {br} 倍。这个例子只写了 1/4096 的字节,没写的部分保持未初始化,实际读取之前必须全部写入。", t=tl(S(4)), done=lidx(S(4), 'vec![0u8', 'with_capacity'), b=bars([['vec![0u8; N]', float(bz), f'{bz} µs'], ['with_capacity + set_len', float(bu), f'{bu} µs']], float(bz), cur=[0], done=[1]), kv=KV([['清零', f'{bz} µs'], ['不清零', f'{bu} µs(约 {br}×)']], ['不清零'])),
]
A = mkart('u118', 118, 'Rust,MaybeUninit,未初始化内存,unsafe,真实验证,动画演示',
    f'用真实运行验证 MaybeUninit:普通变量读未初始化报 E0381;MaybeUninit<u64> 8 字节无标签;逐个 write 初始化 [String; 4] 并与 from_fn 对照;MaybeUninit 不自动 drop(泄漏)、部分初始化只能 drop 已初始化的;1 MiB 缓冲区清零 {bz} µs 对不清零 {bu} µs。',
    'Rust 不让你读没初始化的内存,可有时又需要避开清零的成本或逐个构造数组元素。MaybeUninit 就是这个出口。这篇验证它的大小、用法、drop 规则,并量出清零的代价。',
    [('8 字节', 'MaybeUninit<u64> 的大小(没有初始化标志)'), ('不 drop', 'MaybeUninit 离开作用域时对内部值的处理(泄漏)'), (f'{bz} 对 {bu} µs', '1 MiB 缓冲区:清零与不清零的创建耗时')],
    [('为什么需要 MaybeUninit', '<p>unsafe 的边界见<a href="rust-unsafe-boundary.html">unsafe 的安全边界</a>。</p>'), ('逐个初始化数组', None), ('drop 规则', '<p>Drop 的运行规则见<a href="rust-drop-trait.html">Drop Trait 与资源释放</a>。</p>'), ('省掉清零', '<p>vec![0u8; N] 可能走系统的清零分配(calloc),这里没有区分;数字是本机 release 微基准,且只写了极少数字节,仅用于说明量级。读取从未写入的内存是未定义行为,本文没有演示。</p>')],
    steps, [ENV_U, '没有验证:读取未初始化内存的实际后果(UB,不演示)、assume_init_read / assume_init_ref 的用法、Miri 对 MaybeUninit 误用的检测(需要 nightly)、mem::zeroed 对非零合法类型的 UB、with_capacity 的 spare_capacity_mut 接口'], 'MaybeUninit')
