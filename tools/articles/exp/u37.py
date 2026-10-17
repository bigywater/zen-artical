import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u37'); R = {}
print('== 一:泛型函数里用了某个操作,就必须在 T 上声明对应的 trait bound')
r = tryit('u37a', '''
    fn largest<T>(list: &[T]) -> &T {
        let mut m = &list[0];
        for x in list { if x > m { m = x; } }
        m
    }
    fn main() { println!("{}", largest(&[1, 5, 2])); }
''', maxlines=30); R['e369'] = r['diag'].split('\n')[0]
print()
print('== 二:加上 T: PartialOrd,就可以用于所有实现了它的类型;没实现的类型被拒绝')
r = tryit('u37b', '''
    fn largest<T: PartialOrd>(list: &[T]) -> &T {
        let mut m = &list[0];
        for x in list { if x > m { m = x; } }
        m
    }
    fn main() {
        println!("i32:{}  f64:{}  char:{}  &str:{}", largest(&[1, 5, 2]), largest(&[1.5, 0.2]), largest(&['a', 'z', 'm']), largest(&["pear", "apple"]));
        println!("String:{}", largest(&[String::from("b"), String::from("a")]));
    }
''', quiet_src=False)
r = tryit('u37c', '''
    fn largest<T: PartialOrd>(list: &[T]) -> &T { let mut m = &list[0]; for x in list { if x > m { m = x; } } m }
    struct P { x: i32 }
    fn main() { let v = [P { x: 1 }, P { x: 2 }]; largest(&v); }
''', maxlines=30); R['e277'] = r['diag'].split('\n')[0]
print()
print('== 三:多个约束与 where 子句')
r = tryit('u37d', '''
    use std::fmt::{Debug, Display};
    fn show_both<T: Display + Clone, U: Debug>(t: &T, u: &U) -> String { format!("{} / {:?} / 克隆的 {}", t, u, t.clone()) }
    fn show_where<T, U>(t: &T, u: &U) -> String where T: Display + Clone, U: Debug { show_both(t, u) }
    fn main() {
        println!("{}", show_both(&"hi", &vec![1, 2]));
        println!("{}", show_where(&3.5, &Some('x')));
    }
''', quiet_src=False)
print()
print('== 四:按约束有条件地提供方法:impl<T: Display> 里的方法只有满足约束的类型才有')
r = tryit('u37e', '''
    use std::fmt::Display;
    struct Pair<T> { a: T, b: T }
    impl<T> Pair<T> { fn new(a: T, b: T) -> Self { Pair { a, b } } }                      // 对所有 T 都有
    impl<T: Display + PartialOrd> Pair<T> {                                              // 只有 T 满足约束才有
        fn show_largest(&self) { if self.a >= self.b { println!("最大的是 a = {}", self.a) } else { println!("最大的是 b = {}", self.b) } }
    }
    struct NoDisplay;
    fn main() {
        Pair::new(3, 9).show_largest();
        let p = Pair::new(NoDisplay, NoDisplay);
        p.show_largest();
    }
''', maxlines=30); R['e599'] = r['diag'].split('\n')[0]
print()
print('== 五:约束在编译期解析(单态化):每个具体类型一份机器码 —— 同一个泛型函数,不同 T 生成不同的函数')
code = '''
    #[unsafe(no_mangle)] pub fn add_i32(a: i32, b: i32) -> i32 { add(a, b) }
    #[unsafe(no_mangle)] pub fn add_f64(a: f64, b: f64) -> f64 { add(a, b) }
    #[inline(never)] fn add<T: std::ops::Add<Output = T>>(a: T, b: T) -> T { a + b }
'''
_, txt = asm_of('u37f', code, None)
syms = re.findall(r'^(__R[^\s:]*u37f3add[^\s:]*):', txt, re.M)
print('  生成的 add 函数符号(每个具体类型一份):', len(syms), '个')
for sym in syms:
    m = re.search(rf'^{re.escape(sym)}:\n(.*?)(?=^\s*\.cfi_endproc)', txt, re.S | re.M); body = [l.strip() for l in m.group(1).split('\n') if l.strip() and not l.strip().startswith('.')]
    kind = 'i32' if 'addl' in sym else 'f64' if 'addd' in sym else '?'
    print(f'  add::<{kind}>:', ' ; '.join(body)); R.setdefault('asm', {})[kind] = body
save('u37', R)
