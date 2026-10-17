import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u59'); R = {}
print('== 一:默认哈希每个 HashMap 都有随机种子:同样的键、同样的插入顺序,两个 map 的遍历顺序不同;跨进程也不同')
r = tryit('u59a', '''
    use std::collections::HashMap;
    fn main() {
        let keys = ["a", "b", "c", "d", "e", "f", "g", "h"];
        for n in 0..3 {
            let mut m = HashMap::new(); for k in keys { m.insert(k, 1); }
            println!("map{} 遍历顺序: {}", n, m.keys().copied().collect::<Vec<_>>().join(""));
        }
    }
''', quiet_src=True)
R['same_proc'] = r['out']
runs = []
for i in range(4):
    rr = run(r['bin']); runs.append(rr[1])
print('  同一个程序再运行 4 次,每次第一个 map 的顺序:', [ [l for l in x.splitlines() if 'map0' in l][0].split(': ')[1] for x in runs])
R['procs'] = [[l for l in x.splitlines() if 'map0' in l][0].split(': ')[1] for x in runs]
print()
print('== 二:固定种子(BuildHasherDefault<DefaultHasher>)后顺序稳定;对同一个键哈希两次结果相同;不同 RandomState 对同一键哈希值不同')
r = tryit('u59b', '''
    use std::collections::{HashMap, hash_map::{DefaultHasher, RandomState}};
    use std::hash::{BuildHasher, BuildHasherDefault, Hash, Hasher};
    fn main() {
        for n in 0..2 {
            let mut m: HashMap<&str, i32, BuildHasherDefault<DefaultHasher>> = HashMap::default();
            for k in ["a", "b", "c", "d", "e", "f", "g", "h"] { m.insert(k, 1); }
            println!("固定种子 map{} 顺序: {}", n, m.keys().copied().collect::<Vec<_>>().join(""));
        }
        let (s1, s2) = (RandomState::new(), RandomState::new());
        println!("同一个 RandomState 对 \\"hello\\" 哈希两次: {} {}", s1.hash_one("hello"), s1.hash_one("hello"));
        println!("另一个 RandomState: {}", s2.hash_one("hello"));
        let mut h = DefaultHasher::new(); "hello".hash(&mut h); let a = h.finish();
        let mut h = DefaultHasher::new(); "hello".hash(&mut h); println!("DefaultHasher::new() 两次: {} {}", a, h.finish());
    }
''', quiet_src=True); R['fixed'] = r['out']
print()
print('== 三:容量与扩容:逐个 insert,记录 capacity 变化,并用分配器统计 alloc/dealloc 次数')
r = tryit('u59c', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
    static A: AtomicUsize = AtomicUsize::new(0); static D: AtomicUsize = AtomicUsize::new(0);
    struct C;
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { A.fetch_add(1, Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { D.fetch_add(1, Relaxed); unsafe { System.dealloc(p, l) } }
    }
    #[global_allocator] static G: C = C;
    use std::collections::HashMap;
    fn main() {
        let mut m: HashMap<u64, u64> = HashMap::new();
        let mut log = Vec::with_capacity(32);
        log.push((0usize, m.capacity(), A.load(Relaxed), D.load(Relaxed)));
        let mut last = m.capacity();
        for i in 0..1000u64 { m.insert(i, i); if m.capacity() != last { last = m.capacity(); log.push((m.len(), last, A.load(Relaxed), D.load(Relaxed))); } }
        let a0 = log[0].2; let d0 = log[0].3;
        for (len, cap, a, d) in &log { println!("插入到第 {:>4} 个元素时 capacity = {:>4}  累计 alloc {} dealloc {}", len, cap, a - a0, d - d0); }
        println!("size_of::<HashMap<u64,u64>>() = {}", std::mem::size_of::<HashMap<u64, u64>>());
    }
''', quiet_src=True, release=True); R['cap'] = r['out']
print()
print('== 四:with_capacity 一次到位;remove 之后 capacity() 变小但内存没释放(用分配器验证);shrink_to_fit 才释放')
r = tryit('u59d', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
    static A: AtomicUsize = AtomicUsize::new(0); static D: AtomicUsize = AtomicUsize::new(0);
    struct C;
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { A.fetch_add(1, Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { D.fetch_add(1, Relaxed); unsafe { System.dealloc(p, l) } }
    }
    #[global_allocator] static G: C = C;
    use std::collections::HashMap;
    fn main() {
        let c = || (A.load(Relaxed), D.load(Relaxed));
        let s0 = c();
        let mut m: HashMap<u32, u32> = HashMap::with_capacity(100);
        let s1 = c(); let c1 = m.capacity();
        for i in 0..100 { m.insert(i, i); }
        let s2 = c(); let c2 = m.capacity();
        m.insert(100, 0); let s3 = c(); let c3 = m.capacity();
        let mut m2: HashMap<u32, u32> = HashMap::with_capacity(100); for i in 0..100 { m2.insert(i, i); }
        let s4 = c(); for i in 0..90 { m2.remove(&i); } let s5 = c(); let (l5, c5) = (m2.len(), m2.capacity());
        m2.shrink_to_fit(); let s6 = c(); let c6 = m2.capacity();
        m2.clear(); let s7 = c(); let (l7, c7) = (m2.len(), m2.capacity());
        println!("with_capacity(100): cap {} (alloc {} 次)", c1, s1.0 - s0.0);
        println!("插入 100 个后 cap {}(新增 alloc {} 次,没有再扩容)", c2, s2.0 - s1.0);
        println!("第 101 个后 cap {}(新增 alloc {} 次)", c3, s3.0 - s2.0);
        println!("另一个 map 插 100 个再删 90 个:len {} cap() {}(删除期间 alloc {} dealloc {},内存没有释放)", l5, c5, s5.0 - s4.0, s5.1 - s4.1);
        println!("shrink_to_fit 后 cap() {}(alloc {} dealloc {}:换了块更小的内存)", c6, s6.0 - s5.0, s6.1 - s5.1);
        println!("clear() 之后 len {} cap() {}(dealloc {} 次)", l7, c7, s7.1 - s6.1);
    }
''', quiet_src=True, release=True); R['wc'] = r['out']
print()
print('== 五:键需要 Hash + Eq:f64 做键编译失败;糟糕的哈希函数让 HashMap 退化')
r = tryit('u59e', '''
    use std::collections::HashMap;
    fn main() { let mut m: HashMap<f64, i32> = HashMap::new(); m.insert(1.0, 1); }
''', maxlines=30); R['f64'] = r['diag']
r = tryit('u59f', '''
    use std::collections::HashMap; use std::hash::{BuildHasher, Hasher}; use std::time::Instant;
    #[derive(Default)] struct Zero; impl Hasher for Zero { fn finish(&self) -> u64 { 0 } fn write(&mut self, _: &[u8]) {} }
    #[derive(Default)] struct ZeroBuild; impl BuildHasher for ZeroBuild { type Hasher = Zero; fn build_hasher(&self) -> Zero { Zero } }
    fn main() {
        for n in [1000u32, 2000, 4000, 8000] {
            let t = Instant::now(); let mut a: HashMap<u32, u32> = HashMap::new(); for i in 0..n { a.insert(i, i); } let ta = t.elapsed();
            let t = Instant::now(); let mut b: HashMap<u32, u32, ZeroBuild> = HashMap::with_hasher(ZeroBuild); for i in 0..n { b.insert(i, i); } let tb = t.elapsed();
            println!("n={:>5}: 默认哈希 {:>9.3} ms   恒等于 0 的哈希 {:>9.3} ms", n, ta.as_secs_f64() * 1e3, tb.as_secs_f64() * 1e3);
        }
    }
''', quiet_src=True, release=True); R['zero'] = r['out']
save('u59', R)
