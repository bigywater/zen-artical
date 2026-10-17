import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u71'); R = {}
print('== 一:用 ? 传播:成功时取出值,失败时立刻从当前函数返回 Err;后面的语句不再执行')
r = tryit('u71a', '''
    use std::num::ParseIntError;
    fn parse_sum(a: &str, b: &str) -> Result<i32, ParseIntError> {
        println!("  解析 a = {:?}", a);
        let x: i32 = a.parse()?;
        println!("  解析 b = {:?}", b);
        let y: i32 = b.parse()?;
        println!("  两个都成功,相加");
        Ok(x + y)
    }
    fn main() {
        println!("成功: {:?}", parse_sum("3", "4"));
        println!("第二个失败: {:?}", parse_sum("3", "x"));
        println!("第一个失败: {:?}", parse_sum("", "4"));
    }
''', quiet_src=False); R['basic'] = r['out']
print()
print('== 二:? 只能用在返回 Result / Option 的函数里')
r = tryit('u71b', '''
    fn main() {
        let n: i32 = "5".parse()?;
        println!("{}", n);
    }
''', maxlines=28); R['e_main'] = r['diag']
print()
print('== 三:错误类型不同时需要转换:没有 From 实现就报错;实现 From 后 ? 自动转换')
r = tryit('u71c', '''
    use std::num::ParseIntError;
    #[allow(dead_code)] #[derive(Debug)] enum MyErr { Parse(ParseIntError), Neg }
    fn f(s: &str) -> Result<i32, MyErr> {
        let n = s.parse::<i32>()?;
        if n < 0 { return Err(MyErr::Neg); }
        Ok(n)
    }
    fn main() { println!("{:?}", f("1")); }
''', maxlines=30); R['e_from'] = r['diag']
r = tryit('u71d', '''
    use std::num::ParseIntError;
    #[allow(dead_code)] #[derive(Debug)] enum MyErr { Parse(ParseIntError), Neg }
    impl From<ParseIntError> for MyErr { fn from(e: ParseIntError) -> Self { println!("  From<ParseIntError> 被调用"); MyErr::Parse(e) } }
    fn f(s: &str) -> Result<i32, MyErr> {
        let n: i32 = s.parse()?;
        if n < 0 { return Err(MyErr::Neg); }
        Ok(n)
    }
    fn main() { println!("{:?}", f("7")); println!("{:?}", f("-7")); println!("{:?}", f("abc")); }
''', quiet_src=True); R['from'] = r['out']
print()
print('== 四:Option 上的 ?;Option 与 Result 不能混用(要先 ok_or)')
r = tryit('u71e', '''
    fn first_even(v: &[i32]) -> Option<i32> {
        let f = v.first()?;
        if f % 2 == 0 { Some(*f) } else { None }
    }
    fn to_res(v: &[i32]) -> Result<i32, String> {
        let f = v.first().ok_or("空切片".to_string())?;
        Ok(*f)
    }
    fn main() {
        println!("{:?} {:?} {:?}", first_even(&[]), first_even(&[2, 3]), first_even(&[1]));
        println!("{:?} {:?}", to_res(&[]), to_res(&[9]));
    }
''', quiet_src=True); R['opt'] = r['out']
r = tryit('u71f', '''
    fn f(v: &[i32]) -> Result<i32, String> {
        let x = v.first()?;
        Ok(*x)
    }
    fn main() { println!("{:?}", f(&[1])); }
''', maxlines=28); R['e_mix'] = r['diag']
print()
print('== 五:main 返回 Result:出错时进程退出码 1,stderr 里是 Error: + Debug 格式')
r = tryit('u71g', '''
    fn main() -> Result<(), std::num::ParseIntError> {
        println!("开始");
        let n: i32 = "abc".parse()?;
        println!("不会执行到这里 {}", n);
        Ok(())
    }
''', quiet_src=False); R['main'] = {'rc': r['rc'], 'out': r['out'], 'err': r['err']}
save('u71', R)
