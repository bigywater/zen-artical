import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u67'); R = {}
BENCH = '''
    use std::hint::black_box; use std::time::Instant;
    fn chain(v: &[u64]) -> u64 { v.iter().filter(|&&x| x % 2 == 0).map(|&x| x * x).sum() }
    fn forloop(v: &[u64]) -> u64 { let mut s = 0u64; for &x in v { if x % 2 == 0 { s += x * x; } } s }
    fn indexed(v: &[u64]) -> u64 { let mut s = 0u64; let mut i = 0; while i < v.len() { let x = v[i]; if x % 2 == 0 { s += x * x; } i += 1; } s }
    fn middle_vec(v: &[u64]) -> u64 { let ev: Vec<u64> = v.iter().filter(|&&x| x % 2 == 0).copied().collect(); let sq: Vec<u64> = ev.iter().map(|&x| x * x).collect(); sq.iter().sum() }
    fn main() {
        let n: u64 = std::env::args().nth(1).unwrap().parse().unwrap(); let reps: usize = std::env::args().nth(2).unwrap().parse().unwrap();
        let v: Vec<u64> = (0..n).map(|i| i % 1000).collect();
        let mut best = [f64::MAX; 4]; let mut res = [0u64; 4];
        for _ in 0..reps {
            let t = Instant::now(); res[0] = chain(black_box(&v)); best[0] = best[0].min(t.elapsed().as_secs_f64() * 1e3);
            let t = Instant::now(); res[1] = forloop(black_box(&v)); best[1] = best[1].min(t.elapsed().as_secs_f64() * 1e3);
            let t = Instant::now(); res[2] = indexed(black_box(&v)); best[2] = best[2].min(t.elapsed().as_secs_f64() * 1e3);
            let t = Instant::now(); res[3] = middle_vec(black_box(&v)); best[3] = best[3].min(t.elapsed().as_secs_f64() * 1e3);
        }
        println!("链 {:.3} ms | for 循环 {:.3} ms | 下标 while {:.3} ms | 中间 Vec {:.3} ms | 结果相同: {}", best[0], best[1], best[2], best[3], res.iter().all(|r| *r == res[0]));
    }
'''
print('== 一:release,1000 万个元素,取 5 次最小:迭代器链 vs for 循环 vs 下标 while vs 中间 Vec')
r = tryit('u67a', BENCH, quiet_src=True, release=True, args=('10000000', '5')); R['rel'] = r['out']
print()
print('== 二:同样的程序在 debug 模式下(不开优化),100 万个元素,取 3 次最小')
r = tryit('u67b', BENCH, quiet_src=True, release=False, args=('1000000', '3')); R['dbg'] = r['out']
print()
print('== 三:同一个 debug 构建在不同 opt-level 下(0 / 1 / 2 / 3;1000 万个元素,取 3 次最小)')
R['opt'] = {}
for lv in (0, 1, 2, 3):
    r = tryit(f'u67c{lv}', BENCH, quiet_src=True, flags=('-C', f'opt-level={lv}'), args=('10000000', '3'), show_run=False)
    o = run(r['bin'], '10000000', '3')[1].strip()
    print(f'  opt-level={lv}: ', o); R['opt'][str(lv)] = o
print()
print('== 四:中间 Vec 的代价:分配次数(全局分配器计数)')
r = tryit('u67d', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
    static A: AtomicUsize = AtomicUsize::new(0); static RE: AtomicUsize = AtomicUsize::new(0); static B: AtomicUsize = AtomicUsize::new(0);
    struct C;
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { A.fetch_add(1, Relaxed); B.fetch_add(l.size(), Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { unsafe { System.dealloc(p, l) } }
        unsafe fn realloc(&self, p: *mut u8, l: Layout, n: usize) -> *mut u8 { RE.fetch_add(1, Relaxed); B.fetch_add(n, Relaxed); unsafe { System.realloc(p, l, n) } }
    }
    #[global_allocator] static G: C = C;
    fn snap() -> (usize, usize, usize) { (A.load(Relaxed), RE.load(Relaxed), B.load(Relaxed)) }
    fn main() {
        let v: Vec<u64> = (0..100_000u64).map(|i| i % 1000).collect();
        let s0 = snap(); let a: u64 = v.iter().filter(|&&x| x % 2 == 0).map(|&x| x * x).sum(); let s1 = snap();
        let ev: Vec<u64> = v.iter().filter(|&&x| x % 2 == 0).copied().collect(); let sq: Vec<u64> = ev.iter().map(|&x| x * x).collect(); let b: u64 = sq.iter().sum(); let s2 = snap();
        println!("惰性链:  alloc {} realloc {} 申请字节 {}  结果 {}", s1.0 - s0.0, s1.1 - s0.1, s1.2 - s0.2, a);
        println!("中间 Vec: alloc {} realloc {} 申请字节 {}  结果 {}", s2.0 - s1.0, s2.1 - s1.1, s2.2 - s1.2, b);
    }
''', quiet_src=True, release=True); R['alloc'] = r['out']
save('u67', R)
