import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u17'); R = {}
print('== 一:Copy 类型:赋值后两个变量都能用')
r = tryit('u17a', '''
    fn main() {
        let a = 5;
        let b = a;
        println!("a = {a}, b = {b}");
        let p = (1, 2.5);
        let q = p;
        println!("p = {:?}, q = {:?}", p, q);
    }
''', quiet_src=False)
print()
print('== 二:哪些类型是 Copy?对每个类型编译一次 fn needs_copy<T: Copy>() 来判断')
types = ['i32', 'f64', 'bool', 'char', '()', '&i32', '&mut i32', '(i32, i32)', '(i32, String)', '[i32; 3]', '[String; 1]', 'String', 'Vec<i32>', 'Box<i32>', 'Option<i32>', 'Option<String>', 'std::rc::Rc<i32>', 'fn(i32) -> i32', 'std::cell::Cell<i32>', '&str', 'std::ops::Range<i32>']
rows = []
print(f'  {"类型":<22}{"是 Copy 吗":<10}')
for i, t in enumerate(types):
    ok, diag, _, _ = rustc(f'u17t{i}', f'fn needs_copy<T: Copy>() {{}}\nfn main() {{ needs_copy::<{t}>(); }}\n', crate_type='bin')
    rows.append((t, ok)); print(f'  {t:<22}{"是" if ok else "否":<10}')
R['rows'] = rows
print()
print('== 三:#[derive(Copy)] 必须同时 derive(Clone);Copy 与 Drop 互斥')
r = tryit('u17b', '''
    #[derive(Copy)]
    struct P { x: i32 }
    fn main() {}
''', maxlines=18); R['e_clone'] = r['diag'].split('\n')[0]
r = tryit('u17c', '''
    #[derive(Clone, Copy)]
    struct P { x: i32 }
    impl Drop for P { fn drop(&mut self) {} }
    fn main() {}
''', maxlines=18); R['e_drop'] = r['diag'].split('\n')[0]
print()
print('== 四:Copy 就是按位复制:一个大数组的赋值是一次 memcpy,成本随大小增长')
r = tryit('u17d', '''
    use std::hint::black_box;
    use std::time::Instant;
    fn main() {
        for &n in &[16usize, 4096, 1 << 20] {
            macro_rules! bench { ($N:expr) => {{
                let a = black_box([7u8; $N]);
                let t = Instant::now();
                let mut acc = 0u64;
                for _ in 0..2000 { let b = black_box(a); acc += b[0] as u64; }
                black_box(acc);
                t.elapsed().as_nanos() as f64 / 2000.0
            }} }
            let ns = match n { 16 => bench!(16), 4096 => bench!(4096), _ => bench!(1048576) };
            println!("[u8; {:>7}] 每次赋值(拷贝)约 {:>9.0} ns", n, ns);
        }
    }
''', release=True, quiet_src=False)
R['bench'] = r['out']
save('u17', R)
