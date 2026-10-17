import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u5'); R = {}
print('== 一:标量类型的大小与范围(std::mem::size_of、MIN / MAX)')
r = tryit('u5a', '''
    use std::mem::size_of;
    macro_rules! int { ($($t:ty),*) => { $( println!("{:>6}  {:>2} 字节  {} ..= {}", stringify!($t), size_of::<$t>(), <$t>::MIN, <$t>::MAX); )* } }
    fn main() {
        int!(i8, u8, i16, u16, i32, u32, i64, u64, i128, u128, isize, usize);
        println!("   f32  {:>2} 字节", size_of::<f32>());
        println!("   f64  {:>2} 字节", size_of::<f64>());
        println!("  bool  {:>2} 字节", size_of::<bool>());
        println!("  char  {:>2} 字节(Unicode 标量值)", size_of::<char>());
        println!("    ()  {:>2} 字节", size_of::<()>());
    }
''', quiet_src=True); R['sizes'] = r['out']
print()
print('== 二:没有标注时的默认类型(用 std::any::type_name 打印编译器推断出的类型)')
r = tryit('u5b', '''
    fn tn<T>(_: &T) -> &'static str { std::any::type_name::<T>() }
    fn main() {
        let a = 42;
        let b = 2.5;
        let c = true;
        let d = 'x';
        let e = "hi";
        let f = [1, 2, 3];
        let g = (1, 2.0, 'c');
        println!("42 → {}", tn(&a));
        println!("2.5 → {}", tn(&b));
        println!("true → {}", tn(&c));
        println!("'x' → {}", tn(&d));
        println!("\\"hi\\" → {}", tn(&e));
        println!("[1,2,3] → {}", tn(&f));
        println!("(1,2.0,'c') → {}", tn(&g));
    }
''')
print()
print('== 三:类型由后文的使用决定;信息不够时编译器要求标注')
r = tryit('u5c', '''
    fn tn<T>(_: &T) -> &'static str { std::any::type_name::<T>() }
    fn takes_u8(_: u8) {}
    fn main() {
        let a = 5;            // 暂时不知道是什么整数类型
        takes_u8(a);          // 后面这一行把它定成 u8
        println!("a: {}", tn(&a));
        let mut v = Vec::new();
        v.push(1.5f32);
        println!("v: {}", tn(&v));
    }
''')
r = tryit('u5d', '''
    fn main() {
        let n = "5".parse().unwrap();
        println!("{}", n);
    }
''', maxlines=24); R['e_ann'] = r['diag'].split('\n')[0]
print()
print('== 四:整数溢出:debug 构建 panic,release 构建回绕;四种显式写法')
code = '''
    fn main() {
        let n: u8 = std::env::args().count() as u8 + 254;   // 运行时才知道:255
        println!("n = {n}");
        println!("checked_add(1)    = {:?}", n.checked_add(1));
        println!("wrapping_add(1)   = {}", n.wrapping_add(1));
        println!("saturating_add(1) = {}", n.saturating_add(1));
        println!("overflowing_add(1)= {:?}", n.overflowing_add(1));
        let m = n + 1;        // 普通的 +
        println!("n + 1 = {m}");
    }
'''
print('  (1) debug 构建:'); r1 = tryit('u5e', code, quiet_src=False); R['debug'] = (r1['out'] + r1.get('err', '')).strip().split('\n')[-3:]
print('  (2) release 构建 (-O):'); r2 = tryit('u5e2', code, release=True, quiet_src=True); R['release'] = r2['out'].strip().split('\n')[-1]
print()
print('== 五:as 转换的规则')
r = tryit('u5f', '''
    fn main() {
        println!("300i32 as u8        = {}", 300i32 as u8);
        println!("-1i32 as u32        = {}", -1i32 as u32);
        println!("200u8 as i8         = {}", 200u8 as i8);
        println!("3.99f64 as i32      = {}", 3.99f64 as i32);
        println!("-3.99f64 as i32     = {}", -3.99f64 as i32);
        println!("1e20f64 as i32      = {}", 1e20f64 as i32);
        println!("f64::NAN as i32     = {}", f64::NAN as i32);
        println!("65u8 as char        = {}", 65u8 as char);
        println!("'中' as u32         = {}", '中' as u32);
        println!("true as i32         = {}", true as i32);
    }
''', quiet_src=False); R['cast'] = r['out']
save('u5', R)
