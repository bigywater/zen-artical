import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u32'); R = {}
print('== 一:RefCell<T>:把借用检查从编译期推迟到运行期;通过 & 也能修改内部值')
r = tryit('u32a', '''
    use std::cell::RefCell;
    fn main() {
        let c = RefCell::new(vec![1, 2, 3]);       // 注意:c 不是 mut
        c.borrow_mut().push(4);                     // 通过共享引用修改
        println!("{:?},长度 {}", c.borrow(), c.borrow().len());
        {
            let r1 = c.borrow(); let r2 = c.borrow();      // 多个不可变借用:可以
            println!("同时两个 borrow():{} {}", r1.len(), r2.len());
        }
    }
''', quiet_src=False)
print()
print('== 二:违反借用规则在运行时才会被发现:panic')
r = tryit('u32b', '''
    use std::cell::RefCell;
    fn main() {
        let c = RefCell::new(5);
        let r = c.borrow();
        println!("持有一个 borrow() 时再 borrow_mut() ...");
        let w = c.borrow_mut();
        println!("不会走到这里 {} {}", r, w);
    }
''', quiet_src=True); R['panic'] = [l for l in (r.get('err', '')).split('\n') if 'panicked' in l or 'already' in l][:2]
r = tryit('u32c', '''
    use std::cell::RefCell;
    fn main() {
        let c = RefCell::new(5);
        let _w1 = c.borrow_mut();
        println!("try_borrow_mut() 在已有可变借用时:{:?}", c.try_borrow_mut().is_err());
        println!("try_borrow()     在已有可变借用时:{:?}", c.try_borrow().is_err());
    }
''', quiet_src=False)
print()
print('== 三:同样的错误,编译期的 &mut 在编译时就发现(对比)')
r = tryit('u32d', '''
    fn main() {
        let mut x = 5;
        let r = &x;
        let w = &mut x;
        println!("{} {}", r, w);
    }
''', maxlines=18); R['e502'] = r['diag'].split('\n')[0]
print()
print('== 四:典型用途:Rc<RefCell<T>> 共享并修改;以及空间成本(多出一个借用标志)')
r = tryit('u32e', '''
    use std::cell::RefCell;
    use std::rc::Rc;
    fn main() {
        let shared = Rc::new(RefCell::new(Vec::<i32>::new()));
        let a = Rc::clone(&shared); let b = Rc::clone(&shared);
        a.borrow_mut().push(1);
        b.borrow_mut().push(2);
        println!("两个所有者各自 push 一次,共享的 Vec = {:?}", shared.borrow());
    }
''', quiet_src=False)
r = tryit('u32f', '''
    use std::cell::RefCell;
    fn main() {
        println!("size_of::<u64>() = {},size_of::<RefCell<u64>>() = {}(借用标志是一个 isize,占 8 字节)", std::mem::size_of::<u64>(), std::mem::size_of::<RefCell<u64>>());
        println!("size_of::<u8>() = {},size_of::<RefCell<u8>>() = {}", std::mem::size_of::<u8>(), std::mem::size_of::<RefCell<u8>>());
    }
''', quiet_src=True)
save('u32', R)
