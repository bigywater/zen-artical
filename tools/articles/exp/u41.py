import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u41'); R = {}
print('== 一:四种调用方式的每次调用耗时(release,100 万个对象,每种遍历 20 次取中位数)')
r = tryit('u41a', '''
    use std::hint::black_box;
    use std::time::Instant;
    trait Shape { fn area(&self) -> f64; }
    struct Circle(f64); struct Rect(f64, f64); struct Tri(f64, f64);
    impl Shape for Circle { #[inline] fn area(&self) -> f64 { 3.14159 * self.0 * self.0 } }
    impl Shape for Rect { #[inline] fn area(&self) -> f64 { self.0 * self.1 } }
    impl Shape for Tri { #[inline] fn area(&self) -> f64 { 0.5 * self.0 * self.1 } }
    enum AnyShape { C(Circle), R(Rect), T(Tri) }
    impl AnyShape { #[inline] fn area(&self) -> f64 { match self { AnyShape::C(c) => c.area(), AnyShape::R(r) => r.area(), AnyShape::T(t) => t.area() } } }
    fn median(mut v: Vec<f64>) -> f64 { v.sort_by(|a, b| a.partial_cmp(b).unwrap()); v[v.len() / 2] }
    fn bench<F: FnMut() -> f64>(n: usize, mut f: F) -> f64 {
        let mut ts = vec![]; let mut acc = 0.0;
        for _ in 0..20 { let t = Instant::now(); acc += f(); ts.push(t.elapsed().as_nanos() as f64 / n as f64); }
        black_box(acc); median(ts)
    }
    fn main() {
        const N: usize = 1_000_000;
        let stat: Vec<Circle> = (0..N).map(|i| Circle(i as f64 * 1e-6)).collect();
        let dyn_same: Vec<Box<dyn Shape>> = (0..N).map(|i| Box::new(Circle(i as f64 * 1e-6)) as Box<dyn Shape>).collect();
        let dyn_mixed: Vec<Box<dyn Shape>> = (0..N).map(|i| { let x = i as f64 * 1e-6; match i % 3 { 0 => Box::new(Circle(x)) as Box<dyn Shape>, 1 => Box::new(Rect(x, 2.0)), _ => Box::new(Tri(x, 3.0)) } }).collect();
        let dyn_rand: Vec<Box<dyn Shape>> = { let mut s = 12345u64; (0..N).map(|i| { s = s.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407); let x = i as f64 * 1e-6; match (s >> 33) % 3 { 0 => Box::new(Circle(x)) as Box<dyn Shape>, 1 => Box::new(Rect(x, 2.0)), _ => Box::new(Tri(x, 3.0)) } }).collect() };
        let en: Vec<AnyShape> = (0..N).map(|i| { let x = i as f64 * 1e-6; match i % 3 { 0 => AnyShape::C(Circle(x)), 1 => AnyShape::R(Rect(x, 2.0)), _ => AnyShape::T(Tri(x, 3.0)) } }).collect();
        let a = bench(N, || stat.iter().map(|s| s.area()).sum());
        let b = bench(N, || dyn_same.iter().map(|s| s.area()).sum());
        let c = bench(N, || dyn_mixed.iter().map(|s| s.area()).sum());
        let d = bench(N, || dyn_rand.iter().map(|s| s.area()).sum());
        let e = bench(N, || en.iter().map(|s| s.area()).sum());
        println!("泛型/静态分发 Vec<Circle>(可内联、可向量化)      每个对象 {:.2} ns", a);
        println!("动态分发 Vec<Box<dyn Shape>>,全是 Circle           每个对象 {:.2} ns", b);
        println!("动态分发,三种类型按 0,1,2,0,1,2 规律交替             每个对象 {:.2} ns", c);
        println!("动态分发,三种类型随机排列(分支预测失败)            每个对象 {:.2} ns", d);
        println!("enum 分发 Vec<AnyShape>(match,可内联)             每个对象 {:.2} ns", e);
    }
''', release=True, quiet_src=True); R['bench'] = r['out']
print()
print('== 二:为什么静态分发更快:调用能不能被内联(看汇编)')
code = '''
    pub trait Shape { fn area(&self) -> f64; }
    pub struct Circle(pub f64);
    impl Shape for Circle { fn area(&self) -> f64 { 3.14159 * self.0 * self.0 } }
    #[unsafe(no_mangle)] pub fn static_call(c: &Circle) -> f64 { c.area() }
    #[unsafe(no_mangle)] pub fn dyn_call(s: &dyn Shape) -> f64 { s.area() }
'''
a1, _ = asm_of('u41b', code, 'static_call'); a2, _ = asm_of('u41b', code, 'dyn_call')
print('  static_call(&Circle) 的汇编:', ' ; '.join(a1)); print('  dyn_call(&dyn Shape) 的汇编:', ' ; '.join(a2)); R['asm'] = [a1, a2]
save('u41', R)
