import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u31'); R = {}
print('== 一:Rc 循环引用会泄漏:两个节点互相持有对方的 Rc,计数永远降不到 0,Drop 永远不执行')
r = tryit('u31a', '''
    use std::cell::RefCell;
    use std::rc::Rc;
    struct Node { name: &'static str, next: RefCell<Option<Rc<Node>>> }
    impl Drop for Node { fn drop(&mut self) { println!("  drop {}", self.name); } }
    fn main() {
        println!("-- 没有循环:离开作用域时两个节点都被 drop");
        { let a = Rc::new(Node { name: "a1", next: RefCell::new(None) }); let b = Rc::new(Node { name: "b1", next: RefCell::new(Some(Rc::clone(&a))) }); let _ = &b; }
        println!("-- 有循环:a2 → b2 → a2");
        {
            let a = Rc::new(Node { name: "a2", next: RefCell::new(None) });
            let b = Rc::new(Node { name: "b2", next: RefCell::new(Some(Rc::clone(&a))) });
            *a.next.borrow_mut() = Some(Rc::clone(&b));
            println!("  a 的强引用数 = {},b 的强引用数 = {}", Rc::strong_count(&a), Rc::strong_count(&b));
        }
        println!("-- 块结束了,但没有看到 drop a2 / drop b2:它们泄漏了");
    }
''', quiet_src=False)
print()
print('== 二:Weak 不增加强引用计数,不阻止释放;upgrade() 返回 Option<Rc<T>>')
r = tryit('u31b', '''
    use std::rc::{Rc, Weak};
    struct D(&'static str);
    impl Drop for D { fn drop(&mut self) { println!("  drop {}", self.0); } }
    fn main() {
        let strong = Rc::new(D("数据"));
        let weak: Weak<D> = Rc::downgrade(&strong);
        println!("strong_count = {},weak_count = {}", Rc::strong_count(&strong), Rc::weak_count(&strong));
        println!("upgrade() 时数据还在:{}", weak.upgrade().map(|d| d.0).unwrap_or("已释放"));
        println!("upgrade 之后(临时 Rc 已释放)strong_count = {}", Rc::strong_count(&strong));
        drop(strong);
        println!("drop(strong) 之后,upgrade() = {:?}", weak.upgrade().map(|d| d.0));
    }
''', quiet_src=False)
print()
print('== 三:树:父节点用 Rc 拥有孩子,孩子用 Weak 指回父节点,没有循环')
r = tryit('u31c', '''
    use std::cell::RefCell;
    use std::rc::{Rc, Weak};
    struct Node { name: &'static str, parent: RefCell<Weak<Node>>, children: RefCell<Vec<Rc<Node>>> }
    impl Drop for Node { fn drop(&mut self) { println!("  drop {}", self.name); } }
    fn main() {
        let leaf = Rc::new(Node { name: "leaf", parent: RefCell::new(Weak::new()), children: RefCell::new(vec![]) });
        println!("leaf 的父节点(挂接前) = {:?}", leaf.parent.borrow().upgrade().map(|p| p.name));
        {
            let branch = Rc::new(Node { name: "branch", parent: RefCell::new(Weak::new()), children: RefCell::new(vec![Rc::clone(&leaf)]) });
            *leaf.parent.borrow_mut() = Rc::downgrade(&branch);
            println!("leaf 的父节点(挂接后) = {:?}", leaf.parent.borrow().upgrade().map(|p| p.name));
            println!("branch:strong = {},weak = {};leaf:strong = {},weak = {}", Rc::strong_count(&branch), Rc::weak_count(&branch), Rc::strong_count(&leaf), Rc::weak_count(&leaf));
        }
        println!("branch 离开作用域之后,leaf 的父节点 = {:?}(leaf 的 strong_count = {})", leaf.parent.borrow().upgrade().map(|p| p.name), Rc::strong_count(&leaf));
    }
''', quiet_src=False, flags=('-A', 'dead_code'))
save('u31', R)
