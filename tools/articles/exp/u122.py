import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u122'); R = {}
print('== 一:调用 libc:extern "C" 声明 + unsafe 调用 strlen / abs / getpid;字符串要用 CString(以 \\0 结尾)')
r = tryit('u122a', '''
    use std::ffi::{c_char, c_int, CString, CStr};
    unsafe extern "C" { fn strlen(s: *const c_char) -> usize; fn abs(x: c_int) -> c_int; fn getpid() -> c_int; fn toupper(c: c_int) -> c_int; }
    fn main() {
        let s = CString::new("héllo").unwrap();
        unsafe {
            println!("  strlen(\\"héllo\\") = {}(C 数的是字节:é 占 2 字节)  Rust 的 len() = {}", strlen(s.as_ptr()), "héllo".len());
            println!("  abs(-42) = {}  toupper('a') = {}", abs(-42), toupper('a' as c_int) as u8 as char);
            println!("  getpid() == std::process::id(): {}", getpid() as u32 == std::process::id());
        }
        let bad = CString::new("a\\0b"); println!("  CString::new(\\"a\\\\0b\\") = {:?}(字符串中间不能有 \\\\0)", bad.map(|_| "ok").map_err(|e| e.to_string()));
        let c: &CStr = c"字面量"; println!("  c\\"…\\" 字面量(以 \\\\0 结尾的 &CStr):{:?} 字节数 {}", c, c.to_bytes().len());
    }
''', quiet_src=True); R['libc'] = r['out']
print()
print('== 二:回调:把 Rust 函数作为 extern "C" 函数指针交给 libc 的 qsort')
r = tryit('u122b', '''
    use std::ffi::c_void;
    unsafe extern "C" { fn qsort(base: *mut c_void, n: usize, size: usize, cmp: extern "C" fn(*const c_void, *const c_void) -> i32); }
    static CALLS: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
    extern "C" fn cmp_desc(a: *const c_void, b: *const c_void) -> i32 { CALLS.fetch_add(1, std::sync::atomic::Ordering::Relaxed); let (a, b) = unsafe { (*(a as *const i32), *(b as *const i32)) }; b.cmp(&a) as i32 }
    fn main() {
        let mut v = [5, 2, 9, 1, 7, 3, 8];
        unsafe { qsort(v.as_mut_ptr() as *mut c_void, v.len(), std::mem::size_of::<i32>(), cmp_desc); }
        println!("  qsort 用 Rust 写的 extern \\"C\\" 比较函数降序排序:{:?};回调被 C 调用了 {} 次", v, CALLS.load(std::sync::atomic::Ordering::Relaxed));
    }
''', quiet_src=True); R['qsort'] = r['out']
print()
print('== 三:链接自己的 C 库:用 clang 编译一个含结构体、字符串、数组的 C 文件成静态库,在 Rust 里按 repr(C) 声明并调用')
cdir = RS / 'cproj'; shutil.rmtree(cdir, ignore_errors=True); cdir.mkdir(parents=True)
(cdir / 'vec2.c').write_text('''
#include <stdint.h>
#include <string.h>
typedef struct { double x; double y; } Vec2;
Vec2 vec2_add(Vec2 a, Vec2 b) { Vec2 r = { a.x + b.x, a.y + b.y }; return r; }
double vec2_len2(const Vec2 *v) { return v->x * v->x + v->y * v->y; }
void vec2_scale_all(Vec2 *vs, size_t n, double k) { for (size_t i = 0; i < n; i++) { vs[i].x *= k; vs[i].y *= k; } }
size_t fill_greeting(char *buf, size_t cap) { const char *s = "hello from C"; size_t n = strlen(s); if (n + 1 > cap) return 0; memcpy(buf, s, n + 1); return n; }
int32_t sum_i32(const int32_t *p, size_t n) { int32_t s = 0; for (size_t i = 0; i < n; i++) s += p[i]; return s; }
''')
rc, o, e = sh(['clang', '-c', '-O2', '-o', str(cdir / 'vec2.o'), str(cdir / 'vec2.c')]); rc2, o2, e2 = sh(['ar', 'rcs', str(cdir / 'libvec2.a'), str(cdir / 'vec2.o')])
print(f'  clang -c vec2.c → vec2.o(退出码 {rc});ar rcs libvec2.a(退出码 {rc2})')
code = '''
    use std::ffi::{c_char, c_double};
    #[repr(C)] #[derive(Debug, Clone, Copy)] struct Vec2 { x: c_double, y: c_double }
    #[link(name = "vec2", kind = "static")]
    unsafe extern "C" {
        fn vec2_add(a: Vec2, b: Vec2) -> Vec2; fn vec2_len2(v: *const Vec2) -> c_double; fn vec2_scale_all(vs: *mut Vec2, n: usize, k: c_double);
        fn fill_greeting(buf: *mut c_char, cap: usize) -> usize; fn sum_i32(p: *const i32, n: usize) -> i32;
    }
    fn main() {
        unsafe {
            let r = vec2_add(Vec2 { x: 1.0, y: 2.0 }, Vec2 { x: 10.0, y: 20.0 }); println!("  vec2_add(按值传递、按值返回结构体) = {:?}", r);
            println!("  vec2_len2(&r)(按指针传递)= {}", vec2_len2(&r));
            let mut vs = [Vec2 { x: 1.0, y: 1.0 }, Vec2 { x: 2.0, y: 3.0 }]; vec2_scale_all(vs.as_mut_ptr(), vs.len(), 10.0); println!("  vec2_scale_all 原地修改 Rust 的数组:{:?}", vs);
            let mut buf = [0 as c_char; 32]; let n = fill_greeting(buf.as_mut_ptr(), buf.len()); let s = std::ffi::CStr::from_ptr(buf.as_ptr()).to_str().unwrap(); println!("  fill_greeting 往 Rust 的缓冲区写了 {} 字节:{:?}", n, s);
            let mut tiny = [0 as c_char; 4]; println!("  缓冲区太小(4 字节):C 返回 {}(约定:0 表示放不下)", fill_greeting(tiny.as_mut_ptr(), tiny.len()));
            let a = [1, 2, 3, 4, 5]; println!("  sum_i32(Rust 数组) = {}", sum_i32(a.as_ptr(), a.len()));
        }
    }
'''
f = src_file('u122c', code); out = RS / 'bin' / 'u122c'
rc, o, e = sh(['rustc', '--edition=2024', '--color=never', str(f), '-o', str(out), '-L', str(cdir)]); print('  rustc 链接静态库:', '成功' if rc == 0 else (o + e)[:600])
rc, so, se, _ = run(out); print('\n'.join('  ' + l for l in so.rstrip().splitlines())); R['clib'] = so.rstrip()
print()
print('== 四:声明写错 rustc 不会报错:把 sum_i32 错误地声明成返回 f64 或参数少一个;结果是垃圾或崩溃,编译器完全没有提示')
def trial(name, decl, call):
    code = f'''
    #[link(name = "vec2", kind = "static")]
    unsafe extern "C" {{ {decl} }}
    fn main() {{ let a = [1i32, 2, 3]; {call} }}
'''
    f = src_file(name, code); out = RS / 'bin' / name; rc, o, e = sh(['rustc', '--edition=2024', '--color=never', str(f), '-o', str(out), '-L', str(cdir)])
    if rc != 0: return '编译失败:' + (o + e)[:200]
    rc2, so, se, _ = run(out); warn = '没有任何警告' if not (o + e).strip() else '有编译器输出'; txt = so.strip(); txt = txt if len(txt) < 40 else txt[:12] + '…(很小的数,共 %d 个字符)' % len(txt)
    return f'编译通过({warn});运行退出码 {rc2},输出 {txt!r}'
res = {}
res['right'] = trial('u122d', 'fn sum_i32(p: *const i32, n: usize) -> i32;', 'println!("{}", unsafe { sum_i32(a.as_ptr(), a.len()) });')
res['ret_f64'] = trial('u122e', 'fn sum_i32(p: *const i32, n: usize) -> f64;', 'println!("{}", unsafe { sum_i32(a.as_ptr(), a.len()) });')
res['no_n'] = trial('u122f', 'fn sum_i32(p: *const i32) -> i32;', 'println!("{}", unsafe { sum_i32(a.as_ptr()) });')
res['n_wrong_ptr'] = trial('u122g', 'fn sum_i32(p: *const i32, n: usize) -> i32;', 'println!("{}", unsafe { sum_i32(a.as_ptr(), 1000) });')
for k, v in res.items(): print(f'  {k:<12} {v}')
R['decl'] = res
print('  编译器没有机会核对 C 头文件:声明与定义是否一致完全靠人;bindgen / cbindgen 就是用来自动生成声明的(本文没有使用)')
save('u122', R)
