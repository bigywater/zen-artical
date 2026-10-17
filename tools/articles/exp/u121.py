import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u121'); R = {}
print('== 一:创建裸指针是安全的;解引用才需要 unsafe。*const T 与 *mut T,从引用转换;裸指针可以为空、可以相等比较、可以悬空')
r = tryit('u121a', '''
    fn main() {
        let mut x = 10; let p: *const i32 = &x; let q: *mut i32 = &mut x;
        println!("  创建裸指针不需要 unsafe;p == q(同一地址): {}", p == q as *const i32);
        let null: *const i32 = std::ptr::null(); println!("  null.is_null() = {}  p.is_null() = {}", null.is_null(), p.is_null());
        unsafe { *q += 5; println!("  通过 *mut 修改后 *p = {}", *p); }
        let dangling: *const i32 = { let y = 7; &y as *const i32 };   // y 已经离开作用域
        println!("  悬空指针(指向已销毁的 y)创建不报错:地址 {:p}(解引用它是未定义行为,这里不解引用)", dangling);
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:指针算术:add / offset / sub 以「元素」为单位(不是字节);wrapping_add 与 byte_add')
r = tryit('u121b', '''
    fn main() {
        let a = [10u32, 20, 30, 40, 50]; let p = a.as_ptr();
        unsafe { println!("  p.add(2) 指向 {}(add 的单位是元素,u32 = 4 字节)", *p.add(2)); }
        println!("  p.add(2) 比 p 大 {} 字节", p.wrapping_add(2) as usize - p as usize);
        println!("  byte_add(4) 比 p 大 {} 字节", p.wrapping_byte_add(4) as usize - p as usize);
        let q = unsafe { p.add(4) }; println!("  q - p = {} 个元素(offset_from)", unsafe { q.offset_from(p) });
        let b = [1u8, 2, 3]; let pb = b.as_ptr(); println!("  同样的 add(2),u8 数组:相差 {} 字节", pb.wrapping_add(2) as usize - pb as usize);
    }
''', quiet_src=True); R['arith'] = r['out']
print()
print('== 三:引用 vs 裸指针:两个 &mut 指向同一个值编译不过,裸指针是 Copy、可以有多份;解引用时要自己保证不出现并发的读写冲突')
r = tryit('u121c', '''
    fn main() {
        let mut x = 1;
        let p1 = &mut x as *mut i32; let p2 = p1;     // 裸指针是 Copy:两个可变裸指针指向同一个值,编译通过
        unsafe { *p1 += 1; *p2 += 10; println!("  两个 *mut 都指向 x:修改后 x = {}(这里按顺序访问,没有同时读写,结果是确定的)", *p1); }
    }
''', quiet_src=True); R['alias'] = r['out']
r = tryit('u121d', '''
    fn main() { let mut x = 1; let a = &mut x; let b = &mut x; *a += 1; *b += 1; }
''', maxlines=20); R['e0499'] = r['diag']
print()
print('== 四:把 Box 变成裸指针再变回来:into_raw / from_raw;忘记 from_raw 就泄漏,重复 from_raw 会双重释放(这里只演示泄漏)')
r = tryit('u121e', '''
    struct Noisy(u32); impl Drop for Noisy { fn drop(&mut self) { println!("  Noisy({}) drop", self.0); } }
    fn main() {
        let leaked = Box::into_raw(Box::new(Noisy(1)));
        println!("  into_raw 得到 {:p} —— 所有权交给了裸指针,Box 不会再 drop 它", leaked);
        let again = Box::into_raw(Box::new(Noisy(2)));
        let back = unsafe { Box::from_raw(again) }; println!("  from_raw 把 Noisy(2) 的所有权拿回来,离开作用域时正常 drop:"); drop(back);
        println!("  Noisy(1) 从未 from_raw:泄漏,永远不会有它的 drop 输出");
        let _ = leaked;
    }
''', quiet_src=True); R['box'] = r['out']
print()
print('== 五:C 风格的链表:用裸指针实现的简单双向链接(安全 Rust 里需要 Rc<RefCell>),并且正确释放')
r = tryit('u121f', '''
    struct Node { val: i32, next: *mut Node, prev: *mut Node }
    struct DList { head: *mut Node, tail: *mut Node, len: usize }
    impl DList {
        fn new() -> Self { DList { head: std::ptr::null_mut(), tail: std::ptr::null_mut(), len: 0 } }
        fn push_back(&mut self, v: i32) { let n = Box::into_raw(Box::new(Node { val: v, next: std::ptr::null_mut(), prev: self.tail })); if self.tail.is_null() { self.head = n; } else { unsafe { (*self.tail).next = n; } } self.tail = n; self.len += 1; }
        fn to_vec(&self) -> Vec<i32> { let mut o = vec![]; let mut c = self.head; while !c.is_null() { unsafe { o.push((*c).val); c = (*c).next; } } o }
        fn to_vec_rev(&self) -> Vec<i32> { let mut o = vec![]; let mut c = self.tail; while !c.is_null() { unsafe { o.push((*c).val); c = (*c).prev; } } o }
    }
    impl Drop for DList { fn drop(&mut self) { let mut c = self.head; let mut n = 0; while !c.is_null() { let b = unsafe { Box::from_raw(c) }; c = b.next; n += 1; } println!("  DList drop:释放了 {} 个节点", n); } }
    fn main() { let mut l = DList::new(); for i in 1..=4 { l.push_back(i * 10); } println!("  正向 {:?}  反向 {:?}  长度 {}", l.to_vec(), l.to_vec_rev(), l.len); }
''', quiet_src=True); R['dlist'] = r['out']
save('u121', R)
