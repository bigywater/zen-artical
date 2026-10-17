import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u65'); R = {}
print('== 一:flat_map = map + flatten;展开嵌套数据:二维数组、字符串拆词、Option')
r = tryit('u65a', '''
    fn main() {
        let grid = vec![vec![1, 2], vec![], vec![3, 4, 5]];
        let a: Vec<i32> = grid.iter().flat_map(|row| row.iter().copied()).collect();
        let b: Vec<i32> = grid.iter().map(|row| row.iter().copied()).flatten().collect();
        let c: Vec<i32> = grid.iter().flatten().copied().collect();
        println!("flat_map {:?} / map+flatten {:?} / flatten {:?}", a, b, c);
        let lines = ["to be or", "not to be"];
        let words: Vec<&str> = lines.iter().flat_map(|l| l.split(' ')).collect();
        println!("按行拆词: {:?}", words);
        let chars: Vec<char> = ["ab", "cd"].iter().flat_map(|s| s.chars()).collect();
        println!("字符: {:?}", chars);
        let opts = [Some(1), None, Some(3)];
        println!("flat_map 把 Option 当作 0 或 1 个元素: {:?}", opts.iter().flat_map(|o| o.iter()).collect::<Vec<_>>());
        println!("一对多:每个数 n 展开成 1..=n: {:?}", (1..=3).flat_map(|n| 1..=n).collect::<Vec<_>>());
        println!("笛卡尔积: {:?}", (1..=2).flat_map(|x| ['a', 'b'].into_iter().map(move |c| (x, c))).collect::<Vec<_>>());
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:内层闭包借用外层变量会报错:需要 move')
r = tryit('u65b', '''
    fn main() {
        let v: Vec<(i32, i32)> = (1..=2).flat_map(|x| (1..=2).map(|y| (x, y))).collect();
        println!("{:?}", v);
    }
''', maxlines=40); R['e0373'] = r['diag']
print()
print('== 三:惰性:内层迭代器只在需要时才创建;take 提前结束时后面的外层元素不会被展开(计数)')
r = tryit('u65c', '''
    use std::cell::Cell;
    fn main() {
        let made = Cell::new(0); let yielded = Cell::new(0);
        let it = (1..=1000).flat_map(|n| { made.set(made.get() + 1); (0..n).inspect(|_| yielded.set(yielded.get() + 1)) });
        let first: Vec<i32> = it.take(7).collect();
        println!("take(7) = {:?}", first);
        println!("内层迭代器创建了 {} 个(外层有 1000 个),内层元素共产出 {} 个", made.get(), yielded.get());
    }
''', quiet_src=True); R['lazy'] = r['out']
print()
print('== 四:flatten 的类型:Result 和 Option 都是迭代器;双端迭代 rev;size_hint')
r = tryit('u65d', '''
    fn main() {
        let v = vec![vec![1, 2], vec![3], vec![4, 5, 6]];
        println!("rev: {:?}", v.iter().flatten().rev().collect::<Vec<_>>());
        println!("size_hint: flatten {:?} / 单层 iter {:?}", v.iter().flatten().size_hint(), v.iter().size_hint());
        let f = v.iter().flatten(); println!("flatten 在没开始消费时 size_hint 的下界 {} 是真实元素数 {} 吗? 否:展开前不知道内层长度", f.size_hint().0, f.count());
        let rs = vec![Ok(1), Err("bad"), Ok(3)];
        println!("Result 展开丢弃 Err: {:?}", rs.into_iter().flatten().collect::<Vec<i32>>());
    }
''', quiet_src=True); R['flatten'] = r['out']
print()
print('== 五:性能:展平 1000×1000 的 Vec<Vec<u32>> 求和,flat_map 链 vs 双重 for 循环(release,取 5 次最小)')
r = tryit('u65e', '''
    use std::hint::black_box; use std::time::Instant;
    fn main() {
        let g: Vec<Vec<u32>> = (0..1000).map(|i| (0..1000).map(|j| i * j % 7).collect()).collect();
        let (mut a, mut b, mut c) = (f64::MAX, f64::MAX, f64::MAX); let (mut sa, mut sb, mut sc) = (0u64, 0u64, 0u64);
        for _ in 0..5 {
            let t = Instant::now(); sa = black_box(black_box(&g).iter().flat_map(|r| r.iter()).map(|&x| x as u64).sum::<u64>()); a = a.min(t.elapsed().as_secs_f64() * 1e3);
            let t = Instant::now(); let mut s = 0u64; for r in black_box(&g) { for &x in r { s += x as u64; } } sb = black_box(s); b = b.min(t.elapsed().as_secs_f64() * 1e3);
            let t = Instant::now(); sc = black_box(black_box(&g).iter().map(|r| r.iter().map(|&x| x as u64).sum::<u64>()).sum::<u64>()); c = c.min(t.elapsed().as_secs_f64() * 1e3);
        }
        println!("flat_map 链 {:.3} ms  双重 for {:.3} ms  先对每行 sum 再 sum {:.3} ms  (结果 {} {} {})", a, b, c, sa, sb, sc);
    }
''', quiet_src=True, release=True); R['bench'] = r['out']
save('u65', R)
