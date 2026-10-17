import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u113'); R = {}
print('== 一:基本类型的大小与对齐(align_of);结构体的对齐是字段对齐的最大值,大小是对齐的整数倍')
r = tryit('u113a', '''
    #![allow(dead_code)]
    use std::mem::{size_of, align_of};
    struct S1 { a: u8, b: u8 } struct S2 { a: u8, b: u32 } struct S3 { a: u64, b: u8 } struct S4 { a: [u8; 5], b: u16 }
    fn main() {
        macro_rules! p { ($t:ty) => { println!("  {:<14} size {:>2}  align {:>2}", stringify!($t), size_of::<$t>(), align_of::<$t>()); } }
        p!(u8); p!(u16); p!(u32); p!(u64); p!(u128); p!(f64); p!(char); p!(bool); p!(usize); p!(&u8); p!((u8, u32)); p!([u16; 3]);
        p!(S1); p!(S2); p!(S3); p!(S4);
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:编译器自己打印的布局(-Z print-type-sizes):字段偏移、填充(padding)和重排后的顺序')
code = '''
    #![allow(dead_code)]
    pub struct Mixed { a: u8, b: u64, c: u8, d: u32, e: u16 }
    #[repr(C)] pub struct MixedC { a: u8, b: u64, c: u8, d: u32, e: u16 }
    pub fn make() -> (Mixed, MixedC) { (Mixed { a: 1, b: 2, c: 3, d: 4, e: 5 }, MixedC { a: 1, b: 2, c: 3, d: 4, e: 5 }) }
'''
f = src_file('u113b', code); rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '-Z', 'print-type-sizes', '--emit=metadata', '-o', str(RS / 'bin' / 'u113b.rmeta'), str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
L = [l for l in o.splitlines() if 'Mixed' in l or l.startswith('print-type-size   ')]
sel = []; on = False
for l in o.splitlines():
    if l.startswith('print-type-size type:') : on = 'Mixed' in l
    if on: sel.append(l.replace('print-type-size ', ''))
print('\n'.join('  ' + l for l in sel)); R['pts'] = sel
print()
print('== 三:对齐的实际表现:Vec<S> 的元素间距(stride)等于 size;地址总是 align 的倍数')
r = tryit('u113c', '''
    use std::mem::{size_of, align_of};
    #[repr(C)] struct S { a: u8, b: u32 }
    fn main() {
        let v = vec![S { a: 1, b: 2 }, S { a: 3, b: 4 }, S { a: 5, b: 6 }];
        let (p0, p1, p2) = (&v[0] as *const S as usize, &v[1] as *const S as usize, &v[2] as *const S as usize);
        println!("size_of::<S>() = {},元素间距 = {} 和 {}", size_of::<S>(), p1 - p0, p2 - p1);
        println!("每个元素地址 % align({}) = {} {} {}", align_of::<S>(), p0 % align_of::<S>(), p1 % align_of::<S>(), p2 % align_of::<S>());
        let bytes = [0u8; 16]; let mut mis = 0; for off in 0..8 { if (bytes.as_ptr() as usize + off) % 4 != 0 { mis += 1; } }
        println!("一个 u8 数组里偏移 0..8 的位置,按 u32 对齐的占 {} 个,不对齐的占 {} 个", 8 - mis, mis);
    }
''', quiet_src=True); R['stride'] = r['out']
print()
print('== 四:读不对齐的数据:read_unaligned 的正确性与速度(aarch64 允许不对齐访问);直接解引用不对齐的指针是未定义行为')
r = tryit('u113d', '''
    use std::{hint::black_box, time::Instant};
    fn main() {
        let buf: Vec<u8> = (0..4096u32).map(|i| (i * 7) as u8).collect();
        let n = 50_000_000u64;
        let mut res = [0.0f64; 2]; let mut sums = [0u64; 2];
        for (k, off) in [0usize, 1].into_iter().enumerate() {
            let mut best = f64::MAX;
            for _ in 0..3 { let t = Instant::now(); let mut s = 0u64; for i in 0..n { let idx = ((i as usize * 4) % 4000) & !3; let p = unsafe { black_box(buf.as_ptr().add(idx + off)) }; s = s.wrapping_add(unsafe { (p as *const u32).read_unaligned() } as u64); } sums[k] = s; best = best.min(t.elapsed().as_secs_f64() * 1e9 / n as f64); }
            res[k] = best;
        }
        println!("对齐的 u32 读取(偏移 0):       每次 {:.2} ns", res[0]);
        println!("不对齐的 u32 读取(偏移 1):     每次 {:.2} ns(read_unaligned,结果不同是因为读的字节不同:{} 对 {})", res[1], sums[0], sums[1]);
    }
''', quiet_src=True, release=True); R['unaligned'] = r['out']
r = tryit('u113e', '''
    fn main() {
        let buf = [1u8, 2, 3, 4, 5, 6, 7, 8];
        let p = unsafe { buf.as_ptr().add(1) } as *const u32;
        let v = unsafe { std::ptr::read_unaligned(p) };
        println!("read_unaligned 读偏移 1 的 u32 = {:#x}", v);
        let r = unsafe { &*p }; println!("{}", r);
    }
''', quiet_src=True, release=False); R['ub'] = {'rc': r['rc'], 'out': r['out'], 'err': [l for l in r['err'].splitlines() if l.strip() and 'note: run' not in l][:3]}
save('u113', R)
