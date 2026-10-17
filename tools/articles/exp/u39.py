import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u39'); R = {}
print('== 一:Trait Object:用 Box<dyn Trait> 把不同类型放进同一个集合,运行时按实际类型调用')
r = tryit('u39a', '''
    trait Shape { fn area(&self) -> f64; fn name(&self) -> &'static str; }
    struct Circle(f64); struct Rect(f64, f64); struct Tri(f64, f64);
    impl Shape for Circle { fn area(&self) -> f64 { 3.14159 * self.0 * self.0 } fn name(&self) -> &'static str { "圆" } }
    impl Shape for Rect { fn area(&self) -> f64 { self.0 * self.1 } fn name(&self) -> &'static str { "矩形" } }
    impl Shape for Tri { fn area(&self) -> f64 { 0.5 * self.0 * self.1 } fn name(&self) -> &'static str { "三角形" } }
    fn main() {
        let shapes: Vec<Box<dyn Shape>> = vec![Box::new(Circle(1.0)), Box::new(Rect(2.0, 3.0)), Box::new(Tri(4.0, 5.0))];
        for s in &shapes { println!("{} 面积 {:.2}", s.name(), s.area()); }
        println!("总面积 {:.2}", shapes.iter().map(|s| s.area()).sum::<f64>());
    }
''', quiet_src=False)
print()
print('== 二:dyn Trait 的大小不固定,只能放在指针后面;指针是胖指针(数据指针 + vtable 指针)')
r = tryit('u39b', '''
    trait T { fn f(&self) {} }
    struct A; impl T for A {}
    fn main() { let x: dyn T = A; }
''', maxlines=24); R['e277'] = r['diag'].split('\n')[0]
r = tryit('u39c', '''
    use std::mem::size_of;
    trait Shape { fn area(&self) -> f64; }
    fn main() {
        println!("&Circle(普通引用)    = {} 字节", size_of::<&f64>());
        println!("&dyn Shape(胖指针)   = {} 字节", size_of::<&dyn Shape>());
        println!("Box<dyn Shape>       = {} 字节", size_of::<Box<dyn Shape>>());
        println!("Box<f64>             = {} 字节", size_of::<Box<f64>>());
        println!("Rc<dyn Shape>        = {} 字节", size_of::<std::rc::Rc<dyn Shape>>());
    }
''', quiet_src=True, flags=('-A', 'dead_code'))
print()
print('== 三:偷看胖指针:同一类型的 dyn 指针共用一张 vtable,不同类型的 vtable 不同;vtable 里能读出类型的 size 和 align(布局是实现细节,仅用于观察)')
r = tryit('u39d', '''
    use std::mem::{size_of, align_of, transmute};
    trait Shape { fn area(&self) -> f64; }
    struct Circle(f64);                  // 8 字节
    struct Big { a: [u64; 5] }           // 40 字节
    struct Unit;                          // 0 字节
    impl Shape for Circle { fn area(&self) -> f64 { self.0 } }
    impl Shape for Big { fn area(&self) -> f64 { self.a[0] as f64 } }
    impl Shape for Unit { fn area(&self) -> f64 { 0.0 } }
    fn parts(s: &dyn Shape) -> (usize, usize) { unsafe { transmute::<&dyn Shape, (usize, usize)>(s) } }
    fn vt_size_align(vt: usize) -> (usize, usize) { let p = vt as *const usize; unsafe { (*p.add(1), *p.add(2)) } }   // 观察到的布局:[drop_in_place, size, align, 方法...]
    fn main() {
        let (c1, c2, b, u) = (Circle(1.0), Circle(2.0), Big { a: [1; 5] }, Unit);
        let (d1, v1) = parts(&c1); let (d2, v2) = parts(&c2); let (_d3, v3) = parts(&b); let (_d4, v4) = parts(&u);
        println!("Circle 的两个对象:数据地址不同 {},vtable 地址相同 {}", d1 != d2, v1 == v2);
        println!("Circle 与 Big 的 vtable 不同:{};Circle 与 Unit 的 vtable 不同:{}", v1 != v3, v1 != v4);
        for (name, vt, sz, al) in [("Circle", v1, size_of::<Circle>(), align_of::<Circle>()), ("Big", v3, size_of::<Big>(), align_of::<Big>()), ("Unit", v4, size_of::<Unit>(), align_of::<Unit>())] {
            let (s, a) = vt_size_align(vt);
            println!("{:<7} vtable 里读出 size = {:>2}, align = {};size_of / align_of = {} / {}", name, s, a, sz, al);
        }
    }
''', quiet_src=False, flags=('-A', 'dead_code')); R['vt'] = r['out']
print()
print('== 四:从泛型到 trait 对象:同样的函数,用 &dyn Trait 参数只编译一份,用泛型每个类型一份')
code = '''
    pub trait Shape { fn area(&self) -> f64; }
    pub struct A(pub f64); pub struct B(pub f64);
    impl Shape for A { fn area(&self) -> f64 { self.0 } }
    impl Shape for B { fn area(&self) -> f64 { self.0 * 2.0 } }
    #[inline(never)] pub fn total_dyn(s: &dyn Shape) -> f64 { s.area() + 1.0 }
    #[inline(never)] pub fn total_gen<S: Shape>(s: &S) -> f64 { s.area() + 1.0 }
    #[unsafe(no_mangle)] pub fn use_all(a: &A, b: &B) -> f64 { total_dyn(a) + total_dyn(b) + total_gen(a) + total_gen(b) }
'''
_, txt = asm_of('u39e', code, None)
n_dyn = len(re.findall(r'^__R[^\s:]*total_dyn[^\s:]*:', txt, re.M)); n_gen = len(re.findall(r'^__R[^\s:]*total_gen[^\s:]*:', txt, re.M))
print(f'  total_dyn(&dyn Shape) 生成的函数个数:{n_dyn};total_gen<S: Shape> 生成的函数个数(A、B 各一份):{n_gen}'); R['n'] = (n_dyn, n_gen)
calls = [re.sub(r'__R\w*?(total_\w+?)(?:NtB2_1(\w)EB2_)?$', lambda m: m.group(1) + ('::<' + m.group(2) + '>' if m.group(2) else ''), l.split()[-1]) for l in txt.split('\n') if l.strip().startswith('bl') and 'total_' in l]
print('  use_all 里的四次调用依次指向:', calls)
save('u39', R)
