import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u33'); R = {}
print('== 一:Cell<T>:通过共享引用整体替换里面的值,不借出引用')
r = tryit('u33a', '''
    use std::cell::Cell;
    fn main() {
        let c = Cell::new(10);                  // 不是 mut
        c.set(20);
        let old = c.replace(30);
        println!("replace 返回旧值 {},现在的值 {}", old, c.get());
        let n = c.take();                       // 取出并留下默认值 0
        println!("take 取出 {},之后 get() = {}", n, c.get());
    }
''', quiet_src=False)
print()
print('== 二:Cell 不能借出里面的引用:get() 只对 Copy 类型可用;非 Copy 要用 take / replace / swap')
r = tryit('u33b', '''
    use std::cell::Cell;
    fn main() {
        let c = Cell::new(String::from("hi"));
        let s = c.get();
        println!("{s}");
    }
''', maxlines=24); R['e599'] = r['diag'].split('\n')[0]
r = tryit('u33c', '''
    use std::cell::Cell;
    fn main() {
        let c = Cell::new(String::from("hi"));
        let old = c.replace(String::from("new"));
        println!("旧值 {old},现在 {}", c.take());
    }
''', quiet_src=False)
print()
print('== 三:没有运行时借用标志,没有 panic:大小与 T 相同')
r = tryit('u33d', '''
    use std::cell::{Cell, RefCell};
    use std::mem::size_of;
    fn main() {
        println!("u32 = {},Cell<u32> = {},RefCell<u32> = {}", size_of::<u32>(), size_of::<Cell<u32>>(), size_of::<RefCell<u32>>());
        println!("String = {},Cell<String> = {}", size_of::<String>(), size_of::<Cell<String>>());
    }
''', quiet_src=True)
print()
print('== 四:典型用途:在 &self 方法里更新一个计数器或缓存')
r = tryit('u33e', '''
    use std::cell::Cell;
    struct Counter { hits: Cell<u32>, name: String }
    impl Counter {
        fn lookup(&self, key: &str) -> usize { self.hits.set(self.hits.get() + 1); key.len() + self.name.len() }    // &self,不是 &mut self
    }
    fn main() {
        let c = Counter { hits: Cell::new(0), name: "cfg".into() };
        let r1 = &c; let r2 = &c;
        r1.lookup("a"); r2.lookup("bb"); r1.lookup("ccc");
        println!("通过两个共享引用共调用 3 次,hits = {}", c.hits.get());
    }
''', quiet_src=False)
print()
print('== 五:Cell 不是 Sync:不能跨线程共享(见 Send 与 Sync 一篇),需要原子类型')
r = tryit('u33f', '''
    use std::cell::Cell;
    use std::thread;
    fn main() {
        let c = Cell::new(0);
        thread::scope(|s| { s.spawn(|| c.set(1)); });
    }
''', maxlines=16); R['e277'] = r['diag'].split('\n')[0]
save('u33', R)
