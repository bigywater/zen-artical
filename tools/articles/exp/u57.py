import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u57'); R = {}
print('== 一:push_front / push_back / pop_front 的结果,以及 as_slices 暴露出的环形布局')
r = tryit('u57a', '''
    use std::collections::VecDeque;
    fn main() {
        let mut d: VecDeque<i32> = VecDeque::with_capacity(8);
        println!("with_capacity(8): len {} cap {}", d.len(), d.capacity());
        for i in 1..=5 { d.push_back(i); }
        println!("push_back 1..=5:  {:?}  as_slices = {:?}", d, d.as_slices());
        d.pop_front(); d.pop_front();
        println!("pop_front ×2:     {:?}  as_slices = {:?}", d, d.as_slices());
        for i in 6..=9 { d.push_back(i); }
        println!("再 push_back 6..=9: {:?}  as_slices = {:?}  (逻辑上连续,物理上绕回了缓冲区开头)", d, d.as_slices());
        d.push_front(0);
        println!("push_front(0):    {:?}  as_slices = {:?}  cap {}", d, d.as_slices(), d.capacity());
        let s = d.make_contiguous();
        println!("make_contiguous:  {:?}", s);
        println!("之后 as_slices = {:?}", d.as_slices());
    }
''', quiet_src=True, release=True); R['slices'] = r['out']
print()
print('== 二:内存位置:用元素地址证明环形(元素地址在缓冲区内回绕)')
r = tryit('u57b', '''
    use std::collections::VecDeque;
    fn main() {
        let mut d: VecDeque<u64> = VecDeque::with_capacity(4);
        let base = { d.push_back(0); let p = &d[0] as *const u64 as usize; d.pop_back(); p };
        println!("cap {}", d.capacity());
        for i in 0..4u64 { d.push_back(i); }
        d.pop_front(); d.pop_front();
        d.push_back(10); d.push_back(11);
        for (i, x) in d.iter().enumerate() {
            let off = (x as *const u64 as usize).wrapping_sub(base) / 8;
            println!("逻辑下标 {} 值 {:>2}  物理槽位 {}", i, x, off);
        }
    }
''', quiet_src=True, release=True); R['slots'] = r['out']
print()
print('== 三:Vec::insert(0) 与 VecDeque::push_front 在 5 万个元素上的耗时(release,各 3 次)')
r = tryit('u57c', '''
    use std::collections::VecDeque; use std::hint::black_box; use std::time::Instant;
    fn main() {
        let n = 50_000u32;
        for _ in 0..3 {
            let t = Instant::now(); let mut v: Vec<u32> = Vec::new(); for i in 0..n { v.insert(0, black_box(i)); } let a = t.elapsed();
            let t = Instant::now(); let mut d: VecDeque<u32> = VecDeque::new(); for i in 0..n { d.push_front(black_box(i)); } let b = t.elapsed();
            assert_eq!(v.len(), d.len());
            println!("Vec::insert(0) {:>9.2} ms   VecDeque::push_front {:>7.3} ms", a.as_secs_f64() * 1e3, b.as_secs_f64() * 1e3);
        }
    }
''', quiet_src=True, release=True); R['bench'] = r['out']
print()
print('== 四:VecDeque 不是切片:可以下标访问,但 &VecDeque 不能当 &[T];要切片得 make_contiguous / as_slices')
r = tryit('u57d', '''
    use std::collections::VecDeque;
    fn main() {
        let mut d: VecDeque<i32> = (1..=5).collect(); d.rotate_left(2);
        println!("d = {:?}  d[0] = {}  d[4] = {}  get(9) = {:?}", d, d[0], d[4], d.get(9));
    }
''', quiet_src=True); R['idx'] = r['out']
r = tryit('u57d2', '''
    use std::collections::VecDeque;
    fn main() {
        let d: VecDeque<i32> = (1..=5).collect();
        let sl: &[i32] = &d;
        println!("{:?}", sl);
    }
''', quiet_src=False, maxlines=25); R['e0308'] = r['diag'].split('\n')[0]
r = tryit('u57e', '''
    use std::collections::VecDeque;
    fn main() {
        let mut d: VecDeque<i32> = (1..=5).collect(); d.rotate_left(2);
        d.make_contiguous().sort();
        println!("make_contiguous().sort() 之后 {:?}", d);
        let v: Vec<i32> = d.into();  println!("VecDeque → Vec: {:?}", v);
        let d2: VecDeque<i32> = v.into(); println!("Vec → VecDeque: {:?} (as_slices {:?})", d2, d2.as_slices());
    }
''', quiet_src=True); R['conv'] = r['out']
save('u57', R)
