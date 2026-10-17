import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u54'); R = {}
print('== 一:for 循环对 v、&v、&mut v 迭代的元素类型不同')
r = tryit('u54a', '''
    fn tn<T>(_: &T) -> &'static str { std::any::type_name::<T>() }
    fn main() {
        let mut v = vec![String::from("a"), String::from("b")];
        for x in &v { println!("for x in &v      → x 的类型 {}", tn(&x)); break; }
        for x in &mut v { println!("for x in &mut v  → x 的类型 {}", tn(&x)); x.push('!'); }
        for x in v.clone() { println!("for x in v      → x 的类型 {}", tn(&x)); break; }
        println!("修改之后 v = {:?}", v);
    }
''', quiet_src=False)
print()
print('== 二:for x in v 把 v 的所有权移进了迭代器,之后 v 不能再用')
r = tryit('u54b', '''
    fn main() {
        let v = vec![1, 2, 3];
        for x in v { println!("{x}"); }
        println!("{:?}", v);
    }
''', maxlines=30); R['e382'] = r['diag'].split('\n')[0]
print()
print('== 三:为自己的集合实现 IntoIterator(三种形式各一个 impl)')
r = tryit('u54c', '''
    struct Bag { items: Vec<i32> }
    impl IntoIterator for Bag { type Item = i32; type IntoIter = std::vec::IntoIter<i32>; fn into_iter(self) -> Self::IntoIter { self.items.into_iter() } }
    impl<'a> IntoIterator for &'a Bag { type Item = &'a i32; type IntoIter = std::slice::Iter<'a, i32>; fn into_iter(self) -> Self::IntoIter { self.items.iter() } }
    impl<'a> IntoIterator for &'a mut Bag { type Item = &'a mut i32; type IntoIter = std::slice::IterMut<'a, i32>; fn into_iter(self) -> Self::IntoIter { self.items.iter_mut() } }
    fn main() {
        let mut bag = Bag { items: vec![1, 2, 3] };
        for x in &bag { print!("读 {x} "); }
        println!();
        for x in &mut bag { *x *= 10; }
        for x in &bag { print!("读 {x} "); }
        println!();
        let total: i32 = bag.into_iter().sum();           // 消费 bag
        println!("消费后求和 = {total}");
    }
''', quiet_src=False)
r = tryit('u54d', '''
    struct Bag { items: Vec<i32> }
    fn main() { let bag = Bag { items: vec![1] }; for x in &bag { println!("{x}"); } }
''', maxlines=24, quiet_src=True); R['e277'] = r['diag'].split('\n')[0]
print()
print('== 四:其它标准集合:数组按值迭代(2021+)、HashMap 迭代的是键值对')
r = tryit('u54e', '''
    use std::collections::BTreeMap;
    fn tn<T>(_: &T) -> &'static str { std::any::type_name::<T>() }
    fn main() {
        let arr = [String::from("x"), String::from("y")];
        for s in arr { println!("数组 for s in arr → {}", tn(&s)); break; }
        let mut m = BTreeMap::new(); m.insert("k", 1);
        for kv in &m { println!("for kv in &m      → {}", tn(&kv)); }
        for kv in m.clone() { println!("for kv in m       → {}", tn(&kv)); }
        for v in m.values_mut() { *v += 1; }
        println!("values_mut 之后 {:?}", m);
    }
''', quiet_src=False)
save('u54', R)
