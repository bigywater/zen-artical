import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u58'); R = {}
ALLOC = '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
    static A: AtomicUsize = AtomicUsize::new(0); static RE: AtomicUsize = AtomicUsize::new(0); static B: AtomicUsize = AtomicUsize::new(0); static LAST: AtomicUsize = AtomicUsize::new(0);
    struct C;
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { A.fetch_add(1, Relaxed); B.fetch_add(l.size(), Relaxed); LAST.store(l.size(), Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { unsafe { System.dealloc(p, l) } }
        unsafe fn realloc(&self, p: *mut u8, l: Layout, n: usize) -> *mut u8 { RE.fetch_add(1, Relaxed); B.fetch_add(n, Relaxed); unsafe { System.realloc(p, l, n) } }
    }
    #[global_allocator] static G: C = C;
    fn snap() -> (usize, usize, usize) { (A.load(Relaxed), RE.load(Relaxed), B.load(Relaxed)) }
'''
print('== 一:LinkedList 每个元素一次堆分配(用全局分配器计数,存 1000 个 u64)')
r = tryit('u58a', ALLOC + '''
    use std::collections::LinkedList;
    fn main() {
        let s0 = snap();
        let mut l: LinkedList<u64> = LinkedList::new(); for i in 0..1000u64 { l.push_back(i); }
        let s1 = snap(); let node = LAST.load(Relaxed);
        let mut v: Vec<u64> = Vec::new(); for i in 0..1000u64 { v.push(i); }
        let s2 = snap();
        println!("LinkedList<u64> 1000 个元素: alloc {} 次, 每次 {} 字节(元素本身 8 字节), 共申请 {} 字节", s1.0 - s0.0, node, s1.2 - s0.2);
        println!("Vec<u64>        1000 个元素: alloc {} 次 realloc {} 次, 共申请 {} 字节(含扩容过程中的所有申请)", s2.0 - s1.0, s2.1 - s1.1, s2.2 - s1.2);
        println!("size_of::<LinkedList<u64>>() = {}  size_of::<Vec<u64>>() = {}", std::mem::size_of::<LinkedList<u64>>(), std::mem::size_of::<Vec<u64>>());
    }
''', quiet_src=True, release=True); R['alloc'] = r['out']
print()
print('== 二:遍历求和 100 万个 u64,LinkedList 与 Vec(release,各 5 次取最小)')
r = tryit('u58b', '''
    use std::collections::LinkedList; use std::hint::black_box; use std::time::Instant;
    fn main() {
        let n = 1_000_000u64;
        let l: LinkedList<u64> = (0..n).collect(); let v: Vec<u64> = (0..n).collect();
        let (mut bl, mut bv) = (f64::MAX, f64::MAX);
        for _ in 0..5 {
            let t = Instant::now(); let s: u64 = black_box(&l).iter().sum(); black_box(s); bl = bl.min(t.elapsed().as_secs_f64() * 1e3);
            let t = Instant::now(); let s: u64 = black_box(&v).iter().sum(); black_box(s); bv = bv.min(t.elapsed().as_secs_f64() * 1e3);
        }
        println!("遍历求和 100 万个 u64: LinkedList 最快 {:.3} ms  Vec 最快 {:.3} ms", bl, bv);
    }
''', quiet_src=True, release=True); R['iter'] = r['out']
print()
print('== 三:LinkedList 的卖点:两端 O(1)、append / split_off 拼接 —— 实际表现')
r = tryit('u58c', '''
    use std::collections::{LinkedList, VecDeque}; use std::hint::black_box; use std::time::Instant;
    fn main() {
        let n = 1_000_000u64;
        for _ in 0..3 {
            let t = Instant::now(); let mut l: LinkedList<u64> = LinkedList::new(); for i in 0..n { l.push_back(black_box(i)); } let a = t.elapsed();
            let t = Instant::now(); let mut d: VecDeque<u64> = VecDeque::new(); for i in 0..n { d.push_back(black_box(i)); } let b = t.elapsed();
            println!("push_back 100 万次: LinkedList {:>7.2} ms  VecDeque {:>6.2} ms", a.as_secs_f64() * 1e3, b.as_secs_f64() * 1e3);
            black_box((&l, &d));
        }
        let mut a: LinkedList<u64> = (0..n).collect(); let mut b: LinkedList<u64> = (0..n).collect();
        let t = Instant::now(); a.append(&mut b); let ta = t.elapsed();
        let mut x: Vec<u64> = (0..n).collect(); let mut y: Vec<u64> = (0..n).collect();
        let t = Instant::now(); x.append(&mut y); let tx = t.elapsed();
        println!("两个 100 万元素的容器拼接: LinkedList::append {:?}  Vec::append {:?}  (拼接后长度 {} / {})", ta, tx, a.len(), x.len());
    }
''', quiet_src=True, release=True); R['ends'] = r['out']
print()
print('== 四:没有下标访问:要第 k 个元素只能 iter().nth(k) 一路走过去')
r = tryit('u58d', '''
    use std::collections::LinkedList;
    fn main() {
        let l: LinkedList<i32> = (1..=5).collect();
        println!("{}", l[2]);
    }
''', quiet_src=False, maxlines=25); R['e0608'] = r['diag'].split('\\n')[0]
r = tryit('u58e', '''
    use std::collections::LinkedList; use std::hint::black_box; use std::time::Instant;
    fn main() {
        let l: LinkedList<u64> = (0..1_000_000u64).collect();
        for k in [10usize, 1000, 100_000, 900_000] {
            let t = Instant::now(); let x = black_box(&l).iter().nth(black_box(k)); let e = t.elapsed();
            println!("iter().nth({:>6}) = {:?}  用时 {:?}", k, x, e);
        }
        let mut l2: LinkedList<u64> = (0..5u64).collect();
        let tail = l2.split_off(2);
        println!("split_off(2): 前 {:?} 后 {:?}", l2, tail);
    }
''', quiet_src=True, release=True); R['nth'] = r['out']
save('u58', R)
