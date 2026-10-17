import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u115'); R = {}
print('== 一:胖指针的元数据:dyn Trait 是 vtable 指针;切片与 str 是长度;转成 *const () 就只剩数据地址')
r = tryit('u115a', '''
    use std::{mem::{size_of, transmute}, fmt::Debug};
    fn main() {
        println!("&u8 {}  &[u8] {}  &str {}  &dyn Debug {}  *const dyn Debug {}  Box<dyn Debug> {}", size_of::<&u8>(), size_of::<&[u8]>(), size_of::<&str>(), size_of::<&dyn Debug>(), size_of::<*const dyn Debug>(), size_of::<Box<dyn Debug>>());
        let v = [1u8, 2, 3, 4, 5]; let sl: &[u8] = &v[1..4];
        let (ptr, len): (usize, usize) = unsafe { transmute(sl) };
        println!("&v[1..4] 拆开:数据地址 = v 的地址 + 1: {}  长度元数据 = {}", ptr == v.as_ptr() as usize + 1, len);
        let s: &str = "héllo"; let (_, slen): (usize, usize) = unsafe { transmute(s) }; println!("&str 的元数据是字节数,不是字符数:\\"héllo\\" 长度 {} 字节({} 个字符)", slen, s.chars().count());
        let d: &dyn Debug = &42u32; let thin = d as *const dyn Debug as *const (); println!("&dyn Debug 转成 *const (): 8 字节数据地址 = {:p},vtable 信息丢掉了", thin);
    }
''', quiet_src=True); R['meta'] = r['out']
print()
print('== 二:不同类型的 trait object vtable 不同;上转型(dyn Sub → dyn Super)之后 vtable 指针有没有变')
r = tryit('u115b', '''
    #![allow(dead_code)]
    use std::mem::transmute;
    trait Super { fn name(&self) -> &'static str { "Super" } }
    trait Sub: Super { fn id(&self) -> u32; }
    struct A(u32); struct B(u32);
    impl Super for A { fn name(&self) -> &'static str { "A" } } impl Sub for A { fn id(&self) -> u32 { self.0 } }
    impl Super for B { fn name(&self) -> &'static str { "B" } } impl Sub for B { fn id(&self) -> u32 { self.0 + 100 } }
    fn parts(p: *const dyn Sub) -> (usize, usize) { unsafe { transmute::<*const dyn Sub, (usize, usize)>(p) } }
    fn parts_s(p: *const dyn Super) -> (usize, usize) { unsafe { transmute::<*const dyn Super, (usize, usize)>(p) } }
    fn main() {
        let (a1, a2, b1) = (A(1), A(2), B(3));
        let (pa1, pa2, pb) = (parts(&a1 as &dyn Sub), parts(&a2 as &dyn Sub), parts(&b1 as &dyn Sub));
        println!("两个 A:vtable 相同 {}  A 与 B:vtable 相同 {}  数据地址不同 {}", pa1.1 == pa2.1, pa1.1 == pb.1, pa1.0 != pa2.0);
        let sub: &dyn Sub = &a1; let sup: &dyn Super = sub;       // trait upcasting(稳定特性)
        let (ps, pu) = (parts(sub), parts_s(sup));
        println!("上转型 &dyn Sub → &dyn Super:数据地址不变 {}  vtable 指针变了 {}(这个例子里没变)  通过 Super 调用 name() = {}", ps.0 == pu.0, ps.1 != pu.1, sup.name());
    }
''', quiet_src=True); R['upcast'] = r['out']
print()
print('== 三:比较 dyn 指针:ptr::eq 同时比较数据地址与 vtable;只想比对象身份要先转成 *const ()')
r = tryit('u115c', '''
    #![allow(dead_code)]
    use std::ptr;
    trait T { fn f(&self) {} } struct Z; impl T for Z {}
    fn main() {
        let z = Z;
        let a: &dyn T = &z; let b: &dyn T = &z;
        println!("同一个对象两个 &dyn T:ptr::eq(a, b) = {}", ptr::eq(a, b));
        println!("按数据地址比较(转成 *const ()):{}", ptr::eq(a as *const dyn T as *const (), b as *const dyn T as *const ()));
    }
''', quiet_src=True); R['eq'] = r['out']
print()
print('== 四:运行时才知道的大小:size_of_val / align_of_val 通过 vtable 取到具体类型的值;drop 也通过 vtable 调到具体类型的 Drop')
r = tryit('u115d', '''
    use std::mem::{size_of_val, align_of_val};
    trait Animal { fn name(&self) -> String; }
    struct Cat; struct Elephant { _w: [u8; 100] }
    struct Noisy(&'static str); impl Drop for Noisy { fn drop(&mut self) { println!("  Noisy({}) 的 Drop 通过 vtable 被调用", self.0); } }
    impl Animal for Cat { fn name(&self) -> String { "cat".into() } } impl Animal for Elephant { fn name(&self) -> String { "elephant".into() } } impl Animal for Noisy { fn name(&self) -> String { self.0.into() } }
    fn main() {
        let zoo: Vec<Box<dyn Animal>> = vec![Box::new(Cat), Box::new(Elephant { _w: [0; 100] }), Box::new(Noisy("tiger"))];
        for a in &zoo { println!("  {:<10} size_of_val = {:>3}  align_of_val = {}", a.name(), size_of_val(&**a), align_of_val(&**a)); }
        println!("  Vec<Box<dyn Animal>> 离开作用域:");
    }
''', quiet_src=True); R['val'] = r['out']
print()
print('== 五:dyn Any:类型信息来自 vtable 里的 type_id;downcast 对比 TypeId')
r = tryit('u115e', '''
    use std::any::{Any, TypeId};
    fn main() {
        let items: Vec<Box<dyn Any>> = vec![Box::new(5i32), Box::new("str"), Box::new(String::from("owned")), Box::new(2.5f64)];
        for it in &items {
            if let Some(i) = it.downcast_ref::<i32>() { println!("  i32 = {}", i); }
            else if let Some(s) = it.downcast_ref::<&str>() { println!("  &str = {}", s); }
            else if let Some(s) = it.downcast_ref::<String>() { println!("  String = {}", s); }
            else { println!("  未知类型,type_id 与 f64 相同吗: {}", (**it).type_id() == TypeId::of::<f64>()); }
        }
    }
''', quiet_src=True); R['any'] = r['out']
save('u115', R)
