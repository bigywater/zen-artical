import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u109'); R = {}
print('== 一:变量放在哪?打印地址:局部变量在栈上、Box / Vec 的数据在堆上、static 与字面量在数据段 / 代码段')
r = tryit('u109a', '''
    static STATIC_N: u64 = 7;
    fn deeper(label: &str) { let local = 0u64; println!("  {:<16} {:p}", label, &local); }
    fn main() {
        let local = 1u64; let arr = [0u8; 64]; let boxed = Box::new(2u64); let v = vec![3u64; 8]; let s = String::from("heap"); let lit: &str = "字面量";
        println!("  {:<16} {:p}", "局部变量 local", &local);
        println!("  {:<16} {:p}", "数组 [u8; 64]", &arr);
        println!("  {:<16} {:p}", "Box<u64> 的数据", &*boxed);
        println!("  {:<16} {:p}", "Vec 的缓冲区", v.as_ptr());
        println!("  {:<16} {:p}", "String 的缓冲区", s.as_ptr());
        println!("  {:<16} {:p}", "字符串字面量", lit.as_ptr());
        println!("  {:<16} {:p}", "static", &STATIC_N);
        println!("  {:<16} {:p}", "box 变量本身", &boxed);
        deeper("被调函数的局部");
        println!("  {:<16} {:p}", "main 函数代码", main as fn() as *const ());
    }
''', quiet_src=True); R['addr'] = r['out']
print()
print('== 二:栈有固定上限:主线程的栈大小(ulimit -s)与递归到溢出的深度;子线程栈默认更小')
r = tryit('u109b', '''
    use std::{thread, sync::atomic::{AtomicUsize, Ordering::SeqCst}};
    static DEPTH: AtomicUsize = AtomicUsize::new(0);
    #[inline(never)] fn recurse(n: usize) -> usize { DEPTH.store(n, SeqCst); let pad = [n as u8; 128]; if n == usize::MAX { return 0; } recurse(n + 1) + std::hint::black_box(pad[0]) as usize }
    fn main() {
        let which = std::env::args().nth(1).unwrap();
        if which == "main" { recurse(0); } else { thread::spawn(|| { recurse(0); }).join().ok(); }
    }
''', quiet_src=True, show_run=False)
import subprocess
rc, o, e = sh(['sh', '-c', 'ulimit -s'], env=ENVB); print(f'  ulimit -s(主线程栈上限,KiB):{o.strip()}'); R['ulimit'] = o.strip()
for which in ('main', 'thread'):
    rc, so, se, _ = run(r['bin'], which)
    # 递归深度通过重新运行并捕获:用一个子进程方式记录最后深度太复杂,改用 lldb-free 方式:二分
print('  (深度用二分法测量:下面分别对主线程与子线程找到最大不溢出的递归层数)')
r = tryit('u109c', '''
    use std::thread;
    #[inline(never)] fn recurse(n: usize, limit: usize) -> usize { let pad = [n as u8; 128]; if n >= limit { return pad[0] as usize; } recurse(n + 1, limit) + std::hint::black_box(pad[0]) as usize }
    fn main() {
        let which = std::env::args().nth(1).unwrap(); let limit: usize = std::env::args().nth(2).unwrap().parse().unwrap();
        if which == "main" { println!("{}", recurse(0, limit)); } else { println!("{}", thread::spawn(move || recurse(0, limit)).join().unwrap()); }
    }
''', quiet_src=True, show_run=False)
def maxdepth(which):
    lo, hi = 1000, 4_000_000
    while hi - lo > lo // 50:
        mid = (lo + hi) // 2; rc, so, se, _ = run(r['bin'], which, str(mid))
        if rc == 0: lo = mid
        else: hi = mid
    return lo
for which in ('main', 'thread'):
    d = maxdepth(which); print(f'  {"主线程" if which == "main" else "子线程(默认栈)"}:每层约 150 字节栈帧,递归深度约 {d} 层时还正常,再深就栈溢出(误差约 2%)'); R['depth_' + which] = d
rc, so, se, _ = run(r['bin'], 'main', '4000000'); print(f'  递归 400 万层:被信号 {-rc} 终止;stderr:{[l for l in se.splitlines() if l.strip()][-1:]}'); R['overflow'] = [rc, [l for l in se.splitlines() if l.strip()][-1:]]
print()
print('== 三:栈上的大数组:main 里放 16 MiB 的数组,栈溢出;放进 Box 就没事')
r = tryit('u109d', '''
    fn main() { let big = [0u8; 16 * 1024 * 1024]; println!("{}", std::hint::black_box(&big)[100]); }
''', quiet_src=True, release=False, show_run=False)
rc, so, se, _ = run(r['bin']); print(f'  16 MiB 数组放栈上:{"被信号 %d 终止" % -rc if rc < 0 else "退出码 %d" % rc};stderr 末行:{[l for l in se.splitlines() if l.strip()][-1:]}'); R['bigarr'] = [rc, [l for l in se.splitlines() if l.strip()][-1:]]
r = tryit('u109e', '''
    fn main() { let big = vec![0u8; 16 * 1024 * 1024]; let b: Box<[u8]> = big.into_boxed_slice(); println!("16 MiB 放在堆上:b[100] = {},长度 {}", std::hint::black_box(&b)[100], b.len()); }
''', quiet_src=True, release=False); R['heap_ok'] = r['out']
print()
print('== 四:分配成本:栈上的数组 vs 堆上的 Vec(release,每轮创建并使用一个 256 字节缓冲区,2000 万轮)')
r = tryit('u109f', '''
    use std::{hint::black_box, time::Instant};
    fn main() {
        let n = 20_000_000u64; let (mut ts, mut th) = (f64::MAX, f64::MAX);
        for _ in 0..3 {
            let t = Instant::now(); let mut s = 0u64; for i in 0..n { let mut a = [0u8; 256]; a[(i % 256) as usize] = black_box(i as u8); s += a[(i % 256) as usize] as u64; black_box(&a); } black_box(s); ts = ts.min(t.elapsed().as_secs_f64() * 1e9 / n as f64);
            let t = Instant::now(); let mut s = 0u64; for i in 0..n { let mut a = vec![0u8; 256]; a[(i % 256) as usize] = black_box(i as u8); s += a[(i % 256) as usize] as u64; black_box(&a); } black_box(s); th = th.min(t.elapsed().as_secs_f64() * 1e9 / n as f64);
        }
        println!("栈上 [u8; 256]   每轮 {:>6.2} ns", ts); println!("堆上 vec![0u8; 256] 每轮 {:>6.2} ns(分配 + 释放)", th);
    }
''', quiet_src=True, release=True); R['cost'] = r['out']
save('u109', R)
