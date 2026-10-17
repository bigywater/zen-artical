import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u83'); R = {}
def run_stderr(name, code, release=False):
    r = tryit(name, code, quiet_src=True, release=release, show_run=False)
    rc, o, e, _ = run(r['bin']); return rc, o.strip(), [l for l in e.splitlines() if l.strip()]
print('== 一:dbg! 打印到 stderr,带文件名、行号、表达式文本与值,并把值原样返回')
code = '''
    fn main() {
        let a = 2;
        let b = dbg!(a * 3) + 1;
        println!("b = {}", b);
        let v = vec![1, 2, 3];
        dbg!(&v);
        dbg!();
        let (x, y) = dbg!(10, "s");
        println!("x = {} y = {}", x, y);
    }
'''
print('  源码:'); print('\n'.join('    ' + l for l in show(code).splitlines()))
rc, o, e = run_stderr('u83a', code)
print(f'  stdout: {o!r}'); print('  stderr:'); print('\n'.join('    ' + l for l in e)); R['basic'] = {'out': o, 'err': e}
print()
print('== 二:dbg!(v) 会拿走所有权(返回值丢掉就等于 drop);要继续使用必须 dbg!(&v) 或接住返回值')
r = tryit('u83b', '''
    fn main() {
        let v = vec![1, 2, 3];
        dbg!(v);
        println!("{:?}", v);
    }
''', maxlines=30); R['e0382'] = r['diag']
print()
print('== 三:release 构建里 dbg! 仍然输出(它不是 debug_assert):与 debug 构建输出对比')
code = 'fn main() { let x = dbg!(1 + 1); println!("{}", x); }'
for rel in (False, True):
    rc, o, e = run_stderr('u83c', code, release=rel); print(f'  {"release" if rel else "debug  "}: stdout={o!r} stderr 行数={len(e)}  {e[0] if e else ""}'); R['rel_' + str(rel)] = [o, len(e)]
print()
print('== 四:编译器展开 dbg!:一个 match 把值绑定到 tmp,eprintln! 之后返回 tmp(只求值一次)')
code = '''
    pub fn f(a: i32) -> i32 { dbg!(a + 1) }
'''
f = src_file('u83d', code); rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '-Z', 'unpretty=expanded', str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
L = o.splitlines(); i = [k for k, l in enumerate(L) if l.startswith('pub fn f')][0]
print('\n'.join('  ' + l for l in L[i:i + 14])); R['exp'] = L[i:i + 14]
r = tryit('u83e', '''
    use std::cell::Cell;
    fn main() {
        let n = Cell::new(0);
        let v = dbg!({ n.set(n.get() + 1); n.get() });
        println!("表达式被求值 {} 次,值 = {}", n.get(), v);
    }
''', quiet_src=True); R['once'] = r['out']
print()
print('== 五:{:#?} 美化输出:对结构体用 dbg! 自动多行缩进;与 println!("{:?}") 对比')
code = '''
    #[derive(Debug)] struct P { name: String, tags: Vec<u8>, pos: (i32, i32) }
    fn main() { let p = P { name: "a".into(), tags: vec![1, 2], pos: (3, 4) }; dbg!(&p); println!("{:?}", p); }
'''
rc, o, e = run_stderr('u83f', code); print(f'  stdout: {o!r}'); print('  stderr:'); print('\n'.join('    ' + l for l in e)); R['pretty'] = {'out': o, 'err': e}
save('u83', R)
