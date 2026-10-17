import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u94'); R = {}
print('== 一:两个线程同时可变地修改同一个变量:编译器拒绝(E0499)')
r = tryit('u94a', '''
    use std::thread;
    fn main() {
        let mut counter = 0;
        thread::scope(|s| {
            s.spawn(|| { counter += 1; });
            s.spawn(|| { counter += 1; });
        });
        println!("{}", counter);
    }
''', maxlines=40); R['e0499'] = r['diag']
print()
print('== 二:一个线程读、一个线程写(E0502);数据竞争的定义:至少一个写 + 无同步 + 同时访问')
r = tryit('u94b', '''
    use std::thread;
    fn main() {
        let mut v = vec![1, 2, 3];
        thread::scope(|s| {
            s.spawn(|| { println!("{:?}", v); });
            s.spawn(|| { v.push(4); });
        });
    }
''', maxlines=40); R['e0502'] = r['diag']
print()
print('== 三:合法的写法:多个线程只读(共享引用 &T);或者每个线程拿不重叠的 &mut 切片')
r = tryit('u94c', '''
    use std::thread;
    fn main() {
        let v = vec![1, 2, 3, 4, 5, 6];
        let total = thread::scope(|s| { let hs: Vec<_> = (0..3).map(|i| { let v = &v; s.spawn(move || v[i * 2] + v[i * 2 + 1]) }).collect(); hs.into_iter().map(|h| h.join().unwrap()).sum::<i32>() });
        println!("多个线程同时只读 &v:合计 {}", total);
        let mut w = vec![0; 6];
        thread::scope(|s| { for (i, ch) in w.chunks_mut(2).enumerate() { s.spawn(move || { for x in ch.iter_mut() { *x = i as i32 + 1; } }); } });
        println!("每个线程一个不重叠的 &mut 切片:{:?}", w);
    }
''', quiet_src=True); R['ok'] = r['out']
print()
print('== 四:static mut 的引用被 2024 edition 默认拒绝(static_mut_refs);要访问只能用 unsafe + 裸指针')
r = tryit('u94d', '''
    static mut COUNTER: u32 = 0;
    fn main() { unsafe { COUNTER += 1; let r = &COUNTER; println!("{}", r); } }
''', maxlines=30); R['static_mut'] = r['diag']
print()
print('== 五:数据竞争只有 unsafe 才写得出来。先看:给 Racy 实现了 Sync,闭包里直接写 c.0 仍被拒绝(闭包只捕获 c.0 这个字段,而 UnsafeCell 不是 Sync)')
r = tryit('u94e', '''
    use std::{cell::UnsafeCell, thread};
    struct Racy(UnsafeCell<u64>);
    unsafe impl Sync for Racy {}
    fn main() {
        let c = Racy(UnsafeCell::new(0));
        thread::scope(|s| { s.spawn(|| { unsafe { *c.0.get() += 1; } }); });
    }
''', maxlines=24); R['capture'] = r['diag']
print()
print('== 五(续):改成通过方法访问(闭包捕获整个 c),4 线程 × 100 万次 +1。这是未定义行为,只用来展示后果')
r = tryit('u94f2', '''
    use std::{cell::UnsafeCell, thread};
    struct Racy(UnsafeCell<u64>);
    unsafe impl Sync for Racy {}
    impl Racy { fn bump(&self) { unsafe { let p = self.0.get(); p.write_volatile(p.read_volatile() + 1); } } fn get(&self) -> u64 { unsafe { *self.0.get() } } }
    fn main() {
        let c = Racy(UnsafeCell::new(0));
        thread::scope(|s| { for _ in 0..4 { s.spawn(|| { for _ in 0..1_000_000 { c.bump(); } }); } });
        println!("期望 4000000,实际 {}(没有同步的并发写,更新丢失)", c.get());
    }
''', quiet_src=True, release=True); R['racy'] = r['out']
print()
print('== 六:竞态条件(race condition)不等于数据竞争:全用安全代码也能写出逻辑竞态(检查-再-操作)')
r = tryit('u94f', '''
    use std::{sync::{Arc, Mutex}, thread, time::Duration};
    fn main() {
        let stock = Arc::new(Mutex::new(1i32)); let sold = Arc::new(Mutex::new(0u32));
        let hs: Vec<_> = (0..4).map(|_| { let (stock, sold) = (stock.clone(), sold.clone()); thread::spawn(move || {
            let has = *stock.lock().unwrap() > 0;           // 检查
            thread::sleep(Duration::from_millis(20));        // 中间别人可以插进来
            if has { *stock.lock().unwrap() -= 1; *sold.lock().unwrap() += 1; }   // 操作
        }) }).collect();
        for h in hs { h.join().unwrap(); }
        println!("库存只有 1 件,却卖出了 {} 件;库存值 = {}", sold.lock().unwrap(), stock.lock().unwrap());
    }
''', quiet_src=True, release=True); R['logic'] = r['out']
save('u94', R)
