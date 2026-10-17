import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u38'); R = {}
print('== 一:参数位置的 impl Trait 就是匿名的泛型参数:机器码与显式泛型版本相同')
code = '''
    use std::fmt::Display;
    #[inline(never)] pub fn len_impl(x: impl Display) -> usize { x.to_string().len() }
    #[inline(never)] pub fn len_generic<T: Display>(x: T) -> usize { x.to_string().len() }
    #[unsafe(no_mangle)] pub fn via_impl(n: i32) -> usize { len_impl(n) }
    #[unsafe(no_mangle)] pub fn via_generic(n: i32) -> usize { len_generic(n) }
'''
a1, txt = asm_of('u38b', code, 'via_impl'); a2, _ = asm_of('u38b', code, 'via_generic'); al = re.search(r'^(_via_(?:impl|generic)) = (\S+)', txt, re.M)
print('  via_impl(调用 len_impl::<i32>)与 via_generic(调用 len_generic::<i32>)的汇编:')
print('    ', ' ; '.join(a1 or a2)[:200]); print('    别名行:', f'`{al.group(1)} = {al.group(2)}`(两个包装函数被合并,说明它们调用的实例化函数一样)' if al else '(无,两个函数各有函数体:' + ('相同' if a1 == a2 else '不同') + ')'); R['same'] = bool(al) or a1 == a2
print()
print('== 二:返回位置的 impl Trait:隐藏具体类型,但整个函数只能返回同一个具体类型')
r = tryit('u38c', '''
    fn evens(limit: u32) -> impl Iterator<Item = u32> { (0..limit).filter(|n| n % 2 == 0) }
    fn adder(k: i32) -> impl Fn(i32) -> i32 { move |x| x + k }
    fn main() {
        println!("{:?}", evens(10).collect::<Vec<_>>());
        let f = adder(5); println!("adder(5)(3) = {}", f(3));
        println!("evens 返回的具体类型名:{}", std::any::type_name_of_val(&evens(1)));
    }
''', quiet_src=False)
r = tryit('u38d', '''
    use std::fmt::Display;
    fn pick(flag: bool) -> impl Display { if flag { 1 } else { "one" } }
    fn main() { println!("{}", pick(true)); }
''', maxlines=28); R['e308'] = r['diag'].split('\n')[0]
r = tryit('u38e', '''
    use std::fmt::Display;
    fn pick(flag: bool) -> Box<dyn Display> { if flag { Box::new(1) } else { Box::new("one") } }
    fn main() { println!("{} {}", pick(true), pick(false)); }
''', quiet_src=False)
print()
print('== 三:返回的 impl Trait 里藏着对参数的借用:edition 2021 要显式写 + \'a,edition 2024 默认捕获')
code = '''
    fn doubled(v: &Vec<u32>) -> impl Iterator<Item = u32> { v.iter().map(|x| x * 2) }
    fn main() { let v = vec![1, 2, 3]; println!("{:?}", doubled(&v).collect::<Vec<_>>()); }
'''
for ed in ('2021', '2024'):
    print(f'  --edition {ed}:'); r = tryit(f'u38f{ed}', code, edition=ed, quiet_src=(ed == '2024'), maxlines=22); R['ed' + ed] = r['ok']
r = tryit('u38h', '''
    fn doubled<'a>(v: &'a Vec<u32>) -> impl Iterator<Item = u32> + 'a { v.iter().map(|x| x * 2) }
    fn main() { let v = vec![1, 2, 3]; println!("{:?}", doubled(&v).collect::<Vec<_>>()); }
''', edition='2021', quiet_src=False); print('  (上面这段是 2021 里的写法:显式加 + \'a 就可以了)')
print()
print('== 四:参数位置的 impl Trait 不能再用 turbofish 指定它')
r = tryit('u38g', '''
    fn f(x: impl std::fmt::Display) -> String { x.to_string() }
    fn main() { println!("{}", f::<i32>(5)); }
''', maxlines=22); R['e_turbofish'] = r['diag'].split('\n')[0]
save('u38', R)
