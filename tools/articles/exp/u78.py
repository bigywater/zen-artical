import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u78'); R = {}
print('== 一:宏内部的局部变量不会与调用处的同名变量冲突')
r = tryit('u78a', '''
    macro_rules! swap { ($a:expr, $b:expr) => { let tmp = $a; $a = $b; $b = tmp; }; }
    fn main() {
        let mut x = 1; let mut y = 2; let tmp = 100;
        swap!(x, y);
        println!("x = {} y = {} tmp = {}(调用处的 tmp 没有被宏里的 tmp 覆盖)", x, y, tmp);
        let mut tmp2 = 5; let mut other = 6;
        swap!(tmp2, other);
        println!("tmp2 = {} other = {}", tmp2, other);
    }
''', quiet_src=False); R['tmp'] = r['out']
print()
print('== 二:编译器的 hygiene 打印:同名的 tmp 带有不同的语法上下文标记(-Z unpretty=expanded,hygiene)')
code = '''
    macro_rules! twice { ($e:expr) => {{ let v = $e; v + v }}; }
    pub fn f() -> i32 { let v = 10; twice!(v + 1) }
'''
f = src_file('u78b', code); rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '-Z', 'unpretty=expanded,hygiene', str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
lines = [l for l in o.splitlines() if l.strip() and 'fn f' in o and not l.startswith(('#![', 'extern crate', 'use std::prelude', '#[attr', '#[prelude'))]
print('  源码:'); print('\n'.join('    ' + l for l in show(code).splitlines()))
print('  展开(带 hygiene 标记 名字#上下文编号):')
L = o.splitlines(); i = [k for k, l in enumerate(L) if l.startswith('pub fn f')][0]
seg = L[i:i + 7] + [l for l in L if l.startswith('#4:') or 'expn2' in l and 'Macro' in l]
print('\n'.join('    ' + l for l in seg)); R['hyg'] = seg
print()
print('== 三:宏里引用调用处的局部变量(没有作为参数传入)会报错;传入的标识符则可以')
r = tryit('u78c', '''
    macro_rules! show_y { () => { println!("y = {}", y) }; }
    fn main() { let y = 5; show_y!(); }
''', maxlines=30); R['e_y'] = r['diag']
r = tryit('u78d', '''
    macro_rules! show { ($v:ident) => { println!("{} = {}", stringify!($v), $v) }; }
    macro_rules! decl { ($name:ident = $val:expr) => { let $name = $val; }; }
    macro_rules! decl_hidden { ($val:expr) => { let hidden = $val; }; }
    #[allow(unused_variables)] fn main() {
        let y = 5; show!(y);
        decl!(z = 9); println!("宏里 let 传入的名字 z 在调用处可见: z = {}", z);
        decl_hidden!(1);
    }
''', quiet_src=True); R['ok'] = r['out']
r = tryit('u78e', '''
    macro_rules! decl_hidden { ($val:expr) => { let hidden = $val; }; }
    fn main() { decl_hidden!(1); println!("{}", hidden); }
''', maxlines=30); R['e_hidden'] = r['diag']
print()
print('== 四:卫生只管局部变量与标签;函数、结构体等 item 不卫生,宏定义的 fn 在调用处可见')
r = tryit('u78f', '''
    macro_rules! def_helper { () => { fn helper() -> &'static str { "宏里定义的 helper" } }; }
    def_helper!();
    fn main() { println!("{}", helper()); }
''', quiet_src=True); R['item'] = r['out']
print()
print('== 五:标签(break \'label)也是卫生的')
r = tryit('u78g', '''
    macro_rules! find_first { ($v:expr, $p:expr) => {{ let mut r = None; 'outer: for x in $v { if $p(x) { r = Some(x); break 'outer; } } r }}; }
    fn main() {
        'outer: for i in 0..3 {
            let r = find_first!(vec![5, 8, 9], |x: i32| x % 2 == 0);
            println!("i = {} 宏里的 'outer 与调用处的 'outer 不冲突,找到 {:?}", i, r);
            if i == 1 { break 'outer; }
        }
    }
''', quiet_src=True); R['label'] = r['out']
save('u78', R)
