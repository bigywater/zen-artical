import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u60'); R = {}
print('== 一:BTreeMap 遍历有序;range 范围查询;first/last;pop_first')
r = tryit('u60a', '''
    use std::collections::BTreeMap;
    fn main() {
        let mut m = BTreeMap::new();
        for k in [50, 20, 80, 10, 60, 30, 90, 40, 70] { m.insert(k, k * 2); }
        println!("遍历: {:?}", m.keys().collect::<Vec<_>>());
        println!("range(30..=60): {:?}", m.range(30..=60).map(|(k, _)| *k).collect::<Vec<_>>());
        println!("range(..30): {:?}   range(75..): {:?}", m.range(..30).map(|(k, _)| *k).collect::<Vec<_>>(), m.range(75..).map(|(k, _)| *k).collect::<Vec<_>>());
        println!("first_key_value {:?}  last_key_value {:?}", m.first_key_value(), m.last_key_value());
        println!("pop_first {:?}  pop_last {:?}  剩 {} 个", m.pop_first(), m.pop_last(), m.len());
        println!("小于等于 45 的最大键: {:?}", m.range(..=45).next_back().map(|(k, _)| *k));
    }
''', quiet_src=True); R['api'] = r['out']
print()
print('== 二:HashMap 没有 range:同样的需求要全表扫描')
r = tryit('u60b', '''
    use std::collections::HashMap;
    fn main() { let m: HashMap<i32, i32> = HashMap::new(); let _ = m.range(1..5); }
''', maxlines=25); R['e_range'] = r['diag'].split('\\n')[0]
print()
print('== 三:键的要求不同:BTreeMap 要 Ord,HashMap 要 Hash + Eq')
r = tryit('u60c', '''
    use std::collections::{BTreeMap, HashMap};
    #[derive(PartialEq, Eq, Hash, Debug)] struct P(i32);
    fn main() {
        let mut h = HashMap::new(); h.insert(P(1), "hash ok");
        let mut b = BTreeMap::new(); b.insert(P(1), "btree");
        println!("{:?} {:?}", h, b);
    }
''', maxlines=30); R['e_ord'] = r['diag']
r = tryit('u60d', '''
    use std::collections::BTreeMap; use std::cmp::Ordering;
    #[derive(PartialEq, Eq, Debug)] struct Rev(i32);
    impl PartialOrd for Rev { fn partial_cmp(&self, o: &Self) -> Option<Ordering> { Some(self.cmp(o)) } }
    impl Ord for Rev { fn cmp(&self, o: &Self) -> Ordering { o.0.cmp(&self.0) } }
    fn main() {
        let mut b = BTreeMap::new(); for i in [3, 1, 2] { b.insert(Rev(i), i); }
        println!("自定义 Ord(反序)的遍历: {:?}", b.keys().collect::<Vec<_>>());
    }
''', quiet_src=True); R['rev'] = r['out']
print()
print('== 四:速度:随机顺序插入与查找(release;各取 3 次最小);键是 u64')
r = tryit('u60e', '''
    use std::collections::{BTreeMap, HashMap}; use std::hint::black_box; use std::time::Instant;
    fn main() {
        let mut x = 88172645463325252u64; let mut rng = move || { x ^= x << 13; x ^= x >> 7; x ^= x << 17; x };
        for n in [1_000usize, 100_000, 1_000_000] {
            let keys: Vec<u64> = (0..n).map(|_| rng()).collect();
            let (mut ih, mut ib, mut lh, mut lb) = (f64::MAX, f64::MAX, f64::MAX, f64::MAX);
            for _ in 0..3 {
                let t = Instant::now(); let mut h = HashMap::new(); for &k in &keys { h.insert(k, k); } ih = ih.min(t.elapsed().as_secs_f64());
                let t = Instant::now(); let mut b = BTreeMap::new(); for &k in &keys { b.insert(k, k); } ib = ib.min(t.elapsed().as_secs_f64());
                let t = Instant::now(); let mut s = 0u64; for &k in &keys { s = s.wrapping_add(*black_box(&h).get(&k).unwrap()); } black_box(s); lh = lh.min(t.elapsed().as_secs_f64());
                let t = Instant::now(); let mut s = 0u64; for &k in &keys { s = s.wrapping_add(*black_box(&b).get(&k).unwrap()); } black_box(s); lb = lb.min(t.elapsed().as_secs_f64());
            }
            println!("n={:>8}: 插入 HashMap {:>8.2} ms / BTreeMap {:>8.2} ms   查找 HashMap {:>8.2} ms / BTreeMap {:>8.2} ms", n, ih * 1e3, ib * 1e3, lh * 1e3, lb * 1e3);
        }
    }
''', quiet_src=True, release=True); R['bench'] = r['out']
print()
print('== 五:范围查询的代价:100 万个键里取 [a, a+1000) 范围的元素个数;BTreeMap::range 与 HashMap 全表过滤')
r = tryit('u60f', '''
    use std::collections::{BTreeMap, HashMap}; use std::hint::black_box; use std::time::Instant;
    fn main() {
        let n = 1_000_000u64;
        let b: BTreeMap<u64, u64> = (0..n).map(|i| (i * 7, i)).collect(); let h: HashMap<u64, u64> = b.iter().map(|(k, v)| (*k, *v)).collect();
        let (lo, hi) = (3_500_000u64, 3_501_000u64);
        let t = Instant::now(); let c1 = black_box(&b).range(lo..hi).count(); let tb = t.elapsed();
        let t = Instant::now(); let c2 = black_box(&h).iter().filter(|(k, _)| **k >= lo && **k < hi).count(); let th = t.elapsed();
        println!("BTreeMap::range 找到 {} 个,用时 {:?}", c1, tb);
        println!("HashMap 全表过滤 找到 {} 个,用时 {:?}", c2, th);
    }
''', quiet_src=True, release=True); R['range'] = r['out']
print()
print('== 六:分配次数:1000 个 u64 键值对')
r = tryit('u60g', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
    static A: AtomicUsize = AtomicUsize::new(0); static RE: AtomicUsize = AtomicUsize::new(0); static MAXL: AtomicUsize = AtomicUsize::new(0);
    struct C;
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { A.fetch_add(1, Relaxed); MAXL.fetch_max(l.size(), Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { unsafe { System.dealloc(p, l) } }
        unsafe fn realloc(&self, p: *mut u8, l: Layout, n: usize) -> *mut u8 { RE.fetch_add(1, Relaxed); unsafe { System.realloc(p, l, n) } }
    }
    #[global_allocator] static G: C = C;
    use std::collections::{BTreeMap, HashMap};
    fn main() {
        let a0 = A.load(Relaxed); let m0 = MAXL.load(Relaxed);
        let mut b = BTreeMap::new(); for i in 0..1000u64 { b.insert(i, i); }
        let a1 = A.load(Relaxed); let mb = MAXL.load(Relaxed);
        MAXL.store(0, Relaxed);
        let mut h = HashMap::new(); for i in 0..1000u64 { h.insert(i, i); }
        let a2 = A.load(Relaxed); let mh = MAXL.load(Relaxed);
        println!("BTreeMap<u64,u64> 1000 个:alloc {} 次,最大单次 {} 字节", a1 - a0, mb);
        println!("HashMap<u64,u64>  1000 个:alloc {} 次,最大单次 {} 字节", a2 - a1, mh);
        let _ = m0;
    }
''', quiet_src=True, release=True); R['alloc'] = r['out']
save('u60', R)
