import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u10'); R = {}
print('== 一:Option<T> 与 Result<T, E> 就是两个普通的枚举(标准库里的定义)')
r = tryit('u10a', '''
    #[allow(dead_code)]
    enum MyOption<T> { None, Some(T) }
    #[allow(dead_code)]
    enum MyResult<T, E> { Ok(T), Err(E) }
    fn first_even(v: &[i32]) -> MyOption<i32> { for &x in v { if x % 2 == 0 { return MyOption::Some(x); } } MyOption::None }
    fn main() {
        match first_even(&[1, 3, 4, 5]) { MyOption::Some(x) => println!("找到偶数 {x}"), MyOption::None => println!("没有偶数") }
        // 标准库的版本
        let o: Option<i32> = [1, 3, 4, 5].iter().copied().find(|x| x % 2 == 0);
        let e: Result<i32, std::num::ParseIntError> = "12x".parse::<i32>();
        println!("{:?}  {:?}", o, e);
    }
''', quiet_src=False)
print()
print('== 二:没有 null:想要「可能没有」就必须用 Option,编译器不让你直接当值用')
r = tryit('u10b', '''
    fn main() {
        let a: Option<i32> = Some(5);
        let b = a + 1;
        println!("{b}");
    }
''', maxlines=22); R['e_opt'] = r['diag'].split('\n')[0]
print()
print('== 三:常用方法:unwrap_or、map、and_then、ok_or、?')
r = tryit('u10c', '''
    fn parse_and_double(s: &str) -> Result<i32, std::num::ParseIntError> { let n: i32 = s.parse()?; Ok(n * 2) }
    fn main() {
        let a = Some(3); let n: Option<i32> = None;
        println!("unwrap_or:{} {}", a.unwrap_or(0), n.unwrap_or(0));
        println!("map:{:?} {:?}", a.map(|x| x * 10), n.map(|x| x * 10));
        println!("and_then:{:?}", a.and_then(|x| if x > 2 { Some(x + 100) } else { None }));
        println!("ok_or:{:?} {:?}", a.ok_or("没有值"), n.ok_or("没有值"));
        println!("Result 转 Option:{:?} {:?}", "7".parse::<i32>().ok(), "x".parse::<i32>().ok());
        println!("?:{:?}  {:?}", parse_and_double("21"), parse_and_double("abc"));
        println!("filter:{:?} {:?}", a.filter(|x| x % 2 == 1), a.filter(|x| x % 2 == 0));
        println!("take:{:?}", { let mut t = Some(9); let old = t.take(); (old, t) });
    }
''', quiet_src=False)
print()
print('== 四:unwrap 失败时 panic 的信息;expect 可以带上下文')
r = tryit('u10d', '''
    fn main() {
        let r: Result<i32, _> = "abc".parse::<i32>();
        println!("先尝试 expect:");
        let v = r.expect("配置里的端口必须是整数");
        println!("{v}");
    }
''', quiet_src=True); R['panic'] = [l for l in (r.get('err', '')).split('\n') if 'panicked' in l or '配置' in l][:2]
print()
print('== 五:Option 的内存占用:Option<&T>、Option<Box<T>> 没有额外开销;Option<i32> 需要标签')
r = tryit('u10e', '''
    use std::mem::size_of;
    fn main() {
        println!("&u64 = {},Option<&u64> = {}", size_of::<&u64>(), size_of::<Option<&u64>>());
        println!("Box<u64> = {},Option<Box<u64>> = {}", size_of::<Box<u64>>(), size_of::<Option<Box<u64>>>());
        println!("i32 = {},Option<i32> = {}", size_of::<i32>(), size_of::<Option<i32>>());
        println!("u64 = {},Option<u64> = {}", size_of::<u64>(), size_of::<Option<u64>>());
        println!("Result<u8, u8> = {},Result<u32, String> = {}", size_of::<Result<u8, u8>>(), size_of::<Result<u32, String>>());
        println!("String = {},Option<String> = {}", size_of::<String>(), size_of::<Option<String>>());
    }
''', quiet_src=True); R['sizes'] = r['out']
save('u10', R)
