import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u56'); R = {}
print('== 一:不断 push,capacity 怎么变(Vec<u32>,记录每次变化)')
r = tryit('u56a', '''
    fn main() {
        let mut v: Vec<u32> = Vec::new();
        println!("new: len={} cap={}", v.len(), v.capacity());
        let mut last = v.capacity();
        for i in 0..1100u32 {
            v.push(i);
            if v.capacity() != last { println!("push 第 {:>4} 个后 cap {:>4} -> {:>4}", v.len(), last, v.capacity()); last = v.capacity(); }
        }
    }
''', quiet_src=True, release=True); R['grow'] = r['out']
print()
print('== 二:不同元素大小的最小非零容量(第一次 push 后的 capacity)')
r = tryit('u56b', '''
    macro_rules! first { ($name:expr, $t:ty, $val:expr) => {{
        let mut v: Vec<$t> = Vec::new(); v.push($val);
        println!("{:<10} size_of={:<5} 第一次 push 后 cap={}", $name, std::mem::size_of::<$t>(), v.capacity());
    }}; }
    fn main() {
        first!("u8", u8, 0); first!("u32", u32, 0); first!("u64", u64, 0); first!("[u64;16]", [u64; 16], [0; 16]);
        first!("1000 字节", [u8; 1000], [0; 1000]); first!("1024 字节", [u8; 1024], [0; 1024]); first!("1025 字节", [u8; 1025], [0; 1025]); first!("5000 字节", [u8; 5000], [0; 5000]);
        let mut z: Vec<()> = Vec::new(); z.push(());
        println!("Vec<()> cap = {} (usize::MAX = {})", z.capacity(), usize::MAX);
    }
''', quiet_src=True, release=True); R['min'] = r['out']
print()
print('== 三:用全局分配器计数:1000 次 push 发生了几次 alloc / realloc;with_capacity 与 reserve_exact')
r = tryit('u56c', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
    static A: AtomicUsize = AtomicUsize::new(0); static RE: AtomicUsize = AtomicUsize::new(0); static D: AtomicUsize = AtomicUsize::new(0);
    struct C;
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { A.fetch_add(1, Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { D.fetch_add(1, Relaxed); unsafe { System.dealloc(p, l) } }
        unsafe fn realloc(&self, p: *mut u8, l: Layout, n: usize) -> *mut u8 { RE.fetch_add(1, Relaxed); unsafe { System.realloc(p, l, n) } }
    }
    #[global_allocator] static G: C = C;
    fn snap() -> (usize, usize, usize) { (A.load(Relaxed), RE.load(Relaxed), D.load(Relaxed)) }
    fn main() {
        let s0 = snap();
        let mut v: Vec<u64> = Vec::new(); for i in 0..1000u64 { v.push(i); }
        let s1 = snap(); let c1 = v.capacity();
        let mut w: Vec<u64> = Vec::with_capacity(1000); for i in 0..1000u64 { w.push(i); }
        let s2 = snap(); let c2 = w.capacity();
        let mut x: Vec<u64> = vec![1, 2, 3]; let cx = x.capacity();
        let s3 = snap(); x.reserve(10); let cr = x.capacity(); let s4 = snap();
        let mut y: Vec<u64> = vec![1, 2, 3]; y.reserve_exact(10); let cre = y.capacity();
        let mut q: Vec<u64> = Vec::with_capacity(8); q.extend(0..8u64); q.reserve(1); let cq = q.capacity();
        let mut q2: Vec<u64> = Vec::with_capacity(8); q2.extend(0..8u64); q2.reserve_exact(1); let cq2 = q2.capacity();
        let mut z: Vec<u64> = Vec::with_capacity(100); z.extend(0..10u64); let cz0 = z.capacity(); z.shrink_to_fit(); let cz1 = z.capacity();
        println!("逐个 push 1000 次(Vec::new): alloc {} realloc {} 最终 cap {}", s1.0 - s0.0, s1.1 - s0.1, c1);
        println!("with_capacity(1000) 再 push 1000 次: alloc {} realloc {} 最终 cap {}", s2.0 - s1.0, s2.1 - s1.1, c2);
        println!("vec![1,2,3]: cap {} ; reserve(10) 后 cap {} (realloc {} 次)", cx, cr, s4.1 - s3.1);
        println!("vec![1,2,3] 再 reserve_exact(10): cap {}", cre);
        println!("cap 8 已满再 reserve(1): cap {} ; 同样情形 reserve_exact(1): cap {}", cq, cq2);
        println!("with_capacity(100) 存 10 个: cap {} ; shrink_to_fit 后 cap {}", cz0, cz1);
    }
''', quiet_src=True, release=True); R['alloc'] = r['out']
print()
print('== 四:扩容会搬家:缓冲区地址变化,旧引用被编译器拒绝')
r = tryit('u56d', '''
    fn main() {
        let mut v: Vec<u32> = Vec::with_capacity(4);
        v.extend([1, 2, 3, 4]);
        let p0 = v.as_ptr(); println!("cap {} 时地址 {:p}", v.capacity(), p0);
        v.push(5);
        let p1 = v.as_ptr(); println!("push 第 5 个后 cap {} 地址 {:p},地址{}", v.capacity(), p1, if p0 == p1 { "没变" } else { "变了" });
        let mut u: Vec<u32> = Vec::with_capacity(8); u.extend([1, 2, 3, 4]);
        let q0 = u.as_ptr(); u.push(5); println!("cap 8 里 push 第 5 个:地址{}", if q0 == u.as_ptr() { "没变" } else { "变了" });
    }
''', quiet_src=True, release=True); R['move'] = r['out']
r = tryit('u56e', '''
    fn main() {
        let mut v = vec![1, 2, 3];
        let first = &v[0];
        v.push(4);
        println!("{}", first);
    }
''', maxlines=25); R['e0502'] = r['diag'].split('\n')[0]
save('u56', R)
