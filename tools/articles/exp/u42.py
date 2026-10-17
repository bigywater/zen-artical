import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u42'); R = {}
print('== 一:泛型方法让 trait 不能做成对象(编译器无法在 vtable 里为每个 T 预留槽位)')
r = tryit('u42a', '''
    trait Visitor { fn visit<T: std::fmt::Debug>(&self, t: T); }
    struct P; impl Visitor for P { fn visit<T: std::fmt::Debug>(&self, t: T) { println!("{:?}", t); } }
    fn main() { let v: Box<dyn Visitor> = Box::new(P); }
''', maxlines=34); R['e1'] = [l for l in r['diag'].split('\n') if 'E0038' in l][:1]
print()
print('== 二:返回 Self、没有 self 的关联函数 也不行')
r = tryit('u42b', '''
    trait Dup { fn dup(&self) -> Self; }
    struct P; impl Dup for P { fn dup(&self) -> P { P } }
    fn main() { let v: Box<dyn Dup> = Box::new(P); }
''', maxlines=34); R['e2'] = [l for l in r['diag'].split('\n') if 'E0038' in l][:1]
r = tryit('u42c', '''
    trait Make { fn make() -> Self; fn name(&self) -> String; }
    struct P; impl Make for P { fn make() -> P { P } fn name(&self) -> String { "P".into() } }
    fn main() { let v: Box<dyn Make> = Box::new(P); }
''', maxlines=34, quiet_src=True)
print()
print('== 三:supertrait 带 Sized 要求(例如 Clone)也不行')
r = tryit('u42d', '''
    trait Shape: Clone { fn area(&self) -> f64; }
    #[derive(Clone)] struct Sq(f64); impl Shape for Sq { fn area(&self) -> f64 { self.0 } }
    fn main() { let v: Box<dyn Shape> = Box::new(Sq(1.0)); }
''', maxlines=34); R['e3'] = [l for l in r['diag'].split('\n') if 'E0038' in l][:1]
print()
print('== 四:用 where Self: Sized 把「不适合对象」的方法排除出对象接口,trait 的其余部分仍可做成对象')
r = tryit('u42e', '''
    trait Shape {
        fn area(&self) -> f64;
        fn scaled(&self, k: f64) -> Self where Self: Sized;               // 只有具体类型才有,dyn 上没有
        fn describe<T: std::fmt::Display>(&self, tag: T) -> String where Self: Sized { format!("{tag}: {}", self.area()) }
    }
    struct Sq(f64);
    impl Shape for Sq { fn area(&self) -> f64 { self.0 * self.0 } fn scaled(&self, k: f64) -> Sq { Sq(self.0 * k) } }
    fn main() {
        let s = Sq(2.0);
        println!("具体类型可以用全部方法:{} {}", s.scaled(2.0).area(), s.describe("sq"));
        let d: Box<dyn Shape> = Box::new(Sq(3.0));
        println!("dyn 上只有对象安全的方法:{}", d.area());
    }
''', quiet_src=False)
r = tryit('u42f', '''
    trait Shape { fn area(&self) -> f64; fn scaled(&self, k: f64) -> Self where Self: Sized; }
    struct Sq(f64);
    impl Shape for Sq { fn area(&self) -> f64 { self.0 } fn scaled(&self, k: f64) -> Sq { Sq(self.0 * k) } }
    fn main() { let d: Box<dyn Shape> = Box::new(Sq(1.0)); d.scaled(2.0); }
''', maxlines=24, quiet_src=True); R['e4'] = r['diag'].split('\n')[0]
print()
print('== 五:常见的变通:克隆一个 trait 对象 —— 提供返回 Box<dyn Trait> 的 box_clone')
r = tryit('u42g', '''
    trait Shape { fn area(&self) -> f64; fn box_clone(&self) -> Box<dyn Shape>; }
    #[derive(Clone)] struct Sq(f64);
    impl Shape for Sq { fn area(&self) -> f64 { self.0 * self.0 } fn box_clone(&self) -> Box<dyn Shape> { Box::new(self.clone()) } }
    impl Clone for Box<dyn Shape> { fn clone(&self) -> Self { self.box_clone() } }
    fn main() {
        let a: Box<dyn Shape> = Box::new(Sq(3.0));
        let b = a.clone();
        println!("克隆出的 trait 对象:{} {}", a.area(), b.area());
    }
''', quiet_src=False)
save('u42', R)
