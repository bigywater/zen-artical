import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u52'); R = {}
print('== 一:Iterator 只有一个必需方法 next():每次返回 Some(item),耗尽后返回 None;for 循环就是反复调用 next')
r = tryit('u52a', '''
    fn main() {
        let v = vec![10, 20, 30];
        let mut it = v.iter();
        println!("{:?} {:?} {:?} {:?} {:?}", it.next(), it.next(), it.next(), it.next(), it.next());
        println!("手写的 for 展开:");
        let mut it = v.iter();
        while let Some(x) = it.next() { println!("  元素 {x}"); }
        let mut it = v.into_iter().map(|x| x + 1);
        println!("map 适配器也是迭代器:{:?} {:?}", it.next(), it.next());
        println!("迭代器本身需要 mut:不写 mut 会报错(见下)");
    }
''', quiet_src=False)
r = tryit('u52b', '''
    fn main() { let v = vec![1]; let it = v.iter(); it.next(); }
''', maxlines=18, quiet_src=True); R['e596'] = r['diag'].split('\n')[0]
print()
print('== 二:size_hint 给出剩余长度的上下界,适配器会相应调整;ExactSizeIterator::len 要求精确')
r = tryit('u52c', '''
    fn main() {
        let v = vec![1, 2, 3, 4, 5];
        println!("v.iter()                 size_hint = {:?}", v.iter().size_hint());
        println!("v.iter().map(..)         size_hint = {:?}", v.iter().map(|x| x * 2).size_hint());
        println!("v.iter().filter(..)      size_hint = {:?}(过滤后数量未知,下界为 0)", v.iter().filter(|x| **x > 2).size_hint());
        println!("v.iter().chain(v.iter()) size_hint = {:?}", v.iter().chain(v.iter()).size_hint());
        println!("v.iter().take(2)         size_hint = {:?}", v.iter().take(2).size_hint());
        println!("(0..).take(3)            size_hint = {:?}", (0..).take(3).size_hint());
        println!("(0..)                    size_hint = {:?}(无穷)", (0..).size_hint());
        println!("v.iter().len() = {}(ExactSizeIterator)", v.iter().len());
        let mut it = v.iter(); it.next();
        println!("消耗一个之后 len = {}", it.len());
    }
''', quiet_src=False)
print()
print('== 三:双端迭代器 next_back、by_ref() 只消耗一部分、nth 跳过、迭代器耗尽后再调用 next')
r = tryit('u52d', '''
    fn main() {
        let v = vec![1, 2, 3, 4, 5, 6];
        let mut it = v.iter();
        println!("next = {:?},next_back = {:?}", it.next(), it.next_back());
        let first_two: Vec<_> = it.by_ref().take(2).collect();      // 只消耗前 2 个,it 之后还能继续用
        println!("by_ref().take(2) = {:?};剩下 {:?}", first_two, it.collect::<Vec<_>>());
        let mut it2 = v.iter();
        println!("nth(2) = {:?},接着 next = {:?}", it2.nth(2), it2.next());
        let mut e = std::iter::empty::<i32>();
        println!("耗尽后再调用 next:{:?} {:?}", e.next(), e.next());
    }
''', quiet_src=False)
print()
print('== 四:自己造迭代器的现成工具:from_fn、successors、repeat_with、once')
r = tryit('u52e', '''
    use std::iter;
    fn main() {
        let mut n = 0;
        let counter: Vec<i32> = iter::from_fn(|| { n += 1; if n <= 4 { Some(n * n) } else { None } }).collect();
        println!("from_fn:{:?}", counter);
        let pows: Vec<u32> = iter::successors(Some(1u32), |&x| x.checked_mul(10)).collect();
        println!("successors(×10 直到溢出):{:?}", pows);
        let mut k = 0;
        println!("repeat_with:{:?}", iter::repeat_with(|| { k += 3; k }).take(4).collect::<Vec<_>>());
        println!("once + chain:{:?}", iter::once(0).chain(1..3).collect::<Vec<_>>());
    }
''', quiet_src=False)
save('u52', R)
