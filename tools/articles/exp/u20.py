import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u20'); R = {}
print('== 一:任意多个 &T 可以同时存在,它们指向同一块内存,&T 本身是 Copy')
r = tryit('u20a', '''
    fn main() {
        let v = vec![1, 2, 3];
        let a = &v; let b = &v; let c = a;          // 复制一个引用
        println!("a、b、c 指向同一个 Vec:{}", std::ptr::eq(a, b) && std::ptr::eq(b, c));
        println!("len:{} {} {}", a.len(), b.len(), c.len());
        fn is_copy<T: Copy>(_: &T) {}
        is_copy(&a);
        println!("&Vec<i32> 是 Copy(上面的 is_copy 调用编译通过)");
    }
''', quiet_src=False)
print()
print('== 二:多个线程同时读同一份数据(thread::scope):只读共享是安全的')
r = tryit('u20b', '''
    use std::thread;
    fn main() {
        let data: Vec<u64> = (1..=1_000_000).collect();
        let chunks: Vec<&[u64]> = data.chunks(250_000).collect();
        let total: u64 = thread::scope(|s| {
            let hs: Vec<_> = chunks.iter().map(|c| s.spawn(move || c.iter().sum::<u64>())).collect();
            hs.into_iter().map(|h| h.join().unwrap()).sum()
        });
        println!("4 个线程各读 25 万个元素,共享同一个 Vec,总和 = {}(期望 {})", total, 1_000_000u64 * 1_000_001 / 2);
    }
''', release=True, quiet_src=False)
print()
print('== 三:共享 + 可修改 = 数据竞争的温床:Cell 没有实现 Sync,&Cell 不能跨线程')
r = tryit('u20c', '''
    use std::cell::Cell;
    use std::thread;
    fn main() {
        let c = Cell::new(0);
        thread::scope(|s| {
            s.spawn(|| c.set(c.get() + 1));
            s.spawn(|| c.set(c.get() + 1));
        });
    }
''', maxlines=30); R['e_cell'] = r['diag'].split('\n')[0]
print()
print('== 四:共享读的同时不能修改:读者还活着时,写者被拒绝(单线程里也一样)')
r = tryit('u20d', '''
    fn main() {
        let mut v = vec![1, 2, 3];
        let r1 = &v; let r2 = &v;
        v.push(4);
        println!("{:?} {:?}", r1, r2);
    }
''', maxlines=26); R['e_push'] = r['diag'].split('\n')[0]
save('u20', R)
