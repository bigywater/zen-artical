import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u114'); R = {}
print('== 一:Option<T> 的大小:有些类型有「空闲位模式」(niche),Option 不需要额外标签')
r = tryit('u114a', '''
    use std::{mem::size_of, num::{NonZeroU32, NonZeroU8}, rc::Rc};
    #[allow(dead_code)] enum Dir { N, E, S, W }
    fn main() {
        macro_rules! p { ($a:ty, $b:ty) => { println!("  {:<22} {:>2} 字节   {:<26} {:>2} 字节   {}", stringify!($a), size_of::<$a>(), stringify!($b), size_of::<$b>(), if size_of::<$b>() == size_of::<$a>() { "Option 不加大小(niche)" } else { "多出 tag" }); } }
        p!(u32, Option<u32>); p!(u8, Option<u8>); p!(NonZeroU32, Option<NonZeroU32>); p!(NonZeroU8, Option<NonZeroU8>);
        p!(bool, Option<bool>); p!(char, Option<char>); p!(Dir, Option<Dir>); p!(&u64, Option<&u64>); p!(Box<u64>, Option<Box<u64>>); p!(Rc<u64>, Option<Rc<u64>>);
        p!(Vec<u8>, Option<Vec<u8>>); p!(String, Option<String>); p!(f64, Option<f64>);
        println!("  Option<Option<bool>> {} 字节  Option<Option<Option<bool>>> {} 字节(bool 只用了 0、1 两个值,其余位模式都可以拿来当标签)", size_of::<Option<Option<bool>>>(), size_of::<Option<Option<Option<bool>>>>());
    }
''', quiet_src=True); R['option'] = r['out']
print()
print('== 二:带数据的枚举:大小由最大变体加标签决定,有 niche 时标签可以省掉;用 -Z print-type-sizes 看编译器的描述')
code = '''
    #![allow(dead_code)]
    pub enum Shape { Dot, Circle(f32), Rect(f32, f32), Poly([f32; 6]) }
    pub enum Msg { Quit, Move { x: i32, y: i32 }, Write(String), Color(u8, u8, u8) }
    pub fn make() -> (Shape, Msg) { (Shape::Dot, Msg::Quit) }
'''
f = src_file('u114b', code); rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '-Z', 'print-type-sizes', '--emit=metadata', '-o', str(RS / 'bin' / 'u114b.rmeta'), str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
sel = []; on = False
for l in o.splitlines():
    if l.startswith('print-type-size type:'): on = ('Shape' in l or 'Msg' in l) and 'variant' not in l
    if on: sel.append(l.replace('print-type-size ', ''))
print('\n'.join('  ' + l for l in sel)); R['pts'] = sel
print()
print('== 三:判别值(discriminant):mem::discriminant;显式写判别值;C 风格枚举 as 转换')
r = tryit('u114c', '''
    use std::mem::discriminant;
    #[allow(dead_code)] #[derive(Debug)] enum Op { Add = 10, Sub = 20, Mul }
    #[allow(dead_code)] enum Data { A(u8), B(String) }
    fn main() {
        println!("Op::Add as i32 = {}  Op::Sub = {}  Op::Mul(接着前一个 +1) = {}", Op::Add as i32, Op::Sub as i32, Op::Mul as i32);
        println!("discriminant(&Data::A(1)) == discriminant(&Data::A(99)): {}", discriminant(&Data::A(1)) == discriminant(&Data::A(99)));
        println!("discriminant(&Data::A(1)) == discriminant(&Data::B(String::new())): {}", discriminant(&Data::A(1)) == discriminant(&Data::B(String::new())));
        println!("数字转回枚举没有内置的安全方法:要手写 match 或用 TryFrom(下面是编译器的报错)");
    }
''', quiet_src=True); R['disc'] = r['out']
r = tryit('u114d', '''
    #[derive(Debug)] enum Op { Add = 10, Sub = 20 }
    fn main() { let o: Op = 10 as Op; println!("{:?}", o); }
''', maxlines=24); R['e_cast'] = r['diag']
print()
print('== 四:niche 的实际内存:Option<&u64> 的 None 就是全 0 指针;Option<bool> 的 None 是 2;用 transmute 读出字节')
r = tryit('u114e', '''
    use std::mem::transmute;
    fn main() {
        let none_ref: Option<&u64> = None; let n: usize = unsafe { transmute(none_ref) };
        let some_ref: Option<&u64> = Some(&5); let s: usize = unsafe { transmute(some_ref) };
        println!("Option<&u64>:None = {:#x}(空指针);Some 的值 = 指针本身(非 0): {}", n, s != 0);
        let nb: Option<bool> = None; let sb: Option<bool> = Some(true); let fb: Option<bool> = Some(false);
        let (a, b, c): (u8, u8, u8) = unsafe { (transmute(nb), transmute(sb), transmute(fb)) };
        println!("Option<bool>:None = {},Some(true) = {},Some(false) = {}(用 bool 不会出现的 2 作为 None)", a, b, c);
        let ou: Option<u32> = None; let su: Option<u32> = Some(7); let (x, y): (u64, u64) = unsafe { (transmute(ou), transmute(su)) };
        println!("Option<u32>(8 字节):None 的低 4 字节 tag = {},Some(7) 的 tag = {}", x & 0xFFFF_FFFF, y & 0xFFFF_FFFF);
    }
''', quiet_src=True); R['bytes'] = r['out']
save('u114', R)
