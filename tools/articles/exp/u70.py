import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u70'); R = {}
print('== 一:默认是最大堆;peek 看堆顶;into_vec 暴露内部数组(满足堆序但不是排序);into_sorted_vec 升序')
r = tryit('u70a', '''
    use std::collections::BinaryHeap; use std::cmp::Reverse;
    fn main() {
        let mut h = BinaryHeap::new();
        for x in [5, 1, 8, 3, 9, 2, 7] { h.push(x); }
        println!("peek = {:?}  len = {}", h.peek(), h.len());
        println!("内部数组 into_vec(堆序,不是排序): {:?}", h.clone().into_vec());
        println!("连续 pop: {:?}", { let mut c = h.clone(); let mut o = vec![]; while let Some(x) = c.pop() { o.push(x); } o });
        println!("into_sorted_vec(升序): {:?}", h.clone().into_sorted_vec());
        println!("iter() 的顺序是内部数组顺序,不是排序: {:?}", h.iter().collect::<Vec<_>>());
        let mut m = BinaryHeap::new(); for x in [5, 1, 8, 3] { m.push(Reverse(x)); }
        println!("最小堆(Reverse):连续 pop {:?}", std::iter::from_fn(|| m.pop().map(|Reverse(x)| x)).collect::<Vec<_>>());
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:自定义优先级:任务按 priority 大者先出;相同 priority 的出队顺序不保证 FIFO')
r = tryit('u70b', '''
    use std::collections::BinaryHeap; use std::cmp::Ordering;
    #[derive(Debug, PartialEq, Eq)] struct Task { pri: u32, id: u32 }
    impl Ord for Task { fn cmp(&self, o: &Self) -> Ordering { self.pri.cmp(&o.pri) } }
    impl PartialOrd for Task { fn partial_cmp(&self, o: &Self) -> Option<Ordering> { Some(self.cmp(o)) } }
    #[derive(Debug, PartialEq, Eq)] struct Fifo { pri: u32, seq: u32 }
    impl Ord for Fifo { fn cmp(&self, o: &Self) -> Ordering { self.pri.cmp(&o.pri).then(o.seq.cmp(&self.seq)) } }
    impl PartialOrd for Fifo { fn partial_cmp(&self, o: &Self) -> Option<Ordering> { Some(self.cmp(o)) } }
    fn main() {
        let mut h = BinaryHeap::new(); for id in 0..8 { h.push(Task { pri: if id % 2 == 0 { 1 } else { 2 }, id }); }
        println!("只按 pri 比较:   {:?}", std::iter::from_fn(|| h.pop().map(|t| (t.pri, t.id))).collect::<Vec<_>>());
        let mut g = BinaryHeap::new(); for seq in 0..8 { g.push(Fifo { pri: if seq % 2 == 0 { 1 } else { 2 }, seq }); }
        println!("pri 相同再按 seq:{:?}", std::iter::from_fn(|| g.pop().map(|t| (t.pri, t.seq))).collect::<Vec<_>>());
    }
''', quiet_src=True); R['fifo'] = r['out']
print()
print('== 三:peek_mut:修改堆顶,PeekMut 离开作用域时才重新整理堆')
r = tryit('u70c', '''
    use std::collections::{BinaryHeap, binary_heap::PeekMut};
    fn main() {
        let mut h: BinaryHeap<i32> = [10, 7, 8, 1].into();
        println!("初始 peek {:?}", h.peek());
        if let Some(mut top) = h.peek_mut() { *top = 0; println!("把堆顶改成 0,此时 PeekMut 还没离开作用域"); }
        println!("离开作用域后 peek {:?}(堆自动重排)", h.peek());
        if let Some(top) = h.peek_mut() { let v = PeekMut::pop(top); println!("PeekMut::pop 取出 {}", v); }
        println!("剩下按序: {:?}", h.into_sorted_vec());
    }
''', quiet_src=True); R['peekmut'] = r['out']
print()
print('== 四:比较次数(用计数的 Ord):逐个 push n 个 vs BinaryHeap::from(vec)(堆化)vs 全部 pop')
r = tryit('u70d', '''
    use std::collections::BinaryHeap; use std::cmp::Ordering; use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
    static CMP: AtomicUsize = AtomicUsize::new(0);
    #[derive(PartialEq, Eq, Clone)] struct K(u64);
    impl Ord for K { fn cmp(&self, o: &Self) -> Ordering { CMP.fetch_add(1, Relaxed); self.0.cmp(&o.0) } }
    impl PartialOrd for K { fn partial_cmp(&self, o: &Self) -> Option<Ordering> { Some(self.cmp(o)) } }
    fn main() {
        println!("{:>8} {:>14} {:>14} {:>14} {:>10}", "n", "逐个 push", "from(vec)", "全部 pop", "n·log2(n)");
        for n in [1_000usize, 10_000, 100_000] {
            let mut x = 88172645463325252u64; let mut rng = move || { x ^= x << 13; x ^= x >> 7; x ^= x << 17; x };
            let keys: Vec<K> = (0..n).map(|_| K(rng())).collect();
            CMP.store(0, Relaxed); let mut h = BinaryHeap::new(); for k in keys.iter().cloned() { h.push(k); } let c_push = CMP.load(Relaxed);
            CMP.store(0, Relaxed); let h2 = BinaryHeap::from(keys.clone()); let c_from = CMP.load(Relaxed);
            CMP.store(0, Relaxed); while h.pop().is_some() {} let c_pop = CMP.load(Relaxed);
            drop(h2);
            println!("{:>8} {:>14} {:>14} {:>14} {:>10.0}", n, c_push, c_from, c_pop, n as f64 * (n as f64).log2());
        }
    }
''', quiet_src=True, release=True); R['cmp'] = r['out']
print()
print('== 五:Dijkstra 最短路(BinaryHeap<Reverse<(dist, node)>>),一个 6 个节点的小图')
r = tryit('u70e', '''
    use std::collections::BinaryHeap; use std::cmp::Reverse;
    fn main() {
        // 边 (from, to, w)
        let edges = [(0, 1, 7), (0, 2, 9), (0, 5, 14), (1, 2, 10), (1, 3, 15), (2, 3, 11), (2, 5, 2), (3, 4, 6), (4, 5, 9)];
        let n = 6; let mut adj = vec![vec![]; n];
        for &(a, b, w) in &edges { adj[a].push((b, w)); adj[b].push((a, w)); }
        let mut dist = vec![u32::MAX; n]; dist[0] = 0;
        let mut h = BinaryHeap::new(); h.push(Reverse((0u32, 0usize))); let mut pops = 0;
        while let Some(Reverse((d, u))) = h.pop() {
            pops += 1; if d > dist[u] { continue; }
            for &(v, w) in &adj[u] { let nd = d + w; if nd < dist[v] { dist[v] = nd; h.push(Reverse((nd, v))); } }
        }
        println!("从节点 0 出发的最短距离: {:?}(堆总共 pop 了 {} 次)", dist, pops);
    }
''', quiet_src=True); R['dij'] = r['out']
save('u70', R)
