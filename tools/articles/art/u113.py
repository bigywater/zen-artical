from lib import *
import re
S = SS('u113')
R = J('u113')
un = re.search(r'偏移 0\):\s+每次 ([\d.]+) ns.*\n.*偏移 1\):\s+每次 ([\d.]+) ns', R['unaligned']); ua, ub = un.group(1), un.group(2)
steps = [
    step("基本类型的大小与对齐:u8/bool 1/1、u16 2/2、u32/char 4/4、u64/f64/usize/&u8 8/8、u128 16/16(这台机器上 u128 的对齐是 16)。结构体的对齐是字段对齐的最大值,大小是对齐的整数倍:S1 {u8,u8} 2/1、S2 {u8,u32} 8/4、S3 {u64,u8} 16/8(7 字节末尾填充)、S4 {[u8;5],u16} 8/2。", t=tl(S(1)), done=lidx(S(1), 'u8 ', 'u32 ', 'u64 ', 'u128', 'S1', 'S2', 'S3', 'S4'), kv=KV([['S2 {u8, u32}', 'size 8,align 4'], ['S3 {u64, u8}', 'size 16,align 8'], ['u128', 'size 16,align 16']], ['S3 {u64, u8}'])),
    step("编译器自己的说法(-Z print-type-sizes):repr(C) 的 MixedC { a: u8, b: u64, c: u8, d: u32, e: u16 } 是 32 字节、对齐 8:a 之后 padding 7 字节,b 8 字节,c 之后 padding 3 字节,d 4 字节,e 2 字节,最后 end padding 6 字节 —— 一共 16 字节的填充。", t=tl(S(2)), mark=lidx(S(2), 'padding'), done=lidx(S(2), 'MixedC'), b=bars([['有效字段', 16, '16 B'], ['填充', 16, '16 B']], 32, done=[0], cur=[1]), kv=KV([['MixedC', '32 字节,填充 7 + 3 + 6 = 16']], ['MixedC'])),
    step("同样的字段,默认布局的 Mixed 是 16 字节、对齐 8,没有任何填充:rustc 把字段重排成 b(8)、d(4)、e(2)、a(1)、c(1),按大小降序紧挨着排。同一组字段,repr(C) 比默认布局多了整整一倍的空间。", t=tl(S(2)), done=lidx(S(2), 'type: `Mixed`'), kv=KV([['默认布局 Mixed', '16 字节,无填充(重排为 b, d, e, a, c)']], ['默认布局 Mixed'])),
    step("Vec<S> 的元素间距就是 size_of::<S>() = 8(间距 8 和 8),每个元素地址对 align(4) 取余都是 0。数据在内存里总是放在对齐的位置。", t=tl(S(3)), done=lidx(S(3), 'size_of::<S>()', '地址 % align'), kv=KV([['元素间距', '= size_of(含填充)'], ['地址 % align', '0']], ['元素间距'])),
    step(f"不对齐的访问:read_unaligned 读偏移 1 的 u32 是安全且正确的,实测每次 {ub} ns,对齐读取每次 {ua} ns,在这台 aarch64 机器上几乎没有差别(aarch64 允许不对齐访问);但这不代表可以直接解引用不对齐的指针 —— 那是未定义行为。", t=tl(S(4)), done=lidx(S(4), '对齐的 u32', '不对齐的 u32'), b=bars([['对齐读', float(ua), f'{ua} ns'], ['不对齐读(read_unaligned)', float(ub), f'{ub} ns']], max(float(ua), float(ub)) * 1.2, done=[0, 1]), kv=KV([['对齐', f'{ua} ns'], ['read_unaligned', f'{ub} ns']], ['read_unaligned'])),
    step("直接 &*p 解引用偏移 1 的 *const u32:read_unaligned 先成功得到 0x5040302,随后 debug 构建里 panic: misaligned pointer dereference: address must be a multiple of 0x4,并因 non-unwinding panic 而 abort(信号 6)。标准库在 debug 构建里加了对齐检查。", t=tl(S(4)), mark=lidx(S(4), 'misaligned pointer dereference'), done=lidx(S(4), '0x5040302'), kv=KV([['read_unaligned', '正确'], ['&*p 不对齐', 'debug 下 panic + abort']], ['&*p 不对齐'])),
]
A = mkart('u113', 113, 'Rust,对齐,padding,内存布局,真实验证,动画演示',
    f'用 align_of 与编译器的 -Z print-type-sizes 验证对齐与填充:基本类型与结构体的 size/align;repr(C) MixedC 32 字节含 16 字节填充而默认布局 16 字节无填充(自动重排);Vec 元素间距 = size;read_unaligned 不对齐读 {ub} ns 对齐读 {ua} ns,直接解引用不对齐指针在 debug 下 panic。',
    '填充到底是怎么产生的?编译器自己怎么描述它?不对齐的访问有多慢?这篇让 rustc 自己把布局打印出来,逐字段看到偏移与填充,再验证对齐访问的实际表现。',
    [('16 字节', 'repr(C) 的 MixedC(32 字节)里填充占的字节数'), ('32 对 16', 'repr(C) 与默认布局同样五个字段的大小'), ('panic', 'debug 构建里直接解引用不对齐指针的结果')],
    [('大小与对齐', '<p>repr(C) 的基础见<a href="rust-repr-c-layout.html">#[repr(C)] 与内存布局</a>。</p>'), ('编译器打印的布局', '<p>-Z print-type-sizes 需要 RUSTC_BOOTSTRAP=1,输出格式随编译器版本变化。</p>'), ('元素间距', None), ('不对齐访问', '<p>耗时为本机 release 微基准;x86 与 aarch64 上不对齐访问的代价不同,只验证了本机。</p>')],
    steps, [ENV_U + '。print-type-sizes 用 RUSTC_BOOTSTRAP=1', '没有验证:x86_64 上不对齐访问的成本、缓存行对齐(false sharing)、填充字节内容的泄漏风险(未初始化)、repr(align) 在 Vec 中的行为、#[repr(simd)]'], '对齐与填充')
