import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u43'); R = {}
print('== 一:关联类型:trait 里声明一个类型占位符,每个实现者确定它')
r = tryit('u43a', '''
    trait Container {
        type Item;
        fn first(&self) -> Option<&Self::Item>;
        fn size(&self) -> usize;
    }
    struct Words(Vec<String>);
    struct Nums([i32; 3]);
    impl Container for Words { type Item = String; fn first(&self) -> Option<&String> { self.0.first() } fn size(&self) -> usize { self.0.len() } }
    impl Container for Nums { type Item = i32; fn first(&self) -> Option<&i32> { self.0.first() } fn size(&self) -> usize { 3 } }
    fn show<C: Container>(c: &C) -> String where C::Item: std::fmt::Debug { format!("size={} first={:?}", c.size(), c.first()) }
    fn main() {
        println!("{}", show(&Words(vec!["a".into(), "b".into()])));
        println!("{}", show(&Nums([7, 8, 9])));
    }
''', quiet_src=False)
print()
print('== 二:对比泛型参数的 trait:同一个类型可以实现多次,调用时需要消歧;关联类型的 trait 一个类型只能实现一次')
r = tryit('u43b', '''
    trait From2<T> { fn conv(&self) -> T; }
    struct N(i32);
    impl From2<i64> for N { fn conv(&self) -> i64 { self.0 as i64 } }
    impl From2<String> for N { fn conv(&self) -> String { self.0.to_string() } }
    fn main() {
        let n = N(5);
        let a: i64 = n.conv();
        let b: String = n.conv();
        println!("{a} {b}");
    }
''', quiet_src=False)
r = tryit('u43c', '''
    trait From2<T> { fn conv(&self) -> T; }
    struct N(i32);
    impl From2<i64> for N { fn conv(&self) -> i64 { self.0 as i64 } }
    impl From2<String> for N { fn conv(&self) -> String { self.0.to_string() } }
    fn main() { let n = N(5); let x = n.conv(); }
''', maxlines=22, quiet_src=True); R['e283'] = r['diag'].split('\n')[0]
r = tryit('u43d', '''
    trait Container { type Item; fn get(&self) -> Self::Item; }
    struct N(i32);
    impl Container for N { type Item = i64; fn get(&self) -> i64 { self.0 as i64 } }
    impl Container for N { type Item = String; fn get(&self) -> String { self.0.to_string() } }
    fn main() {}
''', maxlines=22); R['e119'] = r['diag'].split('\n')[0]
print()
print('== 三:约束里写关联类型:Iterator<Item = u32>、I::Item、<T as Trait>::Output')
r = tryit('u43e', '''
    use std::fmt::Debug;
    use std::ops::Add;
    fn sum_all<I: Iterator<Item = u32>>(it: I) -> u32 { it.sum() }
    fn debug_all<I>(it: I) -> Vec<String> where I: Iterator, I::Item: Debug { it.map(|x| format!("{:?}", x)).collect() }
    fn add_twice<T: Add<Output = T> + Copy>(a: T) -> T { a + a }
    fn output_name<T: Add>(_: T) -> &'static str { std::any::type_name::<<T as Add>::Output>() }
    fn main() {
        println!("{}", sum_all(vec![1u32, 2, 3].into_iter()));
        println!("{:?}", debug_all("a b".split(' ')));
        println!("{} {}", add_twice(2), add_twice(1.5));
        println!("i32 + i32 的 Output 类型:{}", output_name(1i32));
    }
''', quiet_src=False)
r = tryit('u43f', '''
    fn main() { let x = 1 + 2.0; }
''', maxlines=18, quiet_src=True); R['e277'] = r['diag'].split('\n')[0]
print()
print('== 四:标准库的例子:Iterator::Item、Deref::Target、Add::Output 都是关联类型')
r = tryit('u43g', '''
    use std::any::type_name;
    use std::ops::{Add, Deref};
    fn item_of<I: Iterator>(_: &I) -> &'static str { type_name::<I::Item>() }
    fn target_of<D: Deref>(_: &D) -> &'static str { type_name::<D::Target>() }
    fn output_of<A: Add<B>, B>(_: &A, _: &B) -> &'static str { type_name::<A::Output>() }
    fn main() {
        println!("vec::IntoIter<u8>::Item   = {}", item_of(&vec![1u8].into_iter()));
        println!("Box<String>::Target       = {}", target_of(&Box::new(String::new())));
        println!("String::Target            = {}", target_of(&String::new()));
        println!("String + &str 的 Output   = {}", output_of(&String::new(), &"x"));
    }
''', quiet_src=False)
save('u43', R)
