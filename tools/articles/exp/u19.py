import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u19'); R = {}
print('== 一:&T 只读借用,&mut T 可写借用;通过 & 修改会被拒绝')
r = tryit('u19a', '''
    fn add_one(n: &mut i32) { *n += 1; }
    fn read(n: &i32) -> i32 { *n * 2 }
    fn main() {
        let mut x = 10;
        println!("read(&x) = {}", read(&x));
        add_one(&mut x);
        println!("add_one 之后 x = {x}");
    }
''', quiet_src=False)
r = tryit('u19b', '''
    fn bad(n: &i32) { *n += 1; }
    fn main() { let mut x = 1; bad(&x); }
''', maxlines=22); R['e_ref_mut'] = r['diag'].split('\n')[0]
print()
print('== 二:同一时刻:要么多个 &T,要么一个 &mut T')
r = tryit('u19c', '''
    fn main() {
        let mut s = String::from("hi");
        let a = &s;
        let b = &mut s;
        b.push('!');
        println!("{a} {b}");
    }
''', maxlines=26); R['e_mix'] = r['diag'].split('\n')[0]
r = tryit('u19d', '''
    fn main() {
        let mut s = String::from("hi");
        let a = &mut s;
        let b = &mut s;
        a.push('1'); b.push('2');
        println!("{s}");
    }
''', maxlines=26); R['e_two_mut'] = r['diag'].split('\n')[0]
print()
print('== 三:借用的「生命周期」到最后一次使用为止:最后一次用完之后可以再借')
r = tryit('u19e', '''
    fn main() {
        let mut s = String::from("hi");
        let a = &s;
        println!("a = {a}");        // a 的最后一次使用
        let b = &mut s;             // 此刻 a 已经不再使用,所以允许
        b.push('!');
        println!("b = {b}");
    }
''', quiet_src=False)
print()
print('== 四:函数参数的重借用(reborrow):把 &mut 传给函数不会「用掉」它')
r = tryit('u19f', '''
    fn inc(n: &mut i32) { *n += 1; }
    fn main() {
        let mut x = 0;
        let r = &mut x;
        inc(r);            // 隐式重借用:r 之后仍然可用
        inc(r);
        *r += 10;
        println!("x = {}", x);
    }
''', quiet_src=False)
r = tryit('u19g', '''
    fn consume(r: &mut i32) { *r += 1; }
    fn main() {
        let mut x = 0;
        let r = &mut x;
        let moved = r;     // 这里是移动,不是重借用
        consume(moved);
        consume(r);
    }
''', maxlines=24); R['e_moved_ref'] = r['diag'].split('\n')[0]
save('u19', R)
