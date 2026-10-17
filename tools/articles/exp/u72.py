import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u72'); R = {}
def hir(name, code):
    f = src_file(name, code); rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '-Z', 'unpretty=hir', str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
    return [l for l in o.splitlines() if l.strip() and not l.startswith(('#![', 'extern crate', '#[attr', 'use std::prelude'))], e
print('== 一:Result 上的 ?,编译器真实展开(-Z unpretty=hir)')
code = '''
    pub fn double(s: &str) -> Result<i32, std::num::ParseIntError> {
        let n: i32 = s.parse()?;
        Ok(n * 2)
    }
'''
print('  源码:'); print('\n'.join('    ' + l for l in show(code).splitlines()))
lines, e = hir('u72a', code); print('  HIR:'); print('\n'.join('    ' + l for l in lines)); R['hir_res'] = lines
print()
print('== 二:Option 上的 ?')
code = '''
    pub fn first_plus(v: &[i32]) -> Option<i32> {
        let f = v.first()?;
        Some(*f + 1)
    }
'''
print('  源码:'); print('\n'.join('    ' + l for l in show(code).splitlines()))
lines, e = hir('u72b', code); print('  HIR:'); print('\n'.join('    ' + l for l in lines)); R['hir_opt'] = lines
print()
print('== 三:手写这个展开(用稳定的 match),与 ? 行为一致;并数 From 转换发生的时机')
r = tryit('u72c', '''
    #[allow(dead_code)] #[derive(Debug)] struct E(String);
    impl From<std::num::ParseIntError> for E { fn from(e: std::num::ParseIntError) -> E { println!("  From 转换"); E(e.to_string()) } }
    fn with_q(s: &str) -> Result<i32, E> { let n: i32 = s.parse::<i32>()?; Ok(n + 1) }
    fn manual(s: &str) -> Result<i32, E> {
        let n = match s.parse::<i32>() { Ok(v) => v, Err(e) => return Err(From::from(e)) };
        Ok(n + 1)
    }
    fn main() {
        for s in ["41", "zz"] { println!("? 版本 {:?} -> {:?}", s, with_q(s)); println!("手写版本 {:?} -> {:?}", s, manual(s)); }
    }
''', quiet_src=False); R['manual'] = r['out']
print()
print('== 四:? 在闭包里返回的是闭包本身,不是外层函数')
r = tryit('u72d', '''
    fn outer() -> i32 {
        let parse = |s: &str| -> Result<i32, std::num::ParseIntError> { let n: i32 = s.parse()?; Ok(n) };
        println!("闭包里 ? 失败: {:?}", parse("x"));
        println!("outer 继续往下执行");
        7
    }
    fn main() { println!("outer 返回 {}", outer()); }
''', quiet_src=True); R['closure'] = r['out']
print()
print('== 五:? 让 Err 经过 From::from;Box<dyn Error> 可以接住任何实现 Error 的类型')
r = tryit('u72e', '''
    use std::error::Error;
    fn f(s: &str) -> Result<i32, Box<dyn Error>> {
        let n: i32 = s.parse()?;
        if n < 0 { Err("负数不允许")?; }
        Ok(n)
    }
    fn main() {
        for s in ["5", "x", "-1"] { match f(s) { Ok(v) => println!("{:?} -> Ok({})", s, v), Err(e) => println!("{:?} -> Err({})", s, e) } }
    }
''', quiet_src=True); R['boxdyn'] = r['out']
save('u72', R)
