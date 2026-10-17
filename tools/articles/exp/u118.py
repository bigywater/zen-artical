import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u118'); R = {}
print('== 一:安全 Rust 不允许读未初始化的变量(编译期 E0381);MaybeUninit<T> 是显式的「还没初始化」')
r = tryit('u118a', '''
    fn main() { let x: u32; println!("{}", x); }
''', maxlines=24); R['e0381'] = r['diag']
r = tryit('u118b', '''
    use std::mem::{MaybeUninit, size_of, align_of};
    fn main() {
        println!("  size_of::<u64>() = {}  size_of::<MaybeUninit<u64>>() = {}  align 同样 {} / {}", size_of::<u64>(), size_of::<MaybeUninit<u64>>(), align_of::<u64>(), align_of::<MaybeUninit<u64>>());
        println!("  size_of::<Option<u64>>() = {}(Option 要标签)而 MaybeUninit<u64> 没有额外字节:它不记录是否已初始化", size_of::<Option<u64>>());
        let mut x = MaybeUninit::<u64>::uninit();
        x.write(42);
        let v = unsafe { x.assume_init() };
        println!("  write 之后 assume_init = {}", v);
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:用 MaybeUninit 逐个初始化 [String; 4] 的元素,并与安全的 array::from_fn 对照')
r = tryit('u118c', '''
    use std::mem::MaybeUninit;
    fn main() {
        let mut arr: [MaybeUninit<String>; 4] = [const { MaybeUninit::uninit() }; 4];
        for (i, slot) in arr.iter_mut().enumerate() { slot.write(format!("item-{}", i * i)); }
        let arr: [String; 4] = unsafe { std::mem::transmute(arr) };
        println!("  逐个 write 之后整体转成 [String; 4]:{:?}", arr);
        let b: [String; 4] = std::array::from_fn(|i| format!("item-{}", i * i)); println!("  对照:std::array::from_fn 的安全写法得到相同结果: {}", arr == b);
    }
''', quiet_src=True); R['array'] = r['out']
print()
print('== 三:MaybeUninit 不会自动 drop:忘记手动 drop 就泄漏;部分初始化时只能 drop 已初始化的那些')
r = tryit('u118d', '''
    use std::mem::MaybeUninit;
    struct Noisy(u32); impl Drop for Noisy { fn drop(&mut self) { println!("  Noisy({}) drop", self.0); } }
    fn main() {
        println!("  1) MaybeUninit<Noisy> 离开作用域:");
        { let mut m = MaybeUninit::<Noisy>::uninit(); m.write(Noisy(1)); }
        println!("     (没有看到 Noisy(1) drop —— MaybeUninit 不负责析构,值泄漏了)");
        println!("  2) 手动 assume_init_drop:");
        { let mut m = MaybeUninit::<Noisy>::uninit(); m.write(Noisy(2)); unsafe { m.assume_init_drop(); } }
        println!("  3) 数组只初始化了前 2 个,只 drop 这 2 个:");
        let mut arr: [MaybeUninit<Noisy>; 4] = [const { MaybeUninit::uninit() }; 4];
        arr[0].write(Noisy(10)); arr[1].write(Noisy(11));
        for i in 0..2 { unsafe { arr[i].assume_init_drop(); } }
    }
''', quiet_src=True); R['drop'] = r['out']
print()
print('== 四:省掉清零:创建 1 MiB 缓冲区再整体覆盖写入,vec![0u8; N] 与 Vec::with_capacity + set_len(MaybeUninit 思路)的耗时(release)')
r = tryit('u118e', '''
    use std::{hint::black_box, time::Instant, mem::MaybeUninit};
    fn main() {
        let n = 1 << 20; let reps = 3000;
        let mut best = [f64::MAX; 2];
        for _ in 0..3 {
            let t = Instant::now(); for r in 0..reps { let mut v = vec![0u8; n]; for (i, b) in v.iter_mut().enumerate().step_by(4096) { *b = (i + r) as u8; } black_box(&v); } best[0] = best[0].min(t.elapsed().as_secs_f64() * 1e6 / reps as f64);
            let t = Instant::now(); for r in 0..reps { let mut v: Vec<MaybeUninit<u8>> = Vec::with_capacity(n); unsafe { v.set_len(n); } for (i, b) in v.iter_mut().enumerate().step_by(4096) { b.write((i + r) as u8); } black_box(&v); } best[1] = best[1].min(t.elapsed().as_secs_f64() * 1e6 / reps as f64);
        }
        println!("  vec![0u8; 1 MiB](清零)          每次 {:>8.2} µs", best[0]);
        println!("  with_capacity + set_len(不清零) 每次 {:>8.2} µs(只写了 1/4096 的字节,其余保持未初始化)", best[1]);
    }
''', quiet_src=True, release=True); R['bench'] = r['out']
save('u118', R)
