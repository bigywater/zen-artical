import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u36'); R = {}
print('== 一:定义 trait、为不同类型实现、统一调用;漏实现方法被拒绝')
r = tryit('u36a', '''
    trait Shape {
        fn area(&self) -> f64;
        fn name(&self) -> String;
        fn describe(&self) -> String { format!("{} 面积 {:.2}", self.name(), self.area()) }   // 默认实现
    }
    struct Circle(f64);
    struct Rect { w: f64, h: f64 }
    impl Shape for Circle { fn area(&self) -> f64 { 3.14159 * self.0 * self.0 } fn name(&self) -> String { "圆".into() } }
    impl Shape for Rect {
        fn area(&self) -> f64 { self.w * self.h }
        fn name(&self) -> String { "矩形".into() }
        fn describe(&self) -> String { format!("{}(覆盖了默认实现)", self.name()) }
    }
    fn main() {
        println!("{}", Circle(1.0).describe());
        println!("{}", Rect { w: 2.0, h: 3.0 }.describe());
    }
''', quiet_src=False)
r = tryit('u36b', '''
    trait Shape { fn area(&self) -> f64; fn name(&self) -> String; }
    struct Circle(f64);
    impl Shape for Circle { fn area(&self) -> f64 { self.0 } }
    fn main() {}
''', maxlines=20); R['e046'] = r['diag'].split('\n')[0]
print()
print('== 二:调用 trait 方法要求 trait 在作用域内(use)')
r = tryit('u36c', '''
    mod geometry {
        pub trait Area { fn area(&self) -> f64; }
        pub struct Sq(pub f64);
        impl Area for Sq { fn area(&self) -> f64 { self.0 * self.0 } }
    }
    fn main() {
        let s = geometry::Sq(3.0);
        println!("{}", s.area());
    }
''', maxlines=26); R['e599'] = r['diag'].split('\n')[0]
r = tryit('u36d', '''
    mod geometry {
        pub trait Area { fn area(&self) -> f64; }
        pub struct Sq(pub f64);
        impl Area for Sq { fn area(&self) -> f64 { self.0 * self.0 } }
    }
    use geometry::Area;
    fn main() { println!("{}", geometry::Sq(3.0).area()); }
''', quiet_src=True)
print()
print('== 三:关联常量、静态方法、Self;可以为外部类型(如 i32)实现自己的 trait')
r = tryit('u36e', '''
    trait Animal {
        const LEGS: u32;
        fn new(name: &str) -> Self;
        fn name(&self) -> String;
        fn legs(&self) -> u32 { Self::LEGS }
    }
    struct Dog(String); struct Bird(String);
    impl Animal for Dog { const LEGS: u32 = 4; fn new(n: &str) -> Self { Dog(n.into()) } fn name(&self) -> String { self.0.clone() } }
    impl Animal for Bird { const LEGS: u32 = 2; fn new(n: &str) -> Self { Bird(n.into()) } fn name(&self) -> String { self.0.clone() } }
    fn make<T: Animal>(n: &str) -> T { T::new(n) }
    trait Double { fn double(&self) -> Self; }
    impl Double for i32 { fn double(&self) -> i32 { self * 2 } }
    fn main() {
        let d: Dog = make("旺财"); let b = make::<Bird>("小鸟");
        println!("{} 有 {} 条腿,{} 有 {} 条腿", d.name(), d.legs(), b.name(), b.legs());
        println!("为 i32 实现自己的 trait:21.double() = {}", 21.double());
    }
''', quiet_src=False)
print()
print('== 四:两个 trait 有同名方法:调用有歧义,用完全限定语法消除')
r = tryit('u36f', '''
    trait Pilot { fn fly(&self) -> &'static str; }
    trait Wizard { fn fly(&self) -> &'static str; }
    struct Human;
    impl Pilot for Human { fn fly(&self) -> &'static str { "机长广播" } }
    impl Wizard for Human { fn fly(&self) -> &'static str { "施法飞行" } }
    impl Human { fn fly(&self) -> &'static str { "挥手(Human 自己的方法)" } }
    fn main() {
        let h = Human;
        println!("{}", h.fly());                      // 固有方法优先
        println!("{}", Pilot::fly(&h));
        println!("{}", <Human as Wizard>::fly(&h));
    }
''', quiet_src=False)
r = tryit('u36g', '''
    trait Pilot { fn fly(&self) -> &'static str; }
    trait Wizard { fn fly(&self) -> &'static str; }
    struct Human;
    impl Pilot for Human { fn fly(&self) -> &'static str { "机长广播" } }
    impl Wizard for Human { fn fly(&self) -> &'static str { "施法飞行" } }
    fn main() { println!("{}", Human.fly()); }
''', maxlines=24); R['e034'] = r['diag'].split('\n')[0]
save('u36', R)
