import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u77'); R = {}
print('== 一:一个最小的宏:模式匹配 + 展开;重复 $(...),* 实现可变参数')
r = tryit('u77a', '''
    macro_rules! square { ($x:expr) => { $x * $x }; }
    macro_rules! my_vec {
        () => { Vec::new() };
        ($($x:expr),+ $(,)?) => {{ let mut v = Vec::new(); $( v.push($x); )+ v }};
    }
    macro_rules! maxm {
        ($x:expr) => { $x };
        ($x:expr, $($rest:expr),+) => {{ let a = $x; let b = maxm!($($rest),+); if a > b { a } else { b } }};
    }
    fn main() {
        println!("square!(7) = {}", square!(7));
        let e: Vec<i32> = my_vec![]; let v = my_vec![1, 2, 3,];
        println!("my_vec![] = {:?}   my_vec![1,2,3,] = {:?}", e, v);
        println!("maxm!(3, 9, 4, 7) = {}   maxm!(5) = {}", maxm!(3, 9, 4, 7), maxm!(5));
    }
''', quiet_src=False); R['basic'] = r['out']
print()
print('== 二:编译器真实展开(-Z unpretty=expanded)')
code = '''
    macro_rules! square { ($x:expr) => { $x * $x }; }
    macro_rules! my_vec { ($($x:expr),+) => {{ let mut v = Vec::new(); $( v.push($x); )+ v }}; }
    pub fn demo() -> (i32, Vec<i32>) { (square!(2 + 3), my_vec![1, 2, 3]) }
'''
f = src_file('u77b', code); rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '-Z', 'unpretty=expanded', str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
lines = [l for l in o.splitlines() if l.strip() and not l.startswith(('#![', 'extern crate', 'use std::prelude', '#[attr', '#[prelude'))]
print('  源码:'); print('\n'.join('    ' + l for l in show(code).splitlines()))
print('  展开后:'); print('\n'.join('    ' + l for l in lines)); R['expanded'] = lines
print()
print('== 三:$x:expr 会作为一个整体,所以 square!(2 + 3) 是 25,不是 2 + 3 * 2 + 3 = 11;但表达式的副作用会被求值两次')
r = tryit('u77c', '''
    macro_rules! square { ($x:expr) => { $x * $x }; }
    fn square_fn(x: i32) -> i32 { x * x }
    fn main() {
        println!("square!(2 + 3) = {}(2+3 被当作整体)", square!(2 + 3));
        let mut calls = 0; let mut next = || { calls += 1; calls };
        let m = square!(next());
        println!("square!(next()) = {}:宏把 next() 展开了两次(1 * 2),调用次数 {}", m, calls);
        let mut calls2 = 0; let mut next2 = || { calls2 += 1; calls2 };
        let f = square_fn(next2());
        println!("square_fn(next()) = {}:函数只求值一次,调用次数 {}", f, calls2);
    }
''', quiet_src=True); R['double'] = r['out']
print()
print('== 四:没有匹配的规则:编译错误会指出哪个 token;宏必须先定义后使用')
r = tryit('u77d', '''
    macro_rules! pair { ($a:expr, $b:expr) => { ($a, $b) }; }
    fn main() { let p = pair!(1); println!("{:?}", p); }
''', maxlines=30); R['e_nomatch'] = r['diag']
r = tryit('u77e', '''
    fn main() { println!("{}", late!(2)); }
    macro_rules! late { ($x:expr) => { $x + 1 }; }
''', maxlines=30); R['e_order'] = r['diag']
print()
print('== 五:常用的片段类型:ident 生成函数、ty 生成结构体、literal、tt 递归计数')
r = tryit('u77f', '''
    macro_rules! make_fn { ($name:ident, $val:expr) => { fn $name() -> i32 { $val } }; }
    macro_rules! make_struct { ($name:ident { $($f:ident : $t:ty),* }) => { #[derive(Debug, Default)] struct $name { $($f: $t),* } }; }
    macro_rules! op { ($a:literal plus $b:literal) => { $a + $b }; ($a:literal times $b:literal) => { $a * $b }; }
    macro_rules! count { () => { 0usize }; ($head:tt $($tail:tt)*) => { 1usize + count!($($tail)*) }; }
    make_fn!(seven, 7); make_fn!(forty_two, 40 + 2);
    make_struct!(Point { x: i32, y: i32, tag: String });
    #[allow(dead_code)] fn _unused(p: Point) -> i32 { p.x + p.y + p.tag.len() as i32 }
    fn main() {
        println!("seven() = {}  forty_two() = {}", seven(), forty_two());
        println!("{:?}", Point::default());
        println!("op!(3 plus 4) = {}  op!(3 times 4) = {}", op!(3 plus 4), op!(3 times 4));
        println!("count!(a b c d e) = {}", count!(a b c d e));
    }
''', quiet_src=True); R['frag'] = r['out']
save('u77', R)
