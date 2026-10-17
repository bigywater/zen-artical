import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u110'); R = {}
print('== 一:指针本身的大小:Box / Rc / Arc 都是一个指针(8 字节);指向 dyn / str / 切片时变成胖指针(16 字节);Option 靠空指针优化不增加大小')
r = tryit('u110a', '''
    use std::{mem::size_of, rc::Rc, sync::Arc, fmt::Debug};
    fn main() {
        println!("Box<u64> {}  Rc<u64> {}  Arc<u64> {}  &u64 {}", size_of::<Box<u64>>(), size_of::<Rc<u64>>(), size_of::<Arc<u64>>(), size_of::<&u64>());
        println!("Box<dyn Debug> {}  Rc<dyn Debug> {}  Arc<dyn Debug> {}", size_of::<Box<dyn Debug>>(), size_of::<Rc<dyn Debug>>(), size_of::<Arc<dyn Debug>>());
        println!("Box<[u8]> {}  Rc<str> {}  Arc<[u32]> {}  Box<str> {}", size_of::<Box<[u8]>>(), size_of::<Rc<str>>(), size_of::<Arc<[u32]>>(), size_of::<Box<str>>());
        println!("Option<Box<u64>> {}  Option<Rc<u64>> {}  Option<Arc<u64>> {}", size_of::<Option<Box<u64>>>(), size_of::<Option<Rc<u64>>>(), size_of::<Option<Arc<u64>>>());
        println!("Vec<u8> {}  String {}", size_of::<Vec<u8>>(), size_of::<String>());
    }
''', quiet_src=True); R['sizes'] = r['out']
print()
print('== 二:堆上到底分配了多少字节:用全局分配器记录 Layout(大小与对齐)')
r = tryit('u110b', '''
    use std::{alloc::{GlobalAlloc, Layout, System}, rc::Rc, sync::Arc, sync::atomic::{AtomicUsize, Ordering::Relaxed}};
    static SZ: AtomicUsize = AtomicUsize::new(0); static AL: AtomicUsize = AtomicUsize::new(0); static N: AtomicUsize = AtomicUsize::new(0);
    struct C;
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { SZ.store(l.size(), Relaxed); AL.store(l.align(), Relaxed); N.fetch_add(1, Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { unsafe { System.dealloc(p, l) } }
    }
    #[global_allocator] static G: C = C;
    fn measure<T>(f: impl FnOnce() -> T) -> (usize, usize, usize, T) { let n0 = N.load(Relaxed); let v = f(); (SZ.load(Relaxed), AL.load(Relaxed), N.load(Relaxed) - n0, v) }
    fn main() {
        let (a, b, c, _x) = measure(|| Box::new(7u64)); let r1 = (a, b, c);
        let (a, b, c, _y) = measure(|| Rc::new(7u64)); let r2 = (a, b, c);
        let (a, b, c, _z) = measure(|| Arc::new(7u64)); let r3 = (a, b, c);
        let (a, b, c, _w) = measure(|| Rc::new([0u8; 100])); let r4 = (a, b, c);
        let (a, b, c, _s) = measure(|| Rc::<str>::from("hello")); let r5 = (a, b, c);
        let (a, b, c, _u) = measure(|| Box::new(()));  let r6 = (a, b, c);
        println!("Box<u64>(8 字节的数据):       分配 {} 字节,对齐 {},{} 次分配", r1.0, r1.1, r1.2);
        println!("Rc<u64>:                   分配 {} 字节,对齐 {},{} 次分配(8 字节数据 + {} 字节的计数器)", r2.0, r2.1, r2.2, r2.0 - 8);
        println!("Arc<u64>:                  分配 {} 字节,对齐 {},{} 次分配", r3.0, r3.1, r3.2);
        println!("Rc<[u8; 100]>:             分配 {} 字节(16 字节计数器 + 100 字节数据 = 116,按对齐 8 补到 120)", r4.0);
        println!("Rc<str> from \\"hello\\":     分配 {} 字节(16 字节计数器 + 5 字节字符串 = 21,补到 24),{} 次分配(字符串与计数器在同一块)", r5.0, r5.2);
        println!("Box<()>(零大小类型):         {} 次分配", r6.2);
    }
''', quiet_src=True); R['layout'] = r['out']
print()
print('== 三:偷看计数器:Rc::as_ptr 指向数据,数据前面的 16 字节就是 strong 与 weak 计数(unsafe 读,仅用于观察)')
r = tryit('u110c', '''
    use std::{rc::Rc, sync::Arc};
    fn peek<T>(p: *const T) -> (usize, usize) { unsafe { let base = (p as *const usize).sub(2); (*base, *base.add(1)) } }
    fn main() {
        let a = Rc::new(7u64);
        println!("Rc::new:     (strong, weak) = {:?}(weak 起始为 1:所有 strong 引用合起来持有的那一个隐式 weak)", peek(Rc::as_ptr(&a)));
        let b = Rc::clone(&a); println!("clone 一次:   {:?}  strong_count() = {}  weak_count() = {}", peek(Rc::as_ptr(&a)), Rc::strong_count(&a), Rc::weak_count(&a));
        let w = Rc::downgrade(&a); println!("downgrade:    {:?}  strong_count() = {}  weak_count() = {}", peek(Rc::as_ptr(&a)), Rc::strong_count(&a), Rc::weak_count(&a));
        drop(b); drop(a); println!("drop 两个 Rc: Weak::upgrade() = {:?}(数据已被 drop,但内存块还在,因为还有 Weak)", w.upgrade());
        let x = Arc::new(7u64); let y = Arc::clone(&x); println!("Arc 同样: {:?}  strong_count = {}", peek(Arc::as_ptr(&x)), Arc::strong_count(&y));
    }
''', quiet_src=True); R['counts'] = r['out']
print()
print('== 四:Rc 的数据在最后一个强引用释放时 drop;内存块在最后一个弱引用释放时才归还(用 Drop 与分配器统计证明)')
r = tryit('u110d', '''
    use std::{alloc::{GlobalAlloc, Layout, System}, rc::Rc, sync::atomic::{AtomicIsize, Ordering::Relaxed}};
    static LIVE: AtomicIsize = AtomicIsize::new(0);
    struct C;
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { LIVE.fetch_add(1, Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { LIVE.fetch_sub(1, Relaxed); unsafe { System.dealloc(p, l) } }
    }
    #[global_allocator] static G: C = C;
    struct Noisy; impl Drop for Noisy { fn drop(&mut self) { println!("(Noisy::drop 被调用:数据被销毁)"); } }
    fn main() {
        println!("(先打印一行,让 stdout 的缓冲区先分配好,以免干扰计数)");
        let base = LIVE.load(Relaxed);
        let a = Rc::new(Noisy); let w = Rc::downgrade(&a);
        let s1 = LIVE.load(Relaxed) - base;
        drop(a); let s2 = LIVE.load(Relaxed) - base;
        drop(w); let s3 = LIVE.load(Relaxed) - base;
        println!("创建 Rc + Weak 后:        存活的堆块 +{}", s1);
        println!("drop 最后一个强引用后:   存活的堆块 +{}(上面打印的 Noisy::drop 说明数据已销毁,内存块仍在,因为 Weak 还指着它)", s2);
        println!("drop 最后一个 Weak 后:   存活的堆块 +{}", s3);
    }
''', quiet_src=True); R['free'] = r['out']
save('u110', R)
