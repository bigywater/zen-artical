import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u86'); R = {}
types = [
    ('i32', 'i32'), ('String', 'String'), ('Vec<u8>', 'Vec<u8>'), ('&str', '&str'), ('&mut i32', '&mut i32'),
    ('Rc<i32>', 'std::rc::Rc<i32>'), ('Arc<i32>', 'std::sync::Arc<i32>'), ('Cell<i32>', 'std::cell::Cell<i32>'), ('RefCell<i32>', 'std::cell::RefCell<i32>'),
    ('Mutex<i32>', 'std::sync::Mutex<i32>'), ('RwLock<i32>', 'std::sync::RwLock<i32>'), ('AtomicUsize', 'std::sync::atomic::AtomicUsize'),
    ('Mutex<Rc<i32>>', 'std::sync::Mutex<std::rc::Rc<i32>>'), ('Arc<RefCell<i32>>', 'std::sync::Arc<std::cell::RefCell<i32>>'), ('Arc<Mutex<i32>>', 'std::sync::Arc<std::sync::Mutex<i32>>'),
    ('*const i32', '*const i32'), ('MutexGuard<i32>', 'std::sync::MutexGuard<\'static, i32>'), ('mpsc::Sender<i32>', 'std::sync::mpsc::Sender<i32>'), ('mpsc::Receiver<i32>', 'std::sync::mpsc::Receiver<i32>'),
    ('Box<dyn Fn()>', 'Box<dyn Fn()>'), ('Box<dyn Fn() + Send>', 'Box<dyn Fn() + Send>'), ('Weak<i32>(Rc)', 'std::rc::Weak<i32>'),
]
print('== 一:用 fn assert_send<T: Send>() 与 assert_sync<T: Sync>() 逐个试编译(每个类型各编译两次)')
print(f'  {"类型":<24}{"Send":<8}{"Sync":<8}')
rows = []
for name, ty in types:
    res = []
    for tr in ('Send', 'Sync'):
        ok, d, _, _ = rustc('u86t', f'fn assert<T: {tr}>() {{}}\nfn main() {{ assert::<{ty}>(); }}\n', flags=('--emit=metadata',), crate_type='bin')
        res.append(ok)
    rows.append([name, res[0], res[1]]); print(f'  {name:<24}{"✓" if res[0] else "✗":<8}{"✓" if res[1] else "✗":<8}')
R['matrix'] = rows
print()
print('== 二:Rc 跨线程:编译器的真实报错')
r = tryit('u86a', '''
    use std::rc::Rc; use std::thread;
    fn main() { let r = Rc::new(5); let h = thread::spawn(move || { println!("{}", r); }); h.join().unwrap(); }
''', maxlines=40); R['rc'] = r['diag']
print()
print('== 三:&RefCell 跨线程(RefCell 是 Send 但不是 Sync);改用 Mutex 就可以')
r = tryit('u86b', '''
    use std::cell::RefCell; use std::thread;
    fn main() { let c = RefCell::new(1); thread::scope(|s| { s.spawn(|| { *c.borrow_mut() += 1; }); }); println!("{:?}", c); }
''', maxlines=40); R['refcell'] = r['diag']
r = tryit('u86c', '''
    use std::sync::Mutex; use std::thread;
    fn main() { let c = Mutex::new(1); thread::scope(|s| { for _ in 0..4 { s.spawn(|| { *c.lock().unwrap() += 1; }); } }); println!("{:?}", c.lock().unwrap()); }
''', quiet_src=True); R['mutex'] = r['out']
print()
print('== 四:裸指针不是 Send;自己用 unsafe impl Send 承诺安全(编译器相信你)')
r = tryit('u86d', '''
    use std::thread;
    struct P(*mut i32);
    fn main() { let mut x = 1; let p = P(&mut x); thread::spawn(move || { let q = p; println!("{:p}", q.0); }).join().unwrap(); }
''', maxlines=40); R['rawptr'] = r['diag']
r = tryit('u86e', '''
    use std::thread;
    struct P(*mut i32);
    unsafe impl Send for P {}
    fn main() {
        let b = Box::new(41); let p = P(Box::into_raw(b));
        let h = thread::spawn(move || { let p = p; unsafe { *p.0 += 1; let v = *p.0; drop(Box::from_raw(p.0)); v } });
        println!("子线程通过 unsafe impl Send 的指针得到 {}", h.join().unwrap());
    }
''', quiet_src=True); R['unsafe_send'] = r['out']
print()
print('== 五:Send / Sync 是自动 trait:结构体字段全部是 Send 则自动 Send;一个字段不是,整体就不是')
r = tryit('u86f', '''
    use std::rc::Rc;
    struct Ok1 { a: i32, b: String }
    struct Bad1 { a: i32, b: Rc<i32> }
    fn assert_send<T: Send>() {}
    fn main() { assert_send::<Ok1>(); assert_send::<Bad1>(); }
''', maxlines=40); R['auto'] = r['diag']
save('u86', R)
