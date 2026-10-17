import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u111'); R = {}
def instrs(b): return [l.split()[0] for l in ([re.sub(r'\s+', ' ', x.strip()) for x in b]) if l and not l.startswith(('.', 'L', ';')) and not l.endswith(':') for l in [l]]
def norm(b): return [re.sub(r'\bLBB\d+_\d+\b', 'L', re.sub(r'\s+', ' ', l.strip())) for l in b if l.strip() and not l.strip().startswith(('.', ';'))]
print('== 一:抽象 vs 手写:几组「高层写法」与「手写底层写法」,-O 下汇编是否逐行相同(规范化标签后)')
cases = {
 'Newtype 包装': ('pub struct Meters(pub f64); #[unsafe(no_mangle)] pub fn a(x: Meters, y: Meters) -> Meters { Meters(x.0 + y.0) }', '#[unsafe(no_mangle)] pub fn a(x: f64, y: f64) -> f64 { x + y }'),
 'Option<&T> vs 裸指针判空': ('#[unsafe(no_mangle)] pub fn a(x: Option<&u32>) -> u32 { match x { Some(v) => *v, None => 0 } }', '#[unsafe(no_mangle)] pub unsafe fn a(x: *const u32) -> u32 { if x.is_null() { 0 } else { unsafe { *x } } }'),
 'iter().sum() vs for 循环': ('#[unsafe(no_mangle)] pub fn a(v: &[u32]) -> u32 { v.iter().sum() }', '#[unsafe(no_mangle)] pub fn a(v: &[u32]) -> u32 { let mut s = 0u32; for x in v { s += *x; } s }'),
 'map().sum() vs 手写累加': ('#[unsafe(no_mangle)] pub fn a(v: &[u32]) -> u32 { v.iter().map(|x| x * 2).sum() }', '#[unsafe(no_mangle)] pub fn a(v: &[u32]) -> u32 { let mut s = 0u32; let mut i = 0; while i < v.len() { s += v[i] * 2; i += 1; } s }'),
 '泛型 max<T> vs 具体类型': ('fn mx<T: PartialOrd>(a: T, b: T) -> T { if a > b { a } else { b } } #[unsafe(no_mangle)] pub fn a(x: i32, y: i32) -> i32 { mx(x, y) }', '#[unsafe(no_mangle)] pub fn a(x: i32, y: i32) -> i32 { if x > y { x } else { y } }'),
 '闭包调用 vs 直接计算': ('#[unsafe(no_mangle)] pub fn a(x: u32) -> u32 { let k = 5; let f = |y: u32| y * k + 1; f(x) }', '#[unsafe(no_mangle)] pub fn a(x: u32) -> u32 { x * 5 + 1 }'),
 '&dyn Fn 调用 vs fn 指针调用': ('#[unsafe(no_mangle)] pub fn a(f: &dyn Fn(u32) -> u32, x: u32) -> u32 { f(x) }', '#[unsafe(no_mangle)] pub fn a(f: fn(u32) -> u32, x: u32) -> u32 { f(x) }'),
}
res = {}
for name, (hi, lo) in cases.items():
    b1, _ = asm_of('u111h', hi, 'a'); b2, _ = asm_of('u111l', lo, 'a')
    n1, n2 = norm(b1), norm(b2); same = n1 == n2
    c1 = len([l for l in n1 if not l.endswith(':')]); c2 = len([l for l in n2 if not l.endswith(':')])
    res[name] = [same, c1, c2]; print(f'  {name:<28} 高层 {c1:>3} 条指令 / 手写 {c2:>3} 条指令  逐行相同: {"是" if same else "否"}')
R['asm'] = res
print()
print('== 二:不是所有抽象都零开销:边界检查、动态分发、Vec 的间接层 —— 同一件事不同写法的指令数')
cases2 = {
 '下标访问 v[i](有边界检查)': ('#[unsafe(no_mangle)] pub fn a(v: &[u32], i: usize) -> u32 { v[i] }', '#[unsafe(no_mangle)] pub fn a(v: &[u32], i: usize) -> u32 { unsafe { *v.get_unchecked(i) } }'),
 'checked_add vs 回绕加': ('#[unsafe(no_mangle)] pub fn a(x: u32, y: u32) -> Option<u32> { x.checked_add(y) }', '#[unsafe(no_mangle)] pub fn a(x: u32, y: u32) -> u32 { x.wrapping_add(y) }'),
 'Rc 克隆 vs 复制 u32': ('use std::rc::Rc; #[unsafe(no_mangle)] pub fn a(x: &Rc<u32>) -> Rc<u32> { x.clone() }', '#[unsafe(no_mangle)] pub fn a(x: &u32) -> u32 { *x }'),
}
res2 = {}
for name, (hi, lo) in cases2.items():
    b1, _ = asm_of('u111h', hi, 'a'); b2, _ = asm_of('u111l', lo, 'a')
    n1, n2 = norm(b1), norm(b2); c1 = len([l for l in n1 if not l.endswith(':')]); c2 = len([l for l in n2 if not l.endswith(':')])
    res2[name] = [c1, c2]; print(f'  {name:<28} 带安全检查/抽象的 {c1:>3} 条 / 无检查的 {c2:>3} 条')
R['asm2'] = res2
print()
print('== 三:零开销在 debug 构建里并不成立:同样的 Newtype + 迭代器求和,debug 与 release 的耗时')
r = tryit('u111c', '''
    use std::{hint::black_box, time::Instant};
    #[derive(Clone, Copy)] struct Meters(f64);
    impl std::ops::Add for Meters { type Output = Meters; fn add(self, o: Meters) -> Meters { Meters(self.0 + o.0) } }
    fn main() {
        let v: Vec<Meters> = (0..5_000_000).map(|i| Meters(i as f64)).collect(); let raw: Vec<f64> = (0..5_000_000).map(|i| i as f64).collect();
        let t = Instant::now(); let s = black_box(&v).iter().fold(Meters(0.0), |a, b| a + *b); let ta = t.elapsed().as_secs_f64() * 1e3;
        let t = Instant::now(); let mut r = 0.0; for x in black_box(&raw) { r += *x; } let tb = t.elapsed().as_secs_f64() * 1e3;
        println!("Newtype + 迭代器 fold: {:>8.2} ms   裸 f64 + for 循环: {:>8.2} ms   结果相同: {}", ta, tb, s.0 == r);
    }
''', quiet_src=True, show_run=False)
for rel in (False, True):
    r2 = tryit('u111c', r['src'] if 'src' in r else '', quiet_src=True, release=rel, show_run=False) if False else None
import textwrap as _tw
code3 = open(str(RS / 'src' / 'u111c.rs')).read()
for rel in (False, True):
    ok, d, binp, _ = rustc('u111c', code3, release=rel); rc, so, se, _ = run(binp); print(f'  {"release" if rel else "debug  "}: {so.strip()}'); R['dr_' + ('rel' if rel else 'dbg')] = so.strip()
save('u111', R)
