from lib import *
S = SS('u116')
steps = [
    step("切片 = (指针, 长度),size_of::<&[u32]>() = 16。对 10 个 u32 的 Vec 切片:&v[..] 指针偏移 0、长度 10;&v[2..7] 指针 +8 字节、长度 5;&v[5..] 指针 +20 字节、长度 5;&v[2..7][1..3] 指针 +12 字节、长度 2;空切片 &v[3..3] 指针 +12、长度 0。切一次只是改指针和长度,没有任何数据被复制;数组转 &[u8] 数据地址相同。", t=tl(S(1)), done=lidx(S(1), '&v[..]', '&v[2..7]  ', '&v[5..]', '&v[2..7][1..3]', '数组 [u8; 4]', 'size_of'), kv=KV([['&v[2..7]', '指针 +8 字节,长度 5'], ['&v[2..7][1..3]', '指针 +12 字节,长度 2'], ['复制', '0 个元素']], ['复制'])),
    step("切片只是视图:&mut v[1..4] 改第 0、2 个元素,原 Vec 变成 [1, 20, 3, 40, 5, 6];split_at_mut(3) 得到两个不重叠的 &mut 切片,分别改后 v = [100, 20, 3, 400, 5, 6]。", t=tl(S(2)), done=lidx(S(2), '改 &mut', 'split_at_mut'), kv=KV([['&mut v[1..4]', '改切片 = 改原数据'], ['split_at_mut', '不重叠的两半']], ['split_at_mut'])),
    step("两个重叠的 &mut 切片不允许:let a = &mut v[0..3]; let b = &mut v[2..4]; 报 error[E0499]: cannot borrow `v` as mutable more than once at a time,help 建议 split_at_mut。借用检查器不知道范围是否重叠,所以一律拒绝。", t=tl(S(2)), mark=lidx(S(2), 'error[E0499]', 'split_at_mut(position)'), kv=KV([['两个 &mut v[..]', 'E0499,哪怕范围不重叠']], ['两个 &mut v[..]'])),
    step("越界都是 panic,消息带范围与长度:&v[1..5](长度 3)→「range end index 5 out of range for slice of length 3」;&v[3..1] →「slice index starts at 3 but ends at 1」;str 切在字符中间 →「end byte index 2 is not a char boundary; it is inside 'é' (bytes 1..3 of string)」,退出码都是 101。get(1..5) 返回 None,get(1..3) 返回 Some([2, 3]),不 panic。", t=tl(S(3)), mark=lidx(S(3), '范围越界', '起点大于终点', 'str 切在'), done=lidx(S(3), 'v.get'), kv=KV([['切片越界', 'panic,退出码 101'], ['get(range)', 'None,不 panic']], ['get(range)'])),
    step("零大小元素的切片:100 万个 () 的 &[()] 长度是 1000000,size_of_val 却是 0 字节 —— 长度是真实的,数据不占内存。空切片 &[u64] 的指针是 0x8:非空、对齐到 8,但那是一个悬空的占位地址,没有可读内存。本文只验证了 u64 与零大小元素这两种情形。", t=tl(S(4)), done=lidx(S(4), '&[()]', '空切片'), kv=KV([['&[()] 100 万个', '0 字节'], ['空切片的指针', '0x8,非空对齐的悬空地址']], ['空切片的指针'])),
    step("切片的各种操作都只改(指针, 长度):from_raw_parts(ptr + 2, 4) 得 [3, 4, 5, 6];chunks(3) 的 (偏移, 长度) 是 (0, 3)、(3, 3)、(6, 2);windows(3) 的前三个窗口偏移 0、1、2,长度 3;split_first 得到 first = 1,rest 偏移 1、长度 7。没有元素被复制。", t=tl(S(5)), done=lidx(S(5), 'from_raw_parts', 'chunks(3)', 'windows(3)', 'split_first'), kv=KV([['chunks(3)', '偏移 0/3/6,长度 3/3/2'], ['windows(3)', '偏移 0/1/2'], ['split_first', 'rest = 偏移 1,长度 7']], ['chunks(3)'])),
]
A = mkart('u116', 116, 'Rust,切片,胖指针,内存布局,真实验证,动画演示',
    '用真实运行验证切片的胖指针:size 16(指针 + 长度);切出子切片只改指针与长度、不复制;改切片就改原数据,重叠的 &mut 切片报 E0499 而 split_at_mut 给出不重叠两半;三种越界 panic 的消息;100 万个零大小元素的切片 size_of_val 为 0、空切片指针是 0x8;chunks/windows/split_first 的偏移与长度。',
    '&v[2..7] 是怎么做到不复制的?切片里到底存了什么?越界会怎样?空切片和零大小元素的切片指针又是什么?这篇把切片拆成「指针 + 长度」逐项验证。',
    [('16 字节', '&[T] 的大小(指针 + 长度)'), ('0 次复制', '切出子切片时被复制的元素数'), ('0x8', '空 &[u64] 的指针(非空、对齐的悬空地址)')],
    [('指针与长度', '<p>数组、切片与 Vec 的区别见<a href="rust-array-slice-vec.html">数组、切片与 Vec</a>;trait object 的胖指针见<a href="rust-trait-object-fat-pointer.html">Trait Object 的胖指针</a>。</p>'), ('切片是视图', None), ('越界', None), ('零大小与空切片', '<p>0x8 是这台机器上 u64 空切片的占位地址,是实现细节,换类型或平台可能不同。</p>'), ('拆分操作', None)],
    steps, [ENV_U, '没有验证:空切片的占位地址是否总等于对齐值(只测了 u64)、from_raw_parts 违反安全条件时的后果、&mut 切片别名的编译器优化(noalias)、切片比较与排序的复杂度'], '切片的胖指针')
