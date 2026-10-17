import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u11'); R = {}
print('== 一:没有 derive 的结构体:不能打印、不能比较、不能克隆')
r = tryit('u11a', '''
    struct P { x: i32, y: i32 }
    fn main() {
        let a = P { x: 1, y: 2 };
        println!("{:?}", a);
        let b = a.clone();
        println!("{}", a == b);
    }
''', maxlines=40); R['errs'] = re.findall(r'error\[(E\d+)\]', r['diag'])
print()
print('== 二:加上 #[derive(Debug, Clone, PartialEq, Default)] 之后')
r = tryit('u11b', '''
    #[derive(Debug, Clone, PartialEq, Default)]
    struct P { x: i32, y: i32, name: String }
    fn main() {
        let a = P { x: 1, y: 2, name: "a".into() };
        let b = a.clone();
        println!("{:?}", a);
        println!("{:#?}", b);
        println!("a == b : {}", a == b);
        println!("Default:{:?}", P::default());
    }
''', quiet_src=False)
print()
print('== 三:derive 到底生成了什么:用 -Z unpretty=expanded 展开(RUSTC_BOOTSTRAP=1 在稳定版编译器上打开 -Z 选项)')
ok, diag, b, t = rustc('u11c', '''
    #[derive(Debug, Clone, PartialEq)]
    struct P { x: i32, y: i32 }
    fn main() {}
''', flags=('-Z', 'unpretty=expanded', '-o', '-'), boot=True)
f = src_file('u11c', '''
    #[derive(Debug, Clone, PartialEq)]
    struct P { x: i32, y: i32 }
    fn main() {}
''')
rc, o, e = sh(['rustc', '--edition=2024', '-Z', 'unpretty=expanded', str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
lines = [l for l in o.split('\n') if l.strip() and not l.startswith(('#![', 'use std::prelude', '#[macro_use]', 'extern crate'))]
print('\n'.join('  ' + l for l in lines)); R['expanded'] = lines
print()
print('== 四:Copy 要求所有字段都是 Copy;PartialOrd 按字段顺序比较')
r = tryit('u11d', '''
    #[derive(Clone, Copy)]
    struct S { name: String }
    fn main() {}
''', maxlines=18); R['e_copy'] = r['diag'].split('\n')[0]
r = tryit('u11e', '''
    #[derive(Debug, PartialEq, PartialOrd)]
    struct Ver { major: u32, minor: u32 }
    #[derive(Debug, PartialEq, PartialOrd)]
    enum Level { Low, Mid, High }
    fn main() {
        println!("{}", Ver { major: 1, minor: 9 } < Ver { major: 2, minor: 0 });
        println!("{}", Ver { major: 2, minor: 1 } < Ver { major: 2, minor: 0 });
        println!("{}", Level::Low < Level::High);
        println!("{:?}", Level::Mid.partial_cmp(&Level::Low));
    }
''', quiet_src=False)
print()
print('== 五:泛型结构体上的 derive 会给类型参数加约束')
r = tryit('u11f', '''
    #[derive(Debug, Clone)]
    struct W<T> { v: T }
    struct NoClone;
    fn main() {
        let a = W { v: 5 }; let b = a.clone(); println!("{:?}", b);
        let c = W { v: NoClone };
        let d = c.clone();
    }
''', maxlines=30); R['e_bound'] = r['diag'].split('\n')[0]
save('u11', R)
