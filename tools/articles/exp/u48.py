import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u48'); R = {}
print('== 一:blanket impl:为「所有满足约束的类型」一次性实现 trait')
r = tryit('u48a', '''
    use std::fmt::Display;
    trait Loud { fn loud(&self) -> String; }
    impl<T: Display> Loud for T { fn loud(&self) -> String { format!("{}!!!", self).to_uppercase() } }
    struct Name(&'static str);
    impl Display for Name { fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result { write!(f, "{}", self.0) } }
    fn main() {
        println!("{} {} {} {}", "hello".loud(), 42.loud(), 3.5.loud(), Name("rust").loud());     // 任何实现了 Display 的类型都有 loud()
    }
''', quiet_src=False)
r = tryit('u48b', '''
    use std::fmt::Display;
    trait Loud { fn loud(&self) -> String; }
    impl<T: Display> Loud for T { fn loud(&self) -> String { format!("{}!!!", self) } }
    struct NoDisplay;
    fn main() { println!("{}", NoDisplay.loud()); }
''', maxlines=26, quiet_src=True); R['e599'] = r['diag'].split('\n')[0]
print()
print('== 二:标准库里的 blanket impl:ToString(来自 Display)、Into(来自 From)')
r = tryit('u48c', '''
    use std::fmt;
    struct Celsius(f64);
    impl fmt::Display for Celsius { fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "{:.1}°C", self.0) } }
    struct Meters(f64);
    struct Km(f64);
    impl From<Km> for Meters { fn from(k: Km) -> Meters { Meters(k.0 * 1000.0) } }
    fn main() {
        println!("只实现了 Display,免费得到 to_string():{}", Celsius(36.6).to_string());
        let m: Meters = Km(2.5).into();               // 只实现了 From,免费得到 Into
        println!("只实现了 From<Km> for Meters,免费得到 Into:{} 米", m.0);
    }
''', quiet_src=False)
r = tryit('u48d', '''
    struct Meters(f64); struct Km(f64);
    impl Into<Meters> for Km { fn into(self) -> Meters { Meters(self.0 * 1000.0) } }       // 只实现 Into
    fn main() { let _m: Meters = Meters::from(Km(1.0)); }
''', maxlines=24); R['e277'] = r['diag'].split('\n')[0]
print()
print('== 三:扩展 trait(extension trait)模式:给已有类型添加方法')
r = tryit('u48e', '''
    trait StrExt { fn shout(&self) -> String; fn word_count(&self) -> usize; }
    impl<T: AsRef<str> + ?Sized> StrExt for T {
        fn shout(&self) -> String { self.as_ref().to_uppercase() + "!" }
        fn word_count(&self) -> usize { self.as_ref().split_whitespace().count() }
    }
    fn main() {
        let s = String::from("hello rust world");
        let c: std::borrow::Cow<str> = std::borrow::Cow::Borrowed("cow str");
        println!("&str:{} {}", "a b".shout(), "a b".word_count());
        println!("String:{} {}", s.shout(), s.word_count());
        println!("Cow:{} {}", c.shout(), c.word_count());
    }
''', quiet_src=False)
print()
print('== 四:为引用类型也提供实现(impl<T: Trait + ?Sized> Trait for &T),这样「&x」也能当作满足约束的值')
r = tryit('u48f', '''
    trait Speak { fn speak(&self) -> String; }
    struct Dog; impl Speak for Dog { fn speak(&self) -> String { "汪".into() } }
    fn talk<S: Speak>(s: S) -> String { s.speak() }
    fn main() { println!("{}", talk(Dog)); println!("{}", talk(&Dog)); }
''', maxlines=24, quiet_src=True); R['e277b'] = r['diag'].split('\n')[0]
r = tryit('u48g', '''
    trait Speak { fn speak(&self) -> String; }
    struct Dog; impl Speak for Dog { fn speak(&self) -> String { "汪".into() } }
    impl<T: Speak + ?Sized> Speak for &T { fn speak(&self) -> String { (**self).speak() } }
    impl<T: Speak + ?Sized> Speak for Box<T> { fn speak(&self) -> String { (**self).speak() } }
    fn talk<S: Speak>(s: S) -> String { s.speak() }
    fn main() { println!("{} {} {}", talk(Dog), talk(&Dog), talk(Box::new(Dog))); }
''', quiet_src=False)
save('u48', R)
