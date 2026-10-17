import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u8'); R = {}
print('== 一:漏掉一个变体:编译器列出没覆盖的模式')
r = tryit('u8a', '''
    enum Dir { North, East, South, West }
    fn turn(d: Dir) -> &'static str {
        match d {
            Dir::North => "向北",
            Dir::East => "向东",
        }
    }
    fn main() { println!("{}", turn(Dir::South)); }
''', maxlines=30); R['e0004'] = r['diag'].split('\n')[0]
print()
print('== 二:模式的几种写法:字面量、范围、|、守卫、@ 绑定、解构、元组')
r = tryit('u8b', '''
    #[derive(Debug)] enum Msg { Quit, Move { x: i32, y: i32 }, Write(String) }
    fn classify(n: u32) -> &'static str {
        match n { 0 => "零", 1 | 2 | 3 => "很小", 4..=9 => "个位数", 10..=99 => "两位数", _ => "更大" }
    }
    fn main() {
        for n in [0, 2, 7, 42, 1000] { println!("{n} → {}", classify(n)); }
        let m = [Msg::Quit, Msg::Move { x: 3, y: -1 }, Msg::Write("hi".into())];
        for x in &m {
            let s = match x { Msg::Quit => "退出".to_string(), Msg::Move { x, y: 0 } => format!("水平移动 {x}"), Msg::Move { x, y } if *y < 0 => format!("向下 {y},横向 {x}"), Msg::Move { .. } => "其它移动".to_string(), Msg::Write(t) => format!("写入 {t}") };
            println!("{:?} → {s}", x);
        }
        let age = 25;
        match age { n @ 18..=64 => println!("成年人,年龄 {n}"), n => println!("其它 {n}") }
        match (3, -3) { (x, y) if x + y == 0 => println!("元组:和为零"), (x, _) if x % 2 == 1 => println!("x 是奇数"), _ => println!("都不是") }
    }
''', quiet_src=False)
print()
print('== 三:_ 通配符会隐藏「新增变体」:给 enum 加一个变体,显式列全的 match 报错,带 _ 的 match 悄悄通过')
hdr = '#[derive(Debug)] enum Level { Low, High%s }\n'
exp_fn = 'fn f(l: Level) -> u8 { match l { Level::Low => 1, Level::High => 2 } }\n'
wild_fn = 'fn f(l: Level) -> u8 { match l { Level::Low => 1, _ => 2 } }\nfn main() { println!("{}", f(Level::High)); }\n'
print('  (1) 显式列全每个变体的 match,Level 只有 Low、High:'); tryit('u8c', hdr % '' + exp_fn + 'fn main() { println!("{}", f(Level::High)); }\n', quiet_src=True, flags=('-A', 'dead_code'))
print('  (2) 给 Level 新增变体 Critical,显式 match 一行不改:'); r = tryit('u8d', hdr % ', Critical' + exp_fn + 'fn main() { println!("{}", f(Level::High)); }\n', maxlines=18, quiet_src=True, flags=('-A', 'dead_code')); R['add_variant'] = r['diag'].split('\n')[0]
print('  (3) 同样新增 Critical,但 match 里用了 _ 通配:'); r = tryit('u8g', hdr % ', Critical' + wild_fn.replace('Level::High', 'Level::Critical'), quiet_src=True, flags=('-A', 'dead_code')); R['wild_out'] = r['out'].strip()
print()
print('== 四:match 是表达式,所有分支类型必须一致;整数的穷尽性也要检查')
r = tryit('u8e', '''
    fn main() {
        let n = 3;
        let s = match n { 1 => "one", 2 => 2, _ => "many" };
        println!("{}", s);
    }
''', maxlines=24); R['e_arms'] = r['diag'].split('\n')[0]
r = tryit('u8f', '''
    fn main() {
        let x: u8 = std::env::args().count() as u8;
        let s = match x { 0..=254 => "不是 255" };
        println!("{s}");
    }
''', maxlines=18); R['e_u8'] = [l for l in r['diag'].split('\n') if 'not covered' in l][:1]
save('u8', R)
