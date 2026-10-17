import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u12'); R = {}
print('== 一:类型别名 type 不创建新类型,newtype(元组结构体)才创建')
r = tryit('u12a', '''
    type Meters = f64;
    type Seconds = f64;
    fn speed(d: Meters, t: Seconds) -> f64 { d / t }
    fn main() {
        let m: Meters = 100.0; let s: Seconds = 9.58;
        println!("正确的顺序  speed(m, s) = {:.2}", speed(m, s));
        println!("参数写反了 speed(s, m) = {:.4}(编译器没有报任何错误)", speed(s, m));
    }
''', quiet_src=False)
r = tryit('u12b', '''
    struct Meters(f64);
    struct Seconds(f64);
    fn speed(d: Meters, t: Seconds) -> f64 { d.0 / t.0 }
    fn main() {
        let m = Meters(100.0); let s = Seconds(9.58);
        println!("{:.2}", speed(s, m));
    }
''', maxlines=30); R['e_swap'] = r['diag'].split('\n')[0]
print()
print('== 二:newtype 是零成本的:大小相同,生成的机器码相同')
r = tryit('u12c', '''
    use std::mem::size_of;
    struct Meters(f64);
    fn main() { println!("size_of::<f64>() = {},size_of::<Meters>() = {}", size_of::<f64>(), size_of::<Meters>()); }
''', quiet_src=True, flags=('-A', 'dead_code'))
code = '''
    pub struct Meters(pub f64);
    #[unsafe(no_mangle)] pub fn add_raw(a: f64, b: f64) -> f64 { a + b }
    #[unsafe(no_mangle)] pub fn add_new(a: Meters, b: Meters) -> Meters { Meters(a.0 + b.0) }
'''
a1, txt = asm_of('u12d', code, 'add_raw'); a2, _ = asm_of('u12d', code, 'add_new'); al = re.search(r'^(_add_(?:raw|new)) = (\S+)', txt, re.M)
body = a1 or a2
print('  两个函数共同的机器码:', ' ; '.join(body))
print('  汇编里的别名行:' + (f'`{al.group(1)} = {al.group(2)}`(LLVM 发现两个函数完全相同,把其中一个合并成另一个的别名)' if al else '(没有,两个函数各有函数体)')); R['same'] = bool(al) or a1 == a2; R['asm'] = body
print()
print('== 三:孤儿规则:不能为外部类型实现外部 trait;newtype 绕过它')
r = tryit('u12e', '''
    use std::fmt;
    impl fmt::Display for Vec<String> {
        fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "[{}]", self.join(", ")) }
    }
    fn main() {}
''', maxlines=24); R['e_orphan'] = r['diag'].split('\n')[0]
r = tryit('u12f', '''
    use std::fmt;
    struct Wrapper(Vec<String>);
    impl fmt::Display for Wrapper {
        fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "[{}]", self.0.join(", ")) }
    }
    fn main() {
        let w = Wrapper(vec!["hello".to_string(), "world".to_string()]);
        println!("w = {w}");
    }
''', quiet_src=False)
print()
print('== 四:newtype 默认没有内部类型的方法;实现 Deref 可以转发')
r = tryit('u12g', '''
    struct Names(Vec<String>);
    fn main() {
        let n = Names(vec!["a".into()]);
        println!("{}", n.len());
    }
''', maxlines=20); R['e_len'] = r['diag'].split('\n')[0]
r = tryit('u12h', '''
    use std::ops::Deref;
    struct Names(Vec<String>);
    impl Deref for Names { type Target = Vec<String>; fn deref(&self) -> &Vec<String> { &self.0 } }
    fn main() {
        let n = Names(vec!["a".into(), "b".into()]);
        println!("len = {},first = {:?},iter 拼接 = {}", n.len(), n.first(), n.iter().cloned().collect::<Vec<_>>().join("+"));
    }
''', quiet_src=False)
save('u12', R)
