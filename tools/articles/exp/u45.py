import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u45'); R = {}
print('== 一:supertrait:实现 Pretty 的前提是已经实现 Display;trait 里的默认方法可以直接用 supertrait 的功能')
r = tryit('u45a', '''
    use std::fmt::Display;
    trait Pretty: Display {
        fn pretty(&self) -> String { format!("★ {} ★", self) }          // 能用 Display,因为它是 supertrait
    }
    struct Name(&'static str);
    impl Display for Name { fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result { write!(f, "{}", self.0) } }
    impl Pretty for Name {}
    fn main() { println!("{}", Name("rust").pretty()); }
''', quiet_src=False)
r = tryit('u45b', '''
    use std::fmt::Display;
    trait Pretty: Display { fn pretty(&self) -> String { format!("★ {} ★", self) } }
    struct Plain;
    impl Pretty for Plain {}
    fn main() {}
''', maxlines=24); R['e277'] = r['diag'].split('\n')[0]
print()
print('== 二:泛型约束里只写子 trait,就自动拥有所有 supertrait 的方法')
r = tryit('u45c', '''
    trait Named { fn name(&self) -> String; }
    trait Aged { fn age(&self) -> u32; }
    trait Person: Named + Aged { fn intro(&self) -> String { format!("{},{} 岁", self.name(), self.age()) } }
    struct Ann; impl Named for Ann { fn name(&self) -> String { "Ann".into() } } impl Aged for Ann { fn age(&self) -> u32 { 30 } } impl Person for Ann {}
    fn greet<T: Person>(p: &T) -> String { format!("你好 {}(也能直接用 name():{})", p.intro(), p.name()) }   // T: Person 就够了,不需要再写 Named + Aged
    fn main() { println!("{}", greet(&Ann)); }
''', quiet_src=False)
print()
print('== 三:trait 对象向上转型(trait upcasting):&dyn Person → &dyn Named')
r = tryit('u45d', '''
    trait Named { fn name(&self) -> String; }
    trait Person: Named { fn id(&self) -> u32; }
    struct Ann; impl Named for Ann { fn name(&self) -> String { "Ann".into() } } impl Person for Ann { fn id(&self) -> u32 { 7 } }
    fn only_named(n: &dyn Named) -> String { n.name() }
    fn main() {
        let p: &dyn Person = &Ann;
        println!("通过 &dyn Person 调用 id() = {},name() = {}", p.id(), p.name());
        println!("向上转型成 &dyn Named:{}", only_named(p));
        let b: Box<dyn Person> = Box::new(Ann); let n: Box<dyn Named> = b;
        println!("Box<dyn Person> 转成 Box<dyn Named>:{}", n.name());
    }
''', quiet_src=False); R['upcast_ok'] = r['ok']
print()
print('== 四:两个 supertrait 有同名方法时,在子 trait 里用到它会有歧义')
r = tryit('u45e', '''
    trait A { fn hello(&self) -> &'static str { "A" } }
    trait B { fn hello(&self) -> &'static str { "B" } }
    trait C: A + B { fn call(&self) -> &'static str { self.hello() } }
    fn main() {}
''', maxlines=26); R['e034'] = r['diag'].split('\n')[0]
r = tryit('u45f', '''
    trait A { fn hello(&self) -> &'static str { "A" } }
    trait B { fn hello(&self) -> &'static str { "B" } }
    trait C: A + B { fn call(&self) -> String { format!("{} {}", A::hello(self), B::hello(self)) } }
    struct S; impl A for S {} impl B for S {} impl C for S {}
    fn main() { println!("{}", S.call()); }
''', quiet_src=False)
save('u45', R)
