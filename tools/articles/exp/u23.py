import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u23'); R = {}
print('== 一:返回引用、但有两个输入引用时,编译器不知道返回值借的是哪一个')
r = tryit('u23a', '''
    fn longest(x: &str, y: &str) -> &str { if x.len() > y.len() { x } else { y } }
    fn main() { println!("{}", longest("abc", "de")); }
''', maxlines=26); R['e106'] = r['diag'].split('\n')[0]
r = tryit('u23b', '''
    fn longest<'a>(x: &'a str, y: &'a str) -> &'a str { if x.len() > y.len() { x } else { y } }
    fn main() { println!("{}", longest("abc", "de")); }
''', quiet_src=False)
print()
print('== 二:标注不改变任何值活多久,只是声明「返回值的有效期不超过两个输入中较短的那个」')
r = tryit('u23c', '''
    fn longest<'a>(x: &'a str, y: &'a str) -> &'a str { if x.len() > y.len() { x } else { y } }
    fn main() {
        let a = String::from("long string");
        let result;
        {
            let b = String::from("xyz");
            result = longest(a.as_str(), b.as_str());
        }
        println!("{}", result);
    }
''', maxlines=26); R['e597'] = r['diag'].split('\n')[0]
r = tryit('u23d', '''
    fn longest<'a>(x: &'a str, y: &'a str) -> &'a str { if x.len() > y.len() { x } else { y } }
    fn main() {
        let a = String::from("long string");
        {
            let b = String::from("xyz");
            let result = longest(a.as_str(), b.as_str());
            println!("在内层使用 result:{}", result);
        }
    }
''', quiet_src=False)
print()
print('== 三:不同的生命周期参数:返回值只借自第一个参数,却返回了第二个')
r = tryit('u23e', '''
    fn first<'a, 'b>(x: &'a str, y: &'b str) -> &'a str { let _ = x; y }
    fn main() { println!("{}", first("a", "b")); }
''', maxlines=26); R['e_lt'] = r['diag'].split('\n')[0]
r = tryit('u23f', '''
    fn first<'a, 'b>(x: &'a str, _y: &'b str) -> &'a str { x }
    fn main() {
        let a = String::from("long");
        let r;
        { let b = String::from("short"); r = first(&a, &b); }   // 返回值只与 a 相关,b 先死也没关系
        println!("{r}");
    }
''', quiet_src=False)
print()
print('== 四:生命周期在运行时不存在:加不加标注,生成的机器码完全一样')
code = '''
    #[unsafe(no_mangle)] pub fn elided(x: &(u32, u32)) -> &u32 { &x.1 }
    #[unsafe(no_mangle)] pub fn explicit<'a>(x: &'a (u32, u32)) -> &'a u32 { &x.1 }
'''
a1, txt = asm_of('u23g', code, 'elided'); a2, _ = asm_of('u23g', code, 'explicit'); al = re.search(r'^(_(?:elided|explicit)) = (\S+)', txt, re.M)
print('  elided 与 explicit 共同的汇编:', ' ; '.join(a1 or a2)); print('  别名行:', f'`{al.group(1)} = {al.group(2)}`(LLVM 合并了两个相同的函数)' if al else '(无)'); R['same'] = bool(al) or a1 == a2
print(f'  size_of::<&u32>() 在有无生命周期标注时都是 8 字节;生命周期只在编译期存在')
save('u23', R)
