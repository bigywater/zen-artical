import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u27'); R = {}
print('== 规则 1:每个被省略的输入引用各自得到一个独立的生命周期(这一条只影响输入)')
r = tryit('u27a', '''
    fn lens(a: &str, b: &str) -> usize { a.len() + b.len() }                  // 省略写法
    fn lens_explicit<'a, 'b>(a: &'a str, b: &'b str) -> usize { a.len() + b.len() }   // 等价的完整写法
    fn main() {
        let a = String::from("long lived");
        let r;
        { let b = String::from("short"); r = (lens(&a, &b), lens_explicit(&a, &b)); }
        println!("两种写法结果相同:{:?}", r);
    }
''', quiet_src=False)
print()
print('== 规则 2:只有一个输入生命周期(省略的或显式的)时,它被赋给所有省略的输出生命周期')
r = tryit('u27b', '''
    fn first_char(s: &str) -> &str { &s[..1] }                 // 省略写法
    fn first_char_explicit<'a>(s: &'a str) -> &'a str { &s[..1] }
    fn pair(p: &(String, String)) -> (&String, &String) { (&p.0, &p.1) }   // 输出有两个引用,都借自唯一的输入
    fn main() {
        let s = String::from("你好");
        println!("{} {}", first_char("abc"), first_char_explicit("xyz"));
        let t = (String::from("a"), String::from("b"));
        let (x, y) = pair(&t);
        println!("{x} {y}   {}", s.len());
    }
''', quiet_src=False)
print()
print('== 规则 3:有 &self 或 &mut self 时,所有省略的输出生命周期等于 self 的生命周期(即使还有别的引用参数)')
r = tryit('u27c', '''
    struct Store { name: String }
    impl Store {
        fn get(&self, other: &str) -> &str { &self.name }          // 返回值借自 self
        fn wrong(&self, other: &str) -> &str { other }              // 想返回 other:被拒绝
    }
    fn main() {}
''', maxlines=30); R['e_rule3'] = [l for l in r['diag'].split('\n') if l.startswith('error')][:1]
print()
print('== 省略规则覆盖不到的情形:没有输入引用、有多个输入引用的普通函数')
r = tryit('u27d', '''
    fn make() -> &str { "x" }
    fn main() {}
''', maxlines=22); R['e_noinput'] = r['diag'].split('\n')[0]
r = tryit('u27e', '''
    fn pick(a: &str, b: &str) -> &str { a }
    fn main() {}
''', maxlines=22); R['e_two'] = r['diag'].split('\n')[0]
print()
print("== 匿名生命周期 '_:在 impl 与类型路径里提示「这里有一个被省略的生命周期」")
r = tryit('u27f', '''
    struct Excerpt<'a> { part: &'a str }
    impl Excerpt<'_> { fn len(&self) -> usize { self.part.len() } }       // 不需要名字时用 '_
    fn show(e: &Excerpt<'_>) -> usize { e.len() }
    fn main() { let t = String::from("abc"); let e = Excerpt { part: &t }; println!("{}", show(&e)); }
''', quiet_src=False)
r = tryit('u27g', '''
    struct Excerpt<'a> { part: &'a str }
    fn show(e: &Excerpt) -> usize { e.part.len() }          // 路径里藏着一个被省略的生命周期
    fn main() { let t = String::from("abc"); println!("{}", show(&Excerpt { part: &t })); }
''', flags=('-W', 'elided-lifetimes-in-paths'), quiet_src=True, maxlines=14); R['lint'] = [l for l in r['diag'].split('\n') if l.startswith('warning')][:1]
save('u27', R)
