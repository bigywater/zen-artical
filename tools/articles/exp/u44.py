import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u44'); R = {}
print('== 一:标准 Iterator 做不到「借出自己内部缓冲区」的迭代(每次返回的引用都指向同一块可变数据)')
r = tryit('u44a', '''
    struct Windows { buf: Vec<i32>, pos: usize }
    impl Iterator for Windows {
        type Item = &mut [i32];
        fn next(&mut self) -> Option<Self::Item> { None }
    }
    fn main() {}
''', maxlines=24); R['e1'] = r['diag'].split('\n')[0]
r = tryit('u44b', '''
    struct Windows { buf: Vec<i32>, pos: usize }
    impl Iterator for Windows {
        type Item = &'static mut [i32];
        fn next(&mut self) -> Option<Self::Item> {
            if self.pos + 2 > self.buf.len() { return None; }
            let w = &mut self.buf[self.pos..self.pos + 2]; self.pos += 1; Some(w)
        }
    }
    fn main() {}
''', maxlines=28); R['e2'] = [l for l in r['diag'].split('\n') if l.startswith('error')][:1]
print()
print('== 二:GAT:关联类型自己带生命周期参数,让每次 next 的返回值借自 &mut self(「借出式迭代器」)')
r = tryit('u44c', '''
    trait LendingIterator {
        type Item<'a> where Self: 'a;
        fn next<'a>(&'a mut self) -> Option<Self::Item<'a>>;
    }
    struct WindowsMut<'s> { data: &'s mut [i32], pos: usize }
    impl<'s> LendingIterator for WindowsMut<'s> {
        type Item<'a> = &'a mut [i32] where Self: 'a;
        fn next<'a>(&'a mut self) -> Option<&'a mut [i32]> {
            if self.pos + 2 > self.data.len() { return None; }
            let w = &mut self.data[self.pos..self.pos + 2]; self.pos += 1; Some(w)
        }
    }
    fn main() {
        let mut v = vec![1, 2, 3, 4];
        let mut it = WindowsMut { data: &mut v, pos: 0 };
        while let Some(w) = it.next() { w[1] += w[0]; println!("窗口 {:?}", w); }    // 相邻窗口重叠,每个窗口可修改
        println!("最终数据 {:?}", v);
    }
''', quiet_src=False)
print()
print('== 三:GAT 还能让关联类型带类型参数(「容器族」):同一个 trait,不同实现把 T 包进 Vec 或 Option')
r = tryit('u44d', '''
    trait Family { type Of<T>; fn wrap<T>(t: T) -> Self::Of<T>; fn peek<T: std::fmt::Debug>(w: &Self::Of<T>) -> String; }
    struct VecFamily; struct OptFamily;
    impl Family for VecFamily { type Of<T> = Vec<T>; fn wrap<T>(t: T) -> Vec<T> { vec![t] } fn peek<T: std::fmt::Debug>(w: &Vec<T>) -> String { format!("{:?}", w) } }
    impl Family for OptFamily { type Of<T> = Option<T>; fn wrap<T>(t: T) -> Option<T> { Some(t) } fn peek<T: std::fmt::Debug>(w: &Option<T>) -> String { format!("{:?}", w) } }
    fn demo<F: Family>() -> (String, String) { (F::peek(&F::wrap(1u8)), F::peek(&F::wrap("x"))) }
    fn main() { println!("VecFamily:{:?}", demo::<VecFamily>()); println!("OptFamily:{:?}", demo::<OptFamily>()); }
''', quiet_src=False)
print()
print('== 四:漏写 where Self: \'a 约束时的报错')
r = tryit('u44e', '''
    trait Lending { type Item<'a>; fn next<'a>(&'a mut self) -> Option<Self::Item<'a>>; }
    fn main() {}
''', maxlines=24); R['e_bound'] = r['diag'].split('\n')[0]
save('u44', R)
