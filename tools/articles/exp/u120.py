import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u120'); R = {}
print('== 一:unsafe 只多出五种能力:解引用裸指针、调用 unsafe 函数、访问/修改 static mut、实现 unsafe trait、访问 union 字段。没有 unsafe 时逐个报 E0133')
cases = [
 ('解引用裸指针', 'fn main() { let x = 5; let p = &x as *const i32; println!("{}", *p); }'),
 ('调用 unsafe 函数', 'unsafe fn danger() {} fn main() { danger(); }'),
 ('访问 static mut', 'static mut N: u32 = 0; fn main() { N += 1; }'),
 ('访问 union 字段', 'union U { a: u32, b: f32 } fn main() { let u = U { a: 1 }; let _ = u.b; }'),
]
R['e0133'] = {}
for name, code in cases:
    ok, d, _, _ = rustc('u120a', code, flags=('--emit=metadata',), crate_type='bin')
    first = [l for l in d.splitlines() if l.startswith('error')][:1]; print(f'  【{name}】编译{"成功" if ok else "失败"}:{first}'); R['e0133'][name] = first
r = tryit('u120b', '''
    unsafe trait Zeroable {}
    struct S; impl Zeroable for S {}
    fn main() {}
''', maxlines=16); R['e0200'] = r['diag'].split('\\n')[:2]
print()
print('== 二:放进 unsafe { } 之后,这五种就都编译通过;unsafe 块只是「我保证这里满足前提条件」的声明')
r = tryit('u120c', '''
    static mut N: u32 = 0;
    union U { a: u32, b: f32 }
    unsafe fn read(p: *const i32) -> i32 { unsafe { *p } }
    unsafe trait Zeroable {} unsafe impl Zeroable for u32 {}
    fn main() {
        let x = 5; let p = &x as *const i32;
        unsafe {
            println!("解引用裸指针 = {}", *p);
            println!("调用 unsafe fn  = {}", read(p));
            N += 1; println!("static mut N    = {}", *(&raw const N));
            let u = U { a: 0x3f800000 }; println!("union 字段 b    = {}(把 u32 0x3f800000 当 f32 读)", u.b);
        }
        println!("unsafe impl Zeroable for u32:编译通过(实现 unsafe trait 本身也要写 unsafe impl)");
    }
''', quiet_src=True); R['ok'] = r['out']
print()
print('== 三:unsafe 不会关掉借用检查器:unsafe 块里违反借用规则照样报错')
r = tryit('u120d', '''
    fn main() { let mut v = vec![1]; let first = &v[0]; unsafe { v.push(2); } println!("{}", first); }
''', maxlines=24); R['e0502'] = r['diag']
print()
print('== 四:安全抽象:用 unsafe 实现一个安全的 split_at_mut,对外只暴露安全接口;越界参数被 assert 挡住')
r = tryit('u120e', '''
    fn my_split_at_mut(s: &mut [i32], mid: usize) -> (&mut [i32], &mut [i32]) {
        let len = s.len(); let p = s.as_mut_ptr();
        assert!(mid <= len, "mid 必须 <= 长度");            // 这个检查就是 unsafe 块成立的前提条件
        unsafe { (std::slice::from_raw_parts_mut(p, mid), std::slice::from_raw_parts_mut(p.add(mid), len - mid)) }
    }
    fn main() {
        let mut v = vec![1, 2, 3, 4, 5];
        let (a, b) = my_split_at_mut(&mut v, 2); a[0] = 10; b[0] = 30;
        println!("安全接口的结果:{:?}", v);
        let _ = my_split_at_mut(&mut v, 99);
    }
''', quiet_src=True); R['abs'] = {'rc': r['rc'], 'out': r['out'], 'err': [l for l in r['err'].splitlines() if l.strip() and 'note: run' not in l][:2]}
print()
print('== 五:#![forbid(unsafe_code)] 让整个 crate 不允许 unsafe;2024 edition 里 unsafe fn 内部也要显式写 unsafe 块')
r = tryit('u120f', '''
    #![forbid(unsafe_code)]
    fn main() { let x = 1; let p = &x as *const i32; let _ = unsafe { *p }; }
''', maxlines=18); R['forbid'] = r['diag'].split('\\n')[:3]
r = tryit('u120g', '''
    unsafe fn f(p: *const i32) -> i32 { *p }
    fn main() { let x = 1; println!("{}", unsafe { f(&x) }); }
''', maxlines=24); R['e_in_unsafe_fn'] = r['diag']
save('u120', R)
