import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u69'); R = {}
print('== 一:稳定性:按 key 排序,key 相同的元素 sort 保持原来的相对顺序,sort_unstable 不保证(找一个真实打乱的例子)')
r = tryit('u69a', '''
    fn main() {
        // (key, 原始序号);key 只有 3 种,所以有大量相同 key
        let mut x = 88172645463325252u64; let mut rng = move || { x ^= x << 13; x ^= x >> 7; x ^= x << 17; x };
        let base: Vec<(u32, u32)> = (0..200).map(|i| ((rng() % 3) as u32, i)).collect();
        let mut a = base.clone(); a.sort_by_key(|p| p.0);
        let mut b = base.clone(); b.sort_unstable_by_key(|p| p.0);
        let stable_ok = a.windows(2).all(|w| w[0].0 != w[1].0 || w[0].1 < w[1].1);
        let unstable_ok = b.windows(2).all(|w| w[0].0 != w[1].0 || w[0].1 < w[1].1);
        println!("200 个元素、3 种 key:sort_by_key 保持了相同 key 的原顺序: {}  sort_unstable_by_key 保持了: {}", stable_ok, unstable_ok);
        let first_bad = b.windows(2).find(|w| w[0].0 == w[1].0 && w[0].1 > w[1].1).unwrap();
        println!("sort_unstable 打乱的一个例子:相邻两个 key 相同的元素 {:?} 排在 {:?} 前面(原始序号反了)", first_bad[0], first_bad[1]);
        println!("两种排序的 key 序列相同: {}", a.iter().map(|p| p.0).eq(b.iter().map(|p| p.0)));
    }
''', quiet_src=True); R['stab'] = r['out']
print()
print('== 二:内存:sort 需要辅助缓冲区(分配器计数),sort_unstable 原地排序')
r = tryit('u69b', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
    static A: AtomicUsize = AtomicUsize::new(0); static B: AtomicUsize = AtomicUsize::new(0); static MX: AtomicUsize = AtomicUsize::new(0);
    struct C;
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { A.fetch_add(1, Relaxed); B.fetch_add(l.size(), Relaxed); MX.fetch_max(l.size(), Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { unsafe { System.dealloc(p, l) } }
    }
    #[global_allocator] static G: C = C;
    fn main() {
        for n in [10usize, 20, 100, 10_000] {
            let mut x = 88172645463325252u64; let mut rng = move || { x ^= x << 13; x ^= x >> 7; x ^= x << 17; x };
            let base: Vec<u64> = (0..n).map(|_| rng()).collect();
            let mut a = base.clone(); let mut b = base.clone();
            let (a0, b0) = (A.load(Relaxed), B.load(Relaxed)); a.sort(); let (a1, b1) = (A.load(Relaxed), B.load(Relaxed));
            b.sort_unstable(); let (a2, b2) = (A.load(Relaxed), B.load(Relaxed));
            if n == 10_000 {
                let mut first = None;
                for m in 1..=5000usize {
                    let mut y = base[..m].to_vec(); let c0 = A.load(Relaxed); y.sort(); if A.load(Relaxed) != c0 { first = Some(m); break; }
                }
                let mut first_u = None;
                for m in 1..=5000usize {
                    let mut y = base[..m].to_vec(); let c0 = A.load(Relaxed); y.sort_unstable(); if A.load(Relaxed) != c0 { first_u = Some(m); break; }
                }
                println!("第一个让 sort 发生堆分配的元素个数(u64,在 1..=5000 里扫描): {:?};sort_unstable 在 1..=5000 里的第一次分配: {:?}", first, first_u);
            }
            println!("n={:>6}: sort 分配 {} 次 {} 字节   sort_unstable 分配 {} 次 {} 字节", n, a1 - a0, b1 - b0, a2 - a1, b2 - b1);
        }
    }
''', quiet_src=True, release=True); R['mem'] = r['out']
print()
print('== 三:速度(release,各 5 次取最小):随机 / 已有序 / 逆序 / 大量重复(只有 10 种值),100 万个 u64')
r = tryit('u69c', '''
    use std::hint::black_box; use std::time::Instant;
    fn bench(name: &str, base: &Vec<u64>) {
        let (mut s, mut u) = (f64::MAX, f64::MAX);
        for _ in 0..5 {
            let mut a = base.clone(); let t = Instant::now(); black_box(&mut a).sort(); s = s.min(t.elapsed().as_secs_f64() * 1e3);
            let mut b = base.clone(); let t = Instant::now(); black_box(&mut b).sort_unstable(); u = u.min(t.elapsed().as_secs_f64() * 1e3);
            assert!(a == b);
        }
        println!("{:<10} sort {:>8.3} ms   sort_unstable {:>8.3} ms", name, s, u);
    }
    fn main() {
        let n = 1_000_000u64; let mut x = 88172645463325252u64; let mut rng = move || { x ^= x << 13; x ^= x >> 7; x ^= x << 17; x };
        let rand: Vec<u64> = (0..n).map(|_| rng()).collect();
        let mut sorted = rand.clone(); sorted.sort(); let mut rev = sorted.clone(); rev.reverse();
        let dups: Vec<u64> = rand.iter().map(|v| v % 10).collect();
        bench("随机", &rand); bench("已有序", &sorted); bench("逆序", &rev); bench("大量重复", &dups);
    }
''', quiet_src=True, release=True); R['speed'] = r['out']
print()
print('== 四:sort_by_key 对每次比较都重新计算 key;sort_by_cached_key 每个元素只算一次(调用次数)')
r = tryit('u69d', '''
    use std::cell::Cell;
    fn main() {
        let words: Vec<String> = (0..1000).map(|i| format!("w{:04}", (i * 7919) % 1000)).collect();
        let calls = Cell::new(0);
        let mut a = words.clone(); a.sort_by_key(|s| { calls.set(calls.get() + 1); s.len() as u32 * 100000 + s[1..].parse::<u32>().unwrap() });
        let c1 = calls.get(); calls.set(0);
        let mut b = words.clone(); b.sort_by_cached_key(|s| { calls.set(calls.get() + 1); s.len() as u32 * 100000 + s[1..].parse::<u32>().unwrap() });
        println!("1000 个元素:sort_by_key 的 key 函数被调用 {} 次;sort_by_cached_key 调用 {} 次;结果相同: {}", c1, calls.get(), a == b);
    }
''', quiet_src=True, release=True); R['key'] = r['out']
print()
print('== 五:f64 没有 Ord:v.sort() 报错;用 sort_by(partial_cmp) 或 total_cmp;NaN 的处理')
r = tryit('u69e', '''
    fn main() { let mut v = vec![2.5, 1.0]; v.sort(); }
''', maxlines=25); R['e_f64'] = r['diag']
r = tryit('u69f', '''
    fn main() {
        let mut v = vec![2.5, f64::NAN, -1.0, 0.0, -0.0, 1.0];
        v.sort_by(|a, b| a.total_cmp(b)); println!("total_cmp: {:?}", v);
        let mut w = vec![2.5, -1.0, 1.0]; w.sort_by(|a, b| a.partial_cmp(b).unwrap()); println!("partial_cmp.unwrap(): {:?}", w);
        println!("total_cmp 把 -0.0 排在 0.0 前面,NaN 排在最后(正 NaN)");
    }
''', quiet_src=True); R['f64'] = r['out']
save('u69', R)
