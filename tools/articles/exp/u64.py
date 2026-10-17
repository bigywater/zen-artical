import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u64'); R = {}
print('== 一:没有目标类型就无法 collect:E0283;三种给类型的方式')
r = tryit('u64a', '''
    fn main() {
        let v = (1..4).map(|x| x * 2).collect();
        println!("{:?}", v);
    }
''', maxlines=35); R['e0283'] = r['diag']
r = tryit('u64b', '''
    use std::collections::{BTreeSet, HashMap, VecDeque};
    fn evens() -> Vec<u32> { (1..=6).filter(|x| x % 2 == 0).collect() }
    fn main() {
        let a: Vec<i32> = (1..4).collect();
        let b = (1..4).collect::<VecDeque<i32>>();
        let c = (1..4).map(|x| x * x).collect::<Vec<_>>();
        println!("标注变量类型 {:?} / turbofish {:?} / turbofish+占位符 {:?} / 靠函数返回类型 {:?}", a, b, c, evens());
        let m: HashMap<&str, usize> = ["a", "bb", "ccc"].iter().map(|s| (*s, s.len())).collect();
        let mut keys: Vec<_> = m.iter().collect(); keys.sort();
        println!("HashMap(排序后显示): {:?}", keys);
        let st: BTreeSet<char> = "hello".chars().collect(); println!("BTreeSet<char>: {:?}", st);
        let s: String = vec!['r', 'u', 's', 't'].into_iter().collect(); let t: String = ["ru", "st"].into_iter().collect(); let u: String = vec![String::from("a"), String::from("b")].into_iter().collect();
        println!("String 可以从 char / &str / String 收集: {} {} {}", s, t, u);
        let bx: Box<[i32]> = (1..4).collect(); println!("Box<[i32]>: {:?}", bx);
        let (ev, od): (Vec<i32>, Vec<i32>) = (1..=6).partition(|x| x % 2 == 0); println!("partition: {:?} {:?}", ev, od);
        let (xs, ys): (Vec<i32>, Vec<char>) = [(1, 'a'), (2, 'b')].into_iter().unzip(); println!("unzip: {:?} {:?}", xs, ys);
        println!("collect 成 (): {:?}", [Ok::<(), ()>(()), Ok(())].into_iter().collect::<Result<(), ()>>());
    }
''', quiet_src=True); R['forms'] = r['out']
print()
print('== 二:collect 到 Result / Option:遇到第一个失败就停止,后面的元素不再被处理(计数)')
r = tryit('u64c', '''
    use std::cell::Cell;
    fn main() {
        let seen = Cell::new(0);
        let r: Result<Vec<i32>, std::num::ParseIntError> = ["1", "2", "x", "4", "5"].iter().map(|s| { seen.set(seen.get() + 1); s.parse::<i32>() }).collect();
        println!("Result<Vec<_>,_>: {:?}  闭包只被调用了 {} 次(共 5 个元素)", r, seen.get());
        seen.set(0);
        let o: Option<Vec<u32>> = ["1", "2", "3"].iter().map(|s| { seen.set(seen.get() + 1); s.parse().ok() }).collect();
        println!("全部成功: {:?}  调用 {} 次", o, seen.get());
        let sum: Option<u32> = [Some(1u32), None, Some(3)].into_iter().sum(); let sum2: Option<u32> = [Some(1u32), Some(3)].into_iter().sum();
        println!("Option 的 sum: {:?} / {:?}", sum, sum2);
    }
''', quiet_src=True); R['res'] = r['out']
print()
print('== 三:同一个迭代器收集成不同类型,结果不同(推断出来的类型决定语义):重复键')
r = tryit('u64d', '''
    use std::collections::{HashMap, HashSet, BTreeMap};
    fn main() {
        let pairs = [("a", 1), ("b", 2), ("a", 3)];
        let v: Vec<_> = pairs.iter().collect();
        let m: BTreeMap<_, _> = pairs.iter().cloned().collect();
        let hs: HashSet<_> = pairs.iter().map(|p| p.0).collect();
        println!("Vec 保留 {} 个: {:?}", v.len(), v);
        println!("BTreeMap 重复键后者覆盖前者,剩 {} 个: {:?}", m.len(), m);
        println!("HashSet 只取键,剩 {} 个", hs.len());
        let h: HashMap<_, _> = pairs.iter().cloned().collect(); println!("HashMap 里 a = {:?}", h["a"]);
    }
''', quiet_src=True); R['dup'] = r['out']
print()
print('== 四:预分配:collect 到 Vec 时用 size_hint 一次分配;filter 的下界是 0,会多次 realloc(全局分配器计数)')
r = tryit('u64e', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
    static A: AtomicUsize = AtomicUsize::new(0); static RE: AtomicUsize = AtomicUsize::new(0);
    struct C;
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { A.fetch_add(1, Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { unsafe { System.dealloc(p, l) } }
        unsafe fn realloc(&self, p: *mut u8, l: Layout, n: usize) -> *mut u8 { RE.fetch_add(1, Relaxed); unsafe { System.realloc(p, l, n) } }
    }
    #[global_allocator] static G: C = C;
    fn snap() -> (usize, usize) { (A.load(Relaxed), RE.load(Relaxed)) }
    fn main() {
        let n = 10_000u64;
        let s0 = snap(); let a: Vec<u64> = (0..n).map(|x| x * 2).collect(); let s1 = snap();
        let b: Vec<u64> = (0..n).filter(|x| x % 2 == 0).collect(); let s2 = snap();
        let c: Vec<u64> = (0..n).filter(|x| x % 2 == 0).map(|x| x + 1).collect(); let s3 = snap();
        let hint_map = (0..n).map(|x| x * 2).size_hint(); let hint_filter = (0..n).filter(|x| x % 2 == 0).size_hint();
        println!("map:    alloc {} realloc {}  size_hint {:?}  len {} cap {}", s1.0 - s0.0, s1.1 - s0.1, hint_map, a.len(), a.capacity());
        println!("filter: alloc {} realloc {}  size_hint {:?}  len {} cap {}", s2.0 - s1.0, s2.1 - s1.1, hint_filter, b.len(), b.capacity());
        println!("filter+map: alloc {} realloc {}  len {} cap {}", s3.0 - s2.0, s3.1 - s2.1, c.len(), c.capacity());
    }
''', quiet_src=True, release=True); R['prealloc'] = r['out']
save('u64', R)
