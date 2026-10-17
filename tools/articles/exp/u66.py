import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u66'); R = {}
print('== 一:peek 看一眼不消费;peek 本身会让源头多产出一个元素(计数);next 先返回被 peek 缓存的值')
r = tryit('u66a', '''
    use std::cell::Cell;
    fn main() {
        let pulled = Cell::new(0);
        let mut it = (1..=5).inspect(|_| pulled.set(pulled.get() + 1)).peekable();
        println!("刚创建:源已产出 {} 个", pulled.get());
        println!("peek -> {:?},源已产出 {} 个", it.peek(), pulled.get());
        println!("再 peek -> {:?},源已产出 {} 个(没有再拉)", it.peek(), pulled.get());
        println!("next -> {:?},源已产出 {} 个(返回的是缓存的 1)", it.next(), pulled.get());
        println!("next -> {:?},源已产出 {} 个", it.next(), pulled.get());
        println!("peek_mut 改成 99: {:?}", { if let Some(x) = it.peek_mut() { *x = 99; } it.next() });
        println!("size_of Peekable<Range<i32>> = {} 字节(Range 本身 {})", std::mem::size_of::<std::iter::Peekable<std::ops::Range<i32>>>(), std::mem::size_of::<std::ops::Range<i32>>());
    }
''', quiet_src=True); R['peek'] = r['out']
print()
print('== 二:peek 的借用:拿着 peek 返回的引用时不能 next(E0499)')
r = tryit('u66b', '''
    fn main() {
        let mut it = [1, 2, 3].iter().peekable();
        let first = it.peek().unwrap();
        it.next();
        println!("{}", first);
    }
''', maxlines=30); R['e0499'] = r['diag']
print()
print('== 三:用 peekable 写词法分析:数字要看到下一个字符不是数字才结束,而 take_while 会吃掉那个分隔符')
r = tryit('u66c', '''
    fn main() {
        let src = "12+345*6";
        // 写法一:peekable + next_if 不消费分隔符
        let mut it = src.chars().peekable(); let mut toks = Vec::new();
        while let Some(&c) = it.peek() {
            if c.is_ascii_digit() { let mut n = String::new(); while let Some(d) = it.next_if(|c| c.is_ascii_digit()) { n.push(d); } toks.push(n); }
            else { toks.push(c.to_string()); it.next(); }
        }
        println!("peekable + next_if: {:?}", toks);
        // 写法二:take_while 吃掉了分隔符
        let mut it2 = src.chars(); let n: String = it2.by_ref().take_while(|c| c.is_ascii_digit()).collect();
        println!("take_while 读第一个数字 {:?},剩余 {:?}(分隔符 '+' 已经被丢掉)", n, it2.collect::<String>());
        let mut it3 = "ab".chars().peekable();
        println!("next_if_eq(&'a') -> {:?}  next_if_eq(&'z') -> {:?}  剩余 {:?}", it3.next_if_eq(&'a'), it3.next_if_eq(&'z'), it3.collect::<String>());
    }
''', quiet_src=True); R['lex'] = r['out']
print()
print('== 四:inspect:在链中间看数据,不改变结果')
r = tryit('u66d', '''
    fn main() {
        let r: Vec<i32> = (1..=5)
            .inspect(|x| println!("  [源] {}", x))
            .filter(|x| x % 2 == 1)
            .inspect(|x| println!("  [filter 之后] {}", x))
            .map(|x| x * x)
            .inspect(|x| println!("  [map 之后] {}", x))
            .collect();
        println!("结果 {:?}", r);
        let s: i32 = [1, 2, 3].iter().inspect(|x| print!("{} ", x)).sum();
        println!("sum = {}(inspect 的参数是 &Item,不能修改元素)", s);
    }
''', quiet_src=False); R['inspect'] = r['out']
r = tryit('u66e', '''
    fn main() {
        let v: Vec<i32> = [1, 2, 3].iter().inspect(|x| **x += 1).copied().collect();
        println!("{:?}", v);
    }
''', maxlines=25); R['e_inspect'] = r['diag']
save('u66', R)
