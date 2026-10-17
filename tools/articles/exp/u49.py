import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u49'); R = {}
print('== 一:From 定义「怎样从 A 构造出我」;标准库为无损转换实现了 From,有损的没有')
r = tryit('u49a', '''
    use std::collections::HashMap;
    fn main() {
        let a = i64::from(7i32);                // i32 → i64 无损
        let b = f64::from(3u8);
        let s = String::from("text"); let c = String::from('c');
        let v = Vec::from([1, 2, 3]); let bs: Vec<u8> = Vec::from("hi");
        let m = HashMap::from([("a", 1), ("b", 2)]);
        println!("{a} {b} {s} {c} {:?} {:?} 长度 {}", v, bs, m.len());
    }
''', quiet_src=False)
r = tryit('u49b', '''
    fn main() { let x: i32 = i32::from(5i64); let y: u8 = u8::from(300u32); }
''', maxlines=26); R['e277'] = r['diag'].split('\n')[0]
print()
print('== 二:为自己的类型实现 From,免费得到 Into;并让 ? 自动转换错误类型')
r = tryit('u49c', '''
    use std::num::ParseIntError;
    use std::fmt;
    #[derive(Debug)] enum AppError { Parse(ParseIntError), Negative(i32) }
    impl From<ParseIntError> for AppError { fn from(e: ParseIntError) -> Self { AppError::Parse(e) } }
    impl fmt::Display for AppError { fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { match self { AppError::Parse(e) => write!(f, "解析失败:{e}"), AppError::Negative(n) => write!(f, "{n} 是负数") } } }
    fn parse_positive(s: &str) -> Result<i32, AppError> {
        let n: i32 = s.parse()?;               // ParseIntError 通过 From 自动变成 AppError
        if n < 0 { return Err(AppError::Negative(n)); }
        Ok(n)
    }
    fn main() {
        for s in ["42", "abc", "-5"] { match parse_positive(s) { Ok(n) => println!("{s} → Ok({n})"), Err(e) => println!("{s} → Err({e})") } }
    }
''', quiet_src=False)
print()
print('== 三:参数里用 impl Into<String>:调用者可以传 &str 也可以传 String;传 String 时不会再分配(计数分配器)')
r = tryit('u49d', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicUsize, Ordering};
    struct C; static AL: AtomicUsize = AtomicUsize::new(0);
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { AL.fetch_add(1, Ordering::Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { unsafe { System.dealloc(p, l) } }
    }
    #[global_allocator] static G: C = C;
    struct User { name: String }
    fn new_user(name: impl Into<String>) -> User { User { name: name.into() } }
    fn main() {
        let owned = String::from("alice");                       // 这次分配不计入下面的统计
        let a0 = AL.load(Ordering::Relaxed);
        let u1 = new_user("bob");                                // &str → String:要分配
        let a1 = AL.load(Ordering::Relaxed);
        let u2 = new_user(owned);                                // String → String:Into 是恒等转换,直接移动
        let a2 = AL.load(Ordering::Relaxed);
        println!("传 &str:分配 {} 次;传 String:分配 {} 次", a1 - a0, a2 - a1);
        println!("{} {}", u1.name, u2.name);
    }
''', release=True, quiet_src=False); R['alloc'] = r['out']
print()
print('== 四:From 是自反的(From<T> for T),所以泛型代码里 T: Into<U> 对 U 自己也成立')
r = tryit('u49e', '''
    fn total<T: Into<f64>>(items: Vec<T>) -> f64 { items.into_iter().map(Into::into).sum() }
    fn main() { println!("{} {} {}", total(vec![1u8, 2]), total(vec![1.5f32, 2.5]), total(vec![2.5f64, 0.5])); }
''', quiet_src=False)
save('u49', R)
