import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u28'); R = {}
print('== 一:Box<T> 把值放到堆上;Box 本身是一个指针(8 字节),离开作用域时释放堆内存')
r = tryit('u28a', '''
    use std::mem::size_of;
    fn main() {
        let local = 5i32;
        let boxed = Box::new(5i32);
        println!("size_of::<i32>() = {},size_of::<Box<i32>>() = {}", size_of::<i32>(), size_of::<Box<i32>>());
        let stack = &local as *const i32 as usize;
        let heap = &*boxed as *const i32 as usize;
        println!("局部 i32 的地址 {:#x}(栈),Box 里的 i32 地址 {:#x}(堆);相差 {} MiB", stack, heap, stack.abs_diff(heap) >> 20);
        println!("*boxed + 1 = {}(自动解引用)", *boxed + 1);
    }
''', quiet_src=False)
print()
print('== 二:递归类型的大小必须有限:没有 Box 的链表无法编译')
r = tryit('u28b', '''
    enum List { Cons(i32, List), Nil }
    fn main() {}
''', maxlines=30); R['e0072'] = r['diag'].split('\n')[0]
r = tryit('u28c', '''
    use std::mem::size_of;
    #[allow(dead_code)]
    enum List { Cons(i32, Box<List>), Nil }
    use List::{Cons, Nil};
    fn sum(l: &List) -> i32 { match l { Cons(v, rest) => v + sum(rest), Nil => 0 } }
    fn main() {
        let list = Cons(1, Box::new(Cons(2, Box::new(Cons(3, Box::new(Nil))))));
        println!("sum = {},size_of::<List>() = {} 字节(i32 + Box 指针 + 标签,与链表长度无关)", sum(&list), size_of::<List>());
    }
''', quiet_src=False)
print()
print('== 三:移动 Box 只复制 8 字节的指针,移动大数组要复制全部数据(release 计时)')
r = tryit('u28d', '''
    use std::hint::black_box;
    use std::time::Instant;
    const N: usize = 1 << 20;
    fn pass_array(a: [u8; N]) -> [u8; N] { black_box(a) }
    fn pass_box(a: Box<[u8; N]>) -> Box<[u8; N]> { black_box(a) }
    fn main() {
        let arr = [1u8; N];
        let t = Instant::now(); let mut acc = 0u64;
        for _ in 0..200 { let x = pass_array(black_box(arr)); acc += x[0] as u64; }
        let t_arr = t.elapsed().as_nanos() as f64 / 200.0;
        let bx: Box<[u8; N]> = vec![1u8; N].into_boxed_slice().try_into().unwrap();
        let t = Instant::now(); let mut cur = bx;
        for _ in 0..200 { cur = pass_box(black_box(cur)); acc += cur[0] as u64; }
        let t_box = t.elapsed().as_nanos() as f64 / 200.0;
        black_box(acc);
        println!("按值传递并返回 [u8; 1 MiB]:每次约 {:.0} ns", t_arr);
        println!("按值传递并返回 Box<[u8; 1 MiB]>:每次约 {:.1} ns", t_box);
    }
''', release=True, quiet_src=False); R['move_bench'] = r['out']
print()
print('== 四:Box 的 drop 释放堆内存(计数分配器)')
r = tryit('u28e', '''
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
        let mid;
        {
            let b = Box::new([0u8; 128]);
            std::hint::black_box(&b);
            mid = (AL.load(Ordering::Relaxed) - a0, DE.load(Ordering::Relaxed) - d0);     // 先记下数字,再打印(打印自己也会分配内存)
        }
        let end = (AL.load(Ordering::Relaxed) - a0, DE.load(Ordering::Relaxed) - d0);
        println!("Box 存在时:alloc +{},dealloc +{}", mid.0, mid.1);
        println!("离开作用域后:alloc +{},dealloc +{}", end.0, end.1);
    }
''', quiet_src=True)
save('u28', R)
