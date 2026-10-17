import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u106'); R = {}
print('== 一:为什么需要 Pin:自引用结构体一旦被移动,内部指针就指向旧地址')
r = tryit('u106a', '''
    struct SelfRef { data: [u8; 4], ptr: *const u8 }
    #[inline(never)] fn consume(s: SelfRef) -> SelfRef { s }
    fn main() {
        let mut s = SelfRef { data: [1, 2, 3, 4], ptr: std::ptr::null() };
        s.ptr = s.data.as_ptr();    // 在 main 的栈上就地建立自引用
        println!("创建后:data 在 {:p},ptr 指向 {:p},二者相同: {}", s.data.as_ptr(), s.ptr, s.data.as_ptr() == s.ptr);
        let moved = consume(s);   // 按值移动(搬到另一块栈空间)
        println!("移动后:data 在 {:p},ptr 仍指向 {:p},二者相同: {}", moved.data.as_ptr(), moved.ptr, moved.data.as_ptr() == moved.ptr);
    }
''', quiet_src=True); R['move'] = r['out']
print()
print('== 二:Pin<Box<T>> 保证数据地址不再变:Box 自己可以随便移动,堆上的数据地址不变')
r = tryit('u106b', '''
    use std::{pin::Pin, marker::PhantomPinned};
    struct Data { v: u32, _p: PhantomPinned }
    fn main() {
        let b: Pin<Box<Data>> = Box::pin(Data { v: 7, _p: PhantomPinned });
        let addr1 = &b.v as *const u32 as usize;
        let moved = b;                       // 移动的是 Pin<Box>(一个指针),堆上的 Data 没动
        let v = vec![moved];                 // 再放进 Vec,再取出来
        let again = v.into_iter().next().unwrap();
        let addr2 = &again.v as *const u32 as usize;
        println!("Pin<Box<Data>> 被移动了两次,Data 的地址不变: {}", addr1 == addr2);
    }
''', quiet_src=True); R['pinbox'] = r['out']
print()
print('== 三:!Unpin 的类型:拿不到 &mut T(否则能 mem::swap 把它搬走)')
r = tryit('u106c', '''
    use std::{pin::Pin, marker::PhantomPinned};
    struct NoMove { v: u32, _p: PhantomPinned }
    fn main() {
        let mut p = Box::pin(NoMove { v: 1, _p: PhantomPinned });
        let r: &mut NoMove = p.as_mut().get_mut();
        r.v = 2;
    }
''', maxlines=30); R['e_getmut'] = r['diag']
r = tryit('u106d', '''
    use std::{pin::Pin, marker::PhantomPinned};
    struct NoMove { v: u32, _p: PhantomPinned }
    fn main() { let x = NoMove { v: 1, _p: PhantomPinned }; let p = Pin::new(&x); let _ = p; }
''', maxlines=30); R['e_new'] = r['diag']
print()
print('== 四:Unpin 是自动 trait:大多数类型都是 Unpin,Pin 对它们没有限制;逐个检查常见类型')
rows = []
types = [('i32', 'i32'), ('String', 'String'), ('Vec<u8>', 'Vec<u8>'), ('Box<T>', 'Box<i32>'), ('&mut i32', '&mut i32'), ('PhantomPinned', 'std::marker::PhantomPinned'), ('含 PhantomPinned 的 struct', 'S'), ('async fn 的 Future(跨 await 借用)', 'impl std::future::Future<Output = ()>'), ('async 块(无借用)', 'impl std::future::Future<Output = ()>')]
for name, ty in types:
    if name.startswith('async fn'):
        code = 'async fn f() { let a = [1u8]; let r = &a; async {}.await; let _ = r; }\nfn is_unpin<T: Unpin>(_: &T) {}\nfn main() { let f = f(); is_unpin(&f); }\n'
    elif name.startswith('async 块'):
        code = 'fn is_unpin<T: Unpin>(_: &T) {}\nfn main() { let f = async { 1 + 1; }; is_unpin(&f); }\n'
    else:
        code = f'struct S(std::marker::PhantomPinned);\nfn is_unpin<T: Unpin>() {{}}\nfn main() {{ is_unpin::<{ty}>(); }}\n'
    ok, d, _, _ = rustc('u106e', code, flags=('--emit=metadata',), crate_type='bin'); rows.append([name, ok]); print(f'  {name:<32} Unpin: {"✓" if ok else "✗"}')
R['unpin'] = rows
print()
print('== 五:栈上固定:std::pin::pin! 宏把值固定在当前栈帧里(不需要堆分配),之后值不能被移动')
r = tryit('u106f', '''
    use std::{pin::pin, future::Future, task::{Context, Poll, Waker}};
    async fn work() -> u32 { let a = [1u32, 2, 3]; let r = &a; std::future::ready(()).await; r.iter().sum() }
    fn main() {
        let fut = pin!(work());                              // Pin<&mut impl Future>,固定在栈上
        let mut cx = Context::from_waker(Waker::noop());
        let mut fut = fut;
        println!("poll 栈上固定的 Future: {:?}", fut.as_mut().poll(&mut cx));
    }
''', quiet_src=True); R['stack'] = r['out']
r = tryit('u106g', '''
    use std::pin::pin;
    fn main() { let mut p = pin!(String::from("x")); let s2 = std::mem::take(&mut *p); println!("{}", s2); }
''', quiet_src=True); R['unpin_take'] = r['out']
save('u106', R)
