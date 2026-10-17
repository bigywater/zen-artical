import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u53'); R = {}
print('== 一:自定义 Iterator:一个结构体 + 一个 next() —— 无穷的斐波那契数列')
r = tryit('u53a', '''
    struct Fib { a: u64, b: u64 }
    impl Fib { fn new() -> Self { Fib { a: 0, b: 1 } } }
    impl Iterator for Fib {
        type Item = u64;
        fn next(&mut self) -> Option<u64> {
            let r = self.a;
            let next = self.a.checked_add(self.b)?;        // 溢出时返回 None,迭代结束
            self.a = self.b; self.b = next; Some(r)
        }
    }
    fn main() {
        println!("前 10 项:{:?}", Fib::new().take(10).collect::<Vec<_>>());
        println!("小于 100 的偶数项:{:?}", Fib::new().take_while(|&x| x < 100).filter(|x| x % 2 == 0).collect::<Vec<_>>());
        println!("一共有 {} 项(在 u64 溢出之前),最后一项 {:?}", Fib::new().count(), Fib::new().last());
    }
''', quiet_src=False)
print()
print('== 二:借用数据的迭代器:带生命周期的结构体,零拷贝地产出相邻元素对')
r = tryit('u53b', '''
    struct Pairs<'a, T> { items: &'a [T], i: usize }
    impl<'a, T> Iterator for Pairs<'a, T> {
        type Item = (&'a T, &'a T);
        fn next(&mut self) -> Option<Self::Item> {
            if self.i + 1 >= self.items.len() { return None; }
            let p = (&self.items[self.i], &self.items[self.i + 1]); self.i += 1; Some(p)
        }
    }
    fn pairs<T>(items: &[T]) -> Pairs<'_, T> { Pairs { items, i: 0 } }
    fn main() {
        let words = vec!["a".to_string(), "b".to_string(), "c".to_string()];
        for (x, y) in pairs(&words) { println!("{x}-{y}"); }
        println!("差分:{:?}", pairs(&[1, 4, 9, 16]).map(|(a, b)| b - a).collect::<Vec<_>>());
    }
''', quiet_src=False)
print()
print('== 三:想用 rev() 就要实现 DoubleEndedIterator;想要 len() 就要实现 ExactSizeIterator')
r = tryit('u53c', '''
    struct Count { lo: u32, hi: u32 }
    impl Iterator for Count {
        type Item = u32;
        fn next(&mut self) -> Option<u32> { if self.lo >= self.hi { None } else { self.lo += 1; Some(self.lo - 1) } }
    }
    fn main() { println!("{:?}", Count { lo: 0, hi: 3 }.rev().collect::<Vec<_>>()); }
''', maxlines=24, quiet_src=True); R['e277'] = r['diag'].split('\n')[0]
r = tryit('u53d', '''
    struct Count { lo: u32, hi: u32 }
    impl Iterator for Count {
        type Item = u32;
        fn next(&mut self) -> Option<u32> { if self.lo >= self.hi { None } else { self.lo += 1; Some(self.lo - 1) } }
        fn size_hint(&self) -> (usize, Option<usize>) { let n = (self.hi - self.lo) as usize; (n, Some(n)) }
    }
    impl DoubleEndedIterator for Count {
        fn next_back(&mut self) -> Option<u32> { if self.lo >= self.hi { None } else { self.hi -= 1; Some(self.hi) } }
    }
    impl ExactSizeIterator for Count {}
    fn main() {
        println!("rev:{:?}", Count { lo: 0, hi: 5 }.rev().collect::<Vec<_>>());
        println!("len:{},size_hint:{:?}", Count { lo: 2, hi: 9 }.len(), Count { lo: 2, hi: 9 }.size_hint());
        let mut c = Count { lo: 0, hi: 6 };
        println!("两头同时取:{:?} {:?} {:?} {:?}", c.next(), c.next_back(), c.next(), c.next_back());
    }
''', quiet_src=False)
print()
print('== 四:实现 size_hint 的意义:collect 用它预分配容量')
r = tryit('u53e', '''
    struct NoHint(u32); struct WithHint(u32);
    impl Iterator for NoHint { type Item = u32; fn next(&mut self) -> Option<u32> { if self.0 == 0 { None } else { self.0 -= 1; Some(self.0) } } }
    impl Iterator for WithHint { type Item = u32; fn next(&mut self) -> Option<u32> { if self.0 == 0 { None } else { self.0 -= 1; Some(self.0) } } fn size_hint(&self) -> (usize, Option<usize>) { (self.0 as usize, Some(self.0 as usize)) } }
    fn main() {
        let a: Vec<u32> = NoHint(1000).collect(); let b: Vec<u32> = WithHint(1000).collect();
        println!("没有 size_hint:collect 之后 len = {},capacity = {}", a.len(), a.capacity());
        println!("有 size_hint  :collect 之后 len = {},capacity = {}", b.len(), b.capacity());
    }
''', quiet_src=False)
save('u53', R)
