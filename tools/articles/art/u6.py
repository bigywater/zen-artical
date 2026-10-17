from lib import *
R = J('u6')
S = SS('u6')
steps = [
    step("数组 [i32; 5] 占 20 字节(5 个 i32),长度是类型的一部分、存在栈上。越界有两层检查:下标在编译期就能确定时直接拒绝编译(error: this operation will panic at runtime,deny(unconditional_panic));运行时才知道的下标则在运行时 panic:index out of bounds: the len is 5 but the index is 7(退出码 101)。", t=tl(S(1)), mark=lidx(S(1), 'will panic at runtime', 'index out of bounds'), kv=KV([['数组大小', '20 字节'], ['越界', '编译期拒绝 / 运行时 panic']], ['越界'])),
    step("切片 &[i32] 是胖指针:size_of::<&i32>() 是 8 字节(一个地址),size_of::<&[i32]>() 是 16 字节(地址 + 长度)。同一个函数 sum(xs: &[i32]) 既接受 &数组、&Vec,也接受它们的子范围 &arr[1..4]、&v[..2];切片 &v[1..3] 的数据地址比 v 的起点大 4 字节(一个 i32)—— 切片不拷贝、不拥有数据。范围写反(3..2)运行时 panic:slice index starts at 3 but ends at 2。", t=tl(S(2)), done=lidx(S(2), 'size_of', 'sum('), mark=lidx(S(2), 'slice index starts'), kv=KV([['&i32', '8 字节'], ['&[i32]', '16 字节']], ['&[i32]'])),
    step("Vec<i32> 本身只有 24 字节(指针、长度、容量各 8),元素在堆上。Vec::new() 时 cap=0,还没有分配堆内存;逐个 push 的容量变化是 0 → 4 → 8 → 16 → 32 → 64(每次翻倍,第一次是 4);with_capacity(100) 一次分够;vec![1,2,3] 再 reserve(10) 得 cap=13;shrink_to_fit 后降回 3。", t=tl(S(3)), done=lidx(S(3), 'push 第'), kv=KV([['Vec 本身', '24 字节'], ['扩容序列', '4 → 8 → 16 → 32 → 64']], ['扩容序列'])),
    step("栈与堆:数组元素的地址与局部变量紧挨着(相差 1 字节,都在栈上);Vec 的元素地址 0x1007…与局部变量(0x16fd…)相差约 18 亿字节(在堆上);但 Vec 的三个字本身(0x16fd72710)仍在栈上。", t=tl(S(4)), mark=lidx(S(4), 'Vec 元素地址'), kv=KV([['数组元素', '栈上'], ['Vec 元素', '堆上'], ['Vec 的三个字', '栈上']], ['Vec 元素'])),
    step("get 返回 Option,不 panic:v.get(1) 是 Some(20),v.get(9) 是 None,范围也一样(get(1..3) 是 Some([20, 30]),get(2..9) 是 None);first()/last() 同理。不确定下标是否合法时,用 get 代替 [ ]。", t=tl(S(5)), done=lidx(S(5), 'Some'), mark=lidx(S(5), 'None'), kv=KV([['v[9]', 'panic'], ['v.get(9)', 'None']], ['v.get(9)'])),
]
A = dict(
    n=6, series='rust', tags='Rust,数组,切片,Vec,真实验证,动画演示',
    desc='真实运行验证数组、切片与 Vec:数组 20 字节在栈上、越界在编译期或运行时被拦截;&[T] 是 16 字节的胖指针、一个函数同时接受数组、Vec 与它们的子范围;Vec 本身 24 字节、容量按 4→8→16→32→64 翻倍;栈与堆地址对比;get 返回 Option。',
    lead='数组、切片和 Vec 是新手最先用到、也最容易混的三样东西。这篇用真实的编译与运行结果分清:谁在栈上、谁在堆上,&[T] 到底是什么,Vec 容量怎么增长,以及越界时编译器和运行时分别怎么反应。',
    facts=[('16 字节', '&[i32] 切片(胖指针:地址 + 长度),普通引用只有 8 字节'), ('24 字节', 'Vec<i32> 本身(指针、长度、容量),元素在堆上'), ('4→8→16→32→64', 'Vec 逐个 push 时的容量序列')],
    body=[
        sec('数组', '', term('', blk('u6', 1))),
        sec('切片', '', term('', blk('u6', 2)), '<p>胖指针的更多细节见<a href="rust-slice-fat-pointer.html">Slice 的胖指针</a>。</p>'),
        sec('Vec 与扩容', '', term('', blk('u6', 3)), '<p>扩容的实现细节与成本见<a href="rust-vec-growth.html">Vec 扩容机制</a>。</p>'),
        sec('栈与堆', '', term('', blk('u6', 4)), '<p>地址是每次运行都会变的数字,这里只看「相差多远」。栈与堆的更多讨论见<a href="rust-stack-vs-heap.html">Rust 栈与堆分配</a>。</p>'),
        sec('get', '', term('', blk('u6', 5))),
        sec('分步演示', '', demo('数组、切片与 Vec', [('t', 'term', '编译与运行输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_U + '。64 位目标;扩容序列是 rustc 1.98 标准库当前的行为,不是语言规范保证的;地址为单次运行的数字', '没有验证:零长度类型的 Vec、Vec 在 release 下的扩容序列是否相同、大数组放在栈上导致栈溢出的行为、切片模式匹配、多维数组'],
)
