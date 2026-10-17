import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u7'); R = {}
print('== 一:Tuple:匿名、定长、可以混合类型;下标用 .0 .1,可以解构')
r = tryit('u7a', '''
    use std::mem::size_of;
    fn main() {
        let t = (500, 6.4, 'z');
        let (a, b, c) = t;                       // 解构
        println!("t.0 = {}, t.1 = {}, t.2 = {}", t.0, t.1, t.2);
        println!("解构:a = {a}, b = {b}, c = {c}");
        println!("(i32, f64, char) 占 {} 字节,字段字节数之和 = {}", size_of::<(i32, f64, char)>(), size_of::<i32>() + size_of::<f64>() + size_of::<char>());
        let unit = ();
        println!("单元类型 () = {:?},占 {} 字节", unit, size_of::<()>());
        let one = (1,);                          // 单元素元组要带逗号
        println!("(1,) = {:?},(1) 是普通括号表达式 = {}", one, (1));
    }
''', quiet_src=False)
print()
print('== 二:Struct:命名字段、元组结构体、单元结构体;字段会被编译器重排以减少 padding')
r = tryit('u7b', '''
    use std::mem::size_of;
    #[derive(Debug, Clone)] struct User { name: String, age: u8, active: bool }
    struct Point(f64, f64);              // 元组结构体
    struct Marker;                       // 单元结构体
    struct Loose { a: u8, b: u32, c: u8 }
    #[repr(C)] struct LooseC { a: u8, b: u32, c: u8 }
    fn main() {
        let u1 = User { name: "ann".into(), age: 30, active: true };
        let u2 = User { name: "bob".into(), ..u1.clone() };   // 结构体更新语法
        println!("{:?}\\n{:?}", u1, u2);
        let p = Point(1.0, 2.5); println!("Point.0 = {}, Point.1 = {}", p.0, p.1);
        println!("Marker 占 {} 字节", size_of::<Marker>());
        println!("Loose{{u8,u32,u8}} 默认布局:{} 字节;#[repr(C)]:{} 字节;字段之和 = 6", size_of::<Loose>(), size_of::<LooseC>());
    }
''', quiet_src=False, flags=('-A', 'dead_code'))
print()
print('== 三:Enum:每个变体可以带不同的数据;大小 = 最大的变体 + 标签')
r = tryit('u7c', '''
    use std::mem::size_of;
    #[derive(Debug)]
    enum Shape { Circle(f64), Rect { w: f64, h: f64 }, Empty }
    #[derive(Debug, Clone, Copy)] enum Color { Red, Green = 10, Blue }
    fn area(s: &Shape) -> f64 { match s { Shape::Circle(r) => 3.14 * r * r, Shape::Rect { w, h } => w * h, Shape::Empty => 0.0 } }
    fn main() {
        for s in [Shape::Circle(2.0), Shape::Rect { w: 3.0, h: 4.0 }, Shape::Empty] { println!("{:?} 面积 = {}", s, area(&s)); }
        println!("size_of::<Shape>() = {} 字节(最大变体 Rect = 16 字节 + 标签)", size_of::<Shape>());
        println!("Color 是无数据枚举:size_of = {} 字节;Red = {},Green = {},Blue = {}", size_of::<Color>(), Color::Red as i32, Color::Green as i32, Color::Blue as i32);
        println!("size_of::<Option<u8>>() = {};size_of::<Option<u32>>() = {};size_of::<Option<f64>>() = {}", size_of::<Option<u8>>(), size_of::<Option<u32>>(), size_of::<Option<f64>>());
    }
''', quiet_src=False)
print()
print('== 四:枚举变体里的字段不能直接访问,必须先 match / if let')
r = tryit('u7d', '''
    enum Shape { Circle(f64), Empty }
    fn main() {
        let s = Shape::Circle(1.0);
        println!("{}", s.0);
    }
''', maxlines=20); R['e_field'] = r['diag'].split('\n')[0]
save('u7', R)
