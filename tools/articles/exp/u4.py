import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u4'); R = {}
print('== 一:shadowing 可以改变类型,mut 不行')
r = tryit('u4a', '''
    fn main() {
        let spaces = "   ";
        let spaces = spaces.len();   // &str → usize:新变量,新类型
        println!("spaces = {spaces}");
    }
''')
r = tryit('u4b', '''
    fn main() {
        let mut spaces = "   ";
        spaces = spaces.len();       // 想用 mut 把 &str 变成 usize
        println!("spaces = {spaces}");
    }
''', maxlines=22); R['e_type'] = r['diag'].split('\n')[0]
print()
print('== 二:shadowing 的作用域:内层遮蔽只到块结束')
r = tryit('u4c', '''
    fn main() {
        let x = 5;
        let x = x + 1;
        {
            let x = x * 2;
            println!("内层 x = {x}");
        }
        println!("外层 x = {x}");
    }
''')
print()
print('== 三:shadowing 是新变量(新的栈位置),mut 是同一个变量(同一个地址)')
r = tryit('u4d', '''
    fn main() {
        let x = 1u64;
        let p1 = &x as *const u64 as usize;
        let x = x + 1;
        let p2 = &x as *const u64 as usize;
        println!("shadowing:两次 x 的地址相同吗? {}", p1 == p2);
        let mut y = 1u64;
        let q1 = &y as *const u64 as usize;
        y += 1;
        let q2 = &y as *const u64 as usize;
        println!("mut:两次 y 的地址相同吗? {}", q1 == q2);
    }
''', flags=('-C', 'opt-level=0')); R['addr'] = r['out']
print()
print('== 四:被遮蔽的值并没有被提前释放,要等到作用域结束才按相反顺序 drop')
r = tryit('u4e', '''
    struct D(&'static str);
    impl Drop for D { fn drop(&mut self) { println!("drop {}", self.0); } }
    fn main() {
        let a = D("第一个");
        println!("创建第一个");
        let a = D("第二个");
        println!("遮蔽之后,第一个还在吗?(还没有 drop 它)");
        let _ = &a;
        println!("main 结束");
    }
''', flags=('-A', 'unused')); R['drop'] = r['out']
print()
print('== 五:遮蔽 + 移动:原来的变量被移动后,同名新变量接管')
r = tryit('u4f', '''
    fn main() {
        let s = String::from("hello");
        let s = s + ", world";      // 旧 s 被移动进 + ,新 s 是结果
        println!("{s}");
    }
''')
save('u4', R)
