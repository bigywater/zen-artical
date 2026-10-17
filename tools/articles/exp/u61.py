import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u61'); R = {}
print('== 一:insert 返回值就是「是否新增」;集合运算(交、并、差、对称差)')
r = tryit('u61a', '''
    use std::collections::{BTreeSet, HashSet};
    fn main() {
        let mut s = HashSet::new();
        println!("insert 3 -> {}  insert 5 -> {}  再 insert 3 -> {}  len {}", s.insert(3), s.insert(5), s.insert(3), s.len());
        println!("remove 5 -> {}  remove 9 -> {}  contains 3 -> {}", s.remove(&5), s.remove(&9), s.contains(&3));
        let a: BTreeSet<i32> = [1, 2, 3, 4].into(); let b: BTreeSet<i32> = [3, 4, 5].into();
        println!("交 {:?}  并 {:?}  差 a-b {:?}  对称差 {:?}", a.intersection(&b).collect::<Vec<_>>(), a.union(&b).collect::<Vec<_>>(), a.difference(&b).collect::<Vec<_>>(), a.symmetric_difference(&b).collect::<Vec<_>>());
        println!("is_subset {}  is_disjoint {}", [3, 4].iter().copied().collect::<BTreeSet<_>>().is_subset(&a), a.is_disjoint(&b));
        let h1: HashSet<i32> = [1, 2, 3].into(); let h2: HashSet<i32> = [3, 2, 1].into();
        println!("HashSet 相等与顺序无关: {}", h1 == h2);
        println!("&a | &b = {:?}  &a & &b = {:?}", &a | &b, &a & &b);
    }
''', quiet_src=True); R['ops'] = r['out']
print()
print('== 二:去重的三种写法:保序(用 HashSet 记已见)、排序后 dedup、直接 collect 成集合 —— 结果与顺序')
r = tryit('u61b', '''
    use std::collections::{BTreeSet, HashSet};
    fn main() {
        let v = vec![3, 1, 3, 2, 1, 5, 2];
        let mut seen = HashSet::new();
        let keep: Vec<i32> = v.iter().copied().filter(|x| seen.insert(*x)).collect();
        println!("保持首次出现顺序: {:?}", keep);
        let mut s = v.clone(); s.sort(); s.dedup();
        println!("sort + dedup:     {:?}", s);
        let b: BTreeSet<i32> = v.iter().copied().collect();
        println!("BTreeSet:         {:?}", b.iter().collect::<Vec<_>>());
        let mut d = v.clone(); d.dedup();
        println!("只 dedup(不排序): {:?}  ← dedup 只去掉相邻的重复", d);
    }
''', quiet_src=True); R['dedup'] = r['out']
print()
print('== 三:性能:100 万个元素(约 10 万种取值)去重,三种方式(release,各 3 次取最小)')
r = tryit('u61c', '''
    use std::collections::{BTreeSet, HashSet}; use std::hint::black_box; use std::time::Instant;
    fn main() {
        let mut x = 88172645463325252u64; let mut rng = move || { x ^= x << 13; x ^= x >> 7; x ^= x << 17; x };
        let v: Vec<u64> = (0..1_000_000).map(|_| rng() % 100_000).collect();
        let (mut a, mut b, mut c) = (f64::MAX, f64::MAX, f64::MAX); let (mut na, mut nb, mut nc) = (0, 0, 0);
        for _ in 0..3 {
            let t = Instant::now(); let s: HashSet<u64> = black_box(&v).iter().copied().collect(); a = a.min(t.elapsed().as_secs_f64() * 1e3); na = s.len();
            let t = Instant::now(); let mut w = black_box(&v).clone(); w.sort_unstable(); w.dedup(); b = b.min(t.elapsed().as_secs_f64() * 1e3); nb = w.len();
            let t = Instant::now(); let s: BTreeSet<u64> = black_box(&v).iter().copied().collect(); c = c.min(t.elapsed().as_secs_f64() * 1e3); nc = s.len();
        }
        println!("HashSet collect {:>7.2} ms (去重后 {} 个)", a, na);
        println!("sort_unstable + dedup {:>7.2} ms (去重后 {} 个)", b, nb);
        println!("BTreeSet collect {:>7.2} ms (去重后 {} 个)", c, nc);
    }
''', quiet_src=True, release=True); R['bench'] = r['out']
print()
print('== 四:自定义类型进 HashSet:相等与哈希必须一致;只比较部分字段时的去重语义')
r = tryit('u61d', '''
    use std::collections::HashSet; use std::hash::{Hash, Hasher};
    #[derive(Debug)] struct User { id: u32, name: &'static str }
    impl PartialEq for User { fn eq(&self, o: &Self) -> bool { self.id == o.id } }
    impl Eq for User {}
    impl Hash for User { fn hash<H: Hasher>(&self, h: &mut H) { self.id.hash(h); } }
    fn main() {
        let mut s = HashSet::new();
        println!("{}", s.insert(User { id: 1, name: "alice" }));
        println!("同 id 不同 name 再插入 -> {}(被当作重复,保留的是 {:?})", s.insert(User { id: 1, name: "ALICE" }), s.iter().next().unwrap());
        println!("replace 才会替换 -> 旧值 {:?},现在是 {:?}", s.replace(User { id: 1, name: "ALICE" }).map(|u| u.name), s.iter().next().unwrap().name);
    }
''', quiet_src=True); R['custom'] = r['out']
r = tryit('u61e', '''
    use std::collections::HashSet; use std::hash::{Hash, Hasher};
    #[derive(Debug)] struct Bad(u32);
    impl PartialEq for Bad { fn eq(&self, _: &Self) -> bool { true } }   // 所有 Bad 都相等
    impl Eq for Bad {}
    impl Hash for Bad { fn hash<H: Hasher>(&self, h: &mut H) { self.0.hash(h); } }  // 哈希却不同
    fn main() {
        let mut s = HashSet::new(); for i in 0..20 { s.insert(Bad(i)); }
        println!("{}", s.len());
    }
''', quiet_src=True); lens = [int(run(r['bin'])[1].strip()) for _ in range(12)]
print('  eq 恒为 true、哈希按内部值:20 个元素插入后 len,同一个程序运行 12 次:', lens, '(理想的集合应当总是 1)')
R['bad'] = lens
save('u61', R)
