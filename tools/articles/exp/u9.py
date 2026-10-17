import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u9'); R = {}
print('== 一:if let / while let:只关心一个模式时比 match 短')
r = tryit('u9a', '''
    fn main() {
        let a: Option<i32> = Some(7);
        let b: Option<i32> = None;
        if let Some(x) = a { println!("a 有值 {x}"); }
        if let Some(x) = b { println!("b 有值 {x}"); } else { println!("b 是 None"); }
        let mut stack = vec![1, 2, 3];
        while let Some(top) = stack.pop() { println!("pop {top}"); }
        // 2024 edition 可以在 if let 里用 && 连接条件(let chains)
        if let Some(x) = a && x > 5 { println!("let chain:a = {x} 且大于 5"); }
    }
''', quiet_src=False)
print()
print('== 二:let else:匹配失败时必须发散(return / break / continue / panic),成功时绑定留在外层作用域')
r = tryit('u9b', '''
    fn parse_port(s: &str) -> Option<u16> {
        let Ok(p) = s.parse::<u16>() else { return None; };   // 失败就提前返回
        Some(p)       // 这里还能用 p:绑定留在了外层
    }
    fn main() {
        println!("{:?} {:?} {:?}", parse_port("8080"), parse_port("abc"), parse_port("99999"));
    }
''', quiet_src=False)
r = tryit('u9c', '''
    fn main() {
        let o: Option<i32> = Some(1);
        let Some(x) = o else { println!("没有值"); };
        println!("{x}");
    }
''', maxlines=18); R['e_diverge'] = r['diag'].split('\n')[0]
print()
print('== 三:普通 let 只接受「一定匹配」的模式;if let 对一定匹配的模式给警告')
r = tryit('u9d', '''
    fn main() {
        let o: Option<i32> = Some(1);
        let Some(x) = o;
        println!("{x}");
    }
''', maxlines=24); R['e0005'] = r['diag'].split('\n')[0]
r = tryit('u9e', '''
    fn main() {
        let t = (1, 2);
        if let (a, b) = t { println!("{a} {b}"); }
    }
''', maxlines=14)
print()
print('== 四:if let 条件里的临时值何时释放,在 2024 edition 里变了(同一份代码分别用 2021 与 2024 编译)')
code = '''
    struct D;
    impl Drop for D { fn drop(&mut self) { println!("  drop(临时值 D)"); } }
    fn f(_: &D) -> Option<i32> { None }
    fn main() {
        if let Some(_) = f(&D) { println!("  then 分支"); } else { println!("  else 分支"); }
        println!("  if let 语句之后");
    }
'''
for ed in ('2021', '2024'):
    print(f'  --edition {ed}:'); r = tryit(f'u9f{ed}', code, edition=ed, quiet_src=(ed == '2024')); R['tmp_' + ed] = r['out'].strip().split('\n')
save('u9', R)
