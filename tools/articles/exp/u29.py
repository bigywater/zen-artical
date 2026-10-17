import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u29'); R = {}
print('== 一:Rc<T> 让多个所有者共享同一份数据,引用计数记录有几个所有者')
r = tryit('u29a', '''
    use std::rc::Rc;
    fn main() {
        let a = Rc::new(String::from("共享数据"));
        println!("创建 a 之后:strong_count = {}", Rc::strong_count(&a));
        let b = Rc::clone(&a);
        println!("clone 出 b 之后:strong_count = {}", Rc::strong_count(&a));
        {
            let c = Rc::clone(&a);
            println!("内层再 clone 出 c:strong_count = {}(a、b、c 指向同一块内存:{})", Rc::strong_count(&a), Rc::ptr_eq(&a, &c));
        }
        println!("c 离开作用域之后:strong_count = {}", Rc::strong_count(&a));
        drop(b);
        println!("drop(b) 之后:strong_count = {}", Rc::strong_count(&a));
    }
''', quiet_src=False)
print()
print('== 二:Rc 里的数据只读;想修改要么独占(get_mut)要么写时复制(make_mut)')
r = tryit('u29b', '''
    use std::rc::Rc;
    fn main() {
        let a = Rc::new(vec![1, 2, 3]);
        a.push(4);
    }
''', maxlines=24); R['e596'] = r['diag'].split('\n')[0]
r = tryit('u29c', '''
    use std::rc::Rc;
    fn main() {
        let mut a = Rc::new(vec![1, 2, 3]);
        println!("独占时 get_mut 成功:{}", Rc::get_mut(&mut a).map(|v| { v.push(4); true }).unwrap_or(false));
        let b = Rc::clone(&a);
        println!("有第二个所有者时 get_mut 返回 None:{}", Rc::get_mut(&mut a).is_none());
        Rc::make_mut(&mut a).push(5);          // 写时复制:发现不是唯一所有者,先克隆一份
        println!("make_mut 之后:a = {:?},b = {:?},a 与 b 还指向同一块内存吗?{}", a, b, Rc::ptr_eq(&a, &b));
    }
''', quiet_src=False)
print()
print('== 三:Rc 不是 Send:不能把它交给别的线程')
r = tryit('u29d', '''
    use std::rc::Rc;
    use std::thread;
    fn main() {
        let a = Rc::new(5);
        let h = thread::spawn(move || println!("{}", a));
        h.join().unwrap();
    }
''', maxlines=30); R['e277'] = r['diag'].split('\n')[0]
print()
print('== 四:内存布局与成本:Rc 指针 8 字节,堆上多了两个计数;clone 只是加 1,不复制数据')
r = tryit('u29e', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::rc::Rc;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::time::Instant;
    use std::hint::black_box;
    struct C; static LAST: AtomicUsize = AtomicUsize::new(0);
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { LAST.store(l.size(), Ordering::Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { unsafe { System.dealloc(p, l) } }
    }
    #[global_allocator] static G: C = C;
    fn main() {
        let r = Rc::new(0u64);
        let sz = LAST.load(Ordering::Relaxed);
        println!("size_of::<Rc<u64>>() = {} 字节(指针);Rc::new(0u64) 在堆上分配了 {} 字节(强引用计数 8 + 弱引用计数 8 + 数据 8)", std::mem::size_of::<Rc<u64>>(), sz);
        let big = Rc::new(vec![7u8; 1 << 20]);
        let t = Instant::now(); for _ in 0..1_000_000 { let c = black_box(Rc::clone(&big)); black_box(&c); }
        let rc_ns = t.elapsed().as_nanos() as f64 / 1e6;
        let v = vec![7u8; 1 << 20];
        let t = Instant::now(); for _ in 0..200 { let c = black_box(v.clone()); black_box(&c); }
        let deep_ns = t.elapsed().as_nanos() as f64 / 200.0;
        println!("Rc::clone(共享 1 MiB 数据):每次约 {:.1} ns", rc_ns);
        println!("Vec<u8>(1 MiB) 的 clone:每次约 {:.0} ns", deep_ns);
        drop(r);
    }
''', release=True, quiet_src=True); R['cost'] = r['out']
save('u29', R)
