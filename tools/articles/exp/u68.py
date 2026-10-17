import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u68'); R = {}
print('== 一:编译器真实展开的 HIR:一个最普通的 for 循环(-Z unpretty=hir,需要 RUSTC_BOOTSTRAP=1)')
code = '''
    pub fn total(v: &[i32]) -> i32 {
        let mut s = 0;
        for x in v { s += x; }
        s
    }
'''
f = src_file('u68a', code); rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '-Z', 'unpretty=hir', str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
body = o.strip()
print('  源码:'); print('\n'.join('    ' + l for l in show(code).splitlines()))
print('  -Z unpretty=hir 输出(去掉前面的 prelude 行):')
lines = [l for l in body.splitlines() if l.strip() and not l.startswith(('#![', 'extern crate', 'use ::std'))]
print('\n'.join('    ' + l for l in lines)); R['hir'] = lines
print()
print('== 二:手写展开的版本与 for 的行为一致(同一个输出),包括 break 与 continue')
r = tryit('u68b', '''
    fn main() {
        let v = vec![1, 2, 3, 4, 5, 6];
        let mut a = Vec::new();
        for x in &v { if x % 2 == 0 { continue; } if *x > 4 { break; } a.push(*x); }
        let mut b = Vec::new();
        match IntoIterator::into_iter(&v) {
            mut iter => loop {
                match Iterator::next(&mut iter) {
                    None => break,
                    Some(x) => { if x % 2 == 0 { continue; } if *x > 4 { break; } b.push(*x); }
                }
            }
        }
        println!("for: {:?}   手写展开: {:?}   相同: {}", a, b, a == b);
    }
''', quiet_src=False); R['manual'] = r['out']
print()
print('== 三:for 的各个环节:into_iter 只调用一次,next 在每轮开始调用一次,最后一次返回 None(计数)')
r = tryit('u68c', '''
    struct Tracked(u32);
    impl Iterator for Tracked { type Item = u32; fn next(&mut self) -> Option<u32> { println!("  next() 被调用,n = {}", self.0); if self.0 < 3 { self.0 += 1; Some(self.0) } else { None } } }
    struct Src;
    impl IntoIterator for Src { type Item = u32; type IntoIter = Tracked; fn into_iter(self) -> Tracked { println!("  into_iter() 被调用"); Tracked(0) } }
    fn main() {
        for x in Src { println!("循环体 x = {}", x); }
        println!("循环结束");
    }
''', quiet_src=True); R['calls'] = r['out']
print()
print('== 四:遍历时修改容器会被借用检查拒绝;range 的上界只在进入循环时求值一次')
r = tryit('u68d', '''
    fn main() {
        let mut v = vec![1, 2, 3];
        for x in &v { if *x == 2 { v.push(4); } }
    }
''', maxlines=30); R['e0502'] = r['diag']
r = tryit('u68e', '''
    fn main() {
        let mut v = vec![1, 2, 3, 4];
        for i in 0..v.len() { if v[i] % 2 == 0 { v[i] *= 10; } }
        println!("下标写法可以改: {:?}", v);
        for x in v.iter_mut() { *x += 1; }
        println!("iter_mut 写法: {:?}", v);
        let n = 3; let mut c = 0; for _ in 0..n { c += 1; } println!("0..n 循环 {} 次", c);
        let mut m = 3; let mut c2 = 0; for _ in 0..m { m = 100; c2 += 1; } let _ = m; println!("循环体里把 m 改成 100 之后,仍然只循环 {} 次", c2);
    }
''', quiet_src=True); R['mut'] = r['out']
save('u68', R)
