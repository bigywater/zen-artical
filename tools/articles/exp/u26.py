import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u26'); R = {}
print("== 一:&'static 的来源:字符串字面量、static 变量、Box::leak")
r = tryit('u26a', '''
    static GLOBAL: &str = "全局";
    fn lit() -> &'static str { "字面量" }
    fn leaked() -> &'static mut Vec<i32> { Box::leak(Box::new(vec![1, 2, 3])) }
    fn main() {
        println!("{} {}", GLOBAL, lit());
        let v = leaked();
        v.push(4);
        println!("Box::leak 得到的 &'static mut:{:?}", v);
    }
''', quiet_src=False)
print()
print("== 二:T: 'static 的意思是「不含非 'static 的引用」,不是「永远活着」:拥有数据的 String 满足,指向局部变量的 &String 不满足")
r = tryit('u26b', '''
    fn needs_static<T: 'static + std::fmt::Debug>(t: T) { println!("收到 {:?}", t); }
    fn main() {
        let owned = String::from("owned");
        needs_static(owned);                 // 拥有数据:满足 'static
        needs_static(5);                     // 整数:满足
        needs_static("literal");             // &'static str:满足
    }
''', quiet_src=False)
r = tryit('u26c', '''
    fn needs_static<T: 'static + std::fmt::Debug>(t: T) { println!("收到 {:?}", t); }
    fn main() {
        let s = String::from("local");
        needs_static(&s);
    }
''', maxlines=30); R['e597'] = r['diag'].split('\n')[0]
print()
print("== 三:thread::spawn 要求闭包是 'static:借用局部变量的闭包被拒绝,三种解法")
r = tryit('u26d', '''
    use std::thread;
    fn main() {
        let v = vec![1, 2, 3];
        let h = thread::spawn(|| println!("{:?}", v));
        h.join().unwrap();
    }
''', maxlines=32); R['e373'] = r['diag'].split('\n')[0]
r = tryit('u26e', '''
    use std::{sync::Arc, thread};
    fn main() {
        let v = vec![1, 2, 3];
        let h = thread::spawn(move || println!("move 之后线程拥有 v:{:?}", v));        // 解法 1:move
        h.join().unwrap();
        let shared = Arc::new(vec![4, 5, 6]); let s2 = Arc::clone(&shared);
        thread::spawn(move || println!("解法 2:Arc 共享 {:?}", s2)).join().unwrap();
        let local = vec![7, 8, 9];
        thread::scope(|s| { s.spawn(|| println!("解法 3:thread::scope 可以借用局部变量 {:?}", local)); });
    }
''', quiet_src=False)
print()
print("== 四:Box::leak 真的不释放:用计数分配器看 alloc 与 dealloc 的次数")
r = tryit('u26f', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicUsize, Ordering};
    struct C; static AL: AtomicUsize = AtomicUsize::new(0); static DE: AtomicUsize = AtomicUsize::new(0);
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { AL.fetch_add(1, Ordering::Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { DE.fetch_add(1, Ordering::Relaxed); unsafe { System.dealloc(p, l) } }
    }
    #[global_allocator] static G: C = C;
    fn main() {
        let (a0, d0) = (AL.load(Ordering::Relaxed), DE.load(Ordering::Relaxed));
        for i in 0..1000 { let b = Box::new([i as u8; 64]); std::hint::black_box(&b); }          // 释放
        let (a1, d1) = (AL.load(Ordering::Relaxed), DE.load(Ordering::Relaxed));
        for i in 0..1000 { let b: &'static mut [u8; 64] = Box::leak(Box::new([i as u8; 64])); std::hint::black_box(&b); }   // 泄漏
        let (a2, d2) = (AL.load(Ordering::Relaxed), DE.load(Ordering::Relaxed));
        println!("1000 个 Box 正常 drop:alloc +{},dealloc +{}", a1 - a0, d1 - d0);
        println!("1000 个 Box::leak     :alloc +{},dealloc +{}(从不释放)", a2 - a1, d2 - d1);
    }
''', release=True, quiet_src=False); R['leak'] = r['out']
save('u26', R)
